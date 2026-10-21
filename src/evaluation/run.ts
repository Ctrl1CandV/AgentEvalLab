import { mkdir, appendFile, readFile, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { randomUUID, createHash } from "node:crypto";
import { createPiRunner } from "../harness/pi.js";
import { evaluationTools } from "../harness/profiles.js";
import type { ToolProfile } from "../harness/tools.js";
import type { InteractionClass, ModelSelection } from "../types.js";
import { emptyExecution } from "../types.js";
import { persistedExecution } from "../privacy.js";
import { guardEventSink, EventSinkError } from "../events.js";
import { collectPatch } from "../workspace.js";
import { evaluate, skippedEvaluation, EvaluatorCleanupError } from "./evaluator.js";
import { prepareWorkspace } from "./workspace.js";
import { projectPackage } from "./package.js";
import { projectPackageItem, type ManifestItem, type PackageDescriptor } from "./manifest.js";
import { resolveCaseItems } from "./items.js";
import { ArtifactLimitError, copyArtifacts, defaultArtifactLimits } from "./artifacts.js";
import { validatePlan } from "./validate.js";
import { buildReport, markdownReport } from "./report.js";
import { seededRandom, shuffled } from "./statistics.js";
import { preflightPlan } from "./preflight.js";
import { evaluatedCondition, sha256 } from "./condition.js";
import { BatchGuard, resolveBatchPolicy, type NotRunEntry } from "./batch.js";
import { budgetStatement, defaultReminderThresholds } from "../harness/budget-notice.js";
import { loadRecordedTrials } from "./regrade.js";
import { providerSlotsFromEnvironment } from "./provider-slots.js";
import type { EvaluationOptions, EvaluationPlan, TrialRecord } from "./types.js";

interface TrialSlot {
  model: ModelSelection;
  item: EvaluationPlan["cases"][number];
  repetition: number;
  /** The generated package item this trial receives (item packages only). */
  packageItem: ManifestItem | null;
}

/**
 * Every trial the plan asks for, in execution order: repetition by repetition, case by case and item by item, with
 * the model order shuffled per slot so time-dependent provider effects do not favour one model.
 */
export function trialSchedule(plan: EvaluationPlan, seed: number, packages: Map<string, PackageDescriptor>): TrialSlot[] {
  const random = seededRandom(seed);
  const slots: TrialSlot[] = [];
  for (let repetition = 1; repetition <= (plan.repetitions ?? 1); repetition++) {
    for (const item of plan.cases) {
      for (const packageItem of resolveCaseItems(item, packages.get(item.id)) ?? [null]) {
        for (const model of shuffled(plan.models, random)) slots.push({ model, item, repetition, packageItem });
      }
    }
  }
  return slots;
}

/**
 * The plan as it enters the run fingerprint. Concurrency only changes how many trials run at once, not what any model
 * sees, so it is left out: a run can be resumed or merged with a different concurrency.
 */
export function fingerprintedPlan(plan: EvaluationPlan): EvaluationPlan {
  if (plan.batch?.concurrency === undefined) return plan;
  const { concurrency: _concurrency, ...batch } = plan.batch;
  return { ...plan, batch };
}

/** The plan's budget notice with defaults filled in, or null when the budget is not stated to the model. */
export function resolveBudgetNotice(plan: EvaluationPlan): { reminders: readonly number[] } | null {
  if (!plan.budgetNotice) return null;
  return { reminders: plan.budgetNotice === true ? defaultReminderThresholds : plan.budgetNotice.reminders };
}

function trialKey(model: ModelSelection, caseId: string, repetition: number, itemId?: string | null): string {
  return `${model.provider}:${model.id}#${caseId}${itemId ? `@${itemId}` : ""}#${repetition}`;
}

async function countLines(path: string): Promise<number> {
  try { return (await readFile(path, "utf8")).split("\n").filter(Boolean).length; }
  catch { return 0; }
}

export async function runEvaluation(plan: EvaluationPlan, options: EvaluationOptions) {
  validatePlan(plan);
  const artifactLimits = plan.artifactLimits ?? { ...defaultArtifactLimits };
  const taskPackages = await preflightPlan(plan);
  const packageFingerprints = [...taskPackages].map(([caseId, descriptor]) => ({
    caseId,
    id: descriptor.manifest?.id ?? null,
    version: descriptor.manifest?.version ?? null,
    sha256: descriptor.manifestSha256,
    baselineCommit: descriptor.manifest?.baseline?.commit ?? null,
    toolProfiles: descriptor.manifest?.toolProfiles ?? ["workspace-basic"],
    capability: descriptor.manifest?.capability ?? null,
  }));
  const capabilities = Object.fromEntries(plan.cases.map(item => [item.id, taskPackages.get(item.id)?.manifest?.capability ?? "unspecified"]));
  const condition = await evaluatedCondition(plan, taskPackages);
  const fingerprint = sha256({ plan: fingerprintedPlan(plan), packageFingerprints, condition });
  const batchPolicy = resolveBatchPolicy(plan);
  const seed = plan.seed ?? Number.parseInt(fingerprint.slice(0, 8), 16);
  const schedule = trialSchedule(plan, seed, taskPackages);
  const plannedRuns = schedule.length;

  // A resumed run reuses its directory only when the plan, packages and evaluated condition are identical.
  let directory: string;
  const recorded = new Map<string, TrialRecord>();
  if (options.resumeDirectory) {
    directory = resolve(options.resumeDirectory);
    const experiment = JSON.parse(await readFile(join(directory, "experiment.json"), "utf8")) as { fingerprint?: unknown };
    if (experiment.fingerprint !== fingerprint) throw new Error("RESUME_FINGERPRINT_MISMATCH");
    for (const record of await loadRecordedTrials(directory)) recorded.set(trialKey(record.model, record.caseId, record.repetition ?? 1, record.itemId), record);
  } else {
    directory = resolve(options.outputRoot, randomUUID());
    await mkdir(directory, { recursive: true });
    await writeFile(join(directory, "experiment.json"), JSON.stringify({ schemaVersion: 2, name: plan.name, fingerprint, packageFingerprints, condition, models: plan.models, caseIds: plan.cases.map(item => item.id), budget: plan.budget, artifactLimits, batch: batchPolicy, repetitions: plan.repetitions ?? 1, seed, schedule: schedule.map(slot => trialKey(slot.model, slot.item.id, slot.repetition, slot.packageItem?.id)), plannedRuns, isolation: plan.isolation ?? "sandbox", node: process.version, startedAt: new Date().toISOString() }, null, 2));
  }
  const records: TrialRecord[] = [];
  const guard = new BatchGuard(batchPolicy);
  // A resumed run can skip providers already stopped for balance or authentication; their trials are listed as not run.
  for (const [provider, reason] of Object.entries(options.stoppedProviders ?? {})) guard.providerStops[provider] = reason;
  const providerSlots = options.providerSlots ?? providerSlotsFromEnvironment();
  const notice = resolveBudgetNotice(plan);
  const notRun: NotRunEntry[] = [];
  let sequence = await countLines(join(directory, "events.jsonl"));
  let pending = Promise.resolve();
  let completed = false;
  const saveReport = async () => {
    const report = buildReport(records, { plannedRuns, completed, models: plan.models, capabilities, repetitions: plan.repetitions ?? 1, batch: guard.summary(notRun) });
    await writeFile(join(directory, "report.json"), JSON.stringify(report, null, 2));
    await writeFile(join(directory, "report.md"), markdownReport(report));
    return report;
  };
  // Serialise report writes: with concurrent trials, two saves must not interleave their files.
  let reportChain: Promise<unknown> = Promise.resolve();
  const saveReportSerially = () => (reportChain = reportChain.then(saveReport, saveReport));
  const runSlot = async ({ model, item, repetition, packageItem }: TrialSlot): Promise<void> => {
      const previous = recorded.get(trialKey(model, item.id, repetition, packageItem?.id));
      const modelId = `${model.provider}:${model.id}`;
      // Keep finished trials from an earlier attempt of this run; rerun only infrastructure failures.
      if (previous && previous.execution.failureKind !== "infrastructure") {
        guard.record(previous.execution, { model: modelId });
        records.push(previous);
        return;
      }
      if (previous) guard.record(previous.execution, { countFailure: false, model: modelId });
      const blocked = guard.blockedReason(modelId, plan.budget.maxTrialTokens ?? 0);
      if (blocked) {
        notRun.push({ model: modelId, caseId: item.id, repetition, ...(packageItem ? { itemId: packageItem.id } : {}), reason: blocked });
        return;
      }
      const release = guard.reserve(modelId, plan.budget.maxTrialTokens ?? 0);
      const releaseSlot = await providerSlots.acquire(model.provider);
      const start = performance.now();
      const id = randomUUID();
      const trialDirectory = join(directory, id);
      await mkdir(trialDirectory);
      const toolTracePath = join(trialDirectory, "tool-trace.jsonl");
      await writeFile(toolTracePath, "", { encoding: "utf8", flag: "wx" });
      const events = guardEventSink((type, counts, details) => {
        const event = { sequence: ++sequence, at: new Date().toISOString(), runId: id, type, counts, ...(details ? { details } : {}) };
        pending = pending.then(async () => {
          const line = JSON.stringify(event) + "\n";
          await appendFile(join(directory, "events.jsonl"), line);
          if (type === "tool_trace" && details) await appendFile(toolTracePath, JSON.stringify(details) + "\n");
        });
        return pending;
      });
      const packageDescriptor = taskPackages.get(item.id);
      const toolProfile = item.toolProfile ?? packageDescriptor?.manifest?.toolProfiles?.[0] ?? "workspace-basic";
      const interactionClass = item.interactionClass ?? "candidate";
      const record: TrialRecord = { id, caseId: item.id, model, execution: emptyExecution(), evaluation: skippedEvaluation(), cleanup: "cleaned", durationMs: 0, baseline: null,
        scoreRunId: null,
        packageManifest: packageDescriptor?.manifest && packageDescriptor.manifestSha256 ? { version: packageDescriptor.manifest.version, sha256: packageDescriptor.manifestSha256 } : null,
        artifactManifest: null,
        toolProfile: toolProfile as ToolProfile,
        interactionClass: interactionClass as InteractionClass,
        toolTrace: null,
        repetition,
        ...(packageItem ? { itemId: packageItem.id, itemLevel: packageItem.level } : {}),
        supersedes: previous?.id ?? null };
      let workspace: Awaited<ReturnType<typeof prepareWorkspace>> | undefined;
      let fatal: unknown;
      let executionFinished = false;
      let evaluationCommitted = false;
      try {
        await events.emit("workspace_started");
        workspace = await prepareWorkspace(item.repository);
        record.baseline = workspace.git?.commit ?? null;
        const projection = item.packagePath ? await projectPackage(item.packagePath, workspace.path, item.packageManifestSha256, plan.schemaVersion === 3) : null;
        if (projection && projection.manifestSha256 !== (packageDescriptor?.manifestSha256 ?? null)) throw new Error("PACKAGE_CHANGED_AFTER_PREFLIGHT");
        const instruction = projection?.instruction ?? "";
        const itemPrompt = packageItem && projection ? (await projectPackageItem(projection, workspace.path, packageItem.id)).prompt : "";
        await events.emit("execution_started");
        const runner = options.runner ?? createPiRunner({
          ...(notice ? { budgetReminders: notice.reminders } : {}),
          trialId: id,
          interactionClass,
          toolEvidenceMaxBytes: artifactLimits.toolEvidenceMaxBytes,
          toolProfile,
          maxRetries: batchPolicy.maxRetries,
          maxRetryDelayMs: batchPolicy.maxRetryDelayMs,
          createTools: () => plan.trustedLocalExecution ? evaluationTools(
            toolProfile === "doc-evidence" ? join(workspace!.path, "public", "snapshot") : workspace!.path,
            toolProfile,
            { readOnly: item.readOnly, execute: !item.readOnly, isolation: plan.isolation },
          ) : [],
        });
        const prompt = [instruction, itemPrompt, item.input.prompt, notice ? budgetStatement(plan.budget, notice.reminders) : ""].filter(Boolean).join("\n\n");
        record.execution = await runner({ ...item.input, prompt, workspacePath: workspace.path }, model, plan.budget, events.emit);
        executionFinished = true;
        await pending;
        events.check();
        await events.emit("execution_completed");
        const toolTraceText = await readFile(toolTracePath, "utf8");
        record.toolTrace = {
          path: "tool-trace.jsonl",
          bytes: Buffer.byteLength(toolTraceText),
          sha256: createHash("sha256").update(toolTraceText).digest("hex"),
          truncated: record.execution.toolEvidenceTruncated,
        };
        let patch = "";
        if (workspace.git) {
          patch = await collectPatch(workspace.git);
          await writeFile(join(trialDirectory, "submission.patch"), patch);
        }
        await events.emit("evaluation_started");
        const artifactManifest = await copyArtifacts(workspace.path, join(trialDirectory, "artifacts"), artifactLimits);
        record.artifactManifest = { totalBytes: artifactManifest.totalBytes, sha256: artifactManifest.sha256 };
        await writeFile(join(trialDirectory, "artifact-manifest.json"), JSON.stringify(artifactManifest, null, 2));
        const scoreRunId = randomUUID();
        const scoreRunDirectory = join(trialDirectory, "score-runs", scoreRunId);
        await mkdir(scoreRunDirectory, { recursive: true });
        record.scoreRunId = scoreRunId;
        try {
          const frozenCase = item.repository ? { ...item, repository: { ...item.repository, commit: workspace.git!.commit } } : item;
          record.evaluation = await evaluate(frozenCase, record.execution, patch, join(trialDirectory, "artifacts"), artifactLimits, {
            trialId: id,
            scoreRunDirectory,
            packageDescriptor: packageDescriptor ?? null,
            submissionManifest: artifactManifest,
            answerText: persistedExecution(record.execution, plan.budget.maxOutputChars).output,
            tracePath: toolTracePath,
            emit: events.emit,
            isolation: plan.isolation,
            ...(packageItem ? { item: { id: packageItem.id, activeRequirementIds: packageItem.activeRequirementIds } } : {}),
          });
        } catch (error) {
          if (error instanceof EvaluatorCleanupError) record.cleanup = "error";
          record.evaluation = { status: "error", score: null, checks: [], error: "EVALUATOR_FAILED" };
        }
        await writeFile(join(scoreRunDirectory, "score.json"), JSON.stringify({
          schemaVersion: 1,
          scoreRunId,
          trialId: id,
          caseId: item.id,
          ...(packageItem ? { itemId: packageItem.id } : {}),
          createdAt: new Date().toISOString(),
          submission: { snapshotPath: "../../artifacts", artifactManifestSha256: artifactManifest.sha256 },
          scorer: packageDescriptor?.manifest ? {
            kind: item.evaluator.kind,
            taskId: packageDescriptor.manifest.id,
            taskVersion: packageDescriptor.manifest.version,
            taskManifestSha256: packageDescriptor.manifestSha256,
            graderId: packageDescriptor.manifest.grader.id,
            graderVersion: packageDescriptor.manifest.grader.version,
          } : { kind: item.evaluator.kind },
          evaluation: record.evaluation,
        }, null, 2));
        evaluationCommitted = true;
        await events.emit("evaluation_completed");
      } catch (error) {
        try { await pending; events.check(); } catch { fatal = new EventSinkError(); }
        if (error instanceof EventSinkError) fatal = error;
        if (executionFinished) {
          const message = error instanceof Error ? error.message : "";
          if (error instanceof ArtifactLimitError || message === "ARTIFACT_LINK_DENIED" || message === "ARTIFACT_TYPE_DENIED") {
            // The deliverable breaks the artifact rules: too large, or a link or special file the model created.
            record.evaluation = { status: "resource_limit", score: null, checks: [], error: message };
          } else if (fatal) {
            if (!evaluationCommitted) record.evaluation = { status: "error", score: null, checks: [], error: "ARTIFACT_OR_EVENT_FAILED" };
          } else if (!evaluationCommitted) {
            // Any other export or bookkeeping failure, such as a workspace removed from outside, is not the model's
            // doing: record it as an infrastructure failure, which a resumed run retries.
            record.execution = { ...record.execution, failureKind: "infrastructure", error: "ARTIFACT_EXPORT_FAILED" };
            record.evaluation = { status: "skipped", score: null, checks: [], error: "ARTIFACT_EXPORT_FAILED" };
          }
        } else {
          record.execution = { ...record.execution, status: "error", failureKind: "infrastructure", error: "TRIAL_FAILED" };
        }
      } finally {
        if (workspace) {
          try { await workspace.cleanup(); } catch { record.cleanup = "error"; }
        }
        record.durationMs = performance.now() - start;
        record.execution = persistedExecution(record.execution, plan.budget.maxOutputChars);
        records.push(record);
        await releaseSlot();
        await writeFile(join(trialDirectory, "result.json"), JSON.stringify(record, null, 2));
      }
      release();
      guard.record(record.execution, { model: modelId });
      await saveReportSerially();
      if (fatal) throw fatal;
      await events.emit("cleanup_completed", { failed: Number(record.cleanup === "error") });
  };
  // Workers take slots in schedule order; a fatal error stops every worker from starting another trial.
  let nextSlot = 0;
  let fatalError: unknown = null;
  const worker = async () => {
    while (fatalError === null && nextSlot < schedule.length) {
      const slot = schedule[nextSlot++]!;
      try { await runSlot(slot); } catch (error) { fatalError ??= error; }
    }
  };
  await Promise.all(Array.from({ length: Math.max(1, Math.min(batchPolicy.concurrency, schedule.length)) }, worker));
  await reportChain;
  if (fatalError !== null) throw fatalError;
  completed = notRun.length === 0;
  return { directory, report: await saveReport() };
}
