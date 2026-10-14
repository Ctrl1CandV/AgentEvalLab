import { createHash, randomUUID } from "node:crypto";
import { lstat, mkdir, mkdtemp, open, readFile, readdir, realpath, rename, rm, writeFile } from "node:fs/promises";
import { basename, dirname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { tmpdir } from "node:os";
import { defaultArtifactLimits, copyArtifacts } from "./artifacts.js";
import { evaluate } from "./evaluator.js";
import { preflightPlan } from "./preflight.js";
import { markdownReport, summarize } from "./report.js";
import { validatePlan } from "./validate.js";
import type { ArtifactLimits, ArtifactManifest, EvaluationPlan, EvaluationResult, TrialRecord } from "./types.js";
import type { PackageDescriptor } from "./manifest.js";

const MAX_TRIAL_JSON_BYTES = 8 * 1024 * 1024;
const MAX_SCORE_JSON_BYTES = 1024 * 1024;
const MAX_MANIFEST_FILES = 100_000;

function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("TRIAL_RECORD_INVALID");
  return value as Record<string, unknown>;
}

async function readJson(path: string, maxBytes: number): Promise<unknown> {
  const info = await lstat(path).catch(() => null);
  if (!info?.isFile() || info.isSymbolicLink() || info.size > maxBytes) throw new Error("TRIAL_FILE_INVALID");
  try { return JSON.parse(await readFile(path, "utf8")) as unknown; }
  catch { throw new Error("TRIAL_FILE_INVALID_JSON"); }
}

function validEvaluation(value: unknown): value is EvaluationResult {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const result = value as Record<string, unknown>;
  return ["passed", "failed", "scored", "incomplete", "error", "unscored", "resource_limit", "skipped", "pending"].includes(String(result.status)) &&
    (result.score === null || (typeof result.score === "number" && Number.isFinite(result.score))) &&
    Array.isArray(result.checks) && result.checks.every(check => {
      if (!check || typeof check !== "object" || Array.isArray(check)) return false;
      const item = check as Record<string, unknown>;
      return typeof item.id === "string" && (item.passed === true || item.passed === false || item.passed === null);
    }) && (result.error === null || typeof result.error === "string");
}

/** Read and validate a trial's result.json; trials that failed before artifact export have no manifest. */
async function loadTrialRecord(trialDirectory: string): Promise<{ directory: string; record: TrialRecord; rawRecord: Record<string, unknown> }> {
  const directory = resolve(trialDirectory);
  const info = await lstat(directory).catch(() => null);
  if (!info?.isDirectory() || info.isSymbolicLink()) throw new Error("TRIAL_DIRECTORY_INVALID");
  const rawRecord = object(await readJson(join(directory, "result.json"), MAX_TRIAL_JSON_BYTES));
  const execution = object(rawRecord.execution);
  const model = object(rawRecord.model);
  if (typeof rawRecord.id !== "string" || basename(directory) !== rawRecord.id ||
      typeof rawRecord.caseId !== "string" || typeof model.provider !== "string" || typeof model.id !== "string" ||
      !["done", "error", "timeout", "budget_exceeded"].includes(String(execution.status)) ||
      typeof execution.modelCalls !== "number" || !Number.isFinite(execution.modelCalls) ||
      typeof execution.toolCalls !== "number" || !Number.isFinite(execution.toolCalls) ||
      typeof execution.turns !== "number" || !Number.isFinite(execution.turns) ||
      !(execution.reportedTokens === null || (typeof execution.reportedTokens === "number" && Number.isFinite(execution.reportedTokens))) ||
      typeof rawRecord.durationMs !== "number" || !Number.isFinite(rawRecord.durationMs) ||
      !(rawRecord.cleanup === "cleaned" || rawRecord.cleanup === "error") || !validEvaluation(rawRecord.evaluation)) {
    throw new Error("TRIAL_RECORD_INVALID");
  }
  return { directory, record: rawRecord as unknown as TrialRecord, rawRecord };
}

async function loadTrial(trialDirectory: string): Promise<{ directory: string; record: TrialRecord; manifest: ArtifactManifest }> {
  const { directory, record, rawRecord } = await loadTrialRecord(trialDirectory);
  const manifest = validateArtifactManifest(await readJson(join(directory, "artifact-manifest.json"), MAX_TRIAL_JSON_BYTES));
  const summary = object(rawRecord.artifactManifest);
  if (summary.sha256 !== manifest.sha256 || summary.totalBytes !== manifest.totalBytes) throw new Error("TRIAL_ARTIFACT_MANIFEST_MISMATCH");
  return { directory, record, manifest };
}

function validateArtifactManifest(value: unknown): ArtifactManifest {
  const manifest = object(value);
  if (manifest.schemaVersion !== 1 || !Array.isArray(manifest.files) || manifest.files.length > MAX_MANIFEST_FILES ||
      typeof manifest.totalBytes !== "number" || !Number.isSafeInteger(manifest.totalBytes) || manifest.totalBytes < 0 ||
      typeof manifest.sha256 !== "string" || !/^[a-f0-9]{64}$/.test(manifest.sha256)) throw new Error("TRIAL_ARTIFACT_MANIFEST_INVALID");
  const seen = new Set<string>();
  let totalBytes = 0;
  const files: ArtifactManifest["files"] = [];
  for (const rawFile of manifest.files) {
    const file = object(rawFile);
    if (typeof file.path !== "string" || !file.path || file.path.includes("\\") || file.path.includes("\0") ||
        isAbsolute(file.path) || /^[A-Za-z]:/.test(file.path) || file.path.split("/").some(part => !part || part === "." || part === "..") ||
        seen.has(file.path) || typeof file.sizeBytes !== "number" || !Number.isSafeInteger(file.sizeBytes) || file.sizeBytes < 0 ||
        typeof file.sha256 !== "string" || !/^[a-f0-9]{64}$/.test(file.sha256)) throw new Error("TRIAL_ARTIFACT_MANIFEST_INVALID");
    seen.add(file.path);
    totalBytes += file.sizeBytes;
    if (!Number.isSafeInteger(totalBytes)) throw new Error("TRIAL_ARTIFACT_MANIFEST_INVALID");
    files.push({ path: file.path, sizeBytes: file.sizeBytes, sha256: file.sha256 });
  }
  const sorted = [...files].sort((left, right) => left.path.localeCompare(right.path));
  const digest = createHash("sha256").update(JSON.stringify(sorted)).digest("hex");
  if (totalBytes !== manifest.totalBytes || JSON.stringify(files) !== JSON.stringify(sorted) || digest !== manifest.sha256) {
    throw new Error("TRIAL_ARTIFACT_MANIFEST_INVALID");
  }
  return { schemaVersion: 1, files, totalBytes, sha256: digest };
}

function sameManifest(left: ArtifactManifest, right: ArtifactManifest): boolean {
  return left.sha256 === right.sha256 && left.totalBytes === right.totalBytes && JSON.stringify(left.files) === JSON.stringify(right.files);
}

function parseArtifactLimits(value: unknown): ArtifactLimits | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const input = value as Record<string, unknown>;
  const limits: ArtifactLimits = {
    maxFiles: input.maxFiles as number,
    maxFileBytes: input.maxFileBytes as number,
    maxTrialBytes: input.maxTrialBytes as number,
    graderResultMaxBytes: input.graderResultMaxBytes as number,
    toolEvidenceMaxBytes: (input.toolEvidenceMaxBytes as number | undefined) ?? defaultArtifactLimits.toolEvidenceMaxBytes,
  };
  if (Object.values(limits).some(limit => !Number.isSafeInteger(limit) || limit <= 0 || limit > 2_147_483_647)) return null;
  return limits;
}

async function readExperiment(trialDirectory: string): Promise<Record<string, unknown>> {
  return object(await readJson(join(dirname(trialDirectory), "experiment.json"), MAX_TRIAL_JSON_BYTES));
}

function isWithin(parent: string, target: string): boolean {
  const fromParent = relative(parent, target);
  return fromParent === "" || (fromParent !== ".." && !fromParent.startsWith(`..${sep}`) && !isAbsolute(fromParent));
}

async function latestScoreRun(trialDirectory: string, record: TrialRecord, manifest: ArtifactManifest): Promise<Record<string, unknown> | null> {
  const directory = join(trialDirectory, "score-runs");
  const info = await lstat(directory).catch(() => null);
  if (!info) return null;
  if (!info.isDirectory() || info.isSymbolicLink()) throw new Error("SCORE_RUN_DIRECTORY_INVALID");
  const entries = await readdir(directory, { withFileTypes: true });
  const runs: Array<{ id: string; createdAt: string; score: Record<string, unknown> }> = [];
  for (const entry of entries) {
    if (entry.name.startsWith(".pending-")) throw new Error("SCORE_RUN_INCOMPLETE");
    if (!entry.isDirectory()) throw new Error("SCORE_RUN_ENTRY_INVALID");
    const runPath = join(directory, entry.name);
    const runInfo = await lstat(runPath);
    if (runInfo.isSymbolicLink()) throw new Error("SCORE_RUN_ENTRY_INVALID");
    const score = object(await readJson(join(runPath, "score.json"), MAX_SCORE_JSON_BYTES));
    if (score.schemaVersion !== 1 || score.scoreRunId !== entry.name || score.trialId !== record.id || score.caseId !== record.caseId ||
        typeof score.createdAt !== "string" || !Number.isFinite(Date.parse(score.createdAt)) || !validEvaluation(score.evaluation)) {
      throw new Error("SCORE_RUN_INVALID");
    }
    const submission = object(score.submission);
    if (submission.artifactManifestSha256 !== manifest.sha256) throw new Error("SCORE_RUN_SNAPSHOT_MISMATCH");
    runs.push({ id: entry.name, createdAt: score.createdAt, score });
  }
  runs.sort((left, right) => left.createdAt.localeCompare(right.createdAt) || left.id.localeCompare(right.id));
  return runs.at(-1)?.score ?? null;
}

async function writeAtomic(path: string, content: string): Promise<void> {
  const temporary = `${path}.${randomUUID()}.tmp`;
  let created = false;
  try {
    const handle = await open(temporary, "wx");
    created = true;
    try { await handle.writeFile(content, "utf8"); }
    finally { await handle.close(); }
    await rename(temporary, path);
  } catch (error) {
    if (created) {
      try { await rm(temporary, { force: true }); }
      catch { throw new Error("REPORT_TEMP_CLEANUP_FAILED"); }
    }
    throw error;
  }
}

/**
 * Loads every recorded trial of a run with its latest append-only score run applied. Trials that a
 * resumed batch replaced (named by a later record's `supersedes`) are left out but stay on disk.
 */
export async function loadRecordedTrials(runDirectory: string): Promise<TrialRecord[]> {
  const root = resolve(runDirectory);
  const rootInfo = await lstat(root).catch(() => null);
  if (!rootInfo?.isDirectory() || rootInfo.isSymbolicLink()) throw new Error("RUN_DIRECTORY_INVALID");
  const trials: TrialRecord[] = [];
  for (const entry of await readdir(root, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const trialDirectory = join(root, entry.name);
    const trialInfo = await lstat(trialDirectory);
    if (trialInfo.isSymbolicLink()) throw new Error("TRIAL_DIRECTORY_INVALID");
    if (!(await lstat(join(trialDirectory, "result.json")).catch(() => null))) continue;
    // Trials that stopped before artifact export have no manifest and therefore no score runs.
    if (!(await lstat(join(trialDirectory, "artifact-manifest.json")).catch(() => null))) {
      trials.push((await loadTrialRecord(trialDirectory)).record);
      continue;
    }
    const { record, manifest } = await loadTrial(trialDirectory);
    const latest = await latestScoreRun(trialDirectory, record, manifest);
    if (latest) {
      record.evaluation = latest.evaluation as EvaluationResult;
      record.scoreRunId = String(latest.scoreRunId);
    }
    trials.push(record);
  }
  const superseded = new Set(trials.flatMap(trial => trial.supersedes ? [trial.supersedes] : []));
  return trials.filter(trial => !superseded.has(trial.id)).sort((left, right) => left.id.localeCompare(right.id));
}

/** Rebuilds materialized reports from immutable trial records and append-only score runs. */
export async function rebuildReports(runDirectory: string): Promise<unknown> {
  const root = resolve(runDirectory);
  const experiment = object(await readJson(join(root, "experiment.json"), MAX_TRIAL_JSON_BYTES));
  const trials = await loadRecordedTrials(root);
  const oldReportInfo = await lstat(join(root, "report.json")).catch(() => null);
  const oldReport = oldReportInfo?.isFile() ? object(await readJson(join(root, "report.json"), MAX_TRIAL_JSON_BYTES)) : {};
  const modelCount = Array.isArray(experiment.models) ? experiment.models.length : 0;
  const plannedRuns = typeof experiment.plannedRuns === "number" && Number.isSafeInteger(experiment.plannedRuns)
    ? experiment.plannedRuns
    : (typeof oldReport.plannedRuns === "number" ? oldReport.plannedRuns : modelCount * (Array.isArray(experiment.caseIds) ? experiment.caseIds.length : 0));
  const completed = typeof oldReport.completed === "boolean" && experiment.plannedRuns === undefined
    ? oldReport.completed
    : trials.length >= plannedRuns;
  const byModel = new Map<string, TrialRecord[]>();
  for (const trial of trials) {
    const key = `${trial.model.provider}:${trial.model.id}`;
    const group = byModel.get(key) ?? [];
    group.push(trial);
    byModel.set(key, group);
  }
  const report = {
    version: 1,
    plannedRuns,
    recordedRuns: trials.length,
    completed,
    scoreRunPolicy: "latest-append-only-score-run-per-trial",
    ...(oldReport.batch !== undefined ? { batch: oldReport.batch } : {}),
    records: trials,
    summary: summarize(trials),
    byModel: [...byModel.entries()].sort(([left], [right]) => left.localeCompare(right))
      .map(([, records]) => ({ model: records[0]!.model, summary: summarize(records) })),
  };
  await writeAtomic(join(root, "report.json"), JSON.stringify(report, null, 2));
  await writeAtomic(join(root, "report.md"), markdownReport(trials));
  return report;
}

/** Resolves the plan case and pinned task package of a recorded trial and checks they still match the run. */
async function trialTaskPackage(directory: string, record: TrialRecord, plan: EvaluationPlan):
  Promise<{ item: EvaluationPlan["cases"][number]; descriptor: PackageDescriptor & { manifest: NonNullable<PackageDescriptor["manifest"]> } }> {
  const item = plan.cases.find(candidate => candidate.id === record.caseId);
  if (!item || item.evaluator.kind !== "task-package" || !item.packagePath) throw new Error("REGRADE_TASK_PACKAGE_REQUIRED");
  const descriptor = (await preflightPlan(plan)).get(item.id);
  if (!descriptor?.manifest || !descriptor.manifestSha256) throw new Error("REGRADE_TASK_PACKAGE_INVALID");
  if (record.packageManifest?.version !== descriptor.manifest.version) throw new Error("REGRADE_TASK_VERSION_MISMATCH");

  const experiment = await readExperiment(directory);
  const fingerprints = Array.isArray(experiment.packageFingerprints) ? experiment.packageFingerprints : [];
  const originalPackage = fingerprints.find(value => value && typeof value === "object" && !Array.isArray(value) &&
    (value as Record<string, unknown>).caseId === record.caseId) as Record<string, unknown> | undefined;
  if (!originalPackage || originalPackage.id !== descriptor.manifest.id || originalPackage.version !== descriptor.manifest.version) {
    throw new Error("REGRADE_TASK_IDENTITY_MISMATCH");
  }
  return { item, descriptor: descriptor as PackageDescriptor & { manifest: NonNullable<PackageDescriptor["manifest"]> } };
}

/** Appends a new grading result for the exact frozen submission, without rerunning the model. */
export async function regradeTrial(trialDirectory: string, plan: EvaluationPlan, reason: string): Promise<{ scoreRunId: string; evaluation: EvaluationResult; runDirectory: string }> {
  validatePlan(plan);
  if (typeof reason !== "string" || !reason.trim() || reason.length > 500) throw new Error("REGRADE_REASON_REQUIRED");
  const { directory, record, manifest } = await loadTrial(trialDirectory);
  if (record.execution.status !== "done") throw new Error("REGRADE_EXECUTION_INCOMPLETE");
  const { item, descriptor } = await trialTaskPackage(directory, record, plan);

  const limits = plan.artifactLimits ?? { ...defaultArtifactLimits };
  const artifactDirectory = join(directory, "artifacts");
  const verificationRoot = await mkdtemp(join(tmpdir(), "agent-eval-regrade-"));
  const verifiedSnapshot = join(verificationRoot, "submission");
  const scoreRunsDirectory = join(directory, "score-runs");
  const scoreRunId = randomUUID();
  const pendingDirectory = join(scoreRunsDirectory, `.pending-${scoreRunId}`);
  const finalDirectory = join(scoreRunsDirectory, scoreRunId);
  let appended = false;
  let pendingCreated = false;
  let cleanupFailed = false;
  try {
    const verifiedManifest = await copyArtifacts(artifactDirectory, verifiedSnapshot, limits);
    if (!sameManifest(verifiedManifest, manifest)) throw new Error("REGRADE_SNAPSHOT_HASH_MISMATCH");
    await mkdir(scoreRunsDirectory, { recursive: true });
    const previous = await latestScoreRun(directory, record, manifest);
    const previousId = previous?.scoreRunId ?? record.scoreRunId ?? null;
    const previousTime = previous && typeof previous.createdAt === "string" ? Date.parse(previous.createdAt) : 0;
    const createdAt = new Date(Math.max(Date.now(), previousTime + 1)).toISOString();
    await mkdir(pendingDirectory);
    pendingCreated = true;
    let evaluation: EvaluationResult;
    try {
      evaluation = await evaluate(item, record.execution, "", verifiedSnapshot, limits, {
        trialId: record.id,
        scoreRunDirectory: pendingDirectory,
        packageDescriptor: descriptor,
        submissionManifest: verifiedManifest,
        isolation: plan.isolation,
      });
    } catch {
      evaluation = { status: "error", score: null, checks: [], error: "REGRADE_EVALUATOR_FAILED" };
    }
    await writeFile(join(pendingDirectory, "score.json"), JSON.stringify({
      schemaVersion: 1,
      scoreRunId,
      trialId: record.id,
      caseId: record.caseId,
      createdAt,
      reason: reason.trim(),
      previousScoreRunId: previousId,
      submission: { snapshotPath: "../../artifacts", artifactManifestSha256: manifest.sha256 },
      scorer: {
        kind: item.evaluator.kind,
        taskId: descriptor.manifest.id,
        taskVersion: descriptor.manifest.version,
        taskManifestSha256: descriptor.manifestSha256,
        graderId: descriptor.manifest.grader.id,
        graderVersion: descriptor.manifest.grader.version,
      },
      evaluation,
    }, null, 2), { encoding: "utf8", flag: "wx" });
    await rename(pendingDirectory, finalDirectory);
    appended = true;
    await rebuildReports(dirname(directory));
    return { scoreRunId, evaluation, runDirectory: dirname(directory) };
  } finally {
    try { await rm(verificationRoot, { recursive: true, force: true }); }
    catch { cleanupFailed = true; }
    if (!appended && pendingCreated) {
      try { await rm(pendingDirectory, { recursive: true, force: true }); }
      catch { cleanupFailed = true; }
    }
    if (cleanupFailed) throw new Error("REGRADE_CLEANUP_FAILED");
  }
}

/** Restores the manifest-verified artifact snapshot into a new, caller-selected directory. */
export async function restoreTrialSnapshot(trialDirectory: string, destinationPath: string): Promise<{ destination: string; sha256: string }> {
  if (typeof destinationPath !== "string" || !destinationPath.trim()) throw new Error("RESTORE_DESTINATION_REQUIRED");
  const { directory, manifest } = await loadTrial(trialDirectory);
  const destination = resolve(destinationPath);
  const trialRoot = await realpath(dirname(directory));
  if (isWithin(trialRoot, destination)) throw new Error("RESTORE_DESTINATION_INSIDE_RUN");
  const parent = dirname(destination);
  await mkdir(parent, { recursive: true });
  const resolvedParent = await realpath(parent);
  const resolvedDestination = resolve(resolvedParent, basename(destination));
  if (isWithin(trialRoot, resolvedDestination)) throw new Error("RESTORE_DESTINATION_INSIDE_RUN");
  if (await lstat(resolvedDestination).catch(() => null)) throw new Error("RESTORE_DESTINATION_EXISTS");

  const experiment = await readExperiment(directory);
  const limits = parseArtifactLimits(experiment.artifactLimits) ?? {
      maxFiles: Math.max(1, manifest.files.length),
      maxFileBytes: Math.max(1, ...manifest.files.map(file => file.sizeBytes)),
      maxTrialBytes: Math.max(1, manifest.totalBytes),
      graderResultMaxBytes: defaultArtifactLimits.graderResultMaxBytes,
      toolEvidenceMaxBytes: defaultArtifactLimits.toolEvidenceMaxBytes,
    };
  const stage = await mkdtemp(join(resolvedParent, ".agent-eval-restore-"));
  let restored = false;
  try {
    const copied = await copyArtifacts(join(directory, "artifacts"), stage, limits);
    if (!sameManifest(copied, manifest)) throw new Error("RESTORE_SNAPSHOT_HASH_MISMATCH");
    if (await lstat(resolvedDestination).catch(() => null)) throw new Error("RESTORE_DESTINATION_EXISTS");
    await rename(stage, resolvedDestination);
    restored = true;
    return { destination: resolvedDestination, sha256: copied.sha256 };
  } finally {
    if (!restored) {
      const stageInfo = await lstat(stage).catch(() => null);
      const actualParent = await realpath(dirname(stage)).catch(() => "");
      if (stageInfo?.isDirectory() && !stageInfo.isSymbolicLink() && actualParent === resolvedParent && basename(stage).startsWith(".agent-eval-restore-")) {
        await rm(stage, { recursive: true, force: true });
      }
    }
  }
}

interface HumanReviewFile {
  schemaVersion: 1;
  reviewer: string;
  checks: Array<{ id: string; status: "pass" | "fail"; note?: string }>;
}

function parseReviewFile(value: unknown): HumanReviewFile {
  const review = object(value);
  if (review.schemaVersion !== 1 || typeof review.reviewer !== "string" || !review.reviewer.trim() || review.reviewer.length > 200 ||
      !Array.isArray(review.checks) || review.checks.length === 0) throw new Error("REVIEW_FILE_INVALID");
  const seen = new Set<string>();
  const checks = review.checks.map(raw => {
    const check = object(raw);
    if (typeof check.id !== "string" || seen.has(check.id) || (check.status !== "pass" && check.status !== "fail") ||
        (check.note !== undefined && (typeof check.note !== "string" || check.note.length > 2_000))) throw new Error("REVIEW_FILE_INVALID");
    seen.add(check.id);
    return { id: check.id, status: check.status, ...(check.note !== undefined ? { note: check.note as string } : {}) };
  });
  return { schemaVersion: 1, reviewer: review.reviewer.trim(), checks: checks as HumanReviewFile["checks"] };
}

/**
 * Records human judgments for pending non-critical checks as a new append-only score run.
 * The objective verdict, the original trial record and earlier score runs stay unchanged.
 */
export async function importHumanReview(trialDirectory: string, plan: EvaluationPlan, reviewPath: string, reason: string):
  Promise<{ scoreRunId: string; evaluation: EvaluationResult; runDirectory: string }> {
  validatePlan(plan);
  if (typeof reason !== "string" || !reason.trim() || reason.length > 500) throw new Error("REVIEW_REASON_REQUIRED");
  const { directory, record, manifest } = await loadTrial(trialDirectory);
  const { item, descriptor } = await trialTaskPackage(directory, record, plan);
  const review = parseReviewFile(await readJson(resolve(reviewPath), MAX_SCORE_JSON_BYTES));

  const latest = await latestScoreRun(directory, record, manifest);
  if (!latest) throw new Error("REVIEW_SCORE_RUN_REQUIRED");
  const previous = latest.evaluation as EvaluationResult;
  const pending = new Set(previous.review?.status === "pending" ? previous.review.pendingCheckIds : []);
  if (pending.size === 0) throw new Error("REVIEW_NOT_PENDING");
  // Only checks the grader left pending can be reviewed; pending checks are never critical.
  if (!review.checks.every(check => pending.has(check.id))) throw new Error("REVIEW_CHECK_NOT_PENDING");

  const judged = new Map(review.checks.map(check => [check.id, check.status === "pass"]));
  const remaining = [...pending].filter(id => !judged.has(id));
  const evaluation: EvaluationResult = {
    ...previous,
    checks: previous.checks.map(check => judged.has(check.id) ? { id: check.id, passed: judged.get(check.id)! } : check),
    review: { status: remaining.length ? "pending" : "complete", pendingCheckIds: remaining, reason: remaining.length ? previous.review!.reason : null },
  };

  const scoreRunsDirectory = join(directory, "score-runs");
  const scoreRunId = randomUUID();
  const pendingDirectory = join(scoreRunsDirectory, `.pending-${scoreRunId}`);
  const previousTime = typeof latest.createdAt === "string" ? Date.parse(latest.createdAt) : 0;
  let appended = false;
  try {
    await mkdir(pendingDirectory);
    await writeFile(join(pendingDirectory, "review.json"), JSON.stringify(review, null, 2), { encoding: "utf8", flag: "wx" });
    await writeFile(join(pendingDirectory, "score.json"), JSON.stringify({
      schemaVersion: 1,
      scoreRunId,
      trialId: record.id,
      caseId: record.caseId,
      createdAt: new Date(Math.max(Date.now(), previousTime + 1)).toISOString(),
      reason: reason.trim(),
      previousScoreRunId: latest.scoreRunId ?? null,
      submission: { snapshotPath: "../../artifacts", artifactManifestSha256: manifest.sha256 },
      scorer: {
        kind: "human-review",
        reviewer: review.reviewer,
        taskId: descriptor.manifest.id,
        taskVersion: descriptor.manifest.version,
        taskManifestSha256: descriptor.manifestSha256,
        caseEvaluator: item.evaluator.kind,
      },
      evaluation,
    }, null, 2), { encoding: "utf8", flag: "wx" });
    await rename(pendingDirectory, join(scoreRunsDirectory, scoreRunId));
    appended = true;
  } finally {
    if (!appended) await rm(pendingDirectory, { recursive: true, force: true });
  }
  await rebuildReports(dirname(directory));
  return { scoreRunId, evaluation, runDirectory: dirname(directory) };
}
