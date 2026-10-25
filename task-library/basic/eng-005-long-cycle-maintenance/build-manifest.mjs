import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readdir, readFile, writeFile } from "node:fs/promises";
import { join, relative } from "node:path";

const root = new URL("./", import.meta.url).pathname.replace(/^\/(\w:)/, "$1");
const sha256 = async path => createHash("sha256").update(await readFile(join(root, ...path.split("/")))).digest("hex");
const list = async directory => {
  const results = [];
  async function visit(path) {
    for (const entry of await readdir(join(root, path), { withFileTypes: true })) {
      const child = `${path}/${entry.name}`;
      if (entry.isSymbolicLink()) throw new Error(`symlink denied: ${child}`);
      if (entry.isDirectory()) {
        if (entry.name === "__pycache__") continue;
        await visit(child);
      } else if (!entry.name.endsWith(".pyc")) results.push(child);
    }
  }
  await visit(directory);
  return results.sort();
};
const files = async paths => Promise.all(paths.sort().map(async path => ({ path, sha256: await sha256(path) })));
const stageIds = ["S1", "S2", "S3", "S4", "S5", "S6", "S7"];
const previousRequirements = [];
const stageRequirements = {
  S1: ["BASE_CLI", "BASE_DATA", "QUERY"],
  S2: ["BASE_CLI", "BASE_DATA", "QUERY", "DEPENDENCY"],
  S3: ["BASE_CLI", "BASE_DATA", "QUERY", "DEPENDENCY", "NO_MUTATION"],
  S4: ["BASE_CLI", "BASE_DATA", "QUERY", "DEPENDENCY", "NO_MUTATION", "MIGRATION"],
  S5: ["BASE_CLI", "BASE_DATA", "QUERY", "DEPENDENCY", "NO_MUTATION", "MIGRATION", "ERRORS_DOCS"],
  S6: ["BASE_CLI", "BASE_DATA", "QUERY", "DEPENDENCY", "NO_MUTATION", "MIGRATION", "ERRORS_DOCS", "SCALE", "SCALE_SPEED"],
  S7: ["BASE_CLI", "BASE_DATA", "QUERY", "DEPENDENCY", "NO_MUTATION", "MIGRATION", "ERRORS_DOCS", "SCALE", "SCALE_SPEED", "PLAN", "PLAN_QUALITY"],
};
const requirementChecks = {
  BASE_CLI: ["base.read", "base.create", "base.update", "base.export"],
  BASE_DATA: ["data.preserves-seed"],
  QUERY: ["query.filter", "query.order", "query.pagination", "query.invalid", "query.defaults", "query.desc-ties", "query.sort-keys",
    "query.empty-result", "query.page-size-bounds", "query.rejects-malformed"],
  DEPENDENCY: ["dependency.self", "dependency.cycle", "dependency.transition", "dependency.prerequisite", "dependency.duplicate",
    "dependency.unknown", "dependency.transitive-cycle", "dependency.backward", "dependency.all-prerequisites"],
  NO_MUTATION: ["failure.no_mutation", "failure.no_mutation-prerequisite", "failure.no_mutation-dependency"],
  MIGRATION: ["migration.schema", "migration.preserve", "migration.events", "migration.idempotent", "migration.read-only",
    "migration.event-details", "migration.failed-no-write", "migration.cli-shape"],
  ERRORS_DOCS: ["errors.protocol", "errors.codes", "docs.usage", "errors.codes-all", "errors.store-invalid", "errors.clean-output"],
  SCALE: ["scale.list", "scale.dependencies", "scale.status"],
  SCALE_SPEED: ["scale.speed-3", "scale.speed-1.5", "scale.speed-1.1", "scale.speed-0.75"],
  PLAN: ["plan.valid-small", "plan.valid-large", "plan.valid-scale", "plan.read-only", "plan.errors", "plan.fields-preserved"],
  PLAN_QUALITY: ["plan.quality-25", "plan.quality-50", "plan.quality-65", "plan.quality-80", "plan.quality-90", "plan.quality-97"],
};
// The ladders rank deliveries on open-ended goals; everything else is correctness that a careful delivery passes.
const ladders = ["SCALE_SPEED", "PLAN_QUALITY"];
const allPublic = ["instruction.md", "public/project-brief.md"];
const allTrusted = ["card.md", "private/grader.py", "private/base-fixture.json", "private/v1-fixture.json", "private/scale.py", "private/plan.py",
  "private/plan-best.json",
  ...(await list("private/scale-reference"))];
const stages = [];
for (const id of stageIds) {
  const stageRoot = `stages/${id}`;
  const stageFiles = [`${stageRoot}/instruction.md`, ...(await list(`${stageRoot}/public`))];
  stages.push({
    id,
    instruction: `${stageRoot}/instruction.md`,
    files: await files(stageFiles),
    activeRequirementIds: stageRequirements[id],
    publicChecker: {
      entryPoint: `${stageRoot}/public/checker.py`,
      executable: "python3",
      args: ["{entryPoint}", "--submission", "{submission}", "--stage", id, "--sandbox-launcher", "{sandbox}"],
      // S6's checker writes a 100,000-order store and runs four commands of up to 10 seconds each; S7's runs seven.
      timeoutMs: id === "S6" ? 120_000 : id === "S7" ? 90_000 : 25_000,
      maxOutputBytes: 100_000,
      checkIds: [`public-${id.toLowerCase()}`],
    },
  });
}
const baselineCommit = execFileSync("git", ["rev-parse", "HEAD"], { cwd: join(root, "baseline"), encoding: "utf8" }).trim();
const correctness = Object.entries(requirementChecks).filter(([id]) => !ladders.includes(id)).flatMap(([, ids]) => ids);
const manifest = {
  schemaVersion: 2,
  id: "eng-005-long-cycle-maintenance",
  version: "0.5.0",
  familyId: "eng-workflow-evolution",
  capability: "engineering",
  usage: "development",
  source: { kind: "original-design", references: ["docs/design/LONG_HORIZON_ENGINEERING.md", "https://nodejs.org/docs/latest-v22.x/api/typescript.html"] },
  license: { taskText: "Original task specification and materials authored by this project; free to use and adapt.", thirdPartyContent: [] },
  entryPoint: { instruction: "instruction.md" },
  files: { public: await files(allPublic), trusted: await files(allTrusted) },
  // The ladders rank deliveries; correctness is what each stage accepts.
  requirements: Object.entries(requirementChecks).map(([id, checkIds]) => ({ id, critical: !ladders.includes(id), introducedAt: id, checkIds })),
  // Manifest v2 (PLAN-007 WP2.2): the trajectory is one task; resolved = every correctness check of the final stage.
  // The diagnostic keeps the user decision of 2026-10-22, half correctness and half the ladders with every rung equal:
  // correctness weighs 1, the four speed rungs 0.4 and the six quality rungs 0.6.
  tier: "basic",
  capabilities: ["engineering"],
  card: "card.md",
  scoreModel: {
    primary: { kind: "resolved" },
    groups: [
      // Grader 2.5.0 (user decision, 2026-10-25): speed is not scored; the speed rungs stay as reported labels (a group
      // of weight 0). The diagnostic weighs completion (the correctness checks) and quality (the plan ladder) equally;
      // the headline stays resolved until Phase 4 shows whether completion and quality must enter it.
      { id: "correctness", weight: 0.5, critical: true, rule: "fraction", checkIds: correctness },
      { id: "speed-rungs", weight: 0, critical: false, rule: "fraction", checkIds: requirementChecks.SCALE_SPEED },
      { id: "plan-rungs", weight: 0.5, critical: false, rule: "fraction", checkIds: requirementChecks.PLAN_QUALITY },
    ],
  },
  task: { split: "dev", structure: "package:eng-005",
    provenance: { source: "project-authored baseline, stage briefs, references and checks", published: "2026-10-22", license: "project-authored",
      exposure: "private-to-runs" } },
  stages,
  toolProfiles: ["workspace-basic", "workspace-augmented"],
  grader: { id: "eng005-checkpoint-grader", version: "2.5.0", entryPoint: "private/grader.py", executable: "python3",
    args: ["{entryPoint}", "--request", "{request}", "--result", "{result}"] },
  environment: { runtime: "Node.js 22.x + Python 3.x", dependencies: "Node built-ins and Python standard library; no network", network: false,
    runtimeCheck: { executable: "node", args: ["--version"], expectedSubstring: "v22." } },
  baseline: { path: "baseline", commit: baselineCommit },
};
await writeFile(join(root, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
console.log(`manifest created for baseline ${baselineCommit}`);
