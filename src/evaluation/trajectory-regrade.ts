import { randomUUID } from "node:crypto";
import { lstat, mkdir, mkdtemp, readFile, readdir, rename, rm, writeFile } from "node:fs/promises";
import { basename, dirname, join, resolve } from "node:path";
import { tmpdir } from "node:os";
import { copyArtifacts, defaultArtifactLimits } from "./artifacts.js";
import { runTaskGrader } from "./grader.js";
import { preflightPlan } from "./preflight.js";
import { validatePlan } from "./validate.js";
import type { EvaluationPlan, EvaluationResult, TrajectoryRecord } from "./types.js";

/**
 * Append-only re-grading of trajectory snapshots (PLAN-007 WP0.4): each graded snapshot of a recorded trajectory is
 * graded again by the package's current grader into a new score run beside the original one. The trajectory record,
 * its report and earlier score runs stay unchanged; loadTrajectoryRecords overlays the latest score run of each
 * snapshot, so suite reports and evidence tables read the new grade while the old one stays readable.
 */

interface SnapshotScore {
  directory: string;
  stageId: string;
  cycleId: string;
  snapshotManifestSha256: string;
  createdAt: string;
  graderVersion: string | null;
  evaluation: EvaluationResult;
}

async function readJson<T>(path: string): Promise<T> {
  return JSON.parse(await readFile(path, "utf8")) as T;
}

/** Every snapshot score run of a trajectory trial, oldest first, with the grader version that produced it. */
export async function snapshotScores(trialDirectory: string): Promise<SnapshotScore[]> {
  const root = join(trialDirectory, "score-runs");
  const entries = await readdir(root, { withFileTypes: true }).catch(() => []);
  const scores: SnapshotScore[] = [];
  for (const entry of entries) {
    if (!entry.isDirectory() || entry.name.startsWith(".pending-")) continue;
    const directory = join(root, entry.name);
    const score = await readJson<{ stageId?: string; cycleId?: string; snapshotManifestSha256?: string; createdAt?: string; evaluation?: EvaluationResult;
      scorer?: { graderVersion?: string } }>(join(directory, "score.json")).catch(() => null);
    if (!score?.stageId || !score.cycleId || !score.snapshotManifestSha256 || !score.createdAt || !score.evaluation) continue;
    const grader = await readJson<{ graderVersion?: string }>(join(directory, "grader", "result.json")).catch(() => null);
    scores.push({ directory, stageId: score.stageId, cycleId: score.cycleId, snapshotManifestSha256: score.snapshotManifestSha256, createdAt: score.createdAt,
      graderVersion: score.scorer?.graderVersion ?? grader?.graderVersion ?? null, evaluation: score.evaluation });
  }
  return scores.sort((left, right) => left.createdAt.localeCompare(right.createdAt) || left.directory.localeCompare(right.directory));
}

/**
 * The records of a trajectory run with each snapshot's grade taken from its latest score run (optionally only those
 * of one grader version); a snapshot without such a run keeps the grade its record holds.
 */
export async function loadTrajectoryRecords(runDirectory: string, graderVersion?: string): Promise<TrajectoryRecord[]> {
  const report = await readJson<{ records: TrajectoryRecord[] }>(join(runDirectory, "report.json"));
  for (const record of report.records) {
    const scores = (await snapshotScores(join(runDirectory, record.id))).filter(score => !graderVersion || score.graderVersion === graderVersion);
    for (const stage of record.stages) {
      for (const cycle of stage.cycles) {
        if (!cycle.snapshot) continue;
        const latest = scores.filter(score => score.stageId === stage.stageId && score.cycleId === cycle.cycleId &&
          score.snapshotManifestSha256 === cycle.snapshot!.manifest.sha256).at(-1);
        if (latest) cycle.privateGrade = latest.evaluation;
      }
    }
  }
  return report.records;
}

export interface TrajectoryRegrade { stageId: string; cycleId: string; scoreRunId: string; evaluation: EvaluationResult }

/** Grades a trajectory's graded snapshots again ("all"), or only the last one, which its score reads ("final"). */
export async function regradeTrajectory(trialDirectory: string, plan: EvaluationPlan, reason: string, scope: "all" | "final" = "all"): Promise<TrajectoryRegrade[]> {
  validatePlan(plan);
  if (typeof reason !== "string" || !reason.trim() || reason.length > 500) throw new Error("REGRADE_REASON_REQUIRED");
  const trial = resolve(trialDirectory);
  const record = await readJson<TrajectoryRecord>(join(trial, "trajectory.json")).catch(() => { throw new Error("TRAJECTORY_RECORD_INVALID"); });
  if (record.id !== basename(trial) || !Array.isArray(record.stages)) throw new Error("TRAJECTORY_RECORD_INVALID");
  const item = plan.cases.find(candidate => candidate.id === record.caseId);
  if (!item || item.evaluator.kind !== "task-package") throw new Error("REGRADE_TASK_PACKAGE_REQUIRED");
  const descriptor = (await preflightPlan(plan)).get(item.id);
  if (!descriptor?.manifest || !descriptor.manifestSha256) throw new Error("REGRADE_TASK_PACKAGE_INVALID");
  if (record.packageManifest?.version !== descriptor.manifest.version) throw new Error("REGRADE_TASK_VERSION_MISMATCH");
  const experiment = await readJson<{ packageFingerprints?: Array<{ caseId: string; id: string; version: string }>; artifactLimits?: typeof defaultArtifactLimits }>(
    join(dirname(trial), "experiment.json"));
  const original = experiment.packageFingerprints?.find(entry => entry.caseId === record.caseId);
  if (!original || original.id !== descriptor.manifest.id || original.version !== descriptor.manifest.version) throw new Error("REGRADE_TASK_IDENTITY_MISMATCH");
  const limits = { ...defaultArtifactLimits, ...(experiment.artifactLimits ?? {}) };

  const graded = record.stages.flatMap(stage => stage.cycles.filter(cycle => cycle.snapshot && cycle.privateGrade).map(cycle => ({ stage, cycle })));
  const chosen = scope === "final" ? graded.slice(-1) : graded;
  const previous = await snapshotScores(trial);
  const results: TrajectoryRegrade[] = [];
  for (const { stage, cycle } of chosen) {
    const snapshot = cycle.snapshot!;
    const scoreRunId = randomUUID();
    const scoreRuns = join(trial, "score-runs");
    const pending = join(scoreRuns, `.pending-${scoreRunId}`);
    const verification = await mkdtemp(join(tmpdir(), "agent-eval-trajectory-regrade-"));
    let appended = false;
    try {
      // The stored snapshot must still match the manifest recorded when it was taken.
      const copied = await copyArtifacts(join(trial, ...snapshot.path.split("/")), join(verification, "submission"), limits);
      if (copied.sha256 !== snapshot.manifest.sha256 || copied.totalBytes !== snapshot.manifest.totalBytes) throw new Error("REGRADE_SNAPSHOT_HASH_MISMATCH");
      await mkdir(pending, { recursive: true });
      const tracePath = join(trial, "tool-trace.jsonl");
      const evaluation = await runTaskGrader({
        trialId: `${record.id}.${stage.stageId}.${cycle.cycleId}`,
        scoreRunDirectory: pending,
        submissionDirectory: join(verification, "submission"),
        submissionManifest: copied,
        packageDescriptor: descriptor,
        maxOutputBytes: item.evaluator.maxOutputBytes ?? limits.graderResultMaxBytes,
        resultMaxBytes: limits.graderResultMaxBytes,
        timeoutMs: item.evaluator.timeoutMs ?? 30_000,
        ...(cycle.execution?.output !== undefined ? { answerText: cycle.execution.output } : {}),
        ...(await lstat(tracePath).then(() => ({ tracePath }), () => ({}))),
        context: { stageId: stage.stageId, cycleId: cycle.cycleId, activeRequirementIds: stage.activeRequirementIds },
        ...(plan.isolation ? { isolation: plan.isolation } : {}),
      });
      const before = previous.filter(score => score.stageId === stage.stageId && score.cycleId === cycle.cycleId).at(-1);
      await writeFile(join(pending, "score.json"), JSON.stringify({
        schemaVersion: 1, trialId: record.id, stageId: stage.stageId, cycleId: cycle.cycleId, taskManifestSha256: descriptor.manifestSha256,
        snapshotManifestSha256: snapshot.manifest.sha256, evaluation, createdAt: new Date(Math.max(Date.now(), before ? Date.parse(before.createdAt) + 1 : 0)).toISOString(),
        reason: reason.trim(), previousScoreRunId: before ? basename(before.directory) : null,
        scorer: { kind: "task-package", taskId: descriptor.manifest.id, taskVersion: descriptor.manifest.version, graderId: descriptor.manifest.grader.id,
          graderVersion: descriptor.manifest.grader.version },
      }, null, 2), { encoding: "utf8", flag: "wx" });
      await rename(pending, join(scoreRuns, scoreRunId));
      appended = true;
      results.push({ stageId: stage.stageId, cycleId: cycle.cycleId, scoreRunId, evaluation });
    } finally {
      await rm(verification, { recursive: true, force: true });
      if (!appended) await rm(pending, { recursive: true, force: true });
    }
  }
  return results;
}
