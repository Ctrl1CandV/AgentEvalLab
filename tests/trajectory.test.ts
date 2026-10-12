import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { cp, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { AssistantMessageEventStream } from "@earendil-works/pi-ai/utils/event-stream";
import { createPiSession } from "../src/harness/pi.js";
import { parseModel } from "../src/config.js";
import { emptyExecution } from "../src/types.js";
import { validatePlan } from "../src/evaluation/validate.js";
import { runTrajectoryEvaluation } from "../src/evaluation/trajectory.js";
import { restoreTrajectorySnapshot } from "../src/evaluation/trajectory-snapshot.js";
import type { EvaluationPlan, TrajectorySessionFactory } from "../src/evaluation/types.js";

const model = parseModel("anthropic:claude-sonnet-4-6");

test("Pi trajectory session carries transcript and request context across sends", async () => {
  const observed: string[][] = [];
  let toolFactoryCalls = 0;
  const session = createPiSession(model, {
    apiKey: "offline-session-test-key",
    createTools: () => { toolFactoryCalls++; return []; },
    stream: (selectedModel, context) => {
      const userTexts = context.messages.filter(message => message.role === "user")
        .flatMap(message => typeof message.content === "string" ? [message.content] :
          message.content.flatMap(block => block.type === "text" ? [block.text] : []));
      observed.push(userTexts);
      const message = {
        role: "assistant" as const,
        content: [{ type: "text" as const, text: `responses-so-far:${observed.length}` }],
        api: selectedModel.api,
        provider: selectedModel.provider,
        model: selectedModel.id,
        usage: { input: 4, output: 3, cacheRead: 0, cacheWrite: 0, totalTokens: 7,
          cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
        stopReason: "stop" as const,
        timestamp: Date.now(),
      };
      const stream = new AssistantMessageEventStream();
      stream.push({ type: "start", partial: { ...message, content: [], stopReason: "pending" } });
      stream.push({ type: "done", reason: "stop", message });
      return stream;
    },
  });
  const emitted: Array<{ type: string; details?: Record<string, unknown> }> = [];
  const emit = async (type: string, _counts?: Record<string, number>, details?: Record<string, unknown>) => { emitted.push({ type, details }); };
  const budget = { timeoutMs: 5_000, maxTurns: 2, maxModelCalls: 2, maxToolCalls: 0, maxOutputTokensPerCall: 64, maxOutputChars: 1_000 };
  try {
    const first = await session.send({ prompt: "stage one", systemPrompt: "fixed system" }, budget, emit, { stageId: "S1", cycleId: "cycle-1" });
    const second = await session.send({ prompt: "repair one", systemPrompt: "fixed system" }, budget, emit, { stageId: "S1", cycleId: "cycle-2" });
    assert.equal(first.status, "done");
    assert.equal(second.status, "done");
    assert.deepEqual(observed[0], ["stage one"]);
    assert.deepEqual(observed[1], ["stage one", "repair one"]);
    assert.equal(toolFactoryCalls, 1);
    const requests = emitted.filter(event => event.type === "model_request_started").map(event => event.details);
    assert.deepEqual(requests.map(request => [request?.stageId, request?.cycleId]), [["S1", "cycle-1"], ["S1", "cycle-2"]]);
  } finally { await session.dispose(); }
  await assert.rejects(session.send({ prompt: "after close" }, budget, emit, { stageId: "S2", cycleId: "cycle-1" }), /SESSION_DISPOSED/);
});

async function containsScoreRuns(root: string): Promise<boolean> {
  for (const entry of await readdir(root, { withFileTypes: true })) {
    if (entry.isDirectory() && entry.name === "score-runs") return true;
    if (entry.isDirectory() && await containsScoreRuns(join(root, entry.name))) return true;
  }
  return false;
}

test("trajectory releases stages in order, repairs once, and grades only after candidate stops", async () => {
  const plan = JSON.parse(await readFile("examples/eng-005-long-cycle.eval.json", "utf8")) as EvaluationPlan;
  validatePlan(plan);
  if (plan.execution?.kind !== "trajectory") throw new Error("test plan must use trajectory policy");
  plan.budget.maxModelCalls = 3;
  plan.execution.stageBudget.maxModelCalls = 3;
  const outputRoot = await mkdtemp(join(tmpdir(), "eng005-trajectory-test-"));
  const restoreRoot = await mkdtemp(join(tmpdir(), "eng005-trajectory-restore-test-"));
  const seen: Array<{ stageId: string; cycleId: string; prompt: string; workspacePath: string; maxModelCalls: number }> = [];
  let disposed = false;
  let sessionCreations = 0;
  const sessionFactory: TrajectorySessionFactory = () => {
    sessionCreations++;
    return {
      async send(input, budget, _emit, context) {
        seen.push({ stageId: context.stageId, cycleId: context.cycleId, prompt: input.prompt, workspacePath: input.workspacePath, maxModelCalls: budget.maxModelCalls });
        assert.equal(await containsScoreRuns(outputRoot), false, "private grader started while the candidate session was still active");
        const stageText = await readFile(join(input.workspacePath, "stages", context.stageId, "instruction.md"), "utf8");
        assert.ok(stageText.startsWith(`# ${context.stageId}`));
        const nextStage = `S${Number(context.stageId.slice(1)) + 1}`;
        if (Number(context.stageId.slice(1)) < 5) {
          await assert.rejects(readFile(join(input.workspacePath, "stages", nextStage, "instruction.md")));
        }
        return { ...emptyExecution(), output: "candidate response", modelCalls: 1, turns: 1 };
      },
      async dispose() { disposed = true; },
    };
  };
  try {
    const result = await runTrajectoryEvaluation(plan, { outputRoot, sessionFactory });
    const trajectory = result.report.records[0]!;
    assert.equal(disposed, true);
    assert.equal(sessionCreations, 1);
    assert.deepEqual(seen.map(item => [item.stageId, item.cycleId]), [["S1", "cycle-1"], ["S1", "cycle-2"], ["S2", "cycle-1"]]);
    assert.ok(seen[1]!.prompt.includes("Public check feedback"));
    assert.equal(new Set(seen.map(item => item.workspacePath)).size, 1);
    assert.deepEqual(seen.map(item => item.maxModelCalls), [3, 2, 1]);
    assert.equal(trajectory.status, "stopped");
    assert.equal(trajectory.stopReason, "BUDGET_EXHAUSTED");
    assert.deepEqual(trajectory.stages.map(stage => stage.status), ["completed", "stopped", "not_reached", "not_reached", "not_reached"]);
    assert.equal(trajectory.budget.used.maxModelCalls, 3);
    assert.equal(trajectory.stages[0]!.cycles[0]!.publicCheck?.status, "failed");
    assert.equal(trajectory.stages[0]!.cycles[1]!.publicCheck?.status, "failed");
    assert.equal(trajectory.stages[0]!.cycles[0]!.privateGrade?.status, "failed");
    assert.equal(trajectory.metrics?.publicRepair.initialFailures, 2);
    assert.equal(trajectory.metrics?.publicRepair.repairPrompts, 1);
    assert.equal(trajectory.metrics?.publicRepair.attemptedFailures, 1);
    assert.equal(trajectory.metrics?.publicRepair.repaired, 0);
    const firstSnapshot = JSON.parse(await readFile(join(result.directory, trajectory.id, "snapshots", "S1-cycle-1", "data", "work-orders.json"), "utf8"));
    assert.equal(firstSnapshot.version, 1);
    const snapshotManifest = trajectory.stages[0]!.cycles[0]!.snapshot!.manifest;
    const restored = await restoreTrajectorySnapshot(join(result.directory, trajectory.id), "S1", "cycle-1", join(restoreRoot, "checkpoint"));
    assert.equal(restored.sha256, snapshotManifest.sha256);
    assert.deepEqual(JSON.parse(await readFile(join(restored.destination, "data", "work-orders.json"), "utf8")), firstSnapshot);
    await assert.rejects(restoreTrajectorySnapshot(join(result.directory, trajectory.id), "S1", "cycle-1", join(restoreRoot, "checkpoint")), /RESTORE_DESTINATION_EXISTS/);
    await assert.rejects(restoreTrajectorySnapshot(join(result.directory, trajectory.id), "S1", "cycle-1", join(result.directory, "restore-inside-run")), /RESTORE_DESTINATION_INSIDE_RUN/);
    await assert.rejects(restoreTrajectorySnapshot(join(result.directory, trajectory.id), "S9", "cycle-1", join(restoreRoot, "missing")), /TRAJECTORY_SNAPSHOT_NOT_FOUND/);
    const released = await readFile(join(result.directory, trajectory.id, "trajectory.json"), "utf8");
    assert.ok(released.includes("not_reached"));
    assert.equal(await containsScoreRuns(outputRoot), true);
  } finally {
    await rm(outputRoot, { recursive: true, force: true });
    await rm(restoreRoot, { recursive: true, force: true });
  }
});

test("trajectory harness completes five stages with a calibrated reference snapshot and no forced repair", async () => {
  const plan = JSON.parse(await readFile("examples/eng-005-long-cycle.eval.json", "utf8")) as EvaluationPlan;
  validatePlan(plan);
  const testRoot = await mkdtemp(join(tmpdir(), "eng005-reference-trajectory-test-"));
  try {
    for (const referenceName of ["ref-a", "ref-b"]) {
      const referencePath = resolve(`task-library/calibration/eng-005-long-cycle-maintenance/references/${referenceName}`);
      let expectedSignature: string | undefined;
      for (let repetition = 1; repetition <= 3; repetition++) {
        const outputRoot = join(testRoot, `runs-${referenceName}-${repetition}`);
        const sent: Array<{ stageId: string; cycleId: string; workspacePath: string }> = [];
        let disposed = false;
        const sessionFactory: TrajectorySessionFactory = () => ({
          async send(input, _budget, _emit, context) {
            sent.push({ stageId: context.stageId, cycleId: context.cycleId, workspacePath: input.workspacePath });
            if (context.stageId === "S1") await cp(referencePath, input.workspacePath, { recursive: true, force: true });
            return { ...emptyExecution(), output: `replayed ${context.stageId}`, modelCalls: 1, turns: 1 };
          },
          async dispose() { disposed = true; },
        });
        const result = await runTrajectoryEvaluation(plan, { outputRoot, sessionFactory });
        const trajectory = result.report.records[0]!;
        assert.equal(disposed, true, `${referenceName}:${repetition}`);
        assert.deepEqual(sent.map(item => [item.stageId, item.cycleId]), [
          ["S1", "cycle-1"], ["S2", "cycle-1"], ["S3", "cycle-1"], ["S4", "cycle-1"], ["S5", "cycle-1"],
        ], `${referenceName}:${repetition}`);
        assert.equal(new Set(sent.map(item => item.workspacePath)).size, 1, `${referenceName}:${repetition}`);
        assert.equal(trajectory.status, "completed", `${referenceName}:${repetition}`);
        assert.deepEqual(trajectory.stages.map(stage => stage.status), ["completed", "completed", "completed", "completed", "completed"], `${referenceName}:${repetition}`);
        assert.ok(trajectory.stages.every(stage => stage.cycles.length === 1 && stage.cycles[0]!.publicCheck?.status === "passed"), `${referenceName}:${repetition}`);
        assert.ok(trajectory.stages.every(stage => stage.cycles[0]!.privateGrade?.status === "passed"), `${referenceName}:${repetition}`);
        assert.equal(trajectory.metrics?.finalDeliveryAccepted, true, `${referenceName}:${repetition}`);
        assert.equal(trajectory.metrics?.allStageStableDelivery, true, `${referenceName}:${repetition}`);
        assert.equal(trajectory.metrics?.stageCompletion.completed, 5, `${referenceName}:${repetition}`);
        const signature = JSON.stringify({
          status: trajectory.status,
          stages: trajectory.stages.map(stage => ({ stageId: stage.stageId, status: stage.status,
            cycles: stage.cycles.map(cycle => ({ cycleId: cycle.cycleId, publicStatus: cycle.publicCheck?.status,
              privateStatus: cycle.privateGrade?.status, checks: cycle.privateGrade?.checks })) })),
          metrics: trajectory.metrics,
        });
        if (expectedSignature === undefined) expectedSignature = signature;
        else assert.equal(signature, expectedSignature, `${referenceName}:non-deterministic repetition ${repetition}`);
      }
    }
  } finally { await rm(testRoot, { recursive: true, force: true }); }
});

test("public stage checkers expose only their own stage logic", async () => {
  const checkers = new Map<string, string>();
  for (let number = 1; number <= 5; number++) {
    const stageId = `S${number}`;
    checkers.set(stageId, await readFile(
      `task-library/candidates/eng-005-long-cycle-maintenance/stages/${stageId}/public/checker.py`, "utf8"));
  }
  for (let number = 1; number <= 5; number++) {
    const stageId = `S${number}`;
    const source = checkers.get(stageId)!;
    assert.match(source, new RegExp(`def check_${stageId.toLowerCase()}\\(`));
    for (let other = 1; other <= 5; other++) {
      if (other !== number) assert.doesNotMatch(source, new RegExp(`def check_s${other}\\(`));
    }
  }
  assert.doesNotMatch(checkers.get("S1")!, /depends|state_migrated|UNKNOWN_COMMAND|FIX-01/);
  assert.doesNotMatch(checkers.get("S2")!, /state_migrated|UNKNOWN_COMMAND|FIX-01/);
  assert.doesNotMatch(checkers.get("S3")!, /state_migrated|UNKNOWN_COMMAND|FIX-01/);
  assert.doesNotMatch(checkers.get("S4")!, /UNKNOWN_COMMAND|FINAL_PROTOCOL_OR_DOCS_MISMATCH/);
});

test("public checker mutations stay outside the archived trajectory snapshot", async () => {
  const plan = JSON.parse(await readFile("examples/eng-005-long-cycle.eval.json", "utf8")) as EvaluationPlan;
  const fixtureRoot = await mkdtemp(join(tmpdir(), "eng005-checker-isolation-test-"));
  const packagePath = join(fixtureRoot, "package");
  const referencePath = resolve("task-library/calibration/eng-005-long-cycle-maintenance/references/ref-a");
  const restoreRoot = join(fixtureRoot, "restored");
  await cp(resolve("task-library/candidates/eng-005-long-cycle-maintenance"), packagePath, { recursive: true });
  const manifestPath = join(packagePath, "manifest.json");
  const manifest = JSON.parse(await readFile(manifestPath, "utf8")) as {
    stages: Array<{ id: string; publicChecker: { executable: string; args: string[]; timeoutMs: number; maxOutputBytes: number } }>;
  };
  const checker = manifest.stages.find(stage => stage.id === "S1")!.publicChecker;
  const code = "import argparse,json,sys;from pathlib import Path;p=argparse.ArgumentParser();p.add_argument('--submission');p.add_argument('--stage');a=p.parse_args(sys.argv[2:]);(Path(a.submission)/'data/work-orders.json').unlink();print(json.dumps(dict(schemaVersion=1,stageId='S1',status='passed',checks=[dict(id='public-s1',passed=True,reasonCode='OK',feedback='ok')])))";
  checker.executable = "python";
  checker.args = ["-c", code, "{entryPoint}", "--submission", "{submission}", "--stage", "S1"];
  checker.timeoutMs = 5_000;
  checker.maxOutputBytes = 1_000;
  await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
  const item = plan.cases[0]!;
  item.packagePath = packagePath;
  item.repository = { ...item.repository!, path: join(packagePath, "baseline") };
  item.packageManifestSha256 = createHash("sha256").update(await readFile(manifestPath)).digest("hex");
  validatePlan(plan);
  const outputRoot = join(fixtureRoot, "runs");
  const sessionFactory: TrajectorySessionFactory = () => ({
    async send(input, _budget, _emit, context) {
      if (context.stageId === "S1") await cp(referencePath, input.workspacePath, { recursive: true, force: true });
      return { ...emptyExecution(), output: `reference ${context.stageId}`, modelCalls: 1, turns: 1 };
    },
    async dispose() {},
  });
  try {
    const result = await runTrajectoryEvaluation(plan, { outputRoot, sessionFactory });
    const trajectory = result.report.records[0]!;
    const checkpoint = trajectory.stages[0]!.cycles[0]!;
    assert.equal(trajectory.status, "completed", `stop reason: ${trajectory.stopReason}`);
    assert.equal(checkpoint.publicCheck?.status, "passed");
    assert.equal(checkpoint.privateGrade?.status, "passed");
    const snapshotDirectory = join(result.directory, trajectory.id, checkpoint.snapshot!.path);
    assert.ok((await readFile(join(snapshotDirectory, "data", "work-orders.json"), "utf8")).includes("WO-101"));
    const restored = await restoreTrajectorySnapshot(join(result.directory, trajectory.id), "S1", "cycle-1", restoreRoot);
    assert.equal(restored.sha256, checkpoint.snapshot!.manifest.sha256);
  } finally { await rm(fixtureRoot, { recursive: true, force: true }); }
});

test("trajectory classifies public checker timeout, output, protocol, exit and spawn failures", async () => {
  const plan = JSON.parse(await readFile("examples/eng-005-long-cycle.eval.json", "utf8")) as EvaluationPlan;
  const fixtureRoot = await mkdtemp(join(tmpdir(), "eng005-checker-failure-test-"));
  const packagePath = join(fixtureRoot, "package");
  const sourcePackage = resolve("task-library/candidates/eng-005-long-cycle-maintenance");
  await cp(sourcePackage, packagePath, { recursive: true });
  const manifestPath = join(packagePath, "manifest.json");
  const manifest = JSON.parse(await readFile(manifestPath, "utf8")) as {
    stages: Array<{ id: string; publicChecker: { executable: string; args: string[]; timeoutMs: number; maxOutputBytes: number } }>;
  };
  const checker = manifest.stages.find(stage => stage.id === "S1")!.publicChecker;
  const item = plan.cases[0]!;
  item.packagePath = packagePath;
  item.repository = { ...item.repository!, path: join(packagePath, "baseline") };
  validatePlan(plan);
  const sessionFactory: TrajectorySessionFactory = () => ({
    async send() { return { ...emptyExecution(), output: "candidate answer", modelCalls: 1, turns: 1 }; },
    async dispose() {},
  });
  try {
    const scenarios = [
      { id: "timeout", executable: "python", code: "import time;time.sleep(1)", timeoutMs: 100, maxOutputBytes: 1_000, reason: "PUBLIC_CHECK_TIMEOUT" },
      { id: "output", executable: "python", code: "import sys;sys.stdout.write('x'*1000)", timeoutMs: 1_000, maxOutputBytes: 8, reason: "PUBLIC_CHECK_OUTPUT_LIMIT" },
      { id: "protocol", executable: "python", code: "import sys;sys.stdout.write(chr(123))", timeoutMs: 1_000, maxOutputBytes: 1_000, reason: "PUBLIC_CHECK_RESULT_INVALID_JSON" },
      { id: "exit", executable: "python", code: "raise SystemExit(3)", timeoutMs: 1_000, maxOutputBytes: 1_000, reason: "PUBLIC_CHECK_NONZERO_EXIT" },
      { id: "spawn", executable: join(fixtureRoot, "missing-checker.exe"), code: "pass", timeoutMs: 1_000, maxOutputBytes: 1_000, reason: "PUBLIC_CHECK_SPAWN_FAILED" },
    ];
    for (const scenario of scenarios) {
      checker.executable = scenario.executable;
      checker.args = ["-c", scenario.code, "{entryPoint}", "--submission", "{submission}"];
      checker.timeoutMs = scenario.timeoutMs;
      checker.maxOutputBytes = scenario.maxOutputBytes;
      const manifestBytes = `${JSON.stringify(manifest, null, 2)}\n`;
      await writeFile(manifestPath, manifestBytes, "utf8");
      item.packageManifestSha256 = createHash("sha256").update(manifestBytes).digest("hex");
      const outputRoot = join(fixtureRoot, `runs-${scenario.id}`);
      const result = await runTrajectoryEvaluation(plan, { outputRoot, sessionFactory });
      const trajectory = result.report.records[0]!;
      assert.equal(trajectory.status, "stopped", scenario.id);
      assert.equal(trajectory.stopReason, scenario.reason, scenario.id);
      assert.deepEqual(trajectory.stages.map(stage => stage.status), ["stopped", "not_reached", "not_reached", "not_reached", "not_reached"], scenario.id);
      assert.notEqual(trajectory.stages[0]!.cycles[0]!.snapshot, null, scenario.id);
      assert.equal(trajectory.stages[0]!.cycles[0]!.publicCheck, null, scenario.id);
      assert.equal(trajectory.stages[0]!.cycles[0]!.privateGrade?.status, "failed", scenario.id);
    }
  } finally { await rm(fixtureRoot, { recursive: true, force: true }); }
});

test("trajectory snapshot limits stop before public checking without fabricating a snapshot", async () => {
  const plan = JSON.parse(await readFile("examples/eng-005-long-cycle.eval.json", "utf8")) as EvaluationPlan;
  validatePlan(plan);
  plan.artifactLimits!.maxTrialBytes = 1;
  const outputRoot = await mkdtemp(join(tmpdir(), "eng005-snapshot-limit-test-"));
  const sessionFactory: TrajectorySessionFactory = () => ({
    async send() { return { ...emptyExecution(), output: "candidate answer", modelCalls: 1, turns: 1 }; },
    async dispose() {},
  });
  try {
    const result = await runTrajectoryEvaluation(plan, { outputRoot, sessionFactory });
    const trajectory = result.report.records[0]!;
    assert.equal(trajectory.status, "stopped");
    assert.equal(trajectory.stopReason, "ARTIFACT_TRIAL_SIZE_LIMIT");
    assert.equal(trajectory.stages[0]!.cycles[0]!.snapshot, null);
    assert.equal(trajectory.stages[0]!.cycles[0]!.publicCheck, null);
    assert.deepEqual(trajectory.stages.map(stage => stage.status), ["stopped", "not_reached", "not_reached", "not_reached", "not_reached"]);
    assert.equal(await containsScoreRuns(outputRoot), false);
  } finally { await rm(outputRoot, { recursive: true, force: true }); }

  const fileLimitRoot = await mkdtemp(join(tmpdir(), "eng005-snapshot-file-limit-test-"));
  const fileLimitPlan = JSON.parse(await readFile("examples/eng-005-long-cycle.eval.json", "utf8")) as EvaluationPlan;
  validatePlan(fileLimitPlan);
  fileLimitPlan.artifactLimits!.maxFiles = 1;
  try {
    const result = await runTrajectoryEvaluation(fileLimitPlan, { outputRoot: fileLimitRoot, sessionFactory });
    assert.equal(result.report.records[0]!.stopReason, "ARTIFACT_FILE_LIMIT");
    assert.equal(result.report.records[0]!.stages[0]!.cycles[0]!.snapshot, null);
  } finally { await rm(fileLimitRoot, { recursive: true, force: true }); }
});

test("trajectory provider failure stops before snapshot and does not create later stages", async () => {
  const plan = JSON.parse(await readFile("examples/eng-005-long-cycle.eval.json", "utf8")) as EvaluationPlan;
  validatePlan(plan);
  const outputRoot = await mkdtemp(join(tmpdir(), "eng005-provider-failure-test-"));
  const sessionFactory: TrajectorySessionFactory = () => ({
    async send() { return { ...emptyExecution(), status: "error", failureKind: "infrastructure", error: "PROVIDER_ERROR" }; },
    async dispose() {},
  });
  try {
    const result = await runTrajectoryEvaluation(plan, { outputRoot, sessionFactory });
    const trajectory = result.report.records[0]!;
    assert.equal(trajectory.status, "stopped");
    assert.equal(trajectory.stopReason, "PROVIDER_ERROR");
    assert.equal(trajectory.stages[0]!.cycles[0]!.snapshot, null);
    assert.deepEqual(trajectory.stages.map(stage => stage.status), ["stopped", "not_reached", "not_reached", "not_reached", "not_reached"]);
  } finally { await rm(outputRoot, { recursive: true, force: true }); }
});

test("trajectory event persistence failure remains explicit in the saved trial record", async () => {
  const plan = JSON.parse(await readFile("examples/eng-005-long-cycle.eval.json", "utf8")) as EvaluationPlan;
  validatePlan(plan);
  const outputRoot = await mkdtemp(join(tmpdir(), "eng005-event-failure-test-"));
  let trialId = "";
  const sessionFactory: TrajectorySessionFactory = (_model, id) => {
    trialId = id;
    return {
      async send(_input, _budget, emit) {
        const circular: Record<string, unknown> = {};
        circular.self = circular;
        await emit("tool_trace", undefined, circular);
        return { ...emptyExecution(), output: "unreachable", modelCalls: 1, turns: 1 };
      },
      async dispose() {},
    };
  };
  try {
    await assert.rejects(runTrajectoryEvaluation(plan, { outputRoot, sessionFactory }), /EVENT_SINK_FAILED/);
    const experimentId = (await readdir(outputRoot))[0]!;
    const trialDirectory = join(outputRoot, experimentId, trialId);
    const saved = JSON.parse(await readFile(join(trialDirectory, "trajectory.json"), "utf8")) as {
      status: string; stopReason: string; cleanup: string; stages: Array<{ status: string }>;
    };
    assert.equal(saved.status, "stopped");
    assert.equal(saved.stopReason, "EVENT_SINK_FAILED");
    assert.equal(saved.cleanup, "cleaned");
    assert.deepEqual(saved.stages.map(stage => stage.status), ["stopped", "not_reached", "not_reached", "not_reached", "not_reached"]);
    assert.ok(await readFile(join(trialDirectory, "result.json"), "utf8"));
  } finally { await rm(outputRoot, { recursive: true, force: true }); }
});

test("trajectory disposal failure is reflected in cleanup status", async () => {
  const plan = JSON.parse(await readFile("examples/eng-005-long-cycle.eval.json", "utf8")) as EvaluationPlan;
  validatePlan(plan);
  const outputRoot = await mkdtemp(join(tmpdir(), "eng005-dispose-failure-test-"));
  const sessionFactory: TrajectorySessionFactory = () => ({
    async send() { return { ...emptyExecution(), status: "timeout", failureKind: "budget", error: "TIMEOUT" }; },
    async dispose() { throw new Error("synthetic dispose fault"); },
  });
  try {
    const result = await runTrajectoryEvaluation(plan, { outputRoot, sessionFactory });
    const trajectory = result.report.records[0]!;
    assert.equal(trajectory.status, "stopped");
    assert.equal(trajectory.stopReason, "TIMEOUT");
    assert.equal(trajectory.cleanup, "error");
    assert.deepEqual(trajectory.stages.map(stage => stage.status), ["stopped", "not_reached", "not_reached", "not_reached", "not_reached"]);
  } finally { await rm(outputRoot, { recursive: true, force: true }); }
});

test("trajectory records workspace cleanup failure after preserving the stopped run", async () => {
  const plan = JSON.parse(await readFile("examples/eng-005-long-cycle.eval.json", "utf8")) as EvaluationPlan;
  validatePlan(plan);
  const outputRoot = await mkdtemp(join(tmpdir(), "eng005-workspace-cleanup-test-"));
  let workspacePath = "";
  const sessionFactory: TrajectorySessionFactory = () => ({
    async send(input) {
      workspacePath = input.workspacePath;
      return { ...emptyExecution(), status: "timeout", failureKind: "budget", error: "TIMEOUT" };
    },
    async dispose() {
      const ownedRoot = dirname(workspacePath);
      await writeFile(join(ownedRoot, "cleanup-test-sentinel"), "force rmdir to report its real failure", "utf8");
    },
  });
  try {
    const result = await runTrajectoryEvaluation(plan, { outputRoot, sessionFactory });
    const trajectory = result.report.records[0]!;
    assert.equal(trajectory.status, "stopped");
    assert.equal(trajectory.stopReason, "TIMEOUT");
    assert.equal(trajectory.cleanup, "error");
  } finally {
    const ownedRoot = workspacePath ? dirname(workspacePath) : "";
    if (ownedRoot && basename(ownedRoot).startsWith("agent-eval-")) await rm(ownedRoot, { recursive: true, force: true });
    await rm(outputRoot, { recursive: true, force: true });
  }
});
