import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { inspectPackage } from "../src/evaluation/manifest.js";
import { runTaskGrader } from "../src/evaluation/grader.js";

const sha256 = (text: string) => createHash("sha256").update(text).digest("hex");

/** A v2 package whose grader writes the given metrics (a JSON literal) into a schema 2 result. */
async function v2Package(root: string, metricsLiteral: string, schemaVersion = 2): Promise<string> {
  const path = join(root, `package-${sha256(metricsLiteral + schemaVersion).slice(0, 8)}`);
  await mkdir(join(path, "private"), { recursive: true });
  const grader = [
    'import { readFile, writeFile } from "node:fs/promises";',
    "const arg = name => process.argv[process.argv.indexOf(name) + 1];",
    'const request = JSON.parse(await readFile(arg("--request"), "utf8"));',
    `const result = { schemaVersion: ${schemaVersion}, requestId: request.requestId, taskId: request.task.id, taskVersion: request.task.version, graderVersion: "1.0.0",`,
    '  gradingStatus: "completed", checks: [{ id: "valid", requirementId: "REQ-VALID", status: "pass", evidenceRefs: [] }], dimensions: [], unscoredCheckIds: [], reason: null, error: null };',
    `if (${schemaVersion} === 2) result.metrics = ${metricsLiteral};`,
    'await writeFile(arg("--result"), JSON.stringify(result));',
  ].join("\n");
  const files: Record<string, string> = { "instruction.md": "Solve it.", "card.md": "# Card\n", "private/grader.mjs": grader };
  for (const [name, content] of Object.entries(files)) await writeFile(join(path, name), content);
  const manifest = {
    schemaVersion: 2, id: "metric-task", version: "0.1.0", familyId: "metric", capability: "engineering", usage: "development",
    source: { kind: "original-design", references: [] }, license: { taskText: "test", thirdPartyContent: [] }, entryPoint: { instruction: "instruction.md" },
    files: { public: [{ path: "instruction.md", sha256: sha256(files["instruction.md"]!) }],
      trusted: [{ path: "card.md", sha256: sha256(files["card.md"]!) }, { path: "private/grader.mjs", sha256: sha256(grader) }] },
    requirements: [{ id: "REQ-VALID", critical: true, introducedAt: "0.1.0", checkIds: ["valid"] }],
    grader: { id: "g", version: "1.0.0", entryPoint: "private/grader.mjs", executable: process.execPath, args: ["{entryPoint}", "--request", "{request}", "--result", "{result}"] },
    environment: { runtime: "Node.js", dependencies: "none", network: false },
    tier: "frontier", capabilities: ["engineering"], card: "card.md",
    scoreModel: { primary: { kind: "metric", metric: "score" }, groups: [{ id: "valid", weight: 1, critical: true, rule: "all", checkIds: ["valid"] }],
      metrics: [{ id: "score", unit: "points", direction: "higher", anchors: { version: "1", points: [{ name: "naive", maps: 0 }, { name: "strong", maps: 1 }] } }] },
    task: { split: "dev", structure: "problem:metric", provenance: { source: "test", published: "2026-10-24", license: "test", exposure: "generated" },
      anchors: { score: { naive: 10, strong: 20 } } },
  };
  await writeFile(join(path, "manifest.json"), JSON.stringify(manifest));
  return path;
}

async function grade(root: string, packagePath: string, name: string) {
  const descriptor = await inspectPackage(packagePath);
  const scoreRunDirectory = join(root, name);
  await mkdir(scoreRunDirectory);
  return runTaskGrader({ trialId: name, scoreRunDirectory, submissionDirectory: root, packageDescriptor: descriptor,
    submissionManifest: { schemaVersion: 1, files: [], totalBytes: 0, sha256: "0".repeat(64) }, maxOutputBytes: 100_000, resultMaxBytes: 100_000, timeoutMs: 30_000,
    isolation: "host" });
}

test("grader result v2: metrics are carried, the score model's metrics are required, values must be finite", async () => {
  const root = await mkdtemp(join(tmpdir(), "grader-v2-"));
  try {
    const ok = await grade(root, await v2Package(root, '[{ id: "score", value: 17.5, unit: "points" }, { id: "cases", value: 50 }]'), "ok");
    assert.equal(ok.status, "passed");
    assert.deepEqual(ok.metrics, [{ id: "score", value: 17.5, unit: "points" }, { id: "cases", value: 50 }]);
    const missing = await grade(root, await v2Package(root, '[{ id: "cases", value: 50 }]'), "missing");
    assert.deepEqual([missing.status, missing.error], ["error", "GRADER_METRIC_MISSING"]);
    const infinite = await grade(root, await v2Package(root, '[{ id: "score", value: "17" }]'), "invalid");
    assert.deepEqual([infinite.status, infinite.error], ["error", "GRADER_METRIC_INVALID"]);
    const duplicate = await grade(root, await v2Package(root, '[{ id: "score", value: 1 }, { id: "score", value: 2 }]'), "duplicate");
    assert.equal(duplicate.error, "GRADER_METRIC_INVALID");
    // A v1 result cannot satisfy a score model that names metrics.
    const v1 = await grade(root, await v2Package(root, "[]", 1), "v1");
    assert.equal(v1.error, "GRADER_METRIC_MISSING");
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
