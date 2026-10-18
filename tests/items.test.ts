import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { defaultBudget } from "../src/config.js";
import { emptyExecution } from "../src/types.js";
import { runEvaluation } from "../src/evaluation/run.js";
import { regradeTrial } from "../src/evaluation/regrade.js";
import { validatePlan } from "../src/evaluation/validate.js";
import { preflightPlan } from "../src/evaluation/preflight.js";
import type { EvaluationPlan } from "../src/evaluation/types.js";

// A grader that checks the answer names the item it was given, and returns checks only for the item's active
// requirements: item i1 activates REQ-A, item i2 activates REQ-A and REQ-B, and both activate REQ-FORMAT.
const grader = `import json, sys
args = dict(zip(sys.argv[1::2], sys.argv[2::2]))
request = json.load(open(args["--request"]))
context = request["context"]
answer = open(request["evidenceRoot"] + "/" + request["answerRef"]).read().strip()
owners = {"REQ-A": "check-a", "REQ-B": "check-b", "REQ-FORMAT": "answer-format"}
checks = []
for requirement in context["activeRequirementIds"]:
    check = owners[requirement]
    passed = answer.startswith(context["itemId"]) if check != "check-b" else answer.endswith("+b")
    checks.append({"id": check, "requirementId": requirement, "status": "pass" if passed else "fail", "evidenceRefs": []})
json.dump({"schemaVersion": 1, "requestId": request["requestId"], "taskId": request["task"]["id"], "taskVersion": request["task"]["version"],
           "graderVersion": "1.0.0", "gradingStatus": "completed", "checks": checks, "dimensions": [], "unscoredCheckIds": [],
           "reason": None, "error": None}, open(args["--result"], "w"))
`;

async function itemPackage(root: string): Promise<{ path: string; manifestSha256: string }> {
  const path = join(root, "items-package");
  const files: Record<string, string> = {
    "instruction.md": "# Generated family\n\nAnswer with the item id.\n",
    "private/grader.py": grader,
    "items/i1/prompt.md": "Item i1: say i1.\n",
    "items/i1/public/data.json": "{\"item\": \"i1\"}\n",
    "items/i2/prompt.md": "Item i2: say i2 and +b.\n",
    "items/i2/public/data.json": "{\"item\": \"i2\"}\n",
  };
  for (const [relative, content] of Object.entries(files)) {
    await mkdir(join(path, relative, ".."), { recursive: true });
    await writeFile(join(path, relative), content);
  }
  const digest = (relative: string) => ({ path: relative, sha256: createHash("sha256").update(files[relative]!).digest("hex") });
  const manifest = {
    schemaVersion: 1, id: "items-test", version: "0.1.0", familyId: "items-test", capability: "reasoning", usage: "development",
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
      { id: "i1", level: "L1", files: [digest("items/i1/prompt.md"), digest("items/i1/public/data.json")], activeRequirementIds: ["REQ-A", "REQ-FORMAT"] },
      { id: "i2", level: "L2", files: [digest("items/i2/prompt.md"), digest("items/i2/public/data.json")], activeRequirementIds: ["REQ-A", "REQ-B", "REQ-FORMAT"] },
    ],
    toolProfiles: ["workspace-basic"],
    grader: { id: "items-test", version: "1.0.0", entryPoint: "private/grader.py", executable: "python3",
      args: ["{entryPoint}", "--request", "{request}", "--result", "{result}"], answerSource: "execution-output" },
    environment: { runtime: "Python 3", dependencies: "standard library", network: false },
  };
  const manifestText = JSON.stringify(manifest, null, 2);
  await writeFile(join(path, "manifest.json"), manifestText);
  return { path, manifestSha256: createHash("sha256").update(manifestText).digest("hex") };
}

function itemPlan(pkg: { path: string; manifestSha256: string }, items: unknown): EvaluationPlan {
  return {
    schemaVersion: 3, name: "items", models: [{ provider: "deepseek", id: "deepseek-flash" }, { provider: "aliplan", id: "qwen3.8-flash" }],
    budget: { ...defaultBudget }, trustedLocalExecution: true,
    artifactLimits: { maxFiles: 50, maxFileBytes: 1_000_000, maxTrialBytes: 5_000_000, graderResultMaxBytes: 1_000_000, toolEvidenceMaxBytes: 1_000_000 },
    cases: [{ id: "family", packagePath: pkg.path, packageManifestSha256: pkg.manifestSha256, input: { prompt: "Answer now." },
      evaluator: { kind: "task-package", timeoutMs: 60_000 }, items: items as never }],
  };
}

test("an item package runs one trial per item, with the item's prompt, files and requirements", async () => {
  const root = await mkdtemp(join(tmpdir(), "items-test-"));
  try {
    const pkg = await itemPackage(root);
    const seen: Array<{ prompt: string; data: string }> = [];
    const result = await runEvaluation(itemPlan(pkg, "all"), { outputRoot: join(root, "runs"), runner: async (input, model) => {
      const data = await readFile(join(input.workspacePath, "public", "data.json"), "utf8");
      seen.push({ prompt: input.prompt, data });
      const item = JSON.parse(data).item as string;
      // deepseek solves both items; qwen solves i1 but misses the second check of i2.
      return { ...emptyExecution(), output: model.provider === "deepseek" && item === "i2" ? "i2 +b" : item };
    } });
    assert.equal(result.report.plannedRuns, 4, "two items times two models");
    const prompts = seen.map(entry => entry.prompt);
    assert.ok(prompts.every(prompt => prompt.startsWith("# Generated family")), "the package instruction comes first");
    assert.ok(seen.every(entry => entry.prompt.includes(`Item ${JSON.parse(entry.data).item}:`)), "each trial gets its own item prompt and files");
    const records = result.report.records;
    assert.deepEqual(records.map(record => [record.itemId, record.itemLevel]).sort(), [["i1", "L1"], ["i1", "L1"], ["i2", "L2"], ["i2", "L2"]]);
    const qwenI2 = records.find(record => record.model.provider === "aliplan" && record.itemId === "i2")!;
    assert.deepEqual(qwenI2.evaluation.checks.map(check => check.id).sort(), ["answer-format", "check-a", "check-b"], "i2 activates REQ-B");
    assert.equal(qwenI2.evaluation.status, "failed");
    const i1 = records.find(record => record.itemId === "i1")!;
    assert.deepEqual(i1.evaluation.checks.map(check => check.id).sort(), ["answer-format", "check-a"], "i1 does not expect check-b");

    const rows = result.report.byTask;
    assert.deepEqual(rows.map(row => [row.level, row.items]), [["L1", 1], ["L1", 1], ["L2", 1], ["L2", 1]], "rows are per level");
    assert.deepEqual(result.report.items.map(row => [row.level, row.allSolved, row.separating]), [["L1", 1, 0], ["L2", 0, 1]]);
    assert.equal(result.report.pairedComparisons[0]!.tasks, 2, "comparisons pair by item");
    const markdown = await readFile(join(result.directory, "report.md"), "utf8");
    assert.match(markdown, /## Items/);
    assert.match(markdown, /\| family \(L2, 1 items\) \|/);

    // Regrading reuses the recorded answer and the item's requirements.
    const regraded = await regradeTrial(join(result.directory, qwenI2.id), itemPlan(pkg, "all"), "items regrade test");
    assert.deepEqual(regraded.evaluation.checks.map(check => check.id).sort(), ["answer-format", "check-a", "check-b"]);
    assert.equal(regraded.evaluation.status, "failed");
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("item selections are validated against the package", async () => {
  const root = await mkdtemp(join(tmpdir(), "items-select-"));
  try {
    const pkg = await itemPackage(root);
    await preflightPlan(itemPlan(pkg, { levels: ["L2"] }));
    await preflightPlan(itemPlan(pkg, ["i1"]));
    await assert.rejects(preflightPlan(itemPlan(pkg, undefined)), /CASE_ITEMS_REQUIRED/);
    await assert.rejects(preflightPlan(itemPlan(pkg, ["i9"])), /UNKNOWN_CASE_ITEM/);
    await assert.rejects(preflightPlan(itemPlan(pkg, { levels: ["L9"] })), /UNKNOWN_CASE_ITEM_LEVEL/);
    assert.throws(() => validatePlan(itemPlan(pkg, { levels: [] })), /INVALID_CASE_ITEMS/);
    const only = await runEvaluation(itemPlan(pkg, { levels: ["L2"] }), { outputRoot: join(root, "runs"), runner: async () => ({ ...emptyExecution(), output: "i2 +b" }) });
    assert.deepEqual([...new Set(only.report.records.map(record => record.itemId))], ["i2"]);
  } finally { await rm(root, { recursive: true, force: true }); }
});
