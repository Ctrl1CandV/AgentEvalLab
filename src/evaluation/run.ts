import { mkdir, appendFile, readFile, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { randomUUID, createHash } from "node:crypto";
import { createPiRunner } from "../harness/pi.js";
import { evaluationTools } from "../harness/profiles.js";
import type { ToolProfile } from "../harness/tools.js";
import type { InteractionClass } from "../types.js";
import { emptyExecution } from "../types.js";
import { persistedExecution } from "../privacy.js";
import { guardEventSink, EventSinkError } from "../events.js";
import { collectPatch } from "../workspace.js";
import { evaluate, skippedEvaluation, EvaluatorCleanupError } from "./evaluator.js";
import { prepareWorkspace } from "./workspace.js";
import { projectPackage } from "./package.js";
import { ArtifactLimitError, copyArtifacts, defaultArtifactLimits } from "./artifacts.js";
import { validatePlan } from "./validate.js";
import { markdownReport, summarize, summarizeInteractionClass } from "./report.js";
import { preflightPlan } from "./preflight.js";
import type { EvaluationOptions, EvaluationPlan, TrialRecord } from "./types.js";

export async function runEvaluation(plan: EvaluationPlan, options: EvaluationOptions) {
  validatePlan(plan);
  const artifactLimits = plan.artifactLimits ?? { ...defaultArtifactLimits };
  const taskPackages = await preflightPlan(plan);
  const directory = resolve(options.outputRoot, randomUUID());
  await mkdir(directory, { recursive: true });
  const records: TrialRecord[] = [];
  const packageFingerprints = [...taskPackages].map(([caseId, descriptor]) => ({
    caseId,
    id: descriptor.manifest?.id ?? null,
    version: descriptor.manifest?.version ?? null,
    sha256: descriptor.manifestSha256,
    baselineCommit: descriptor.manifest?.baseline?.commit ?? null,
    toolProfiles: descriptor.manifest?.toolProfiles ?? ["workspace-basic"],
  }));
  const fingerprint = createHash("sha256").update(JSON.stringify({ plan, packageFingerprints })).digest("hex");
  const plannedRuns = plan.models.length * plan.cases.length;
  await writeFile(join(directory, "experiment.json"), JSON.stringify({ schemaVersion: 1, name: plan.name, fingerprint, packageFingerprints, models: plan.models, caseIds: plan.cases.map(item => item.id), budget: plan.budget, artifactLimits, plannedRuns, node: process.version, startedAt: new Date().toISOString() }, null, 2));
  let sequence = 0;
  let pending = Promise.resolve();
  let completed = false;
  const saveReport = async () => {
    const report = { version: 1, plannedRuns, recordedRuns: records.length, completed, scoreRunPolicy: "latest-append-only-score-run-per-trial", records, summary: summarize(records), byInteractionClass: {
      candidate: summarizeInteractionClass(records, "candidate"),
      probe: summarizeInteractionClass(records, "probe"),
    }, byModel: plan.models.map(model => ({ model, summary: summarize(records.filter(record => record.model.provider === model.provider && record.model.id === model.id)) })) };
    await writeFile(join(directory, "report.json"), JSON.stringify(report, null, 2));
    await writeFile(join(directory, "report.md"), markdownReport(records));
    return report;
  };
  for (const model of plan.models) {
    for (const item of plan.cases) {
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
        toolTrace: null };
      let workspace: Awaited<ReturnType<typeof prepareWorkspace>> | undefined;
      let fatal: unknown;
      let executionFinished = false;
      let evaluationCommitted = false;
      try {
        await events.emit("workspace_started");
        workspace = await prepareWorkspace(item.repository);
        record.baseline = workspace.git?.commit ?? null;
        const projection = item.packagePath ? await projectPackage(item.packagePath, workspace.path, item.packageManifestSha256, plan.schemaVersion === 2) : null;
        if (projection && projection.manifestSha256 !== (packageDescriptor?.manifestSha256 ?? null)) throw new Error("PACKAGE_CHANGED_AFTER_PREFLIGHT");
        const instruction = projection?.instruction ?? "";
        await events.emit("execution_started");
        const runner = options.runner ?? createPiRunner({
          trialId: id,
          interactionClass,
          toolEvidenceMaxBytes: artifactLimits.toolEvidenceMaxBytes,
          toolProfile,
          createTools: () => plan.trustedLocalExecution ? evaluationTools(
            toolProfile === "doc-evidence" ? join(workspace!.path, "public", "snapshot") : workspace!.path,
            toolProfile,
            { readOnly: item.readOnly, execute: !item.readOnly },
          ) : [],
        });
        record.execution = await runner({ ...item.input, prompt: [instruction, item.input.prompt].filter(Boolean).join("\n\n"), workspacePath: workspace.path }, model, plan.budget, events.emit);
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
          if (error instanceof ArtifactLimitError) {
            record.evaluation = { status: "resource_limit", score: null, checks: [], error: error.message };
          } else if (!evaluationCommitted) {
            record.evaluation = { status: "error", score: null, checks: [], error: "ARTIFACT_OR_EVENT_FAILED" };
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
        await writeFile(join(trialDirectory, "result.json"), JSON.stringify(record, null, 2));
      }
      await saveReport();
      if (fatal) throw fatal;
      await events.emit("cleanup_completed", { failed: Number(record.cleanup === "error") });
    }
  }
  completed = true;
  return { directory, report: await saveReport() };
}
