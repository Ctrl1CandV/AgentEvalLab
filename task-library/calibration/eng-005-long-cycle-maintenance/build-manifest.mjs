import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readdir, readFile, writeFile } from "node:fs/promises";
import { join, relative } from "node:path";

const root = new URL("../../candidates/eng-005-long-cycle-maintenance/", import.meta.url).pathname.replace(/^\/(\w:)/, "$1");
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
const stageIds = ["S1", "S2", "S3", "S4", "S5"];
const previousRequirements = [];
const stageRequirements = {
  S1: ["BASE_CLI", "BASE_DATA", "QUERY"],
  S2: ["BASE_CLI", "BASE_DATA", "QUERY", "DEPENDENCY"],
  S3: ["BASE_CLI", "BASE_DATA", "QUERY", "DEPENDENCY", "NO_MUTATION"],
  S4: ["BASE_CLI", "BASE_DATA", "QUERY", "DEPENDENCY", "NO_MUTATION", "MIGRATION"],
  S5: ["BASE_CLI", "BASE_DATA", "QUERY", "DEPENDENCY", "NO_MUTATION", "MIGRATION", "ERRORS_DOCS"],
};
const requirementChecks = {
  BASE_CLI: ["base.read", "base.create", "base.update", "base.export"],
  BASE_DATA: ["data.preserves-seed"],
  QUERY: ["query.filter", "query.order", "query.pagination", "query.invalid"],
  DEPENDENCY: ["dependency.self", "dependency.cycle", "dependency.transition", "dependency.prerequisite"],
  NO_MUTATION: ["failure.no_mutation"],
  MIGRATION: ["migration.schema", "migration.preserve", "migration.events", "migration.idempotent"],
  ERRORS_DOCS: ["errors.protocol", "errors.codes", "docs.usage"],
};
const allPublic = ["instruction.md", "public/project-brief.md"];
const allTrusted = ["private/grader.py", "private/base-fixture.json", "private/v1-fixture.json"];
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
      timeoutMs: 25_000,
      maxOutputBytes: 100_000,
      checkIds: [`public-${id.toLowerCase()}`],
    },
  });
}
const baselineCommit = execFileSync("git", ["rev-parse", "HEAD"], { cwd: join(root, "baseline"), encoding: "utf8" }).trim();
const manifest = {
  schemaVersion: 1,
  id: "eng-005-long-cycle-maintenance",
  version: "0.2.1",
  familyId: "eng-workflow-evolution",
  capability: "engineering",
  usage: "development",
  source: { kind: "original-design", references: ["docs/design/LONG_HORIZON_ENGINEERING.md", "https://nodejs.org/docs/latest-v22.x/api/typescript.html"] },
  license: { taskText: "Original task specification and materials authored by this project; free to use and adapt.", thirdPartyContent: [] },
  entryPoint: { instruction: "instruction.md" },
  files: { public: await files(allPublic), trusted: await files(allTrusted) },
  requirements: Object.entries(requirementChecks).map(([id, checkIds]) => ({ id, critical: true, introducedAt: id, checkIds })),
  stages,
  toolProfiles: ["workspace-basic", "workspace-augmented"],
  grader: { id: "eng005-checkpoint-grader", version: "1.1.0", entryPoint: "private/grader.py", executable: "python3",
    args: ["{entryPoint}", "--request", "{request}", "--result", "{result}"] },
  environment: { runtime: "Node.js 22.x + Python 3.x", dependencies: "Node built-ins and Python standard library; no network", network: false,
    runtimeCheck: { executable: "node", args: ["--version"], expectedSubstring: "v22." } },
  baseline: { path: "baseline", commit: baselineCommit },
};
await writeFile(join(root, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
console.log(`manifest created for baseline ${baselineCommit}`);
