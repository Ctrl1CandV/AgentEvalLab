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
import { importHumanReview, mergeRunReports, regradeTrial, restoreTrialSnapshot } from "./evaluation/regrade.js";
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
      "import-review": { type: "string" },
      review: { type: "string" },
      resume: { type: "string" },
      merge: { type: "string", multiple: true },
      help: { type: "boolean" },
    },
  });

  if (values.help) {
    console.log([
      'npm run harness -- --model provider:id --prompt "..." [--out runs] [--validate-only]',
      "npm run harness -- --plan plan.eval.json [--out runs] [--validate-only] [--resume runs/<run>]",
      "npm run harness -- --merge runs/<run-a> --merge runs/<run-b> [--out runs]",
      "npm run harness -- --plan plan.eval.json --regrade runs/<run>/<trial> --reason \"reason\"",
      "npm run harness -- --plan plan.eval.json --import-review runs/<run>/<trial> --review review.json --reason \"reason\"",
      "npm run harness -- --restore runs/<run>/<trial> --destination path/to/new-snapshot",
      "npm run harness -- --restore-trajectory runs/<run>/<trial> --stage S1 --cycle cycle-1 --destination path/to/new-snapshot",
    ].join("\n"));
    return;
  }

  if (values.merge) {
    if (values.plan || values.model || values.prompt || values.regrade || values.restore || values["restore-trajectory"] || values["import-review"] || values.resume) {
      throw new Error("MERGE_ARGUMENTS_INVALID");
    }
    const result = await mergeRunReports(values.merge, values.out);
    console.log(JSON.stringify({ directory: result.directory, recordedRuns: result.report.recordedRuns, plannedRuns: result.report.plannedRuns }, null, 2));
    return;
  }

  if (values.regrade || values.restore || values["restore-trajectory"] || values["import-review"]) {
    const selectedOperations = [values.regrade, values.restore, values["restore-trajectory"], values["import-review"]].filter(Boolean).length;
    if (selectedOperations !== 1 || values.model || values.prompt || values["validate-only"] || values.resume) {
      throw new Error("INVALID_SNAPSHOT_OPERATION");
    }
    if (values["restore-trajectory"]) {
      if (!values.destination || !values.stage || !values.cycle || values.plan || values.reason ||
          (values.cycle !== "cycle-1" && values.cycle !== "cycle-2")) throw new Error("TRAJECTORY_RESTORE_ARGUMENTS_INVALID");
      const result = await restoreTrajectorySnapshot(values["restore-trajectory"], values.stage, values.cycle, values.destination);
      console.log(JSON.stringify(result, null, 2));
      return;
    }
    if (values["import-review"]) {
      if (!values.plan || !values.review || !values.reason || values.destination || values.stage || values.cycle) throw new Error("IMPORT_REVIEW_ARGUMENTS_INVALID");
      const path = resolve(values.plan);
      if (!basename(path).endsWith(".eval.json")) throw new Error("PLAN_EXTENSION_REQUIRED");
      const plan = JSON.parse(await readFile(path, "utf8")) as EvaluationPlan;
      const result = await importHumanReview(values["import-review"], plan, values.review, values.reason);
      console.log(JSON.stringify(result, null, 2));
      return;
    }
    if (values.restore) {
      if (!values.destination || values.plan || values.reason || values.review || values.stage || values.cycle) throw new Error("RESTORE_ARGUMENTS_INVALID");
      const result = await restoreTrialSnapshot(values.restore, values.destination);
      console.log(JSON.stringify(result, null, 2));
      return;
    }
    if (!values.plan || !values.reason || values.review || values.destination || values.stage || values.cycle) throw new Error("REGRADE_ARGUMENTS_INVALID");
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
      if (values.resume) throw new Error("RESUME_ARGUMENTS_INVALID");
      console.log("Evaluation plan is valid. Credentials were not loaded and no API requests were sent.");
      return;
    }
    // SPEC rule 8: no provider request without an explicit batch budget.
    if (typeof plan.batch?.maxTotalTokens !== "number") throw new Error("BATCH_TOKEN_CEILING_REQUIRED");
    if (values.resume && plan.execution?.kind === "trajectory") throw new Error("RESUME_UNSUPPORTED_FOR_TRAJECTORY");
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
    const result = await runEvaluation(plan, { outputRoot: values.out, resumeDirectory: values.resume });
    console.log(JSON.stringify({ directory: result.directory, summary: result.report.summary }, null, 2));
    if (!result.report.completed || result.report.summary.executionFailures || result.report.summary.evaluatorErrors || result.report.summary.resourceLimitRuns || result.report.summary.cleanupFailures || result.report.records.some(record => record.evaluation.status === "failed")) process.exitCode = 1;
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
