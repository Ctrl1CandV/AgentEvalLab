import { spawnSync } from "node:child_process";
import { createHash, randomUUID } from "node:crypto";
import { cp, mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const calibrationDirectory = dirname(fileURLToPath(import.meta.url));
const repositoryRoot = resolve(calibrationDirectory, "../../..");
const packageRoot = join(repositoryRoot, "task-library/candidates/eng-005-long-cycle-maintenance");
const manifestBytes = await readFile(join(packageRoot, "manifest.json"));
const manifest = JSON.parse(manifestBytes.toString("utf8"));
const manifestSha256 = createHash("sha256").update(manifestBytes).digest("hex");
const referencesRoot = join(calibrationDirectory, "references");
// Calibrate the same sandboxed path that real runs use.
const sandboxLauncher = join(repositoryRoot, "scripts", "sandbox_exec.py");

function run(executable, args, cwd, timeout = 30_000) {
  const result = spawnSync(executable, args, { cwd, encoding: "utf8", timeout, maxBuffer: 2_000_000,
    env: { ...process.env, PYTHONUTF8: "1" } });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`CALIBRATION_COMMAND_FAILED:${executable}:${args[0]}:${result.status}:${result.stderr ?? ""}`);
  return result.stdout;
}

function publicCheck(submission, stageId) {
  const stage = manifest.stages.find(item => item.id === stageId);
  const output = run("python3", [join(packageRoot, ...stage.publicChecker.entryPoint.split("/")), "--submission", submission, "--stage", stageId, "--sandbox-launcher", sandboxLauncher], repositoryRoot, stage.publicChecker.timeoutMs + 2_000);
  const result = JSON.parse(output);
  if (result.status !== "passed" || result.stageId !== stageId || JSON.stringify(result.checks.map(item => item.id).sort()) !== JSON.stringify([...stage.publicChecker.checkIds].sort())) {
    throw new Error(`PUBLIC_REFERENCE_FAILED:${stageId}:${JSON.stringify(result)}`);
  }
  return result;
}

async function privateGrade(submission, stageId, cycleId = "cycle-1", mustPass = true) {
  const stage = manifest.stages.find(item => item.id === stageId);
  const temporary = await mkdtemp(join(tmpdir(), "eng005-calibration-"));
  try {
    const evidenceRoot = join(temporary, "evidence");
    await mkdir(evidenceRoot);
    const requestPath = join(temporary, "request.json");
    const resultPath = join(temporary, "result.json");
    const requestId = randomUUID();
    await writeFile(requestPath, JSON.stringify({
      schemaVersion: 1,
      requestId,
      trialId: `calibration.${stageId}.${cycleId}`,
      task: { id: manifest.id, version: manifest.version, manifestSha256 },
      submission: { snapshotId: `${stageId}-${cycleId}`, directory: submission, manifestSha256: "0".repeat(64) },
      answerRef: null,
      traceRef: null,
      context: { stageId, cycleId, activeRequirementIds: stage.activeRequirementIds },
      evidenceRoot,
      sandbox: { launcher: sandboxLauncher },
    }), "utf8");
    run("python3", [join(packageRoot, ...manifest.grader.entryPoint.split("/")), "--request", requestPath, "--result", resultPath], repositoryRoot, 60_000);
    const result = JSON.parse(await readFile(resultPath, "utf8"));
    const expected = manifest.requirements.filter(item => stage.activeRequirementIds.includes(item.id)).flatMap(item => item.checkIds).sort();
    const actual = result.checks.map(item => item.id).sort();
    if (result.requestId !== requestId || result.taskVersion !== manifest.version || result.graderVersion !== manifest.grader.version ||
        result.gradingStatus !== "completed" || JSON.stringify(actual) !== JSON.stringify(expected) ||
        (mustPass && result.checks.some(item => item.status !== "pass"))) {
      throw new Error(`PRIVATE_REFERENCE_FAILED:${stageId}:${JSON.stringify(result.checks)}`);
    }
    return result.checks.map(item => [item.id, item.status]);
  } finally { await rm(temporary, { recursive: true, force: true }); }
}

const report = { schemaVersion: 1, taskId: manifest.id, taskVersion: manifest.version, manifestSha256,
  runtime: process.version, references: [], mutants: {} };
for (const name of ["ref-a", "ref-b"]) {
  const root = join(referencesRoot, name);
  const repetitions = [];
  for (let repetition = 1; repetition <= 3; repetition++) {
    const checkpoints = [];
    for (const stage of manifest.stages) {
      const publicResult = publicCheck(root, stage.id);
      const hiddenChecks = await privateGrade(root, stage.id);
      checkpoints.push({ stageId: stage.id, publicStatus: publicResult.status, privateChecks: hiddenChecks });
    }
    const signature = JSON.stringify(checkpoints);
    if (repetitions.length && repetitions[0].signature !== signature) throw new Error(`REFERENCE_NONDETERMINISTIC:${name}`);
    repetitions.push({ repetition, signature, checkpoints });
  }
  report.references.push({ name, repetitions: repetitions.map(({ repetition, checkpoints }) => ({ repetition, checkpoints })) });
}

const scratch = await mkdtemp(join(tmpdir(), "eng005-mutants-"));
try {
  const refA = join(referencesRoot, "ref-a");
  const regression = join(scratch, "s4-query-regression");
  await cp(refA, regression, { recursive: true });
  const servicePath = join(regression, "src/service.ts");
  const service = await readFile(servicePath, "utf8");
  const filter = "const selected = store.workOrders.filter(item => query.status === undefined || item.status === query.status);";
  if (!service.includes(filter)) throw new Error("MUTANT_ANCHOR_NOT_FOUND:QUERY_FILTER");
  await writeFile(servicePath, service.replace(filter, "const selected = store.workOrders;"), "utf8");
  const regressionGrade = await privateGrade(regression, "S4", "cycle-1", false);
  if (!regressionGrade.some(([id, status]) => id === "query.filter" && status === "fail")) throw new Error("S4_REGRESSION_NOT_DETECTED");
  const repairedFinal = await privateGrade(refA, "S5");
  if (!repairedFinal.every(([, status]) => status === "pass")) throw new Error("LATE_REPAIR_FINAL_REFERENCE_FAILED");
  report.mutants.lateRepair = { S4QueryFilter: regressionGrade.find(([id]) => id === "query.filter")?.[1],
    S5QueryFilter: repairedFinal.find(([id]) => id === "query.filter")?.[1] };

  const dataLoss = join(scratch, "migration-data-loss");
  await cp(refA, dataLoss, { recursive: true });
  const storePath = join(dataLoss, "src/store.ts");
  const store = await readFile(storePath, "utf8");
  const migration = "workOrders: store.workOrders.map(order => ({ ...order, dependsOn: [...(order.dependsOn ?? [])] })),";
  if (!store.includes(migration)) throw new Error("MUTANT_ANCHOR_NOT_FOUND:MIGRATION");
  await writeFile(storePath, store.replace(migration, 'workOrders: store.workOrders.map(order => ({ ...order, description: "", dependsOn: [] })),'), "utf8");
  const migrationGrade = await privateGrade(dataLoss, "S4", "cycle-1", false);
  if (!migrationGrade.some(([id, status]) => id === "migration.preserve" && status === "fail")) throw new Error("MIGRATION_DATA_LOSS_NOT_DETECTED");
  report.mutants.migrationDataLoss = { preserve: migrationGrade.find(([id]) => id === "migration.preserve")?.[1] };

  const tampered = join(scratch, "tampered-checker-copy");
  await cp(refA, tampered, { recursive: true });
  await mkdir(join(tampered, "stages/S1/public"), { recursive: true });
  await writeFile(join(tampered, "stages/S1/public/checker.py"), "print('{\\\"schemaVersion\\\":1,\\\"stageId\\\":\\\"S1\\\",\\\"status\\\":\\\"passed\\\",\\\"checks\\\":[]}')\n", "utf8");
  report.mutants.candidateCheckerTampering = publicCheck(tampered, "S1").status;
  await mkdir(join(tampered, "tests"), { recursive: true });
  await writeFile(join(tampered, "tests/forged-self-test.mjs"), "console.log('all tests passed')\n", "utf8");
  const forgedTestGrade = await privateGrade(tampered, "S5");
  report.mutants.forgedSelfTests = { result: forgedTestGrade.every(([, status]) => status === "pass") ? "ignored" : "unexpected" };
  if (report.mutants.candidateCheckerTampering !== "passed" || report.mutants.forgedSelfTests.result !== "ignored") throw new Error("TRUST_BOUNDARY_CALIBRATION_FAILED");

  const timeoutCandidate = join(scratch, "candidate-timeout");
  await cp(refA, timeoutCandidate, { recursive: true });
  await writeFile(join(timeoutCandidate, "src/cli.ts"),
    `${await readFile(join(timeoutCandidate, "src/cli.ts"), "utf8")}\nif (process.argv[2] === "create") setInterval(() => {}, 1000);\n`, "utf8");
  const timeoutGrade = await privateGrade(timeoutCandidate, "S1", "cycle-1", false);
  const createStatus = timeoutGrade.find(([id]) => id === "base.create")?.[1];
  report.mutants.candidateTimeout = { gradingStatus: "completed", check: "base.create", result: createStatus };
  if (createStatus !== "fail") throw new Error("CANDIDATE_TIMEOUT_NOT_SCORED_AS_FAILURE");
} finally { await rm(scratch, { recursive: true, force: true }); }

const logPath = join(calibrationDirectory, "logs", "acceptance-self-calibration.json");
await mkdir(dirname(logPath), { recursive: true });
await writeFile(logPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
console.log(JSON.stringify({ status: "passed", references: report.references.map(item => ({ name: item.name, repetitions: item.repetitions.length })), mutants: report.mutants, logPath }, null, 2));
