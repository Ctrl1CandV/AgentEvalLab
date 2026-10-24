import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { glob } from "node:fs/promises";
import { validateTaskPackageManifest } from "../src/evaluation/manifest.js";

const digest = "a".repeat(64);
const item = (id: string, split: string, structure: string, anchors?: Record<string, Record<string, number>>) => ({
  id, level: "L1", files: [{ path: `items/${id}/prompt.md`, sha256: digest }], activeRequirementIds: ["REQ-A", "REQ-FORMAT"],
  split, structure, provenance: { source: "SWE-bench-Live", published: "2026-08-14", license: "MIT", exposure: "public" }, ...(anchors ? { anchors } : {}),
});

function v2(): Record<string, unknown> {
  return {
    schemaVersion: 2, id: "fixture", version: "0.1.0", familyId: "fixture", capability: "engineering", usage: "development",
    source: { kind: "open-source", references: [] }, license: { taskText: "MIT", thirdPartyContent: [] },
    entryPoint: { instruction: "instruction.md" },
    files: { public: [{ path: "instruction.md", sha256: digest }], trusted: [{ path: "card.md", sha256: digest }, { path: "private/grader.py", sha256: digest },
      { path: "private/repos/x.tar", sha256: digest }, { path: "runtime/py/site/lib.py", sha256: digest }] },
    requirements: [
      { id: "REQ-A", critical: true, introducedAt: "0.1.0", checkIds: ["a1", "a2"] },
      { id: "REQ-FORMAT", critical: false, introducedAt: "0.1.0", checkIds: ["answer-format"] },
    ],
    items: [item("i1", "dev", "repo:x", { score: { naive: 1, strong: 9 } }), item("i2", "dev", "repo:x", { score: { naive: 2, strong: 8 } }),
      item("i3", "validation", "repo:y", { score: { naive: 0, strong: 5 } })],
    toolProfiles: ["workspace-basic"],
    grader: { id: "g", version: "1.0.0", entryPoint: "private/grader.py", executable: "python3", args: ["{entryPoint}", "--request", "{request}", "--result", "{result}"] },
    environment: { runtime: "Python 3", dependencies: "none", network: false },
    tier: "core", capabilities: ["engineering"], card: "card.md",
    scoreModel: {
      primary: { kind: "resolved" },
      groups: [{ id: "tests", weight: 1, critical: true, rule: "fraction", checkIds: ["a1", "a2"] },
        { id: "score", weight: 0.5, critical: false, rule: "metric", checkIds: [], metric: "score" }],
      metrics: [{ id: "score", unit: "points", direction: "higher", anchors: { version: "1", points: [{ name: "naive", maps: 0 }, { name: "strong", maps: 1 }] } }],
      format: { checkId: "answer-format", penalty: 0.2 }, structureCap: 0.2,
    },
    runtime: { mounts: [{ path: "runtime/py", env: { PYTHONPATH: "{mount}/site" } }] },
  };
}

const refuses = (change: (manifest: Record<string, unknown>) => void, code: RegExp) => {
  const manifest = v2();
  change(manifest);
  assert.throws(() => validateTaskPackageManifest(manifest), code);
};

test("manifest v2: a complete manifest is accepted and every new field is checked", () => {
  validateTaskPackageManifest(v2());
  refuses(manifest => { manifest.surprise = true; }, /INVALID_PACKAGE_V2_KEYS/);
  refuses(manifest => { manifest.scoring = {}; }, /INVALID_PACKAGE_V2_SCORING/);
  refuses(manifest => { manifest.tier = "retired"; }, /INVALID_PACKAGE_TIER/);
  refuses(manifest => { manifest.capabilities = ["tool"]; }, /INVALID_PACKAGE_CAPABILITIES/);
  refuses(manifest => { manifest.card = "public/card.md"; }, /INVALID_PACKAGE_CARD/);
  refuses(manifest => { (manifest.scoreModel as { groups: Array<{ checkIds: string[] }> }).groups[0]!.checkIds = ["a1"]; }, /SCORE_GROUPS_DO_NOT_COVER_CHECKS/);
  refuses(manifest => { (manifest.scoreModel as { groups: unknown[] }).groups.push({ id: "again", weight: 1, critical: false, rule: "all", checkIds: ["a2"] }); }, /INVALID_SCORE_GROUP_CHECKS/);
  refuses(manifest => { (manifest.scoreModel as { format: { checkId: string } }).format.checkId = "a1"; }, /INVALID_SCORE_GROUP_CHECKS|INVALID_SCORE_FORMAT/);
  refuses(manifest => { (manifest.scoreModel as { primary: unknown }).primary = { kind: "metric", metric: "missing" }; }, /INVALID_SCORE_PRIMARY/);
  refuses(manifest => { ((manifest.scoreModel as { metrics: Array<{ anchors: { points: Array<{ maps: number }> } }> }).metrics[0]!.anchors.points[1]!.maps = 0); }, /INVALID_SCORE_ANCHORS/);
  refuses(manifest => { (manifest.items as Array<{ structure: string }>)[2]!.structure = "repo:x"; }, /INVALID_PACKAGE_SPLITS_OVERLAP/);
  refuses(manifest => { (manifest.items as Array<{ anchors: Record<string, unknown> }>)[0]!.anchors = { score: { naive: 1 } }; }, /ANCHORS_INCOMPLETE/);
  refuses(manifest => { (manifest.items as Array<{ split: string }>)[0]!.split = "test"; }, /INVALID_PACKAGE_ITEM_V2_SPLIT/);
  refuses(manifest => { (manifest.items as Array<{ provenance: { exposure: string } }>)[0]!.provenance.exposure = "secret"; }, /PROVENANCE/);
  refuses(manifest => { manifest.runtime = { mounts: [{ path: "../site", env: {} }] }; }, /INVALID_PACKAGE_RUNTIME/);
  refuses(manifest => { manifest.runtime = { mounts: [{ path: "runtime/py", env: { "bad-name": "x" } }] }; }, /INVALID_PACKAGE_RUNTIME/);
});

test("manifest v2: per-item headlines and item-scoped metric groups; anchors only where an item is scored on the metric", () => {
  const manifest = v2();
  const model = manifest.scoreModel as Record<string, unknown>;
  model.primaryByItem = { i3: { kind: "metric", metric: "score" } };
  (model.groups as Array<Record<string, unknown>>)[1]!.items = ["i3"];
  for (const entry of (manifest.items as Array<Record<string, unknown>>).slice(0, 2)) delete entry.anchors;
  validateTaskPackageManifest(structuredClone(manifest));
  const without = structuredClone(manifest);
  delete (without.items as Array<Record<string, unknown>>)[2]!.anchors;
  assert.throws(() => validateTaskPackageManifest(without), /ANCHORS_INCOMPLETE/);
  const unknownItem = structuredClone(manifest);
  (unknownItem.scoreModel as Record<string, unknown>).primaryByItem = { i9: { kind: "resolved" } };
  assert.throws(() => validateTaskPackageManifest(unknownItem), /INVALID_SCORE_ITEMS/);
  const checkGroupItems = structuredClone(manifest);
  ((checkGroupItems.scoreModel as Record<string, unknown>).groups as Array<Record<string, unknown>>)[0]!.items = ["i1"];
  assert.throws(() => validateTaskPackageManifest(checkGroupItems), /INVALID_SCORE_GROUPS/);
  const reportedByOne = structuredClone(manifest);
  ((reportedByOne.scoreModel as Record<string, unknown>).metrics as Array<Record<string, unknown>>)[0]!.items = ["i3"];
  validateTaskPackageManifest(structuredClone(reportedByOne));
  ((reportedByOne.scoreModel as Record<string, unknown>).primaryByItem as Record<string, unknown>).i1 = { kind: "metric", metric: "score" };
  assert.throws(() => validateTaskPackageManifest(reportedByOne), /INVALID_SCORE_ITEMS|ANCHORS_INCOMPLETE/, "an item cannot be scored on a metric its grading does not report");
  const badHeadline = structuredClone(manifest);
  (badHeadline.scoreModel as Record<string, unknown>).primaryByItem = { i3: { kind: "metric", metric: "nothing" } };
  assert.throws(() => validateTaskPackageManifest(badHeadline), /INVALID_SCORE_PRIMARY/);
});

test("manifest v2: repository items and runtime mounts are hashed trusted files, named exactly", () => {
  const withRepository = (change: (item: Record<string, unknown>, manifest: Record<string, unknown>) => void) => {
    const manifest = v2();
    const first = (manifest.items as Array<Record<string, unknown>>)[0]!;
    first.repository = { archive: "private/repos/x.tar", directory: "repo" };
    first.mounts = ["runtime/py"];
    change(first, manifest);
    return manifest;
  };
  validateTaskPackageManifest(withRepository(() => {}));
  assert.throws(() => validateTaskPackageManifest(withRepository(item => { item.repository = { archive: "private/repos/y.tar", directory: "repo" }; })), /INVALID_PACKAGE_ITEM_REPOSITORY/);
  assert.throws(() => validateTaskPackageManifest(withRepository(item => { item.repository = { archive: "card.md", directory: "repo" }; })), /INVALID_PACKAGE_ITEM_REPOSITORY/);
  assert.throws(() => validateTaskPackageManifest(withRepository(item => { item.repository = { archive: "private/repos/x.tar", directory: "../up" }; })), /INVALID_PACKAGE_ITEM_REPOSITORY/);
  assert.throws(() => validateTaskPackageManifest(withRepository(item => { item.mounts = ["runtime/other"]; })), /INVALID_PACKAGE_ITEM_MOUNTS/);
  assert.throws(() => validateTaskPackageManifest(withRepository((_item, manifest) => { manifest.runtime = { mounts: [{ path: "runtime/py/site", env: {} }] }; })), /INVALID_PACKAGE_RUNTIME/);
  assert.throws(() => validateTaskPackageManifest(withRepository((_item, manifest) => { manifest.runtime = { mounts: [{ path: "runtime/py", env: { HOME: "/x" } }] }; })), /INVALID_PACKAGE_RUNTIME/);
  assert.throws(() => validateTaskPackageManifest(withRepository((_item, manifest) => {
    (manifest.files as { trusted: Array<{ path: string }> }).trusted = (manifest.files as { trusted: Array<{ path: string }> }).trusted.filter(file => !file.path.startsWith("runtime/"));
  })), /INVALID_PACKAGE_RUNTIME_FILES/);
  // An archived runtime: one hashed tar under assets/, and no files under its path.
  const archived = (archive: string, keepFiles = false) => withRepository((_item, manifest) => {
    const files = manifest.files as { trusted: Array<{ path: string; sha256: string }> };
    files.trusted = [...files.trusted.filter(file => keepFiles || !file.path.startsWith("runtime/")), { path: archive, sha256: digest }];
    manifest.runtime = { mounts: [{ path: "runtime/py", archive, env: {} }] };
  });
  validateTaskPackageManifest(archived("assets/runtime-py.tar"));
  assert.throws(() => validateTaskPackageManifest(archived("private/runtime-py.tar")), /INVALID_PACKAGE_RUNTIME_FILES/);
  assert.throws(() => validateTaskPackageManifest(archived("assets/runtime-py.tar", true)), /INVALID_PACKAGE_RUNTIME_FILES/);
});

test("manifest v2: a package without items is one task, placed by its own split and structure", () => {
  const manifest = v2();
  delete manifest.items;
  manifest.requirements = [(manifest.requirements as unknown[])[0], (manifest.requirements as unknown[])[1]];
  (manifest.scoreModel as Record<string, unknown>).groups = [{ id: "tests", weight: 1, critical: true, rule: "all", checkIds: ["a1", "a2"] }];
  delete (manifest.scoreModel as Record<string, unknown>).metrics;
  assert.throws(() => validateTaskPackageManifest(structuredClone(manifest)), /INVALID_PACKAGE_TASK/);
  manifest.task = { split: "dev", structure: "package:fixture", provenance: { source: "original", published: "2026-10", license: "project", exposure: "generated" } };
  validateTaskPackageManifest(manifest);
});

test("manifest v1: every package in the library still loads, and v2 fields are refused in a v1 manifest", async () => {
  let count = 0;
  for await (const path of glob("task-library/*/*/manifest.json")) {
    const manifest = JSON.parse(await readFile(path, "utf8")) as Record<string, unknown>;
    validateTaskPackageManifest(manifest);
    count++;
  }
  assert.ok(count >= 14);
  const manifest = v2();
  manifest.schemaVersion = 1;
  assert.throws(() => validateTaskPackageManifest(manifest), /INVALID_PACKAGE_V1_HAS_V2_FIELDS/);
});
