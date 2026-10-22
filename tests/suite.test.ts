import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { defaultBudget } from "../src/config.js";
import { emptyExecution, type ExecutionResult, type ModelSelection } from "../src/types.js";
import { EventSinkError } from "../src/events.js";
import { runEvaluation } from "../src/evaluation/run.js";
import { loadRecordedTrials } from "../src/evaluation/regrade.js";
import { validatePlan } from "../src/evaluation/validate.js";
import { preflightPlan } from "../src/evaluation/preflight.js";
import { fileProviderSlots, providerHost } from "../src/evaluation/provider-slots.js";
import type { EvaluationPlan } from "../src/evaluation/types.js";
import { checkPolicy, parseModelSpec, validateSuite, type FamilySpec } from "../src/suite/spec.js";
import { CEILING_SLACK, generateFamilyPlans, RESPONSE_CHARS, RESPONSE_TOKENS } from "../src/suite/plans.js";
import { SuiteRunner, type SuiteExecutor } from "../src/suite/run.js";
import { suiteFlags, type FamilyReport } from "../src/suite/report.js";

// A two-item family: check-a passes when the answer starts with the item id, check-b when it ends with "+b", and the
// format check like check-a. A null answer passes nothing. check-b's verdict is explained in an evidence file.
const grader = `import json, sys
args = dict(zip(sys.argv[1::2], sys.argv[2::2]))
request = json.load(open(args["--request"]))
context = request["context"]
answer = open(request["evidenceRoot"] + "/" + request["answerRef"]).read().strip()
checks = [
  {"id": "check-a", "requirementId": "REQ-A", "status": "pass" if answer.startswith(context["itemId"]) else "fail", "evidenceRefs": []},
  {"id": "check-b", "requirementId": "REQ-B", "status": "pass" if answer.endswith("+b") else "fail", "evidenceRefs": ["notes.json"]},
  {"id": "answer-format", "requirementId": "REQ-FORMAT", "status": "pass" if answer.startswith(context["itemId"]) else "fail", "evidenceRefs": []},
]
json.dump({"schemaVersion": 1, "requestId": request["requestId"], "taskId": request["task"]["id"], "taskVersion": request["task"]["version"],
           "graderVersion": "1.0.0", "gradingStatus": "completed", "checks": checks, "dimensions": [], "unscoredCheckIds": [],
           "reason": None, "error": None}, open(args["--result"], "w"))
json.dump({"check-b": "ok" if answer.endswith("+b") else "the answer lacks +b"}, open(request["evidenceRoot"] + "/notes.json", "w"))
`;

async function itemPackage(root: string, name: string, nullPasses = false): Promise<{ path: string; manifestSha256: string }> {
  const path = join(root, name);
  const files: Record<string, string> = {
    "instruction.md": "# Suite family\n\nAnswer with the item id.\n",
    // A defective grader for the smoke test: an empty answer passes check-b.
    "private/grader.py": nullPasses ? grader.replace('answer.endswith("+b")', '(answer.endswith("+b") or answer == "")') : grader,
    "items/i1/prompt.md": "Item i1.\n",
    "items/i2/prompt.md": "Item i2.\n",
  };
  for (const [relative, content] of Object.entries(files)) {
    await mkdir(join(path, relative, ".."), { recursive: true });
    await writeFile(join(path, relative), content);
  }
  const digest = (relative: string) => ({ path: relative, sha256: createHash("sha256").update(files[relative]!).digest("hex") });
  const manifest = {
    schemaVersion: 1, id: name, version: "0.1.0", familyId: name, capability: "reasoning", usage: "development",
    source: { kind: "original-design", references: [] }, license: { taskText: "Test material.", thirdPartyContent: [] },
    entryPoint: { instruction: "instruction.md" },
    files: { public: [digest("instruction.md")], trusted: [digest("private/grader.py")] },
    requirements: [
      { id: "REQ-A", critical: true, introducedAt: "0.1.0", checkIds: ["check-a"] },
      { id: "REQ-B", critical: true, introducedAt: "0.1.0", checkIds: ["check-b"] },
      { id: "REQ-FORMAT", critical: false, introducedAt: "0.1.0", checkIds: ["answer-format"] },
    ],
    scoring: { formatCheckId: "answer-format", formatPenalty: 0.2 },
    items: [
      { id: "i1", level: "L1", files: [digest("items/i1/prompt.md")], activeRequirementIds: ["REQ-A", "REQ-B", "REQ-FORMAT"] },
      { id: "i2", level: "L2", files: [digest("items/i2/prompt.md")], activeRequirementIds: ["REQ-A", "REQ-B", "REQ-FORMAT"] },
    ],
    toolProfiles: ["workspace-basic"],
    grader: { id: name, version: "1.0.0", entryPoint: "private/grader.py", executable: "python3",
      args: ["{entryPoint}", "--request", "{request}", "--result", "{result}"], answerSource: "execution-output" },
    environment: { runtime: "Python 3", dependencies: "standard library", network: false },
  };
  const manifestText = JSON.stringify(manifest, null, 2);
  await writeFile(join(path, "manifest.json"), manifestText);
  return { path, manifestSha256: createHash("sha256").update(manifestText).digest("hex") };
}

function template(pkg: { path: string; manifestSha256: string }, name: string): EvaluationPlan {
  return {
    schemaVersion: 3, name, models: [{ provider: "supercn", id: "glm-5.3", thinkingLevel: "high" }],
    budget: { ...defaultBudget, maxTrialTokens: 100_000 }, trustedLocalExecution: true, repetitions: 2, seed: 7,
    batch: { maxTotalTokensPerModel: 1, concurrency: 2 },
    artifactLimits: { maxFiles: 50, maxFileBytes: 1_000_000, maxTrialBytes: 5_000_000, graderResultMaxBytes: 1_000_000, toolEvidenceMaxBytes: 1_000_000 },
    cases: [{ id: name, packagePath: pkg.path, packageManifestSha256: pkg.manifestSha256, input: { prompt: "Answer now." },
      evaluator: { kind: "task-package", timeoutMs: 60_000 }, items: "all" }],
  };
}

/** The item a trial received, from the prompt the harness built. */
const itemOf = (prompt: string) => /Item (i\d)\./.exec(prompt)![1]!;

type Behaviour = (item: string, model: ModelSelection, attempt: number) => ExecutionResult | "fatal";

/** An in-process executor: plans run through runEvaluation with a scripted runner, so no process or request is made. */
function inProcessExecutor(worktreeFiles: (root: string) => Promise<void>, behaviour: Behaviour, calls: string[], environments: Record<string, string>[]): SuiteExecutor {
  const attempts = new Map<string, number>();
  return {
    async freeze(root) {
      await mkdir(root, { recursive: true });
      await writeFile(join(root, ".git"), "gitdir: test\n");
      await worktreeFiles(root);
      calls.push("freeze");
      return { commit: "0".repeat(40), uncommitted: [] };
    },
    async packageCheck() { calls.push("packageCheck"); return true; },
    async validate(_root, path) {
      calls.push(`validate ${path.replace(/^.*\//, "")}`);
      const plan = JSON.parse(await readFile(path, "utf8")) as EvaluationPlan;
      try { validatePlan(plan); await preflightPlan(plan); return true; } catch { return false; }
    },
    async smoke(_root, path, outDirectory) {
      calls.push(`smoke ${path.replace(/^.*\//, "")}`);
      const plan = JSON.parse(await readFile(path, "utf8")) as EvaluationPlan;
      await runEvaluation({ ...plan, name: `${plan.name}-null-agent` }, { outputRoot: outDirectory, runner: async () => ({ ...emptyExecution(), output: "" }) });
    },
    async run(_root, path, outDirectory, _log, options) {
      calls.push(`run ${path.replace(/^.*\//, "")}${options.resume ? " resume" : ""}`);
      environments.push(options.environment);
      const plan = JSON.parse(await readFile(path, "utf8")) as EvaluationPlan;
      try {
        await runEvaluation(plan, { outputRoot: outDirectory, ...(options.resume ? { resumeDirectory: options.resume } : {}),
          ...(options.stoppedProviders ? { stoppedProviders: options.stoppedProviders } : {}),
          runner: async (input, model) => {
            const key = `${plan.name}|${model.provider}|${itemOf(input.prompt)}`;
            const attempt = (attempts.get(key) ?? 0) + 1;
            attempts.set(key, attempt);
            const outcome = behaviour(itemOf(input.prompt), model, attempt);
            if (outcome === "fatal") throw new EventSinkError();
            return outcome;
          } });
        return 0;
      } catch { return 1; }
    },
    async tournament() { calls.push("tournament"); return 0; },
  };
}

const answer = (output: string, tokens = 1_000): ExecutionResult => ({ ...emptyExecution(), output, modelCalls: 1, turns: 1, reportedTokens: tokens,
  requestUsage: [{ requestId: "r", interactionClass: "candidate", status: "completed", usageStatus: "reported", durationMs: 1, inputTokens: tokens - 10,
    outputTokens: 10, cacheReadTokens: 0, cacheWriteTokens: 0, reasoningTokens: null, totalTokens: tokens, costUsd: null, attempts: 1, failureClass: null }] });

const unavailable = (): ExecutionResult => ({ ...emptyExecution(), status: "error", failureKind: "infrastructure", error: "PROVIDER_UNAVAILABLE", modelCalls: 1,
  requestUsage: [{ requestId: "r", interactionClass: "candidate", status: "error", usageStatus: "missing", durationMs: 1, inputTokens: null, outputTokens: null,
    cacheReadTokens: null, cacheWriteTokens: null, reasoningTokens: null, totalTokens: null, costUsd: null, attempts: 3, failureClass: "server",
    failureMessage: "503 Service Unavailable" }] });

async function suiteFixture(root: string, smokeDefect = false) {
  const alpha = await itemPackage(root, "alpha");
  const beta = await itemPackage(root, "beta", smokeDefect);
  const families: FamilySpec[] = [
    { id: "A", kind: "single", template: "templates/alpha.eval.json", score: { levels: ["L1", "L2"] } },
    { id: "B", kind: "single", template: "templates/beta.eval.json", score: { items: ["i2"] }, overrides: { batch: { concurrency: 1 } } },
  ];
  const write = async (worktree: string) => {
    await mkdir(join(worktree, "templates"), { recursive: true });
    await mkdir(join(worktree, "suites"), { recursive: true });
    await writeFile(join(worktree, "templates", "alpha.eval.json"), JSON.stringify(template(alpha, "alpha")));
    await writeFile(join(worktree, "templates", "beta.eval.json"), JSON.stringify(template(beta, "beta")));
    await writeFile(join(worktree, "suites", "test.json"), JSON.stringify({ schemaVersion: 1, name: "test", target: { model: "deepseek:deepseek-flash", maxScore: 0.8 },
      providerConcurrency: { "*": 2 }, policy: { maxModels: 3, maxRepetitions: 1, maxModelsPerHost: { "api.airy.work": 1 }, forbiddenModels: ["-pro$"] }, families }));
  };
  // The main tree holds the same files; the suite checks a launch against them before freezing.
  await write(root);
  return write;
}

const models = ["deepseek:deepseek-flash", "aliplan:qwen3.8-flash"];

test("model specs take the declared middle thinking level unless one is given", () => {
  assert.deepEqual(parseModelSpec("deepseek:deepseek-flash"), { provider: "deepseek", id: "deepseek-flash", thinkingLevel: "high", temperature: 0 });
  assert.deepEqual(parseModelSpec("aliplan:qwen3.8-flash"), { provider: "aliplan", id: "qwen3.8-flash", thinkingLevel: "provider-default", temperature: 0 });
  assert.deepEqual(parseModelSpec("deepseek:deepseek-flash?thinking=max&temperature=0.5"), { provider: "deepseek", id: "deepseek-flash", thinkingLevel: "max", temperature: 0.5 });
  assert.equal(parseModelSpec("supercn:glm-5.3?temperature=provider-default").temperature, null);
  assert.throws(() => parseModelSpec("deepseek:deepseek-flash?effort=high"), /MODEL_OPTION_UNKNOWN/);
  assert.throws(() => parseModelSpec("deepseek:deepseek-flash?thinking=huge"), /MODEL_THINKING_INVALID/);
  assert.throws(() => parseModelSpec("supercn:kimi-k2.8-preview"), /MODEL_THINKING_REQUIRED/, "unverified models need an explicit level");
  assert.throws(() => parseModelSpec("nowhere:model"), /INVALID_MODEL/);
});

test("the dev policy refuses pro models, a second relay model and extra repetitions", () => {
  const policy = { maxModels: 4, maxRepetitions: 1, maxModelsPerHost: { "api.airy.work": 1 }, forbiddenModels: ["-pro$"] };
  assert.equal(providerHost("supercn"), providerHost("supergpt"), "the relay's two providers share one endpoint host");
  checkPolicy(policy, ["deepseek:deepseek-flash", "supercn:glm-5.3"].map(parseModelSpec), 1);
  assert.throws(() => checkPolicy(policy, ["supercn:glm-5.3", "supergpt:gpt-6-luna"].map(parseModelSpec), 1), /at most 1 models from api.airy.work/);
  assert.throws(() => checkPolicy(policy, ["mimoplan:mimo-v2.6-pro"].map(parseModelSpec), 1), /mimo-v2.6-pro matches/);
  assert.throws(() => checkPolicy(policy, ["deepseek:deepseek-flash"].map(parseModelSpec), 3), /at most 1 repetitions/);
  assert.throws(() => validateSuite({ schemaVersion: 1, name: "x", providerConcurrency: {}, families: [{ id: "A", kind: "single", template: "../a.eval.json" }] }), /SUITE_INVALID:A.template/);
});

test("plans come from templates with the suite's models, repetitions, overrides and standing rules", () => {
  const plan: EvaluationPlan = {
    schemaVersion: 3, name: "t", models: [{ provider: "supercn", id: "glm-5.3", thinkingLevel: "high" }], repetitions: 2, seed: 3,
    budget: { ...defaultBudget, maxOutputTokensPerCall: 32_768, maxOutputChars: 32_768, maxTrialTokens: 300_000 }, trustedLocalExecution: true,
    batch: { maxTotalTokensPerModel: 8_000_000, concurrency: 8 }, cases: [{ id: "c", input: { prompt: "p" }, evaluator: { kind: "exact-match", expected: "x" } }],
  };
  const chosen = models.map(parseModelSpec);
  const [single] = generateFamilyPlans({ id: "T2", kind: "single", template: "t.eval.json", overrides: { batch: { concurrency: 3 } } }, plan, chosen, 1, "s1", () => 12);
  assert.equal(single!.plan.name, "suite-s1-T2");
  assert.deepEqual(single!.plan.models, chosen);
  assert.equal(single!.plan.repetitions, 1);
  assert.equal(single!.plan.seed, undefined, "the template's seed does not carry over");
  assert.equal(single!.plan.budgetNotice, true);
  assert.equal(single!.plan.budget.maxOutputTokensPerCall, RESPONSE_TOKENS);
  assert.equal(single!.plan.budget.maxOutputChars, RESPONSE_CHARS);
  assert.deepEqual(single!.plan.batch, { maxTotalTokensPerModel: 12 * 300_000 * CEILING_SLACK, concurrency: 3 },
    "the per-model ceiling leaves room for each trial's last request; overrides merge");
  assert.equal(single!.adjustments.length, 3);
  assert.equal(plan.budget.maxOutputTokensPerCall, 32_768, "the template itself is untouched");

  const trajectory: EvaluationPlan = { ...plan, execution: { kind: "trajectory", contextPolicy: "continuous", publicRepairMax: 1,
    stageBudget: { ...defaultBudget, maxOutputTokensPerCall: 32_768, maxOutputChars: 60_000, maxTrialTokens: 2_000_000 } },
    budget: { ...plan.budget, maxTrialTokens: 6_000_000 } };
  const perModel = generateFamilyPlans({ id: "E3", kind: "trajectory", template: "e3.eval.json" }, trajectory, chosen, 2, "s1", () => 1);
  assert.deepEqual(perModel.map(entry => entry.key), ["E3-deepseek-deepseek-flash-high-r1", "E3-aliplan-qwen3.8-flash-default-r1",
    "E3-deepseek-deepseek-flash-high-r2", "E3-aliplan-qwen3.8-flash-default-r2"]);
  assert.ok(perModel.every(entry => entry.plan.models.length === 1 && entry.plan.repetitions === undefined));
  assert.equal(perModel[0]!.plan.execution!.kind === "trajectory" && perModel[0]!.plan.execution!.stageBudget.maxOutputTokensPerCall, RESPONSE_TOKENS);
  assert.equal(perModel[0]!.plan.batch!.maxTotalTokensPerModel, 6_000_000 * CEILING_SLACK);
  assert.throws(() => generateFamilyPlans({ id: "X", kind: "single", template: "x.eval.json" }, trajectory, chosen, 1, "s1", () => 1), /SUITE_TEMPLATE_KIND/);
});

test("a suite runs every family, retries infrastructure failures once and reports family scores that match the trials", async () => {
  const root = await mkdtemp(join(tmpdir(), "suite-test-"));
  try {
    const calls: string[] = [];
    const environments: Record<string, string>[] = [];
    // deepseek solves everything; qwen names the item but never adds "+b". qwen's first attempt at beta i1 fails on the provider.
    const behaviour: Behaviour = (item, model, attempt) => {
      if (model.provider === "aliplan" && item === "i1" && attempt === 1) return unavailable();
      return model.provider === "deepseek" ? answer(`${item} +b`, 2_000) : answer(item, 1_000);
    };
    const runner = new SuiteRunner({ repoRoot: root, suitePath: "suites/test.json", models, suitesRoot: join(root, "suites"), log: () => {} },
      inProcessExecutor(await suiteFixture(root), behaviour, calls, environments));
    const result = await runner.run();
    assert.equal(result.status, 0);
    const report = result.report!;
    assert.deepEqual(calls.filter(call => !call.startsWith("validate") && !call.startsWith("run")), ["freeze", "packageCheck", "smoke A.smoke.eval.json", "smoke B.smoke.eval.json"]);
    assert.deepEqual(calls.filter(call => call.startsWith("run")).sort(), ["run A.eval.json", "run A.eval.json resume", "run B.eval.json", "run B.eval.json resume"],
      "both runs are resumed once for qwen's failed i1, which is outside family B's score but part of its run");
    assert.deepEqual(JSON.parse(environments[0]!.AGENTEVAL_PROVIDER_LIMITS!), { "*": 2 });
    assert.ok(environments[0]!.AGENTEVAL_PROVIDER_SLOTS!.startsWith(join(result.directory, "slots")));

    // Family A scores every item; family B only i2. Compare with the trials themselves.
    const state = JSON.parse(await readFile(join(result.directory, "suite.json"), "utf8")) as { runs: Array<{ key: string; runDirectory: string }> };
    for (const [familyId, items] of [["A", ["i1", "i2"]], ["B", ["i2"]]] as const) {
      const directory = state.runs.filter(run => run.key === familyId).at(-1)!.runDirectory;
      const records = (await loadRecordedTrials(directory)).filter(record => (items as readonly string[]).includes(record.itemId!));
      for (const label of ["deepseek:deepseek-flash-high", "aliplan:qwen3.8-flash-default"]) {
        const own = records.filter(record => `${record.model.provider}:${record.model.id}` === label.replace(/-(high|default)$/, ""));
        const expected = own.reduce((sum, record) => sum + record.evaluation.score!, 0) / own.length;
        const row = report.families.find(family => family.id === familyId)!.results.find(entry => entry.label === label)!;
        assert.equal(row.meanScore, expected, `${familyId} ${label}`);
        assert.equal(row.infrastructureFailures, 0, "the retried trial replaced the failed one");
      }
    }
    const familyA = report.families.find(family => family.id === "A")!;
    assert.equal(familyA.results.find(result => result.model === "deepseek:deepseek-flash")!.meanScore, 1);
    assert.equal(familyA.results.find(result => result.model === "deepseek:deepseek-flash")!.medianTokens, 2_000);
    assert.equal(familyA.results.find(result => result.model === "aliplan:qwen3.8-flash")!.resolved, 0);
    assert.equal(familyA.failedChecks[0]!.id, "check-b");
    assert.equal(familyA.failedChecks[0]!.failed, 2);
    const flags = report.flags.map(flag => `${flag.kind} ${flag.family}`);
    assert.ok(flags.includes("target-above A") && flags.includes("target-above B"), "deepseek above 80% is flagged");
    assert.ok(!flags.some(flag => flag.startsWith("saturated")), "qwen is below 90%");
    const markdown = await readFile(join(result.directory, "report.md"), "utf8");
    assert.match(markdown, /## Scores across families/);
    assert.match(markdown, /\| deepseek:deepseek-flash-high \| 100\.0% \| 100\.0% \|/);
    assert.match(markdown, /check-b \| 2\/4 \| aliplan:qwen3\.8-flash-default i\d: the answer lacks \+b/);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("a dry run stops after the smoke step and a resume continues an interrupted suite in its run directories", async () => {
  const root = await mkdtemp(join(tmpdir(), "suite-resume-"));
  try {
    const calls: string[] = [];
    let crash = true;
    // The first launch dies partway through family A (as if the machine stopped); the resume must continue that run.
    const behaviour: Behaviour = (item, model) => {
      if (crash && item === "i2" && model.provider === "aliplan") return "fatal";
      return answer(`${item} +b`);
    };
    const fixture = await suiteFixture(root);
    const options = { repoRoot: root, suitePath: "suites/test.json", models, families: ["A"], suitesRoot: join(root, "suites"), log: () => {} };
    const dry = await new SuiteRunner({ ...options, dryRun: true }, inProcessExecutor(fixture, behaviour, calls, [])).run();
    assert.equal(dry.status, 0);
    assert.equal(dry.report, null);
    assert.ok(!calls.some(call => call.startsWith("run")), "a dry run launches nothing");
    const afterDry = JSON.parse(await readFile(join(dry.directory, "suite.json"), "utf8")) as { phases: Record<string, string> };
    assert.equal(afterDry.phases.smoke, "done");
    assert.equal(afterDry.phases.launch, "skipped (dry run)");

    // The executor's run is interrupted: its process dies, and so does the suite.
    const interrupted = inProcessExecutor(fixture, behaviour, calls, []);
    const run = interrupted.run.bind(interrupted);
    interrupted.run = async (...args) => { await run(...args); throw new Error("SUITE_KILLED"); };
    const first = await new SuiteRunner({ repoRoot: root, resume: dry.directory, log: () => {} }, interrupted).run();
    assert.equal(first.status, 1);
    const killed = JSON.parse(await readFile(join(dry.directory, "suite.json"), "utf8")) as { runs: Array<{ status: string; runDirectory: string | null }> };
    assert.equal(killed.runs[0]!.status, "running");

    crash = false;
    const resumedCalls: string[] = [];
    const resumed = await new SuiteRunner({ repoRoot: root, resume: dry.directory, log: () => {} }, inProcessExecutor(fixture, behaviour, resumedCalls, [])).run();
    assert.equal(resumed.status, 0);
    assert.deepEqual(resumedCalls, ["run A.eval.json resume"], "only the interrupted run continues; no new preflight, smoke or retry");
    const state = JSON.parse(await readFile(join(dry.directory, "suite.json"), "utf8")) as { runs: Array<{ runDirectory: string }> };
    assert.equal(new Set(state.runs.map(entry => entry.runDirectory)).size, 1, "the resume continued the same run directory");
    const row = resumed.report!.families[0]!.results.find(result => result.model === "aliplan:qwen3.8-flash")!;
    assert.equal(row.units, 2);
    assert.equal(row.meanScore, 1);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("a smoke step that finds credit for doing nothing stops the suite before launch", async () => {
  const root = await mkdtemp(join(tmpdir(), "suite-smoke-"));
  try {
    const calls: string[] = [];
    const result = await new SuiteRunner({ repoRoot: root, suitePath: "suites/test.json", models, suitesRoot: join(root, "suites"), log: () => {} },
      inProcessExecutor(await suiteFixture(root, true), () => answer("x"), calls, [])).run();
    assert.equal(result.status, 1);
    assert.ok(!calls.some(call => call.startsWith("run")));
    const state = JSON.parse(await readFile(join(result.directory, "suite.json"), "utf8")) as { phases: Record<string, string>; smoke: Record<string, { ok: boolean; detail: string }> };
    assert.equal(state.phases.smoke, "failed: B");
    assert.equal(state.smoke.A!.ok, true);
    assert.match(state.smoke.B!.detail, /passing checks: check-b/);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("a resumed run lists the trials of providers stopped for balance as not run", async () => {
  const root = await mkdtemp(join(tmpdir(), "suite-stopped-"));
  try {
    const pkg = await itemPackage(root, "gamma");
    const plan = { ...template(pkg, "gamma"), models: models.map(parseModelSpec), repetitions: 1 };
    delete plan.batch;
    const first = await runEvaluation(plan, { outputRoot: root, runner: async (_input, model) => model.provider === "aliplan" ? unavailable() : answer("i1") });
    const resumed = await runEvaluation(plan, { outputRoot: root, resumeDirectory: first.directory, stoppedProviders: { aliplan: "PROVIDER_BALANCE" },
      runner: async () => answer("i1") });
    assert.deepEqual(resumed.report.batch!.notRun.map(entry => [entry.model, entry.reason]), [["aliplan:qwen3.8-flash", "PROVIDER_BALANCE"], ["aliplan:qwen3.8-flash", "PROVIDER_BALANCE"]]);
    assert.equal(resumed.report.records.length, 2, "deepseek's finished trials are kept");
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("provider slots cap concurrent trials per endpoint across holders and take over a dead holder's slot", async () => {
  const root = await mkdtemp(join(tmpdir(), "suite-slots-"));
  try {
    const slots = fileProviderSlots(root, { "api.deepseek.com": 1, "*": 2 }, 10);
    const release = await slots.acquire("deepseek");
    let second = false;
    const waiting = slots.acquire("deepseek").then(next => { second = true; return next; });
    await new Promise(resolve => setTimeout(resolve, 60));
    assert.equal(second, false, "the second trial waits for the slot");
    const other = await slots.acquire("aliplan");
    await release();
    await (await waiting)();
    await other();
    // A lock left by a process that has exited is taken over.
    await mkdir(join(root, "api.deepseek.com"), { recursive: true });
    await writeFile(join(root, "api.deepseek.com", "0.lock"), "999999999");
    await (await slots.acquire("deepseek"))();
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("report flags cover saturation, budget stops, infrastructure rates and stopped providers", () => {
  const row = (label: string, meanScore: number, extra: Partial<FamilyReport["results"][number]> = {}) => ({ familyId: "F", model: label.replace(/-high$|-default$/, ""), label, units: 4, scored: 4,
    meanScore, interval: null, resolved: 0, decided: 4, medianTokens: 1, budgetStops: 0, infrastructureFailures: 0, unscored: 0, notRun: 0, ...extra });
  const family = (id: string, results: FamilyReport["results"], providerStops: Record<string, string> = {}): FamilyReport => ({ id, kind: "single", template: "t.eval.json",
    score: null, adjustments: [], results, notRun: [], infrastructure: [], providerStops, failedChecks: [], runDirectories: [] });
  const families = [
    family("SAT", [row("deepseek:deepseek-flash-high", 0.95), row("aliplan:qwen3.8-flash-default", 0.9)]),
    family("STOPS", [row("deepseek:deepseek-flash-high", 0.5, { budgetStops: 3 }), row("aliplan:qwen3.8-flash-default", 0.2, { infrastructureFailures: 1 })], { supercn: "PROVIDER_BALANCE" }),
    family("OPEN", [row("deepseek:deepseek-flash-high", 0.5, { budgetStops: 4 })]),
  ];
  const specs = new Map<string, FamilySpec>([["OPEN", { id: "OPEN", kind: "single", template: "o.eval.json", openEnded: true }]]);
  const flags = suiteFlags({ target: { model: "deepseek:deepseek-flash", maxScore: 0.8 } }, families, specs).map(flag => `${flag.kind} ${flag.family}`);
  assert.deepEqual(flags.sort(), ["budget-stops STOPS", "infrastructure STOPS", "provider-stopped null", "saturated SAT", "target-above SAT"]);
});
