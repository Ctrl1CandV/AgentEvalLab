import { parseArgs } from "node:util";
import { defaultBudget, parseModel } from "./config.js";
import { resolveModel } from "./harness/pi.js";
import { runHarness } from "./run.js";
import { readFile } from "node:fs/promises";
import { basename, resolve } from "node:path";
import { loadCredentials } from "./providers.js";
import { runEvaluation } from "./evaluation/run.js";
import { runTrajectoryEvaluation } from "./evaluation/trajectory.js";
import { validatePlan } from "./evaluation/validate.js";
import { preflightPlan } from "./evaluation/preflight.js";
import { regradeTrial, restoreTrialSnapshot } from "./evaluation/regrade.js";
import { restoreTrajectorySnapshot } from "./evaluation/trajectory-snapshot.js";
import type { EvaluationPlan } from "./evaluation/types.js";

async function main(): Promise<void> {
  const { values } = parseArgs({
    options: {
      plan: { type: "string" },
      model: { type: "string" },
      prompt: { type: "string" },
      out: { type: "string", default: "runs" },
      "validate-only": { type: "boolean" },
      regrade: { type: "string" },
      restore: { type: "string" },
      "restore-trajectory": { type: "string" },
      stage: { type: "string" },
      cycle: { type: "string" },
      destination: { type: "string" },
      reason: { type: "string" },
      help: { type: "boolean" },
    },
  });

  if (values.help) {
    console.log([
      'npm run harness -- --model provider:id --prompt "..." [--out runs] [--validate-only]',
      "npm run harness -- --plan plan.eval.json --regrade runs/<run>/<trial> --reason \"reason\"",
      "npm run harness -- --restore runs/<run>/<trial> --destination path/to/new-snapshot",
      "npm run harness -- --restore-trajectory runs/<run>/<trial> --stage S1 --cycle cycle-1 --destination path/to/new-snapshot",
    ].join("\n"));
    return;
  }

  if (values.regrade || values.restore || values["restore-trajectory"]) {
    const selectedOperations = [values.regrade, values.restore, values["restore-trajectory"]].filter(Boolean).length;
    if (selectedOperations !== 1 || values.model || values.prompt || values["validate-only"]) {
      throw new Error("INVALID_SNAPSHOT_OPERATION");
    }
    if (values["restore-trajectory"]) {
      if (!values.destination || !values.stage || !values.cycle || values.plan || values.reason ||
          (values.cycle !== "cycle-1" && values.cycle !== "cycle-2")) throw new Error("TRAJECTORY_RESTORE_ARGUMENTS_INVALID");
      const result = await restoreTrajectorySnapshot(values["restore-trajectory"], values.stage, values.cycle, values.destination);
      console.log(JSON.stringify(result, null, 2));
      return;
    }
    if (values.restore) {
      if (!values.destination || values.plan || values.reason || values.stage || values.cycle) throw new Error("RESTORE_ARGUMENTS_INVALID");
      const result = await restoreTrialSnapshot(values.restore, values.destination);
      console.log(JSON.stringify(result, null, 2));
      return;
    }
    if (!values.plan || !values.reason || values.destination || values.stage || values.cycle) throw new Error("REGRADE_ARGUMENTS_INVALID");
    const path = resolve(values.plan);
    if (!basename(path).endsWith(".eval.json")) throw new Error("PLAN_EXTENSION_REQUIRED");
    const plan = JSON.parse(await readFile(path, "utf8")) as EvaluationPlan;
    const result = await regradeTrial(values.regrade!, plan, values.reason);
    console.log(JSON.stringify(result, null, 2));
    return;
  }

  if (values.plan) {
    const path = resolve(values.plan);
    if (!basename(path).endsWith(".eval.json")) throw new Error("PLAN_EXTENSION_REQUIRED");
    const plan = JSON.parse(await readFile(path, "utf8")) as EvaluationPlan;
    validatePlan(plan);
    await preflightPlan(plan);
    if (values["validate-only"]) {
      console.log("Evaluation plan is valid. Credentials were not loaded and no API requests were sent.");
      return;
    }
    loadCredentials();
    if (plan.execution?.kind === "trajectory") {
      const result = await runTrajectoryEvaluation(plan, { outputRoot: values.out });
      const stopped = result.report.records.some(record => record.status !== "completed" || record.cleanup !== "cleaned" ||
        record.stages.some(stage => stage.cycles.some(cycle => cycle.privateGrade?.status === "error" || cycle.privateGrade?.status === "resource_limit")));
      console.log(JSON.stringify({ directory: result.directory, completedRuns: result.report.records.filter(record => record.status === "completed").length,
        plannedRuns: result.report.plannedRuns }, null, 2));
      if (stopped) process.exitCode = 1;
      return;
    }
    const result = await runEvaluation(plan, { outputRoot: values.out });
    console.log(JSON.stringify({ directory: result.directory, summary: result.report.summary }, null, 2));
    if (result.report.summary.executionFailures || result.report.summary.evaluatorErrors || result.report.summary.resourceLimitRuns || result.report.summary.cleanupFailures || result.report.records.some(record => record.evaluation.status === "failed")) process.exitCode = 1;
    return;
  }

  if (!values.model) throw new Error("MODEL_REQUIRED");
  const model = parseModel(values.model);
  resolveModel(model);

  // Validation mode checks model configuration without loading credentials or sending requests.
  if (values["validate-only"]) {
    console.log("Model configuration is valid. Credentials were not read and no API requests were sent.");
    return;
  }

  if (!values.prompt?.trim()) throw new Error("PROMPT_REQUIRED");
  loadCredentials();
  const result = await runHarness({
    input: { prompt: values.prompt },
    model,
    budget: { ...defaultBudget },
    outputRoot: values.out,
  });

  console.log(JSON.stringify(result, null, 2));
  if (result.execution.status !== "done") process.exitCode = 1;
}

main().catch(error => {
  // Report stable error codes such as PACKAGE_FILE_HASH_MISMATCH; free-form messages may carry provider or path details.
  const message = error instanceof Error ? error.message : "";
  const code = /^[A-Z][A-Z0-9_]*(?::[A-Za-z0-9_]+)?$/.test(message) ? message : "UNCLASSIFIED_ERROR";
  console.error(`HARNESS_FAILED: ${code}. Check the model, input, environment credentials, and output directory permissions.`);
  process.exitCode = 1;
});
