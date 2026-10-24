// PLAN-007 WP1.6: the v2 measurement layer on two real families, without model runs.
//
// - AE 0.2.0 (frontier, metric primary, per-item anchors, uncapped): its reference programs are graded as deliveries
//   through the real grader protocol (runTaskGrader, sandboxed), and each grading becomes an outcome record under a
//   reference pseudo-model ("reference:naive", "reference:greedy").
// - R3 0.3.0 (core, resolved primary, cell accuracy diagnostic): the v2 outcomes of the 0.3.0 pilot, re-graded under
//   grader 2.0.0 (runs/e3b89e80-...).
//
// Writes docs/evidence/v2-proof/report-v2.md and .json. Usage: node --import tsx scripts/measurement-proof.ts
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { inspectPackage } from "../src/evaluation/manifest.js";
import { runTaskGrader } from "../src/evaluation/grader.js";
import { copyArtifacts, defaultArtifactLimits } from "../src/evaluation/artifacts.js";
import { emptyExecution } from "../src/types.js";
import { buildOutcome, type OutcomeRecord } from "../src/scoring/model.js";
import { loadOutcomes } from "../src/scoring/outcomes.js";
import { buildReportV2, markdownReportV2, type V2FamilyData } from "../src/analysis/report-v2.js";

const repoRoot = fileURLToPath(new URL("../", import.meta.url));
const AE = "task-library/frontier/ae-heuristic-contests";
const R3_RUN = "runs/e3b89e80-676e-4b9b-a3dc-f5e2ddff6bfb";
// The naive reference of every problem, and the stronger references that exist so far (WP3.5 adds the rest).
const GREEDY: Record<string, string> = { ahc015: "by-flavour.cpp", ahc035: "top-value.cpp", ahc039: "grid.cpp" };

async function aeOutcomes(): Promise<OutcomeRecord[]> {
  const descriptor = await inspectPackage(join(repoRoot, AE));
  const manifest = descriptor.manifest!;
  const anchors = JSON.parse(await readFile(join(repoRoot, AE, "private", "anchors.json"), "utf8")) as Record<string, { naiveReference: string }>;
  const outcomes: OutcomeRecord[] = [];
  for (const item of manifest.items!) {
    const programs: Array<[string, string]> = [["reference:naive", anchors[item.id]!.naiveReference.split("/").at(-1)!]];
    if (GREEDY[item.id]) programs.push(["reference:greedy", GREEDY[item.id]!]);
    for (const [model, program] of programs) {
      const work = await mkdtemp(join(tmpdir(), "measurement-proof-"));
      try {
        await mkdir(join(work, "submission", "public"), { recursive: true });
        await writeFile(join(work, "submission", "public", "main.cpp"), await readFile(join(repoRoot, AE, "private", "references", item.id, program), "utf8"));
        const submission = await copyArtifacts(join(work, "submission"), join(work, "snapshot"), defaultArtifactLimits);
        await mkdir(join(work, "score-run"));
        const trialId = `${model.replace(":", "-")}-${item.id}`;
        const evaluation = await runTaskGrader({ trialId, scoreRunDirectory: join(work, "score-run"), submissionDirectory: join(work, "snapshot"), submissionManifest: submission,
          packageDescriptor: descriptor, maxOutputBytes: 1_000_000, resultMaxBytes: 1_000_000, timeoutMs: 1_800_000,
          context: { stageId: null, cycleId: null, itemId: item.id, activeRequirementIds: item.activeRequirementIds } });
        const expected = manifest.requirements.filter(requirement => item.activeRequirementIds.includes(requirement.id)).flatMap(requirement => requirement.checkIds);
        outcomes.push(buildOutcome({ trialId, model, taskId: manifest.id, taskVersion: manifest.version, graderVersion: manifest.grader.version, itemId: item.id,
          split: item.split ?? null, structure: item.structure ?? null, evaluation, ...(evaluation.metrics ? { metrics: evaluation.metrics } : {}),
          execution: emptyExecution(), scoreModel: manifest.scoreModel!, ...(item.anchors ? { anchors: item.anchors } : {}), expectedCheckIds: expected }));
        console.log(`${model} ${item.id} (${program}): ${evaluation.status}, performance ${evaluation.metrics?.find(metric => metric.id === "performance")?.value}, primary ${outcomes.at(-1)!.primary}`);
      } finally {
        await rm(work, { recursive: true, force: true });
      }
    }
  }
  return outcomes;
}

const ae = await aeOutcomes();
const r3 = await loadOutcomes(join(repoRoot, R3_RUN));
const r3Models = [...new Set(r3.map(outcome => outcome.model))].sort();
const protocol = (budget: string, tools: string, commandLimits: string) => ({ budget, contextPolicy: "single", tools, commandLimits });
const families: V2FamilyData[] = [
  { id: "R3", tier: "core", capability: "reasoning", openEnded: false, structureCap: 0.2, packageId: "r3-logic-grid", taskVersion: "0.3.0", primaryKind: "resolved",
    outcomes: r3, plannedTasks: Object.fromEntries(r3Models.map(model => [model, 24])), notRun: {},
    protocol: protocol("0.3M/task", "workspace-basic, read-only, no execution", "default"), runDirectories: [R3_RUN] },
  { id: "AE", tier: "frontier", capability: "engineering", openEnded: true, structureCap: 0.2, packageId: "ae-heuristic-contests", taskVersion: "0.2.0", primaryKind: "metric",
    outcomes: ae, plannedTasks: { "reference:naive": 10, "reference:greedy": 3 }, notRun: {},
    protocol: protocol("none (reference programs)", "workspace-augmented", "600 s"), runDirectories: [] },
];
const labels = [...r3Models, "reference:naive", "reference:greedy"];
const report = buildReportV2({
  suite: "v2-measurement-proof", id: `proof-${createHash("sha256").update(JSON.stringify(labels)).digest("hex").slice(0, 8)}`, release: null, split: "dev", track: "fixed",
  commit: execFileSync("git", ["rev-parse", "HEAD"], { cwd: repoRoot, encoding: "utf8" }).trim(), startedAt: "2026-10-24", finishedAt: "2026-10-24", status: "completed",
  models: labels.map(label => ({ label, thinking: label.startsWith("reference:") ? "n/a (a program)" : label.split("-").at(-1)!, temperature: label.startsWith("reference:") ? null : 0 })),
  repetitions: 1, capabilityWeights: { reasoning: { R3: 1 } }, families, audits: { R3: null, AE: null },
});
const out = join(repoRoot, "docs", "evidence", "v2-proof");
await mkdir(out, { recursive: true });
await writeFile(join(out, "report-v2.json"), JSON.stringify(report, null, 1) + "\n");
await writeFile(join(out, "report-v2.md"), `${markdownReportV2(report)}\n## About this report\n\nA fixture suite for PLAN-007 WP1.6, built by \`scripts/measurement-proof.ts\` without any model run. R3 rows are the 0.3.0 pilot's trials (\`${R3_RUN}\`) re-graded under grader 2.0.0 into v2 outcomes; glm-5.3, step-5-preview and gpt-6-luna are absent because their trials of that run failed on the provider and were never graded. AE rows are reference programs graded through the real grader protocol: \`reference:naive\` is each problem's naive reference (the anchor that maps to 0), \`reference:greedy\` the stronger references that exist so far. The suite id and commit are the proof's, not a suite run's.\n`);
console.log(JSON.stringify({ out: "docs/evidence/v2-proof/report-v2.md", ae: ae.length, r3: r3.length }));
