import { lstat, mkdir, readFile, realpath, writeFile } from "node:fs/promises";
import { copyFile } from "node:fs/promises";
import { isAbsolute, join, relative, resolve, sep } from "node:path";
import { command } from "../command.js";
import { redact } from "../privacy.js";
import { hostEnvironment, sandboxLauncher, type Isolation, type RuntimeMounts } from "../sandbox.js";
import type { ArtifactManifest, EvaluationResult } from "./types.js";
import { runtimeMounts, type ManifestScoring, type PackageDescriptor, type TaskPackageManifest } from "./manifest.js";

interface GraderRequest {
  schemaVersion: 1;
  requestId: string;
  trialId: string;
  task: { id: string; version: string; manifestSha256: string };
  submission: { snapshotId: string; directory: string; manifestSha256: string };
  answerRef: string | null;
  traceRef: string | null;
  /** itemId is present only for packages with generated items, so earlier graders see an unchanged context. */
  context: { stageId: string | null; cycleId: string | null; itemId?: string; activeRequirementIds: string[] };
  evidenceRoot: string;
  /** Launcher graders must prefix to every candidate command; null when the plan opted into host execution. */
  sandbox: { launcher: string } | null;
  /** Present only for a repository item: the delivered change, under the evidence root. */
  patchRef?: string;
  /**
   * Present only when the package declares runtime mounts: what graders bind into candidate commands (`--mount
   * source:target`) and the environment to set (`--env`), as execute_command does.
   */
  runtime?: RuntimeMounts;
}

interface ValidatedGraderResult {
  gradingStatus: "completed" | "unscored" | "error";
  /** Raw values a v2 grader reports (CODE §3.2); empty for a v1 grader. */
  metrics: Array<{ id: string; value: number; unit?: string }>;
  checks: Array<{ id: string; passed: boolean }>;
  dimensions: Array<{ id: string; value: number; minimum: number; maximum: number; reason: string }>;
  missingCheckIds: string[];
  reason: string | null;
  errorCode: string | null;
}

export interface TaskGraderInput {
  trialId: string;
  scoreRunDirectory: string;
  submissionDirectory: string;
  submissionManifest: ArtifactManifest;
  packageDescriptor: PackageDescriptor;
  maxOutputBytes: number;
  resultMaxBytes: number;
  timeoutMs: number;
  answerText?: string;
  tracePath?: string;
  context?: { stageId: string | null; cycleId: string | null; itemId?: string; activeRequirementIds: string[] };
  isolation?: Isolation;
  /** A repository item's delivered change (CODE §5), handed to the grader as `patchRef`. */
  patchText?: string;
}

function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("GRADER_PROTOCOL_INVALID");
  return value as Record<string, unknown>;
}

function hasExactKeys(value: Record<string, unknown>, expected: readonly string[]): boolean {
  const actual = Object.keys(value).sort();
  return actual.length === expected.length && actual.every((key, index) => key === [...expected].sort()[index]);
}

function isIdentifier(value: unknown): value is string {
  return typeof value === "string" && /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(value);
}

function safeMessage(value: unknown): string {
  if (typeof value !== "string" || !value.trim() || value.length > 2_000) throw new Error("GRADER_PROTOCOL_INVALID");
  return redact(value);
}

async function assertEvidenceReference(evidenceRoot: string, reference: string): Promise<void> {
  if (!reference || reference.includes("\\") || reference.includes("\0") || isAbsolute(reference) || /^[A-Za-z]:/.test(reference)) {
    throw new Error("GRADER_EVIDENCE_PATH_INVALID");
  }
  const segments = reference.split("/");
  if (segments.some(segment => !segment || segment === "." || segment === ".." || segment.includes(":"))) {
    throw new Error("GRADER_EVIDENCE_PATH_INVALID");
  }
  const root = await realpath(evidenceRoot);
  const target = resolve(root, ...segments);
  const pathFromRoot = relative(root, target);
  if (!pathFromRoot || pathFromRoot === ".." || pathFromRoot.startsWith(`..${sep}`) || isAbsolute(pathFromRoot)) {
    throw new Error("GRADER_EVIDENCE_PATH_INVALID");
  }
  let current = root;
  for (const [index, segment] of segments.entries()) {
    current = join(current, segment);
    const info = await lstat(current).catch(() => null);
    if (!info || info.isSymbolicLink()) throw new Error("GRADER_EVIDENCE_MISSING");
    if (index < segments.length - 1 && !info.isDirectory()) throw new Error("GRADER_EVIDENCE_MISSING");
    if (index === segments.length - 1 && !info.isFile()) throw new Error("GRADER_EVIDENCE_MISSING");
  }
}

function expandArguments(
  manifest: TaskPackageManifest,
  values: { entryPoint: string; request: string; result: string; submission: string; evidence: string },
): string[] {
  const placeholders = new Map<string, string>([
    ["{entryPoint}", values.entryPoint],
    ["{request}", values.request],
    ["{result}", values.result],
    ["{submission}", values.submission],
    ["{evidence}", values.evidence],
  ]);
  return manifest.grader.args.map(argument => {
    let expanded = argument;
    for (const [placeholder, replacement] of placeholders) expanded = expanded.split(placeholder).join(replacement);
    if (expanded.includes("{") || expanded.includes("}")) throw new Error("GRADER_ARGUMENT_TEMPLATE_INVALID");
    return expanded;
  });
}

function expectedCheckOwners(manifest: TaskPackageManifest, activeRequirementIds: string[]): Map<string, string> {
  const owners = new Map<string, string>();
  const active = new Set(activeRequirementIds);
  for (const requirement of manifest.requirements.filter(item => active.has(item.id))) {
    for (const checkId of requirement.checkIds) owners.set(checkId, requirement.id);
  }
  return owners;
}

async function validateEvidenceRefs(value: unknown, evidenceRoot: string): Promise<string[]> {
  if (!Array.isArray(value) || !value.every(reference => typeof reference === "string")) throw new Error("GRADER_PROTOCOL_INVALID");
  const references = value as string[];
  for (const reference of references) await assertEvidenceReference(evidenceRoot, reference);
  return references;
}

async function validateGraderResult(
  value: unknown,
  request: GraderRequest,
  manifest: TaskPackageManifest,
  evidenceRoot: string,
): Promise<ValidatedGraderResult> {
  const result = object(value);
  const v1Keys = ["schemaVersion", "requestId", "taskId", "taskVersion", "graderVersion", "gradingStatus", "checks", "dimensions", "unscoredCheckIds", "reason", "error"];
  if (!hasExactKeys(result, result.schemaVersion === 2 ? [...v1Keys, "metrics"] : v1Keys)) throw new Error("GRADER_PROTOCOL_INVALID");
  if ((result.schemaVersion !== 1 && result.schemaVersion !== 2) || result.requestId !== request.requestId || result.taskId !== manifest.id ||
      result.taskVersion !== manifest.version || result.graderVersion !== manifest.grader.version) {
    throw new Error("GRADER_RESULT_IDENTITY_MISMATCH");
  }
  if (!["completed", "unscored", "error"].includes(String(result.gradingStatus)) || !Array.isArray(result.checks) ||
      !Array.isArray(result.dimensions) || !Array.isArray(result.unscoredCheckIds)) throw new Error("GRADER_PROTOCOL_INVALID");

  if (result.gradingStatus === "error") {
    const error = object(result.error);
    if (!hasExactKeys(error, ["code", "phase"]) || !isIdentifier(error.code) || !isIdentifier(error.phase) ||
        result.reason !== null || result.checks.length > 0 || result.dimensions.length > 0 ||
        result.unscoredCheckIds.length > 0) throw new Error("GRADER_ERROR_INVALID");
    return { gradingStatus: "error", metrics: [], checks: [], dimensions: [], missingCheckIds: [], reason: null, errorCode: "GRADER_REPORTED_ERROR" };
  }

  const owners = expectedCheckOwners(manifest, request.context.activeRequirementIds);
  const checks: ValidatedGraderResult["checks"] = [];
  const seen = new Set<string>();
  for (const checkValue of result.checks) {
    const check = object(checkValue);
    if (!hasExactKeys(check, ["id", "requirementId", "status", "evidenceRefs"]) ||
        !isIdentifier(check.id) || seen.has(check.id) || owners.get(check.id) !== check.requirementId ||
        !["pass", "fail"].includes(String(check.status))) throw new Error("GRADER_CHECK_INVALID");
    await validateEvidenceRefs(check.evidenceRefs, evidenceRoot);
    seen.add(check.id);
    checks.push({ id: check.id, passed: check.status === "pass" });
  }

  const missing = [...owners.keys()].filter(id => !seen.has(id)).sort();
  const reportedMissing = result.unscoredCheckIds;
  if (!reportedMissing.every(isIdentifier) || new Set(reportedMissing).size !== reportedMissing.length ||
      [...reportedMissing].sort().join("\n") !== missing.join("\n")) throw new Error("GRADER_MISSING_CHECKS_INVALID");
  if (result.gradingStatus === "completed" && missing.length > 0) throw new Error("GRADER_COMPLETED_WITH_MISSING_CHECKS");
  if (result.gradingStatus === "unscored" && missing.length === 0) throw new Error("GRADER_UNSCORED_WITHOUT_MISSING_CHECKS");

  const dimensions: ValidatedGraderResult["dimensions"] = [];
  const dimensionIds = new Set<string>();
  for (const dimensionValue of result.dimensions) {
    const dimension = object(dimensionValue);
    const scale = object(dimension.scale);
    const registeredScale = manifest.dimensions?.find(candidate => candidate.id === dimension.id);
    if (!hasExactKeys(dimension, ["id", "value", "scale", "evidenceRefs", "reason"]) ||
        !hasExactKeys(scale, ["minimum", "maximum"]) ||
        !isIdentifier(dimension.id) || dimensionIds.has(dimension.id) || typeof dimension.value !== "number" || !Number.isFinite(dimension.value) ||
        typeof scale.minimum !== "number" || !Number.isFinite(scale.minimum) || typeof scale.maximum !== "number" || !Number.isFinite(scale.maximum) ||
        !registeredScale || scale.minimum !== registeredScale.minimum || scale.maximum !== registeredScale.maximum ||
        scale.maximum <= scale.minimum || dimension.value < scale.minimum || dimension.value > scale.maximum) throw new Error("GRADER_DIMENSION_INVALID");
    await validateEvidenceRefs(dimension.evidenceRefs, evidenceRoot);
    dimensions.push({ id: dimension.id, value: dimension.value, minimum: scale.minimum, maximum: scale.maximum, reason: safeMessage(dimension.reason) });
    dimensionIds.add(dimension.id);
  }

  if (result.error !== null) throw new Error("GRADER_PROTOCOL_INVALID");
  const metrics = graderMetrics(result.schemaVersion === 2 ? result.metrics : [], manifest, result.gradingStatus === "completed", request.context.itemId ?? null);
  let reason: string | null = null;
  if (result.gradingStatus === "unscored") {
    const unscoredReason = object(result.reason);
    if (!hasExactKeys(unscoredReason, ["code", "message"]) || !isIdentifier(unscoredReason.code)) throw new Error("GRADER_REASON_INVALID");
    reason = safeMessage(unscoredReason.message);
  } else if (result.reason !== null) throw new Error("GRADER_PROTOCOL_INVALID");
  return { gradingStatus: result.gradingStatus as "completed" | "unscored", metrics, checks, dimensions, missingCheckIds: missing, reason, errorCode: null };
}

/**
 * The raw metrics of a v2 result: finite values under unique identifiers. Every metric the manifest's score model
 * names is required of a completed grading; others are kept as diagnostics.
 */
function graderMetrics(value: unknown, manifest: TaskPackageManifest, completed: boolean, itemId: string | null): ValidatedGraderResult["metrics"] {
  if (!Array.isArray(value)) throw new Error("GRADER_METRIC_INVALID");
  const metrics: ValidatedGraderResult["metrics"] = [];
  for (const raw of value) {
    const metric = object(raw);
    if (!(hasExactKeys(metric, ["id", "value"]) || hasExactKeys(metric, ["id", "value", "unit"])) || !isIdentifier(metric.id) ||
        metrics.some(entry => entry.id === metric.id) || typeof metric.value !== "number" || !Number.isFinite(metric.value) ||
        (metric.unit !== undefined && (typeof metric.unit !== "string" || metric.unit.length > 100))) throw new Error("GRADER_METRIC_INVALID");
    metrics.push({ id: metric.id, value: metric.value, ...(typeof metric.unit === "string" ? { unit: metric.unit } : {}) });
  }
  // A metric declared for some items only (E4's compress bytes) is required for those.
  const required = (manifest.scoreModel?.metrics ?? []).filter(metric => !metric.items || (itemId !== null && metric.items.includes(itemId)));
  if (completed && required.some(entry => !metrics.some(metric => metric.id === entry.id))) {
    throw new Error("GRADER_METRIC_MISSING");
  }
  return metrics;
}

function graderError(code: string): EvaluationResult {
  return { status: "error", score: null, checks: [], error: code };
}

/** Runs a pinned external grader with bounded process I/O and validates its result file. */
/**
 * Partial-credit trial score in [0, 1]: the weighted fraction of judged content checks that passed, reduced by the
 * format penalty when the format check failed. An answer that could not be parsed fails every content check, so it
 * scores 0 whatever the penalty. Null when no content check was judged.
 */
export function trialScore(checks: Array<{ id: string; passed: boolean | null }>, scoring: ManifestScoring | undefined): number | null {
  const content = checks.filter(check => check.passed !== null && check.id !== scoring?.formatCheckId);
  const weight = (id: string) => scoring?.weights?.[id] ?? 1;
  const total = content.reduce((sum, check) => sum + weight(check.id), 0);
  if (total === 0) return null;
  const passed = content.reduce((sum, check) => sum + (check.passed ? weight(check.id) : 0), 0);
  const formatFailed = scoring?.formatCheckId !== undefined && checks.some(check => check.id === scoring.formatCheckId && check.passed === false);
  return (passed / total) * (formatFailed ? 1 - (scoring?.formatPenalty ?? 0) : 1);
}

export async function runTaskGrader(input: TaskGraderInput): Promise<EvaluationResult> {
  const descriptor = input.packageDescriptor;
  const manifest = descriptor.manifest;
  const manifestSha256 = descriptor.manifestSha256;
  if (!manifest || !manifestSha256) return graderError("PACKAGE_MANIFEST_REQUIRED");

  try {
      const graderDirectory = join(input.scoreRunDirectory, "grader");
      const evidenceRoot = join(graderDirectory, "evidence");
      await mkdir(graderDirectory, { recursive: false });
      await mkdir(evidenceRoot, { recursive: false });
      let answerRef: string | null = null;
      if (manifest.grader.answerSource === "execution-output") {
        if (typeof input.answerText !== "string") return graderError("GRADER_ANSWER_MISSING");
        answerRef = "candidate-answer.txt";
        await writeFile(join(evidenceRoot, answerRef), input.answerText, { encoding: "utf8", flag: "wx" });
      }
      let traceRef: string | null = null;
      if (manifest.grader.requiresTrace) {
        if (!input.tracePath) return graderError("GRADER_TRACE_MISSING");
        const traceInfo = await lstat(input.tracePath).catch(() => null);
        if (!traceInfo?.isFile() || traceInfo.isSymbolicLink()) return graderError("GRADER_TRACE_INVALID");
        traceRef = "tool-trace.jsonl";
        await copyFile(input.tracePath, join(evidenceRoot, traceRef));
      }
      let patchRef: string | null = null;
      if (input.patchText !== undefined) {
        patchRef = "submission.patch";
        await writeFile(join(evidenceRoot, patchRef), input.patchText, { encoding: "utf8", flag: "wx" });
      }
      const requestId = `${input.trialId}.grader`;
    const context = input.context ?? { stageId: null, cycleId: null, activeRequirementIds: manifest.requirements.map(requirement => requirement.id) };
    const knownRequirements = new Set(manifest.requirements.map(requirement => requirement.id));
    if (!Array.isArray(context.activeRequirementIds) || context.activeRequirementIds.length === 0 ||
        new Set(context.activeRequirementIds).size !== context.activeRequirementIds.length ||
        !context.activeRequirementIds.every(id => knownRequirements.has(id)) ||
        (context.stageId !== null && !isIdentifier(context.stageId)) ||
        (context.cycleId !== null && !isIdentifier(context.cycleId)) ||
        (context.itemId !== undefined && !manifest.items?.some(item => item.id === context.itemId))) return graderError("GRADER_CONTEXT_INVALID");
    const request: GraderRequest = {
      schemaVersion: 1,
      requestId,
      trialId: input.trialId,
      task: { id: manifest.id, version: manifest.version, manifestSha256 },
      submission: { snapshotId: input.trialId, directory: input.submissionDirectory, manifestSha256: input.submissionManifest.sha256 },
        answerRef,
        traceRef,
      context,
      evidenceRoot,
      sandbox: (input.isolation ?? "sandbox") === "sandbox" ? { launcher: sandboxLauncher } : null,
    };
    if (patchRef) request.patchRef = patchRef;
    const runtime = runtimeMounts(descriptor, manifest.items?.find(item => item.id === context.itemId) ?? null);
    // Without the sandbox nothing is bound: the environment names the mounts' source directories.
    if (runtime) request.runtime = request.sandbox ? runtime : { mounts: runtime.mounts, env: hostEnvironment(runtime) };
    const requestPath = join(graderDirectory, "request.json");
    const resultPath = join(graderDirectory, "result.json");
    await writeFile(requestPath, JSON.stringify(request), { encoding: "utf8", flag: "wx" });
    const entryPoint = join(descriptor.root, ...manifest.grader.entryPoint.split("/"));
    const args = expandArguments(manifest, {
      entryPoint,
      request: requestPath,
      result: resultPath,
      submission: input.submissionDirectory,
      evidence: evidenceRoot,
    });
    const run = await command(manifest.grader.executable, args, graderDirectory, input.timeoutMs, input.maxOutputBytes);
    if (run.status !== "completed" || run.exitCode !== 0) return graderError("GRADER_EXECUTION_FAILED");

    const resultInfo = await lstat(resultPath).catch(() => null);
    if (!resultInfo?.isFile() || resultInfo.isSymbolicLink()) return graderError("GRADER_RESULT_MISSING");
    if (resultInfo.size > input.resultMaxBytes) return graderError("GRADER_RESULT_TOO_LARGE");
    let parsedResult: unknown;
    try { parsedResult = JSON.parse(await readFile(resultPath, "utf8")) as unknown; }
    catch { return graderError("GRADER_RESULT_INVALID_JSON"); }

    let validated: ValidatedGraderResult;
    try { validated = await validateGraderResult(parsedResult, request, manifest, evidenceRoot); }
    catch (error) {
      const code = error instanceof Error && /^[A-Z0-9_]+$/.test(error.message) ? error.message : "GRADER_PROTOCOL_INVALID";
      return graderError(code);
    }
    if (validated.gradingStatus === "error") return graderError(validated.errorCode ?? "GRADER_REPORTED_ERROR");
    const activeRequirements = new Set(context.activeRequirementIds);
    const criticalChecks = new Set(manifest.requirements.filter(requirement => requirement.critical && activeRequirements.has(requirement.id)).flatMap(requirement => requirement.checkIds));
    const knownCriticalFailure = validated.checks.some(check => criticalChecks.has(check.id) && !check.passed);
    const unknownCriticalCheck = validated.missingCheckIds.some(checkId => criticalChecks.has(checkId));
    // The objective verdict depends on critical checks only. Missing non-critical checks
    // (such as human-review items) leave the verdict intact and are reported as pending review.
    const status = knownCriticalFailure ? "failed" : unknownCriticalCheck ? "unscored" : "passed";
    const checks: EvaluationResult["checks"] = validated.checks.map(check => ({ id: check.id, passed: check.passed }));
    for (const checkId of validated.missingCheckIds) checks.push({ id: checkId, passed: null });
    const score = status === "unscored" ? null : trialScore(checks, manifest.scoring);
    const pendingCheckIds = validated.missingCheckIds.filter(checkId => !criticalChecks.has(checkId));
    const review = pendingCheckIds.length > 0 ? { status: "pending" as const, pendingCheckIds, reason: validated.reason } : undefined;
    return { status, score, checks, error: status === "unscored" ? validated.reason : null, ...(review ? { review } : {}),
      ...(validated.metrics.length ? { metrics: validated.metrics } : {}) };
  } catch {
    return graderError("GRADER_IO_FAILED");
  }
}
