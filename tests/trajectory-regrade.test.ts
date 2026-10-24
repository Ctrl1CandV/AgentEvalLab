import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readFile, readdir, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { emptyExecution } from "../src/types.js";
import { validatePlan } from "../src/evaluation/validate.js";
import { runTrajectoryEvaluation } from "../src/evaluation/trajectory.js";
import { loadTrajectoryRecords, regradeTrajectory, snapshotScores } from "../src/evaluation/trajectory-regrade.js";
import type { EvaluationPlan, TrajectorySessionFactory } from "../src/evaluation/types.js";

// PLAN-007 WP0.4: a recorded trajectory's snapshots are graded again into new score runs; the record stays as it was,
// and loading the run overlays the latest grade of each snapshot.
test("re-grading a trajectory appends score runs and leaves the record unchanged", async () => {
  const plan = JSON.parse(await readFile("examples/eng-005-long-cycle.eval.json", "utf8")) as EvaluationPlan;
  validatePlan(plan);
  if (plan.execution?.kind !== "trajectory") throw new Error("test plan must use trajectory policy");
  plan.budget.maxModelCalls = 2;
  plan.execution.stageBudget.maxModelCalls = 2;
  const outputRoot = await mkdtemp(join(tmpdir(), "eng005-trajectory-regrade-"));
  const sessionFactory: TrajectorySessionFactory = () => ({
    async send() { return { ...emptyExecution(), output: "candidate response", modelCalls: 1, turns: 1 }; },
    async dispose() {},
  });
  try {
    const result = await runTrajectoryEvaluation(plan, { outputRoot, sessionFactory });
    const record = result.report.records[0]!;
    const trial = join(result.directory, record.id);
    const recordBefore = await readFile(join(trial, "trajectory.json"), "utf8");
    const reportBefore = await readFile(join(result.directory, "report.json"), "utf8");
    const before = await snapshotScores(trial);
    const graded = record.stages.flatMap(stage => stage.cycles.filter(cycle => cycle.privateGrade)).length;
    assert.ok(graded >= 2, "the fixture grades at least two snapshots");

    const final = await regradeTrajectory(trial, plan, "test: the final snapshot", "final");
    assert.equal(final.length, 1);
    const all = await regradeTrajectory(trial, plan, "test: every snapshot", "all");
    assert.equal(all.length, graded);
    const after = await snapshotScores(trial);
    assert.equal(after.length, before.length + graded + 1);
    assert.ok(after.every(score => score.graderVersion), "every score run names its grader version");
    assert.equal(await readFile(join(trial, "trajectory.json"), "utf8"), recordBefore, "the trajectory record is never rewritten");
    assert.equal(await readFile(join(result.directory, "report.json"), "utf8"), reportBefore, "the run report is never rewritten");
    assert.ok(!(await readdir(join(trial, "score-runs"))).some(name => name.startsWith(".pending-")));

    const overlaid = await loadTrajectoryRecords(result.directory);
    const lastScore = JSON.parse(await readFile(join(trial, "score-runs", all.at(-1)!.scoreRunId, "score.json"), "utf8")) as { previousScoreRunId: string | null; reason: string };
    assert.equal(lastScore.reason, "test: every snapshot");
    assert.ok(lastScore.previousScoreRunId, "a re-grade names the score run it follows");
    const lastCycle = overlaid[0]!.stages.flatMap(stage => stage.cycles).filter(cycle => cycle.privateGrade).at(-1)!;
    assert.deepEqual(lastCycle.privateGrade, all.at(-1)!.evaluation);
    await assert.rejects(regradeTrajectory(trial, plan, ""), /REGRADE_REASON_REQUIRED/);
  } finally {
    await rm(outputRoot, { recursive: true, force: true });
  }
});
