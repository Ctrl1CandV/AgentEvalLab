import { appendFile, mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { createHash, randomUUID } from "node:crypto";
import type { AgentTool } from "@earendil-works/pi-agent-core";
import { command } from "../command.js";
import { createPiSession, type PiAgentSession } from "../harness/pi.js";
import { trajectoryBudgetStatement } from "../harness/budget-notice.js";
import { evaluationTools } from "../harness/profiles.js";
import { emptyExecution, type Budget, type EventSink, type ExecutionResult } from "../types.js";
import { persistedExecution, redact } from "../privacy.js";
import { guardEventSink, EventSinkError } from "../events.js";
import { ArtifactLimitError, copyArtifacts, defaultArtifactLimits, inspectArtifacts } from "./artifacts.js";
import { projectPackage, projectTrajectoryStage, type PackageDescriptor } from "./manifest.js";
import { prepareWorkspace } from "./workspace.js";
import { runTaskGrader } from "./grader.js";
import { preflightPlan } from "./preflight.js";
import { evaluatedCondition, sha256 } from "./condition.js";
import { BatchGuard, resolveBatchPolicy, type BatchPolicy, type NotRunEntry } from "./batch.js";
import { resolveBudgetNotice } from "./run.js";
import { sandboxLauncher, type Isolation } from "../sandbox.js";
import { providerSlotsFromEnvironment } from "./provider-slots.js";
import type { EvaluationOptions, EvaluationPlan, PublicCheckResult, TrajectoryMetrics, TrajectoryRecord, TrajectorySession, TrajectoryStageResult } from "./types.js";
import { modelLabel } from "./report.js";

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("PUBLIC_CHECK_PROTOCOL_INVALID");
  return value as Record<string, unknown>;
}

function exactKeys(value: Record<string, unknown>, expected: string[]): boolean {
  return JSON.stringify(Object.keys(value).sort()) === JSON.stringify([...expected].sort());
}

function safeIdentifier(value: unknown): value is string {
  return typeof value === "string" && /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(value);
}

function min(left: number, right: number): number { return Math.min(left, right); }

function remainingBudget(
  total: Budget,
  stage: Budget,
  aggregate: ExecutionResult,
  stageUsed: ExecutionResult,
  totalElapsedMs: number,
  stageElapsedMs: number,
  totalOutputChars: number,
  stageOutputChars: number,
): Budget | null {
  const timeoutMs = min(total.timeoutMs - totalElapsedMs, stage.timeoutMs - stageElapsedMs);
  const maxTurns = min(total.maxTurns - aggregate.turns, stage.maxTurns - stageUsed.turns);
  const maxModelCalls = min(total.maxModelCalls - aggregate.modelCalls, stage.maxModelCalls - stageUsed.modelCalls);
  const maxToolCalls = min(total.maxToolCalls - aggregate.toolCalls, stage.maxToolCalls - stageUsed.toolCalls);
  const maxOutputChars = min(total.maxOutputChars - totalOutputChars, stage.maxOutputChars - stageOutputChars);
  const maxToolResultChars = min(total.maxToolResultChars, stage.maxToolResultChars);
  if (timeoutMs < 1 || maxTurns < 1 || maxModelCalls < 1 || maxToolCalls < 0 || maxOutputChars < 1) return null;
  // Tokens: what the whole trajectory has left, capped by what the stage has left, when either limit is set.
  const tokenLimits = [
    ...(total.maxTrialTokens != null ? [total.maxTrialTokens - tokensOf(aggregate)] : []),
    ...(stage.maxTrialTokens != null ? [stage.maxTrialTokens - tokensOf(stageUsed)] : []),
  ];
  const maxTrialTokens = tokenLimits.length ? Math.min(...tokenLimits) : null;
  if (maxTrialTokens !== null && maxTrialTokens < 1) return null;
  return {
    ...(maxTrialTokens !== null ? { maxTrialTokens } : {}),
    timeoutMs: Math.floor(timeoutMs),
    maxTurns,
    maxModelCalls,
    maxToolCalls,
    maxOutputTokensPerCall: min(total.maxOutputTokensPerCall, stage.maxOutputTokensPerCall),
    maxOutputChars,
    maxToolResultChars,
  };
}

function tokensOf(result: ExecutionResult): number {
  return result.requestUsage.reduce((sum, request) => sum + (request.totalTokens ?? 0), 0);
}

function accumulate(target: ExecutionResult, next: ExecutionResult): void {
  const hadRequests = target.modelCalls > 0;
  target.durationMs += next.durationMs;
  target.modelCalls += next.modelCalls;
  target.toolCalls += next.toolCalls;
  target.toolAttempts += next.toolAttempts;
  target.toolIntercepts += next.toolIntercepts;
  target.toolExecutions += next.toolExecutions;
  target.turns += next.turns;
  target.toolEvidenceBytes += next.toolEvidenceBytes;
  target.toolEvidenceTruncated ||= next.toolEvidenceTruncated;
  target.requestUsage.push(...next.requestUsage);
  target.output = next.output;
  if (!hadRequests) target.reportedTokens = next.reportedTokens;
  else if (next.reportedTokens === null || target.reportedTokens === null) target.reportedTokens = null;
  else target.reportedTokens += next.reportedTokens;
  if (next.status !== "done") {
    target.status = next.status;
    target.failureKind = next.failureKind;
    target.error = next.error;
  }
}

function makeRunner(plan: EvaluationPlan, options: EvaluationOptions, model: EvaluationPlan["models"][number], trialId: string,
  toolProfile: string, artifactLimits: typeof defaultArtifactLimits, workspacePath: string, item: EvaluationPlan["cases"][number],
  batchPolicy: BatchPolicy): TrajectorySession {
  const createTools = (): AgentTool[] => plan.trustedLocalExecution ? evaluationTools(
    workspacePath,
    toolProfile as Parameters<typeof evaluationTools>[1],
    { readOnly: item.readOnly, execute: !item.readOnly, isolation: plan.isolation },
  ) : [];
  if (options.sessionFactory) return options.sessionFactory(model, trialId, toolProfile as Parameters<typeof evaluationTools>[1], createTools);
  const piSession: PiAgentSession = createPiSession(model, {
    trialId,
    interactionClass: item.interactionClass ?? "candidate",
    toolEvidenceMaxBytes: artifactLimits.toolEvidenceMaxBytes,
    toolProfile,
    maxRetries: batchPolicy.maxRetries,
    maxRetryDelayMs: batchPolicy.maxRetryDelayMs,
    createTools,
    ...(resolveBudgetNotice(plan) ? { budgetReminders: resolveBudgetNotice(plan)!.reminders, budgetScope: "stage" as const } : {}),
  });
  return piSession;
}

async function publicCheck(
  descriptor: PackageDescriptor,
  stageId: string,
  submission: string,
  timeoutMs: number,
  isolation: Isolation = "sandbox",
): Promise<PublicCheckResult> {
  const stage = descriptor.manifest?.stages?.find(candidate => candidate.id === stageId);
  if (!stage) throw new Error("PUBLIC_CHECK_STAGE_MISSING");
  const substitutions = new Map([
    ["{entryPoint}", join(descriptor.root, ...stage.publicChecker.entryPoint.split("/"))],
    ["{submission}", submission],
    // Checkers prefix candidate commands with this launcher; empty means host execution.
    ["{sandbox}", isolation === "sandbox" ? sandboxLauncher : ""],
  ]);
  const args = stage.publicChecker.args.map(argument => {
    let expanded = argument;
    for (const [placeholder, value] of substitutions) expanded = expanded.split(placeholder).join(value);
    if (expanded.includes("{") || expanded.includes("}")) throw new Error("PUBLIC_CHECK_ARGUMENT_INVALID");
    return expanded;
  });
  const result = await command(stage.publicChecker.executable, args, descriptor.root,
    min(stage.publicChecker.timeoutMs, timeoutMs), stage.publicChecker.maxOutputBytes);
  if (result.status === "timeout") throw new Error("PUBLIC_CHECK_TIMEOUT");
  if (result.status === "output_limit") throw new Error("PUBLIC_CHECK_OUTPUT_LIMIT");
  if (result.status === "error") throw new Error("PUBLIC_CHECK_SPAWN_FAILED");
  if (result.exitCode !== 0) throw new Error("PUBLIC_CHECK_NONZERO_EXIT");
  let value: unknown;
  try { value = JSON.parse(result.stdout) as unknown; }
  catch { throw new Error("PUBLIC_CHECK_RESULT_INVALID_JSON"); }
  const output = record(value);
  if (!exactKeys(output, ["schemaVersion", "stageId", "status", "checks"]) || output.schemaVersion !== 1 ||
      output.stageId !== stageId || !["passed", "failed"].includes(String(output.status)) || !Array.isArray(output.checks)) {
    throw new Error("PUBLIC_CHECK_PROTOCOL_INVALID");
  }
  const checks: PublicCheckResult["checks"] = [];
  const seen = new Set<string>();
  for (const raw of output.checks) {
    const check = record(raw);
    if (!exactKeys(check, ["id", "passed", "reasonCode", "feedback"]) || !safeIdentifier(check.id) || seen.has(check.id) ||
        typeof check.passed !== "boolean" || !safeIdentifier(check.reasonCode) || typeof check.feedback !== "string" ||
        check.feedback.length > 1_000 || /[\u0000-\u0008\u000b\u000c\u000e-\u001f]/.test(check.feedback)) {
      throw new Error("PUBLIC_CHECK_PROTOCOL_INVALID");
    }
    seen.add(check.id);
    checks.push({ id: check.id, passed: check.passed, reasonCode: check.reasonCode, feedback: redact(check.feedback) });
  }
  if (JSON.stringify([...seen].sort()) !== JSON.stringify([...stage.publicChecker.checkIds].sort()) || !checks.length) {
    throw new Error("PUBLIC_CHECK_SET_MISMATCH");
  }
  const status = checks.every(check => check.passed) ? "passed" : "failed";
  if (output.status !== status) throw new Error("PUBLIC_CHECK_STATUS_MISMATCH");
  return { schemaVersion: 1, stageId, status, checks };
}

function appendEvent(directory: string, sequence: { value: number }, runId: string): EventSink {
  return async (type, counts, details) => {
    const event = { sequence: ++sequence.value, at: new Date().toISOString(), runId, type, counts, ...(details ? { details } : {}) };
    await appendFile(join(directory, "events.jsonl"), `${JSON.stringify(event)}\n`, "utf8");
    if (type === "tool_trace" && details) await appendFile(join(directory, "tool-trace.jsonl"), `${JSON.stringify(details)}\n`, "utf8");
  };
}

function toBudgetUsed(result: ExecutionResult, elapsedMs: number) {
  return { timeoutMs: Math.ceil(elapsedMs), maxTurns: result.turns, maxModelCalls: result.modelCalls, maxToolCalls: result.toolCalls };
}

function requirementStatus(grade: TrajectoryStageResult["cycles"][number]["privateGrade"], checkIds: string[]): "pass" | "fail" | "unknown" {
  if (!grade || grade.status === "error" || grade.status === "resource_limit" || grade.status === "unscored") return "unknown";
  const checks = new Map(grade.checks.map(check => [check.id, check.passed]));
  const values = checkIds.map(id => checks.get(id));
  if (values.some(value => value === false)) return "fail";
  return values.length > 0 && values.every(value => value === true) ? "pass" : "unknown";
}

function computeMetrics(record: TrajectoryRecord, descriptor: PackageDescriptor): TrajectoryMetrics {
  const manifest = descriptor.manifest!;
  const requirements = new Map(manifest.requirements.map(requirement => [requirement.id, requirement]));
  const stageById = new Map(record.stages.map(stage => [stage.stageId, stage]));
  const snapshots: TrajectoryMetrics["snapshots"] = [];
  for (const stage of record.stages) {
    for (const cycle of stage.cycles) {
      const statuses: Record<string, "pass" | "fail" | "unknown"> = {};
      for (const requirementId of stage.activeRequirementIds) {
        const requirement = requirements.get(requirementId)!;
        statuses[requirementId] = requirementStatus(cycle.privateGrade, requirement.checkIds);
      }
      snapshots.push({ stageId: stage.stageId, cycleId: cycle.cycleId, requirements: statuses });
    }
  }
  const finalStatus = (stageId: string, requirementId: string): "pass" | "fail" | "unknown" => {
    const stage = stageById.get(stageId);
    const cycle = stage?.cycles.at(-1);
    const requirement = requirements.get(requirementId);
    return cycle && requirement ? requirementStatus(cycle.privateGrade, requirement.checkIds) : "unknown";
  };
  const firstStatus = (stageId: string, requirementId: string): "pass" | "fail" | "unknown" => {
    const stage = stageById.get(stageId);
    const cycle = stage?.cycles.find(entry => entry.cycleId === "cycle-1");
    const requirement = requirements.get(requirementId);
    return cycle && requirement ? requirementStatus(cycle.privateGrade, requirement.checkIds) : "unknown";
  };
  const stages = manifest.stages!;
  const newRequirementCompletion: TrajectoryMetrics["newRequirementCompletion"] = [];
  for (const [index, stageInfo] of stages.entries()) {
    const previousActive = new Set(index === 0 ? [] : stages[index - 1]!.activeRequirementIds);
    for (const requirementId of stageInfo.activeRequirementIds.filter(id => !previousActive.has(id))) {
      newRequirementCompletion.push({ stageId: stageInfo.id, requirementId, status: finalStatus(stageInfo.id, requirementId) });
    }
  }
  const regressions: TrajectoryMetrics["regressions"] = [];
  const retention: TrajectoryMetrics["retention"] = [];
  for (let index = 1; index < stages.length; index++) {
    const previous = stages[index - 1]!;
    const current = stages[index]!;
    const shared = previous.activeRequirementIds.filter(id => current.activeRequirementIds.includes(id));
    const eligible = shared.filter(id => finalStatus(previous.id, id) === "pass");
    const judgedCurrent = eligible.map(id => finalStatus(current.id, id));
    const retained = judgedCurrent.filter(status => status === "pass").length;
    for (const requirementId of eligible) {
      if (firstStatus(current.id, requirementId) === "fail") {
        regressions.push({ fromStageId: previous.id, toStageId: current.id, requirementId, firstCycle: "fail", finalCycle: finalStatus(current.id, requirementId) });
      }
    }
    const judged = judgedCurrent.filter(status => status === "pass" || status === "fail").length;
    retention.push({ fromStageId: previous.id, toStageId: current.id, eligible: eligible.length, judged, retained,
      rate: judged ? retained / judged : null, coverage: eligible.length ? judged / eligible.length : null });
  }
  let initialFailures = 0;
  let repairPrompts = 0;
  let attemptedFailures = 0;
  let judged = 0;
  let repaired = 0;
  for (const stage of record.stages) {
    const initial = stage.cycles.find(cycle => cycle.cycleId === "cycle-1")?.publicCheck;
    const repairCycle = stage.cycles.find(cycle => cycle.cycleId === "cycle-2");
    const repair = repairCycle?.publicCheck;
    const failedIds = new Set(initial?.checks.filter(check => !check.passed).map(check => check.id) ?? []);
    initialFailures += failedIds.size;
    if (failedIds.size && repairCycle) {
      repairPrompts++;
      attemptedFailures += failedIds.size;
    }
    if (failedIds.size && repair) {
      for (const id of failedIds) {
        const check = repair.checks.find(entry => entry.id === id);
        if (check) {
          judged++;
          if (check.passed) repaired++;
        }
      }
    }
  }
  const publicRepair = { initialFailures, repairPrompts, attemptedFailures, judged, repaired, rate: judged ? repaired / judged : null,
    coverage: attemptedFailures ? judged / attemptedFailures : null };
  const finalStage = stages.at(-1);
  const finalCritical = finalStage?.activeRequirementIds.filter(id => requirements.get(id)?.critical) ?? [];
  const finalKnown = finalCritical.map(id => finalStatus(finalStage!.id, id));
  const finalDeliveryAccepted = finalKnown.includes("fail") ? false : record.status === "completed" && finalKnown.length > 0 && finalKnown.every(status => status === "pass") ? true : null;
  const allFinal = stages.flatMap(stage => stage.activeRequirementIds.filter(id => requirements.get(id)?.critical).map(id => finalStatus(stage.id, id)));
  const allStageStableDelivery = allFinal.includes("fail") ? false : record.status === "completed" && allFinal.length > 0 && allFinal.every(status => status === "pass") ? true : null;
  return { stageCompletion: { completed: record.stages.filter(stage => stage.status === "completed").length, planned: stages.length },
    finalDeliveryAccepted, allStageStableDelivery, snapshots, newRequirementCompletion, regressions, retention, publicRepair };
}

/** Runs one candidate across a shared Pi session/workspace, then grades immutable checkpoints after the session ends. */
export async function runTrajectoryEvaluation(plan: EvaluationPlan, options: EvaluationOptions) {
  if (plan.execution?.kind !== "trajectory") throw new Error("TRAJECTORY_POLICY_REQUIRED");
  if (options.runner) throw new Error("TRAJECTORY_REQUIRES_SESSION_FACTORY");
  const artifactLimits = plan.artifactLimits ?? { ...defaultArtifactLimits };
  const packages = await preflightPlan(plan);
  const directory = resolve(options.outputRoot, randomUUID());
  await mkdir(directory, { recursive: true });
  const sequence = { value: 0 };
  await writeFile(join(directory, "events.jsonl"), "", { encoding: "utf8", flag: "wx" });
  const packageFingerprints = [...packages].map(([caseId, descriptor]) => ({
    caseId,
    id: descriptor.manifest?.id ?? null,
    version: descriptor.manifest?.version ?? null,
    sha256: descriptor.manifestSha256,
    baselineCommit: descriptor.manifest?.baseline?.commit ?? null,
  }));
  const condition = await evaluatedCondition(plan, packages);
  const fingerprint = sha256({ plan, packageFingerprints, condition });
  const plannedRuns = plan.models.length * plan.cases.length;
  const batchPolicy = resolveBatchPolicy(plan);
  const guard = new BatchGuard(batchPolicy);
  const providerSlots = options.providerSlots ?? providerSlotsFromEnvironment();
  const notRun: NotRunEntry[] = [];
  await writeFile(join(directory, "experiment.json"), JSON.stringify({
    schemaVersion: 2, name: plan.name, fingerprint, packageFingerprints, condition, execution: plan.execution, isolation: plan.isolation ?? "sandbox",
    models: plan.models, caseIds: plan.cases.map(item => item.id), budget: plan.budget, artifactLimits, batch: batchPolicy,
    plannedRuns, node: process.version, startedAt: new Date().toISOString(),
  }, null, 2));
  const records: TrajectoryRecord[] = [];

  for (const model of plan.models) {
    for (const item of plan.cases) {
      const blocked = guard.blockedReason(`${model.provider}:${model.id}`);
      if (blocked) {
        notRun.push({ model: `${model.provider}:${model.id}`, caseId: item.id, repetition: 1, reason: blocked });
        continue;
      }
      const id = randomUUID();
      const trialDirectory = join(directory, id);
      await mkdir(trialDirectory, { recursive: true });
      await writeFile(join(trialDirectory, "events.jsonl"), "", { encoding: "utf8", flag: "wx" });
      await writeFile(join(trialDirectory, "tool-trace.jsonl"), "", { encoding: "utf8", flag: "wx" });
      const rawSink = appendEvent(trialDirectory, sequence, id);
      const events = guardEventSink(rawSink);
      const descriptor = packages.get(item.id);
      if (!descriptor?.manifest?.stages || !descriptor.manifestSha256) throw new Error("TRAJECTORY_PACKAGE_REQUIRED");
      const profile = item.toolProfile ?? descriptor.manifest.toolProfiles?.[0] ?? "workspace-basic";
      const stageIds = descriptor.manifest.stages.map(stage => stage.id);
      // A trajectory sends one request at a time, so it holds one of its provider's slots until its session ends.
      const releaseSlot = await providerSlots.acquire(model.provider);
      const start = performance.now();
      const totalExecution = emptyExecution();
      const recordValue: TrajectoryRecord = {
        id,
        caseId: item.id,
        model,
        status: "stopped",
        stopReason: null,
        stages: [],
        aggregateExecution: totalExecution,
        cleanup: "cleaned",
        durationMs: 0,
        packageManifest: { version: descriptor.manifest.version, sha256: descriptor.manifestSha256 },
        budget: { trajectory: plan.budget, stage: plan.execution.stageBudget, used: { timeoutMs: 0, maxTurns: 0, maxModelCalls: 0, maxToolCalls: 0 } },
      };
      let workspace: Awaited<ReturnType<typeof prepareWorkspace>> | undefined;
      let session: TrajectorySession | undefined;
      let stop = false;
      let executionStart: number | null = null;
      let executionElapsedMs = 0;
      let snapshotBytes = 0;
      let snapshotFiles = 0;
      let outputChars = 0;
      const snapshotRefs: Array<{ stageId: string; cycleId: "cycle-1" | "cycle-2"; directory: string; manifest: Awaited<ReturnType<typeof copyArtifacts>>; activeRequirementIds: string[]; answer: string }> = [];
      const persist = async () => writeFile(join(trialDirectory, "trajectory.json"), JSON.stringify(recordValue, null, 2));
      try {
        await events.emit("workspace_started");
        workspace = await prepareWorkspace(item.repository);
        const projection = await projectPackage(item.packagePath!, workspace.path, item.packageManifestSha256, true);
        if (projection.manifestSha256 !== descriptor.manifestSha256) throw new Error("PACKAGE_CHANGED_AFTER_PREFLIGHT");
        const commonInstruction = projection.instruction;
        const notice = resolveBudgetNotice(plan);
        executionStart = performance.now();
        const perStage = plan.execution!.kind === "trajectory" && plan.execution.contextPolicy === "per-stage";
        session = makeRunner(plan, options, model, id, profile, artifactLimits, workspace.path, item, batchPolicy);
        await events.emit("execution_started");

        for (const [index, stageInfo] of descriptor.manifest.stages.entries()) {
          if (stop) break;
          const stageStart = performance.now();
          const stageRecord: TrajectoryRecord["stages"][number] = {
            stageId: stageInfo.id,
            status: "stopped",
            cycles: [],
            activeRequirementIds: [...stageInfo.activeRequirementIds],
            durationMs: 0,
          };
          recordValue.stages.push(stageRecord);
          const stageInstruction = await projectTrajectoryStage(descriptor, workspace.path, stageInfo.id);
          // Under "per-stage" each stage gets a fresh session: the project carries over, the conversation does not, so
          // the stage budget means the same at the first stage and the last.
          if (perStage && index > 0) {
            try { await session.dispose(); } catch { recordValue.cleanup = "error"; }
            session = makeRunner(plan, options, model, id, profile, artifactLimits, workspace.path, item, batchPolicy);
          }
          for (let cycleIndex = 0; cycleIndex < 2; cycleIndex++) {
            if (cycleIndex === 1 && stageRecord.cycles[0]?.publicCheck?.status !== "failed") break;
            const cycleId = cycleIndex === 0 ? "cycle-1" : "cycle-2";
            const stageElapsed = performance.now() - stageStart;
            const trajectoryElapsed = performance.now() - executionStart;
            const stageOutputChars = stageRecord.cycles.reduce((sum, cycle) => sum + cycle.execution.output.length, 0);
            const budget = remainingBudget(plan.budget, plan.execution.stageBudget, totalExecution,
              stageRecord.cycles.reduce((sum, cycle) => {
                accumulate(sum, cycle.execution);
                return sum;
              }, emptyExecution()), trajectoryElapsed, stageElapsed, outputChars, stageOutputChars);
            if (!budget) {
              recordValue.stopReason = trajectoryElapsed >= plan.budget.timeoutMs || stageElapsed >= plan.execution.stageBudget.timeoutMs ? "TIMEOUT" : "BUDGET_EXHAUSTED";
              stageRecord.status = "stopped";
              stop = true;
              break;
            }

            const opening = index === 0 ? commonInstruction
              : perStage ? `${commonInstruction}\n\nThe earlier stages of this task are done and their work is in the project. This is stage ${index + 1} of ${descriptor.manifest.stages.length}; you do not have the earlier conversation.`
                : "Continue to the next stage in the same project and session.";
            const userPrompt = cycleIndex === 0
              ? [opening, item.input.prompt, stageInstruction,
                (index === 0 || perStage) && notice ? trajectoryBudgetStatement(plan.budget, plan.execution.stageBudget, notice.reminders) : ""].filter(Boolean).join("\n\n")
              : ["Public check feedback follows. Fix these failing items in the current project, change only what is necessary, and preserve completed requirements.", ...stageRecord.cycles[0].publicCheck!.checks.filter(check => !check.passed).map(check => `- ${check.id} (${check.reasonCode}): ${check.feedback}`)].join("\n");
            const execution = await session.send({ prompt: userPrompt, systemPrompt: item.input.systemPrompt, workspacePath: workspace.path }, budget,
              events.emit, { stageId: stageInfo.id, cycleId });
            outputChars += execution.output.length;
            accumulate(totalExecution, execution);
            guard.record(execution, { model: `${model.provider}:${model.id}` });
            const cycle: TrajectoryStageResult["cycles"][number] = { cycleId, execution: persistedExecution(execution, budget.maxOutputChars), publicCheck: null, snapshot: null };
            stageRecord.cycles.push(cycle);
            await events.emit("trajectory_submission_completed", { modelCalls: totalExecution.modelCalls, toolCalls: totalExecution.toolCalls }, { stageId: stageInfo.id, cycleId, status: execution.status });
            // A budget or model stop is the model's own outcome, so what it delivered is graded, as in a single run;
            // after an infrastructure failure nothing more is graded. A stage that used up only its own budget ends
            // there and the next stage is released while the whole task's budget lasts, since only that budget may stop
            // a model (an open-ended stage such as eng-005's S6 uses its whole budget by design).
            const stopped = execution.status !== "done";
            const stageOnly = stopped && execution.failureKind === "budget" &&
              remainingBudget(plan.budget, plan.execution.stageBudget, totalExecution, emptyExecution(), performance.now() - executionStart, 0, outputChars, 0) !== null;
            if (stopped) {
              stageRecord.status = "stopped";
              if (stageOnly) stageRecord.stopReason = execution.error ?? execution.status.toUpperCase();
              else {
                recordValue.stopReason = execution.error ?? execution.status.toUpperCase();
                stop = true;
              }
              if (execution.failureKind === "infrastructure") break;
            }
            // A batch ceiling or a stop of this model's provider ends this trajectory after its current submission is graded.
            const batchStop = guard.blockedReason(`${model.provider}:${model.id}`);

            const snapshotPath = join(trialDirectory, "snapshots", `${stageInfo.id}-${cycleId}`);
            let snapshotManifest: Awaited<ReturnType<typeof copyArtifacts>>;
            if (snapshotBytes >= artifactLimits.maxTrialBytes || snapshotFiles >= artifactLimits.maxFiles) {
              recordValue.stopReason = "TRAJECTORY_SNAPSHOT_LIMIT";
              stageRecord.status = "stopped";
              stop = true;
              break;
            }
            const snapshotLimits = { ...artifactLimits, maxTrialBytes: artifactLimits.maxTrialBytes - snapshotBytes,
              maxFiles: artifactLimits.maxFiles - snapshotFiles };
            try { snapshotManifest = await copyArtifacts(workspace.path, snapshotPath, snapshotLimits); }
            catch (error) {
              if (error instanceof ArtifactLimitError) recordValue.stopReason = error.message;
              else recordValue.stopReason = "SNAPSHOT_FAILED";
              stageRecord.status = "stopped";
              stop = true;
              break;
            }
            cycle.snapshot = { path: `snapshots/${stageInfo.id}-${cycleId}`, manifest: snapshotManifest };
            snapshotBytes += snapshotManifest.totalBytes;
            snapshotFiles += snapshotManifest.files.length;
            snapshotRefs.push({ stageId: stageInfo.id, cycleId, directory: snapshotPath, manifest: snapshotManifest, activeRequirementIds: [...stageInfo.activeRequirementIds], answer: cycle.execution.output });
            if (stopped) break;

            const stageElapsedAfterSnapshot = performance.now() - stageStart;
            const trajectoryElapsedAfterSnapshot = performance.now() - executionStart;
            const checkerBudget = min(stageInfo.publicChecker.timeoutMs,
              min(plan.budget.timeoutMs - trajectoryElapsedAfterSnapshot, plan.execution.stageBudget.timeoutMs - stageElapsedAfterSnapshot));
            if (checkerBudget < 1) {
              recordValue.stopReason = "TIMEOUT";
              stageRecord.status = "stopped";
              stop = true;
              break;
            }
            try {
              const checkerWorkspace = await mkdtemp(join(tmpdir(), "agent-eval-public-check-"));
              try {
                const checkerManifest = await copyArtifacts(snapshotPath, checkerWorkspace, artifactLimits);
                if (checkerManifest.sha256 !== snapshotManifest.sha256 || checkerManifest.totalBytes !== snapshotManifest.totalBytes) {
                  throw new Error("PUBLIC_CHECK_SNAPSHOT_MISMATCH");
                }
                cycle.publicCheck = await publicCheck(descriptor, stageInfo.id, checkerWorkspace, checkerBudget, plan.isolation);
                const archivedManifest = await inspectArtifacts(snapshotPath, artifactLimits);
                if (archivedManifest.sha256 !== snapshotManifest.sha256 || archivedManifest.totalBytes !== snapshotManifest.totalBytes) {
                  throw new Error("PUBLIC_CHECK_MUTATED_SNAPSHOT");
                }
              } finally {
                await rm(checkerWorkspace, { recursive: true, force: true });
              }
            } catch (error) {
              recordValue.stopReason = error instanceof Error && /^[A-Z0-9_]+$/.test(error.message) ? error.message : "PUBLIC_CHECK_FAILED";
              stageRecord.status = "stopped";
              stop = true;
              break;
            }
            await events.emit("public_check_completed", undefined, { stageId: stageInfo.id, cycleId, status: cycle.publicCheck.status,
              passed: cycle.publicCheck.checks.filter(check => check.passed).length, total: cycle.publicCheck.checks.length });
            if (performance.now() - stageStart > plan.execution.stageBudget.timeoutMs ||
                performance.now() - executionStart > plan.budget.timeoutMs) {
              recordValue.stopReason = "TIMEOUT";
              stageRecord.status = "stopped";
              stop = true;
              break;
            }
            stageRecord.status = "completed";
            await persist();
            if (batchStop) {
              recordValue.stopReason = batchStop;
              stop = true;
              break;
            }
          }
          stageRecord.durationMs = performance.now() - stageStart;
          if (stageRecord.status !== "stopped") stageRecord.status = "completed";
          await persist();
          if (!stop && index < descriptor.manifest.stages.length - 1) await events.emit("trajectory_stage_released", undefined, { stageId: descriptor.manifest.stages[index + 1].id });
        }
        if (stop) {
          for (const stageId of stageIds.slice(recordValue.stages.length)) {
            const stage = descriptor.manifest.stages.find(candidate => candidate.id === stageId)!;
            recordValue.stages.push({ stageId, status: "not_reached", cycles: [], activeRequirementIds: [...stage.activeRequirementIds], durationMs: 0 });
          }
        }
        recordValue.status = stop ? "stopped" : "completed";
        if (!stop) recordValue.stopReason = null;
        executionElapsedMs = performance.now() - executionStart;
        await events.emit("candidate_session_completed", { modelCalls: totalExecution.modelCalls, toolCalls: totalExecution.toolCalls }, { status: recordValue.status, stopReason: recordValue.stopReason });
      } catch (error) {
        recordValue.stopReason = error instanceof EventSinkError ? "EVENT_SINK_FAILED" : error instanceof Error && /^[A-Z0-9_]+$/.test(error.message) ? error.message : "TRAJECTORY_FAILED";
        recordValue.status = "stopped";
        stop = true;
      } finally {
        if (session) {
          try { await session.dispose(); } catch {
            recordValue.stopReason ??= "SESSION_DISPOSE_FAILED";
            recordValue.status = "stopped";
            recordValue.cleanup = "error";
          }
        }
        if (workspace) {
          try { await workspace.cleanup(); } catch { recordValue.cleanup = "error"; }
        }
        await releaseSlot();
        recordValue.durationMs = performance.now() - start;
        if (executionStart !== null && executionElapsedMs === 0) executionElapsedMs = performance.now() - executionStart;
        recordValue.aggregateExecution = persistedExecution(totalExecution, plan.budget.maxOutputChars);
      }

      const recordedStageIds = new Set(recordValue.stages.map(stage => stage.stageId));
      for (const stageInfo of descriptor.manifest.stages) {
        if (!recordedStageIds.has(stageInfo.id)) recordValue.stages.push({ stageId: stageInfo.id, status: "not_reached", cycles: [],
          activeRequirementIds: [...stageInfo.activeRequirementIds], durationMs: 0 });
      }

      // Private grading runs only after all candidate prompts and public repair decisions have finished.
      for (const snapshot of snapshotRefs) {
        const scoreRunId = randomUUID();
        const scoreRunDirectory = join(trialDirectory, "score-runs", scoreRunId);
        await mkdir(scoreRunDirectory, { recursive: true });
        const grade = await runTaskGrader({
          trialId: `${id}.${snapshot.stageId}.${snapshot.cycleId}`,
          scoreRunDirectory,
          submissionDirectory: snapshot.directory,
          submissionManifest: snapshot.manifest,
          packageDescriptor: descriptor,
          maxOutputBytes: item.evaluator.kind === "task-package" ? item.evaluator.maxOutputBytes ?? artifactLimits.graderResultMaxBytes : artifactLimits.graderResultMaxBytes,
          resultMaxBytes: artifactLimits.graderResultMaxBytes,
          timeoutMs: item.evaluator.kind === "task-package" ? item.evaluator.timeoutMs ?? 30_000 : 30_000,
          answerText: snapshot.answer,
          tracePath: join(trialDirectory, "tool-trace.jsonl"),
          context: { stageId: snapshot.stageId, cycleId: snapshot.cycleId, activeRequirementIds: snapshot.activeRequirementIds },
          isolation: plan.isolation,
        });
        const stageRecord = recordValue.stages.find(stage => stage.stageId === snapshot.stageId)!;
        const cycle = stageRecord.cycles.find(entry => entry.cycleId === snapshot.cycleId)!;
        cycle.privateGrade = grade;
        await writeFile(join(scoreRunDirectory, "score.json"), JSON.stringify({ schemaVersion: 1, trialId: id, stageId: snapshot.stageId,
          cycleId: snapshot.cycleId, taskManifestSha256: descriptor.manifestSha256, snapshotManifestSha256: snapshot.manifest.sha256,
          evaluation: grade, createdAt: new Date().toISOString() }, null, 2));
      }
      recordValue.metrics = computeMetrics(recordValue, descriptor);
      recordValue.budget.used = toBudgetUsed(totalExecution, executionElapsedMs);
      await persist();
      await writeFile(join(trialDirectory, "result.json"), JSON.stringify(recordValue, null, 2));
      records.push(recordValue);
      await events.emit("trajectory_record_completed", { modelCalls: totalExecution.modelCalls, toolCalls: totalExecution.toolCalls }, { status: recordValue.status });
      await writeFile(join(directory, "report.json"), JSON.stringify({ version: 1, plannedRuns, recordedRuns: records.length, batch: guard.summary(notRun), records }, null, 2));
    }
  }
  const report = { version: 1, plannedRuns, recordedRuns: records.length, completed: records.length === plannedRuns && notRun.length === 0, batch: guard.summary(notRun), records };
  await writeFile(join(directory, "report.json"), JSON.stringify(report, null, 2));
  await writeFile(join(directory, "report.md"), markdownTrajectoryReport(records));
  return { directory, report };
}

function markdownTrajectoryReport(records: TrajectoryRecord[]): string {
  const lines = ["# Long-horizon trajectory report", "", "| Case | Model | Status | Stages released | Model calls | Turns | Stop reason |", "|---|---|---:|---:|---:|---:|---|"];
  for (const record of records) {
    lines.push(`| ${record.caseId} | ${modelLabel(record.model)} | ${record.status} | ${record.stages.filter(stage => stage.status !== "not_reached").length}/${record.stages.length} | ${record.aggregateExecution.modelCalls} | ${record.aggregateExecution.turns} | ${record.stopReason ?? "—"} |`);
  }
  lines.push("", "Stage snapshots are individually graded after candidate execution ends. A trajectory is one sample; stage checkpoints are not independent runs.", "");
  return lines.join("\n");
}
