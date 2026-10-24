import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { defaultBudget } from "../src/config.js";
import { runEvaluation } from "../src/evaluation/run.js";
import { regradeTrial } from "../src/evaluation/regrade.js";
import type { EvaluationPlan } from "../src/evaluation/types.js";
import { emptyExecution } from "../src/types.js";
import { loadOutcomes } from "../src/scoring/outcomes.js";
import type { OutcomeRecord } from "../src/scoring/model.js";

const sha256 = (text: string) => createHash("sha256").update(text).digest("hex");

/** A v2 item package: the answer's number is its raw score; "valid" passes when the answer is a number. */
function graderSource(version: string, bonus: number): string {
  return [
    'import { readFile, writeFile } from "node:fs/promises";',
    "const arg = name => process.argv[process.argv.indexOf(name) + 1];",
    'const request = JSON.parse(await readFile(arg("--request"), "utf8"));',
    'const answer = (await readFile(request.evidenceRoot + "/" + request.answerRef, "utf8")).trim();',
    "const value = Number(answer);",
    "const valid = Number.isFinite(value);",
    `await writeFile(arg("--result"), JSON.stringify({ schemaVersion: 2, requestId: request.requestId, taskId: request.task.id, taskVersion: request.task.version, graderVersion: "${version}",`,
    '  gradingStatus: "completed", checks: [{ id: "valid", requirementId: "REQ-VALID", status: valid ? "pass" : "fail", evidenceRefs: [] }], dimensions: [], unscoredCheckIds: [],',
    `  reason: null, error: null, metrics: [{ id: "score", value: (valid ? value : 0) + ${bonus} }] }));`,
  ].join("\n");
}

async function writePackage(path: string, version: string, bonus: number): Promise<string> {
  const files: Record<string, string> = { "instruction.md": "Answer with a number.", "card.md": "# Card\n", "private/grader.mjs": graderSource(version, bonus),
    "items/p1/prompt.md": "Problem 1.", "items/p2/prompt.md": "Problem 2." };
  for (const [name, content] of Object.entries(files)) {
    await mkdir(join(path, name, ".."), { recursive: true });
    await writeFile(join(path, name), content);
  }
  const placement = (structure: string, naive: number, strong: number) => ({ split: "dev", structure, provenance: { source: "test", published: "2026-10-24", license: "test", exposure: "generated" },
    anchors: { score: { naive, strong } } });
  const manifest = {
    schemaVersion: 2, id: "outcome-task", version: "0.1.0", familyId: "outcome", capability: "engineering", usage: "development",
    source: { kind: "original-design", references: [] }, license: { taskText: "test", thirdPartyContent: [] }, entryPoint: { instruction: "instruction.md" },
    files: { public: [{ path: "instruction.md", sha256: sha256(files["instruction.md"]!) }],
      trusted: [{ path: "card.md", sha256: sha256(files["card.md"]!) }, { path: "private/grader.mjs", sha256: sha256(files["private/grader.mjs"]!) }] },
    requirements: [{ id: "REQ-VALID", critical: true, introducedAt: "0.1.0", checkIds: ["valid"] }],
    items: [
      { id: "p1", level: "L1", files: [{ path: "items/p1/prompt.md", sha256: sha256(files["items/p1/prompt.md"]!) }], activeRequirementIds: ["REQ-VALID"], ...placement("problem:p1", 0, 10) },
      { id: "p2", level: "L1", files: [{ path: "items/p2/prompt.md", sha256: sha256(files["items/p2/prompt.md"]!) }], activeRequirementIds: ["REQ-VALID"], ...placement("problem:p2", 0, 100) },
    ],
    toolProfiles: ["workspace-basic"],
    grader: { id: "g", version, entryPoint: "private/grader.mjs", executable: process.execPath, args: ["{entryPoint}", "--request", "{request}", "--result", "{result}"],
      answerSource: "execution-output" },
    environment: { runtime: "Node.js", dependencies: "none", network: false },
    tier: "frontier", capabilities: ["engineering"], card: "card.md",
    scoreModel: { primary: { kind: "metric", metric: "score" }, groups: [{ id: "valid", weight: 1, critical: true, rule: "all", checkIds: ["valid"] }],
      metrics: [{ id: "score", unit: "points", direction: "higher", anchors: { version: "1", points: [{ name: "naive", maps: 0 }, { name: "strong", maps: 1 }] } }] },
  };
  const text = JSON.stringify(manifest);
  await writeFile(join(path, "manifest.json"), text);
  return sha256(text);
}

test("v2 runs write outcome.json beside each score run, and a re-grade appends a new one", async () => {
  const root = await mkdtemp(join(tmpdir(), "outcome-"));
  try {
    const packagePath = join(root, "package");
    const plan: EvaluationPlan = {
      schemaVersion: 3, name: "outcome-fixture", models: [{ provider: "deepseek", id: "deepseek-flash", thinkingLevel: "high", temperature: 0 }],
      budget: { ...defaultBudget }, trustedLocalExecution: true, isolation: "host",
      artifactLimits: { maxFiles: 20, maxFileBytes: 100_000, maxTrialBytes: 500_000, graderResultMaxBytes: 20_000, toolEvidenceMaxBytes: 100_000 },
      cases: [{ id: "outcome-task", packagePath, packageManifestSha256: await writePackage(packagePath, "1.0.0", 0), input: { prompt: "Go." },
        evaluator: { kind: "task-package" }, items: "all" }],
    };
    // The model answers 15 to every problem: 1.5 of the scale on p1 (above the strong anchor), 0.15 on p2.
    const run = await runEvaluation(plan, { outputRoot: join(root, "runs"), runner: async () => ({ ...emptyExecution(), output: "15", modelCalls: 1 }) });
    const outcomes = await loadOutcomes(run.directory);
    assert.equal(outcomes.length, 2);
    const byItem = (list: OutcomeRecord[], item: string) => list.find(outcome => outcome.task.itemId === item)!;
    assert.equal(byItem(outcomes, "p1").primary, 1.5, "uncapped above the strong anchor");
    assert.equal(byItem(outcomes, "p1").normalised.score!.extrapolated, true);
    assert.equal(byItem(outcomes, "p2").primary, 0.15);
    assert.equal(byItem(outcomes, "p2").task.structure, "problem:p2");
    assert.equal(byItem(outcomes, "p2").model, "deepseek:deepseek-flash-high");
    assert.equal(byItem(outcomes, "p2").resolved, true);

    // A grader fix that adds 5 points: the re-grade appends a score run and its outcome; the first stays.
    plan.cases[0]!.packageManifestSha256 = await writePackage(packagePath, "1.1.0", 5);
    const trial = byItem(outcomes, "p2").trialId;
    await regradeTrial(join(run.directory, trial), plan, "grader 1.1.0");
    const scoreRuns = await readdir(join(run.directory, trial, "score-runs"));
    assert.equal(scoreRuns.length, 2);
    const all = await Promise.all(scoreRuns.map(async name => JSON.parse(await readFile(join(run.directory, trial, "score-runs", name, "outcome.json"), "utf8")) as OutcomeRecord));
    assert.deepEqual(all.map(outcome => outcome.task.graderVersion).sort(), ["1.0.0", "1.1.0"]);
    const latest = await loadOutcomes(run.directory);
    assert.equal(byItem(latest, "p2").primary, 0.2);
    assert.equal(byItem(latest, "p2").task.graderVersion, "1.1.0");
    assert.equal(byItem(latest, "p1").task.graderVersion, "1.0.0", "an untouched trial keeps its outcome");
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
