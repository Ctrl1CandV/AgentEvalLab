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
    run("python3", [join(packageRoot, ...manifest.grader.entryPoint.split("/")), "--request", requestPath, "--result", resultPath], repositoryRoot, 300_000);
    const result = JSON.parse(await readFile(resultPath, "utf8"));
    const expected = manifest.requirements.filter(item => stage.activeRequirementIds.includes(item.id)).flatMap(item => item.checkIds).sort();
    const actual = result.checks.map(item => item.id).sort();
    // The references are the speed bar, so the fastest rungs depend on timing noise; the plan quality rungs rank plans
    // above the references'. Both are recorded, not required.
    const required = result.checks.filter(item => !TIMING_RUNGS.includes(item.id) && !item.id.startsWith("plan.quality-"));
    if (result.requestId !== requestId || result.taskVersion !== manifest.version || result.graderVersion !== manifest.grader.version ||
        result.gradingStatus !== "completed" || JSON.stringify(actual) !== JSON.stringify(expected) ||
        (mustPass && required.some(item => item.status !== "pass"))) {
      throw new Error(`PRIVATE_REFERENCE_FAILED:${stageId}:${JSON.stringify(result.checks)}`);
    }
    return result.checks.map(item => [item.id, item.status]);
  } finally { await rm(temporary, { recursive: true, force: true }); }
}

const TIMING_RUNGS = ["scale.speed-1.1", "scale.speed-0.75"];
/** A grade without the timing rungs, for comparing repetitions. */
const stable = checks => checks.filter(([id]) => !TIMING_RUNGS.includes(id));

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
    const signature = JSON.stringify(checkpoints.map(point => ({ ...point, privateChecks: stable(point.privateChecks) })));
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

  // Hidden checks added in 0.3.0 catch common shortcuts that the public checkers let through.
  const descReverse = join(scratch, "desc-reverses-ties");
  await cp(refA, descReverse, { recursive: true });
  const sortPath = join(descReverse, "src/service.ts");
  const sortSource = await readFile(sortPath, "utf8");
  const comparator = `    if (query.order === "desc") comparison *= -1;
    return comparison || (left.id < right.id ? -1 : left.id > right.id ? 1 : 0);`;
  if (!sortSource.includes(comparator)) throw new Error("MUTANT_ANCHOR_NOT_FOUND:SORT");
  await writeFile(sortPath, sortSource.replace(comparator, `    const result = comparison || (left.id < right.id ? -1 : left.id > right.id ? 1 : 0);
    return query.order === "desc" ? -result : result;`), "utf8");
  const descGrade = await privateGrade(descReverse, "S1", "cycle-1", false);
  const descFailures = descGrade.filter(([, status]) => status === "fail").map(([id]) => id);
  if (JSON.stringify(descFailures) !== JSON.stringify(["query.desc-ties"])) throw new Error(`DESC_TIES_NOT_DETECTED:${descFailures}`);
  report.mutants.descReversesTies = { failed: descFailures };

  const directCycle = join(scratch, "direct-cycles-only");
  await cp(refA, directCycle, { recursive: true });
  const cyclePath = join(directCycle, "src/service.ts");
  const cycleSource = await readFile(cyclePath, "utf8");
  const cycleTest = "if (reaches(store, prerequisiteId, id))";
  if (!cycleSource.includes(cycleTest)) throw new Error("MUTANT_ANCHOR_NOT_FOUND:CYCLE");
  await writeFile(cyclePath, cycleSource.replace(cycleTest, "if (store.workOrders.find(other => other.id === prerequisiteId)?.dependsOn?.includes(id))"), "utf8");
  const cycleGrade = await privateGrade(directCycle, "S3", "cycle-1", false);
  const cycleFailures = cycleGrade.filter(([, status]) => status === "fail").map(([id]) => id).sort();
  if (JSON.stringify(cycleFailures) !== JSON.stringify(["dependency.transitive-cycle", "failure.no_mutation-dependency"])) {
    throw new Error(`TRANSITIVE_CYCLE_NOT_DETECTED:${cycleFailures}`);
  }
  report.mutants.directCyclesOnly = { failed: cycleFailures };

  // S6 (0.4.0): the shortcuts a model may have written in S1-S5 fail at scale; a correct but slower one keeps its
  // correctness checks and the slower rungs.
  const scaleService = await readFile(join(refA, "src/service.ts"), "utf8");
  const iterative = scaleService.slice(scaleService.indexOf("/** Whether targetId is reachable"), scaleService.indexOf("export async function addDependency"));
  if (!iterative.includes("while (pending.length)")) throw new Error("MUTANT_ANCHOR_NOT_FOUND:ITERATIVE_SEARCH");
  const scaleMutants = {
    // The S1-S5 reference as it was: a recursive search that scans the array for every order.
    "recursive-linear-search": iterative.replace(/[\s\S]*/, `function reaches(store: Awaited<ReturnType<typeof readStore>>, currentId: string, targetId: string, seen = new Set<string>()): boolean {
  if (currentId === targetId) return true;
  if (seen.has(currentId)) return false;
  seen.add(currentId);
  const current = store.workOrders.find(order => order.id === currentId);
  return (current?.dependsOn ?? []).some(id => reaches(store, id, targetId, seen));
}

`),
    // An iterative search without a visited set: correct on chains, but the ladder's paths never end.
    "no-visited-set": iterative.replace("      if (!seen.has(next)) {\n        seen.add(next);\n        pending.push(next);\n      }", "      pending.push(next);"),
  };
  const scaleResults = {};
  for (const [name, replacement] of Object.entries(scaleMutants)) {
    if (replacement === iterative) throw new Error(`MUTANT_ANCHOR_NOT_FOUND:${name}`);
    const mutant = join(scratch, name);
    await cp(refA, mutant, { recursive: true });
    await writeFile(join(mutant, "src/service.ts"), scaleService.replace(iterative, replacement), "utf8");
    const grade = await privateGrade(mutant, "S6", "cycle-1", false);
    const failed = grade.filter(([id, status]) => id.startsWith("scale.") && status === "fail").map(([id]) => id);
    if (!failed.includes("scale.dependencies") || failed.includes("scale.status") || failed.includes("scale.list") || !failed.includes("scale.speed-3")) {
      throw new Error(`SCALE_MUTANT_NOT_DETECTED:${name}:${failed}`);
    }
    scaleResults[name] = { failed };
  }
  // Linear lookups of prerequisites and a full copy before every write: correct, and slower than the reference.
  const linear = join(scratch, "linear-lookups");
  await cp(refA, linear, { recursive: true });
  const linearService = scaleService.replace("      if (dependencies.some(id => byId.get(id)?.status !== \"DONE\")) {",
    "      if (dependencies.some(id => store.workOrders.find(candidate => candidate.id === id)?.status !== \"DONE\")) {");
  const storeSource = await readFile(join(refA, "src/store.ts"), "utf8");
  const copying = storeSource.replace("  if (store.version === 2) return store;", "  if (store.version === 2) return structuredClone(store);");
  if (linearService === scaleService || copying === storeSource) throw new Error("MUTANT_ANCHOR_NOT_FOUND:LINEAR_LOOKUPS");
  await writeFile(join(linear, "src/service.ts"), linearService, "utf8");
  await writeFile(join(linear, "src/store.ts"), copying, "utf8");
  const linearGrade = await privateGrade(linear, "S6", "cycle-1", false);
  const linearPassed = linearGrade.filter(([id, status]) => id.startsWith("scale.") && status === "pass").map(([id]) => id);
  if (!["scale.list", "scale.dependencies", "scale.status", "scale.speed-3"].every(id => linearPassed.includes(id)) || linearPassed.includes("scale.speed-0.75")) {
    throw new Error(`LINEAR_LOOKUPS_UNEXPECTED:${linearPassed}`);
  }
  scaleResults["linear-lookups"] = { passed: linearPassed };
  report.mutants.scale = scaleResults;

  // S7 (0.5.0): plans that break a rule fail its validity check; a plan that writes the store fails read-only; ranking
  // by id instead of priority per hour falls below the greedy plan's place.
  const planSource = await readFile(join(refA, "src/plan.ts"), "utf8");
  const planMutants = {
    "plan-ignores-dependencies": [planSource.replace('before: (order.dependsOn ?? []).filter(id => status.get(id) !== "DONE") });', "before: [] });"),
      grade => grade.some(([id, status]) => id === "plan.valid-small" && status === "fail") && grade.some(([id, status]) => id === "plan.valid-large" && status === "fail")],
    "plan-writes-store": [planSource.replace("  const store = await readStore();\n  const jobs = jobsOf(store.workOrders);",
      "  const store = await readStore();\n  await (await import(\"node:fs/promises\")).writeFile((await import(\"./store.ts\")).STORE_PATH, JSON.stringify(store));\n  const jobs = jobsOf(store.workOrders);"),
      grade => grade.some(([id, status]) => id === "plan.read-only" && status === "fail")],
    "plan-ranks-by-id": [planSource.replace("const ratio = (id: string) => jobs.get(id)!.priority / jobs.get(id)!.hours;", "const ratio = (_id: string) => 0;"),
      grade => grade.some(([id, status]) => id === "plan.quality-50" && status === "fail") && grade.every(([id, status]) => !id.startsWith("plan.valid") || status === "pass")],
    "plan-done-prerequisites-block": [planSource.replace('before: (order.dependsOn ?? []).filter(id => status.get(id) !== "DONE") });', "before: order.dependsOn ?? [] });"),
      grade => grade.some(([id, status]) => id.startsWith("plan.valid") && status === "fail")],
  };
  const planResults = {};
  for (const [name, [source, expected]] of Object.entries(planMutants)) {
    if (source === planSource) throw new Error(`MUTANT_ANCHOR_NOT_FOUND:${name}`);
    const mutant = join(scratch, name);
    await cp(refA, mutant, { recursive: true });
    await writeFile(join(mutant, "src/plan.ts"), source, "utf8");
    const grade = await privateGrade(mutant, "S7", "cycle-1", false);
    if (!expected(grade)) throw new Error(`PLAN_MUTANT_NOT_DETECTED:${name}:${JSON.stringify(grade.filter(([id]) => id.startsWith("plan.")))}`);
    planResults[name] = { failed: grade.filter(([id, status]) => id.startsWith("plan.") && status === "fail").map(([id]) => id) };
  }
  report.mutants.plan = planResults;

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
