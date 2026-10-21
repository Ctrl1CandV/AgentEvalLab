// Trivial-agent baseline (ABC R.13): run a plan end to end with an agent that makes no request, calls no
// tool, and gives an empty answer. It exercises workspaces, the sandbox, graders and reports offline, and
// shows what a task awards to doing nothing. No credentials are loaded and no API request is sent.
// Trajectory plans get a session that answers every stage and repair prompt with nothing.
// Usage: node --import tsx scripts/null-agent-baseline.ts plan.eval.json [--out runs/baselines]
import { readFile } from "node:fs/promises";
import { basename, resolve } from "node:path";
import { parseArgs } from "node:util";
import { runEvaluation } from "../src/evaluation/run.js";
import { runTrajectoryEvaluation } from "../src/evaluation/trajectory.js";
import { validatePlan } from "../src/evaluation/validate.js";
import type { EvaluationPlan } from "../src/evaluation/types.js";
import { emptyExecution } from "../src/types.js";

const { values, positionals } = parseArgs({ allowPositionals: true, options: { out: { type: "string", default: "runs/baselines" } } });
const path = resolve(positionals[0] ?? "");
if (!basename(path).endsWith(".eval.json")) throw new Error("PLAN_EXTENSION_REQUIRED");
const plan = JSON.parse(await readFile(path, "utf8")) as EvaluationPlan;
validatePlan(plan);
const nullPlan = { ...plan, name: `${plan.name}-null-agent` };
if (plan.execution?.kind === "trajectory") {
  const result = await runTrajectoryEvaluation(nullPlan, {
    outputRoot: values.out!,
    sessionFactory: () => ({ send: async () => ({ ...emptyExecution(), output: "" }), dispose: async () => {} }),
  });
  const passing = result.report.records.flatMap(record => record.stages.flatMap(stage => stage.cycles.flatMap(cycle =>
    (cycle.privateGrade?.checks ?? []).filter(check => check.passed === true).map(check => `${stage.stageId}/${cycle.cycleId}/${check.id}`))));
  console.log(JSON.stringify({ directory: result.directory, trajectories: result.report.recordedRuns, passingChecks: passing }, null, 2));
  if (passing.length) process.exitCode = 1;
} else {
  const result = await runEvaluation(nullPlan, {
    outputRoot: values.out!,
    runner: async () => ({ ...emptyExecution(), output: "" }),
  });
  const passed = result.report.byTask.filter(row => row.passes > 0).map(row => `${row.caseId} ${row.model}`);
  console.log(JSON.stringify({ directory: result.directory, trials: result.report.recordedRuns, tasksWithAnyPass: passed }, null, 2));
  if (passed.length) process.exitCode = 1;
}
