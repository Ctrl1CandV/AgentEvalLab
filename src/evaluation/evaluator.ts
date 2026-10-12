import { copyArtifacts } from "./artifacts.js";
import { command, git } from "../command.js";
import type { ExecutionResult } from "../types.js";
import type { EvaluationCase, EvaluationResult } from "./types.js";
import { prepareWorkspace } from "./workspace.js";
import type { ArtifactLimits } from "./types.js";
import type { ArtifactManifest } from "./types.js";
import type { PackageDescriptor } from "./manifest.js";
import { runTaskGrader } from "./grader.js";
import type { EventSink } from "../types.js";

export class EvaluatorCleanupError extends Error {}

export interface EvaluationContext {
  trialId: string;
  scoreRunDirectory: string;
  packageDescriptor: PackageDescriptor | null;
  submissionManifest: ArtifactManifest | null;
  answerText?: string;
  tracePath?: string;
  emit?: EventSink;
}

export const skippedEvaluation = (): EvaluationResult => ({
  status: "skipped", score: null, checks: [], error: "EXECUTION_INCOMPLETE",
});

export async function evaluate(
  item: EvaluationCase,
  execution: ExecutionResult,
  patch: string,
  artifacts?: string,
  artifactLimits?: ArtifactLimits,
  context?: EvaluationContext,
): Promise<EvaluationResult> {
  if (execution.status !== "done") return skippedEvaluation();
  const spec = item.evaluator;
  if (spec.kind === "exact-match") {
    const passed = execution.output.trim() === spec.expected.trim();
    return { status: passed ? "passed" : "failed", score: Number(passed), checks: [], error: null };
  }
  if (spec.kind === "human") {
    return { status: "pending", score: null, checks: [], error: null };
  }
  if (spec.kind === "task-package") {
    if (!context?.packageDescriptor || !context.submissionManifest || !artifacts) {
      return { status: "error", score: null, checks: [], error: "TASK_GRADER_INPUT_MISSING" };
    }
    return runTaskGrader({
      trialId: context.trialId,
      scoreRunDirectory: context.scoreRunDirectory,
      submissionDirectory: artifacts,
      submissionManifest: context.submissionManifest,
      packageDescriptor: context.packageDescriptor,
      maxOutputBytes: spec.maxOutputBytes ?? artifactLimits?.graderResultMaxBytes ?? 1_000_000,
      resultMaxBytes: artifactLimits?.graderResultMaxBytes ?? 1_000_000,
      timeoutMs: spec.timeoutMs ?? 30_000,
      answerText: context.answerText,
      tracePath: context.tracePath,
    });
  }
  const workspace = await prepareWorkspace(item.repository);
  try {
    if (!item.repository && artifacts) await copyArtifacts(artifacts, workspace.path, artifactLimits);
    if (patch) await git(workspace.path, ["apply", "--binary", "--whitespace=nowarn", "-"], patch);
    const checks: EvaluationResult["checks"] = [];
    for (const check of spec.checks) {
      const result = await command(check.executable, check.args, workspace.path, spec.timeoutMs ?? 10_000);
      if (result.status !== "completed" || result.exitCode === null) {
        return { status: "error", score: null, checks, error: "CHECK_EXECUTION_FAILED" };
      }
      checks.push({ id: check.id, passed: result.exitCode === 0 });
    }
    const passed = checks.every(check => check.passed);
    return { status: passed ? "passed" : "failed", score: Number(passed), checks, error: null };
  } finally {
    try { await workspace.cleanup(); }
    catch { throw new EvaluatorCleanupError("EVALUATOR_CLEANUP_FAILED"); }
  }
}
