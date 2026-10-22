import { appendFile, mkdir, readFile, readdir, stat, writeFile } from "node:fs/promises";
import { join, relative, resolve } from "node:path";
import { randomBytes } from "node:crypto";
import type { ManifestItem } from "../evaluation/manifest.js";
import type { EvaluationPlan } from "../evaluation/types.js";
import type { ModelSelection } from "../types.js";
import { loadRecordedTrials } from "../evaluation/regrade.js";
import { modelLabel } from "../evaluation/report.js";
import { providerHost } from "../evaluation/provider-slots.js";
import { caseItems, generateFamilyPlans, packageItems, smokePlan, type GeneratedPlan } from "./plans.js";
import { familyResults, loadSingleRun, loadTrajectoryRun, trajectoryCheckIds, trajectoryUnit, type FamilyUnit, type NotRunUnit, type RunContents } from "./score.js";
import { failedChecks, markdownSuiteReport, suiteFlags, type FamilyReport, type SuiteReport } from "./report.js";
import { checkPolicy, parseModelSpec, validateSuite, type FamilySpec, type SuiteFile } from "./spec.js";
import type { TrajectoryRecord } from "../evaluation/types.js";

/** What the suite needs from the outside world; the real one spawns processes in the frozen worktree. */
export interface SuiteExecutor {
  /** Create a detached worktree at `commit` (HEAD when omitted), with dependencies, credentials and runs linked in. */
  freeze(root: string, commit: string | null): Promise<{ commit: string; uncommitted: string[] }>;
  /** Every package's integrity, and the pins of the suite's own plans. */
  packageCheck(root: string, plans: string[], log: string): Promise<boolean>;
  validate(root: string, plan: string, log: string): Promise<boolean>;
  /** Run a plan with the null agent; the run directory appears under outDirectory. */
  smoke(root: string, plan: string, outDirectory: string, log: string): Promise<void>;
  run(root: string, plan: string, outDirectory: string, log: string, options: RunOptions): Promise<number | null>;
  tournament(root: string, runDirectories: string[], visualPackage: string, judges: string[] | undefined, log: string): Promise<number | null>;
}

export interface RunOptions {
  resume?: string;
  stoppedProviders?: Record<string, string>;
  environment: Record<string, string>;
}

export interface SuiteOptions {
  repoRoot: string;
  /** Repository-relative suite file; read from the frozen worktree. Required unless resuming. */
  suitePath?: string;
  models?: string[];
  families?: string[];
  repetitions?: number;
  dryRun?: boolean;
  resume?: string;
  /** Where suite runs live; default <repoRoot>/runs/suites. */
  suitesRoot?: string;
  log?: (line: string) => void;
}

interface RunEntry {
  key: string;
  attempt: "launch" | "retry";
  outDirectory: string;
  runDirectory: string | null;
  exitCode: number | null;
  status: "running" | "finished";
  startedAt: string;
  finishedAt: string | null;
}

interface PlanEntry extends Omit<GeneratedPlan, "plan"> { path: string }

export interface SuiteState {
  schemaVersion: 1;
  id: string;
  suitePath: string;
  suite: SuiteFile;
  modelSpecs: string[];
  models: ModelSelection[];
  familyIds: string[];
  repetitions: number;
  dryRun: boolean;
  commit: string;
  worktree: string;
  uncommitted: string[];
  createdAt: string;
  phases: Record<string, string>;
  plans: PlanEntry[];
  runs: RunEntry[];
  estimate?: { byModel: Record<string, number>; byHost: Record<string, number>; notes: string[] };
  smoke?: Record<string, { ok: boolean; detail: string; directory: string | null }>;
}

const now = () => new Date().toISOString();
const PHASES = ["freeze", "generate", "preflight", "smoke", "launch", "retry", "report"] as const;
const STOPPING_PROVIDER_ERRORS = new Set(["PROVIDER_BALANCE", "PROVIDER_AUTH"]);

/** The run directories a harness process created under its output directory (one per process; a resume reuses it). */
export async function runDirectoriesIn(outDirectory: string): Promise<string[]> {
  const entries = await readdir(outDirectory, { withFileTypes: true }).catch(() => []);
  const found: Array<{ path: string; time: number }> = [];
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const path = join(outDirectory, entry.name);
    const info = await stat(join(path, "experiment.json")).catch(() => null);
    if (info) found.push({ path, time: info.mtimeMs });
  }
  return found.sort((left, right) => left.time - right.time).map(entry => entry.path);
}

async function readJson<T>(path: string): Promise<T> {
  return JSON.parse(await readFile(path, "utf8")) as T;
}

/** The value stored under `key` in a parsed JSON value, searched to a small depth. */
function findKey(value: unknown, key: string, depth: number): unknown {
  if (!value || typeof value !== "object" || depth < 0) return undefined;
  if (!Array.isArray(value) && key in value) return (value as Record<string, unknown>)[key];
  for (const child of Object.values(value)) {
    const found = findKey(child, key, depth - 1);
    if (found !== undefined) return found;
  }
  return undefined;
}

async function exists(path: string): Promise<boolean> {
  return stat(path).then(() => true, () => false);
}

export class SuiteRunner {
  private state!: SuiteState;
  private directory!: string;
  private families = new Map<string, FamilySpec>();
  private items = new Map<string, ManifestItem[] | null>();
  private readonly log: (line: string) => void;

  constructor(private readonly options: SuiteOptions, private readonly executor: SuiteExecutor) {
    this.log = options.log ?? (line => console.log(line));
  }

  get suiteDirectory(): string { return this.directory; }

  private async note(line: string): Promise<void> {
    const stamped = `${now()} ${line}`;
    this.log(stamped);
    if (this.directory) await appendFile(join(this.directory, "suite.log"), `${stamped}\n`);
  }

  private async save(): Promise<void> {
    await writeFile(join(this.directory, "suite.json"), JSON.stringify(this.state, null, 2));
  }

  private logPath(name: string): string { return join(this.directory, "logs", `${name}.log`); }

  /** Runs every phase that has not finished; returns the exit status (0 when the suite completed). */
  async run(): Promise<{ status: number; directory: string; report: SuiteReport | null }> {
    try {
      if (this.options.resume) await this.load(this.options.resume);
      else await this.create();
      if (this.state.phases.generate !== "done") await this.generate();
      await this.loadItems();
      if (this.state.phases.preflight !== "done") await this.preflight();
      if (this.state.phases.smoke !== "done") await this.smoke();
      if (this.state.dryRun && !this.options.resume) {
        this.state.phases.launch = "skipped (dry run)";
        await this.save();
        await this.note(`Dry run complete. Launch with: npm run suite -- --resume ${relative(this.options.repoRoot, this.directory)}`);
        return { status: 0, directory: this.directory, report: null };
      }
      this.state.dryRun = false;
      if (this.state.phases.launch !== "done") await this.launch();
      if (this.state.phases.retry !== "done") await this.retry();
      const report = await this.report();
      return { status: report.status === "completed" ? 0 : 1, directory: this.directory, report };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      await this.note(`Suite stopped: ${message}`);
      if (this.state) await this.save();
      return { status: 1, directory: this.directory ?? "", report: null };
    }
  }

  private async create(): Promise<void> {
    const { suitePath, repoRoot } = this.options;
    if (!suitePath) throw new Error("SUITE_REQUIRED");
    if (!this.options.models?.length) throw new Error("MODELS_REQUIRED");
    const models = this.options.models.map(parseModelSpec);
    if (new Set(models.map(model => `${model.provider}:${model.id}`)).size !== models.length) throw new Error("MODELS_DUPLICATED");
    const repetitions = this.options.repetitions ?? 1;
    if (!Number.isSafeInteger(repetitions) || repetitions < 1) throw new Error("REPETITIONS_INVALID");
    // Check the launch against the suite file before freezing anything; the frozen copy is checked again below.
    const draft = validateSuite(await readJson(resolve(repoRoot, suitePath)));
    checkPolicy(draft.policy, models, repetitions);
    for (const familyId of this.options.families ?? []) if (!draft.families.some(family => family.id === familyId)) throw new Error(`FAMILY_UNKNOWN:${familyId}`);
    const stampedName = suitePath.replace(/^.*\//, "").replace(/\.json$/, "");
    const id = `${now().replace(/[-:]/g, "").replace(/\..*$/, "").replace("T", "-")}-${stampedName}-${randomBytes(2).toString("hex")}`;
    this.directory = resolve(this.options.suitesRoot ?? join(repoRoot, "runs", "suites"), id);
    await mkdir(join(this.directory, "logs"), { recursive: true });
    const worktree = join(this.directory, "worktree");
    await this.note(`Suite ${id}: freezing HEAD into ${worktree}`);
    const frozen = await this.executor.freeze(worktree, null);
    if (frozen.uncommitted.length) {
      await this.note(`Warning: the main tree has uncommitted changes that this suite does not include: ${frozen.uncommitted.slice(0, 20).join(", ")}${frozen.uncommitted.length > 20 ? ", ..." : ""}`);
    }
    const suite = validateSuite(await readJson(join(worktree, suitePath)));
    checkPolicy(suite.policy, models, repetitions);
    const familyIds = this.options.families?.length ? this.options.families : suite.families.map(family => family.id);
    for (const familyId of familyIds) if (!suite.families.some(family => family.id === familyId)) throw new Error(`FAMILY_UNKNOWN:${familyId}`);
    this.state = {
      schemaVersion: 1, id, suitePath, suite, modelSpecs: this.options.models, models, familyIds, repetitions, dryRun: !!this.options.dryRun,
      commit: frozen.commit, worktree, uncommitted: frozen.uncommitted, createdAt: now(), phases: { freeze: "done" }, plans: [], runs: [],
    };
    for (const family of suite.families) this.families.set(family.id, family);
    await this.save();
  }

  private async load(directory: string): Promise<void> {
    this.directory = resolve(directory);
    this.state = await readJson<SuiteState>(join(this.directory, "suite.json"));
    for (const family of this.state.suite.families) this.families.set(family.id, family);
    await this.note(`Resuming suite ${this.state.id} at commit ${this.state.commit}`);
    if (!(await exists(join(this.state.worktree, ".git")))) {
      await this.note(`Recreating the frozen worktree at ${this.state.commit}`);
      await this.executor.freeze(this.state.worktree, this.state.commit);
    }
    // A run left "running" by an interrupted suite ended with its process; the launch phase continues its directory.
    for (const entry of this.state.runs) {
      if (entry.status !== "running") continue;
      entry.runDirectory ??= (await runDirectoriesIn(entry.outDirectory)).at(-1) ?? null;
      entry.status = "finished";
    }
  }

  private family(id: string): FamilySpec { return this.families.get(id)!; }

  private async loadItems(): Promise<void> {
    for (const entry of this.state.plans) {
      const plan = await readJson<EvaluationPlan>(entry.path);
      const packagePath = plan.cases[0]?.packagePath;
      if (packagePath && !this.items.has(packagePath)) this.items.set(packagePath, await packageItems(this.state.worktree, packagePath));
    }
  }

  private async generate(): Promise<void> {
    const plansDirectory = join(this.directory, "plans");
    await mkdir(plansDirectory, { recursive: true });
    this.state.plans = [];
    for (const familyId of this.state.familyIds) {
      const family = this.family(familyId);
      const template = await readJson<EvaluationPlan>(join(this.state.worktree, family.template));
      if (template.cases.length !== 1) throw new Error(`SUITE_TEMPLATE_CASES:${familyId}`);
      const packagePath = template.cases[0]!.packagePath;
      if (packagePath && !this.items.has(packagePath)) this.items.set(packagePath, await packageItems(this.state.worktree, packagePath));
      const trialsPerModel = (plan: EvaluationPlan) => plan.execution?.kind === "trajectory" ? 1 : (caseItems(plan, this.items)?.length ?? 1) * (plan.repetitions ?? 1);
      for (const generated of generateFamilyPlans(family, template, this.state.models, this.state.repetitions, this.state.id, trialsPerModel)) {
        const path = join(plansDirectory, `${generated.key}.eval.json`);
        await writeFile(path, JSON.stringify(generated.plan, null, 2));
        const { plan: _plan, ...entry } = generated;
        this.state.plans.push({ ...entry, path });
        if (generated.adjustments.length) await this.note(`${generated.key}: template adjusted (${generated.adjustments.join("; ")})`);
      }
    }
    this.state.phases.generate = "done";
    await this.save();
    await this.note(`Generated ${this.state.plans.length} plans for ${this.state.familyIds.join(", ")}`);
  }

  /** Worst-case tokens: every trial uses its whole budget. A spending fuse, not an expectation. */
  private async estimate(): Promise<NonNullable<SuiteState["estimate"]>> {
    const byModel: Record<string, number> = {};
    const byHost: Record<string, number> = {};
    const notes: string[] = [];
    for (const entry of this.state.plans) {
      const plan = await readJson<EvaluationPlan>(entry.path);
      const perModel = plan.batch?.maxTotalTokensPerModel;
      if (typeof perModel !== "number") { notes.push(`${entry.key}: no per-trial token budget, so no bound`); continue; }
      for (const model of plan.models) {
        const label = modelLabel(model);
        byModel[label] = (byModel[label] ?? 0) + perModel;
        const host = providerHost(model.provider);
        byHost[host] = (byHost[host] ?? 0) + perModel;
      }
      if (entry.kind === "visual") notes.push(`${entry.key}: the tournament's judge calls come on top`);
    }
    return { byModel, byHost, notes };
  }

  private async preflight(): Promise<void> {
    await this.note("Preflight: package check");
    if (!(await this.executor.packageCheck(this.state.worktree, this.state.plans.map(entry => entry.path), this.logPath("preflight-packages")))) {
      this.state.phases.preflight = "failed: package check";
      throw new Error("PREFLIGHT_PACKAGE_CHECK_FAILED");
    }
    for (const entry of this.state.plans) {
      if (!(await this.executor.validate(this.state.worktree, entry.path, this.logPath(`preflight-${entry.key}`)))) {
        this.state.phases.preflight = `failed: ${entry.key} did not validate`;
        throw new Error(`PREFLIGHT_VALIDATE_FAILED:${entry.key}`);
      }
    }
    this.state.estimate = await this.estimate();
    const thousands = (value: number) => `${(value / 1_000_000).toFixed(1)}M`;
    await this.note(`Worst-case tokens by model: ${Object.entries(this.state.estimate.byModel).map(([label, tokens]) => `${label} ${thousands(tokens)}`).join(", ")}`);
    await this.note(`Worst-case tokens by endpoint: ${Object.entries(this.state.estimate.byHost).map(([host, tokens]) => `${host} ${thousands(tokens)}`).join(", ")}`);
    for (const note of this.state.estimate.notes) await this.note(`Estimate note: ${note}`);
    this.state.phases.preflight = "done";
    await this.save();
  }

  /** Null-agent smoke on one item of each family: every trial graded, nothing earned. */
  private async smoke(): Promise<void> {
    this.state.smoke = {};
    const done = new Set<string>();
    for (const entry of this.state.plans) {
      if (done.has(entry.familyId)) continue;
      done.add(entry.familyId);
      const family = this.family(entry.familyId);
      const generated = { ...entry, plan: await readJson<EvaluationPlan>(entry.path) };
      const plan = smokePlan(generated, family, caseItems(generated.plan, this.items));
      const path = join(this.directory, "plans", `${entry.familyId}.smoke.eval.json`);
      await writeFile(path, JSON.stringify(plan, null, 2));
      const outDirectory = join(this.directory, "smoke", entry.familyId);
      await mkdir(outDirectory, { recursive: true });
      await this.note(`Smoke: ${entry.familyId} with the null agent`);
      await this.executor.smoke(this.state.worktree, path, outDirectory, this.logPath(`smoke-${entry.familyId}`));
      const directory = (await runDirectoriesIn(outDirectory)).at(-1) ?? null;
      const result = directory ? await this.smokeVerdict(family, entry.kind, directory, plan) : { ok: false, detail: "no run directory" };
      this.state.smoke[entry.familyId] = { ...result, directory };
      await this.note(`Smoke ${entry.familyId}: ${result.ok ? "passed" : "FAILED"} (${result.detail})`);
    }
    const failed = Object.entries(this.state.smoke).filter(([, result]) => !result.ok).map(([id]) => id);
    if (failed.length) {
      this.state.phases.smoke = `failed: ${failed.join(", ")}`;
      throw new Error(`SMOKE_FAILED:${failed.join(",")}`);
    }
    this.state.phases.smoke = "done";
    await this.save();
  }

  private async smokeVerdict(family: FamilySpec, kind: FamilySpec["kind"], directory: string, plan: EvaluationPlan): Promise<{ ok: boolean; detail: string }> {
    const maxScore = family.smokeMaxScore ?? 0;
    if (kind === "trajectory") {
      const report = await readJson<{ records: TrajectoryRecord[] }>(join(directory, "report.json")).catch(() => null);
      if (!report?.records.length) return { ok: false, detail: "no trajectory recorded" };
      const checkIds = await trajectoryCheckIds(this.state.worktree, plan.cases[0]!.packagePath!);
      for (const record of report.records) {
        const grades = record.stages.flatMap(stage => stage.cycles.map(cycle => cycle.privateGrade).filter(Boolean));
        const broken = grades.filter(grade => grade!.status !== "passed" && grade!.status !== "failed");
        if (!grades.length || broken.length) return { ok: false, detail: `${grades.length} snapshots graded, ${broken.length} not graded cleanly` };
        const unit = trajectoryUnit(family.id, directory, record, checkIds);
        if ((unit.score ?? 0) > maxScore) return { ok: false, detail: `the null agent scores ${unit.score!.toFixed(3)}; passing: ${unit.passedChecks.join(", ")}` };
        return { ok: true, detail: `${grades.length} snapshots graded, null score ${unit.score?.toFixed(3)}` };
      }
    }
    const records = await loadRecordedTrials(directory);
    if (!records.length) return { ok: false, detail: "no trial recorded" };
    // The format check earns nothing by itself, and a task may pass it when there is no reply at all (so that a missing
    // reply is not deducted twice); only content checks count against the null agent.
    const packagePath = plan.cases[0]?.packagePath;
    const manifest = packagePath ? await readJson<{ scoring?: { formatCheckId?: string } }>(join(this.state.worktree, packagePath, "manifest.json")).catch(() => null) : null;
    const formatCheckId = manifest?.scoring?.formatCheckId;
    for (const record of records) {
      if (record.evaluation.status !== "passed" && record.evaluation.status !== "failed") {
        return { ok: false, detail: `trial ${record.id} was not graded (${record.evaluation.status}${record.evaluation.error ? `: ${record.evaluation.error}` : ""})` };
      }
      const passing = record.evaluation.checks.filter(check => check.passed === true && check.id !== formatCheckId).map(check => check.id);
      if ((record.evaluation.score ?? 0) > maxScore || (maxScore === 0 && passing.length)) {
        return { ok: false, detail: `the null agent earns ${record.evaluation.score}; passing checks: ${passing.join(", ") || "none"}` };
      }
    }
    return { ok: true, detail: `${records.length} trial(s) graded, ${records[0]!.evaluation.checks.length} checks, null score ${records[0]!.evaluation.score}` };
  }

  private environment(attempt: string): Record<string, string> {
    return {
      AGENTEVAL_PROVIDER_SLOTS: join(this.directory, "slots", `${attempt}-${Date.now()}`),
      AGENTEVAL_PROVIDER_LIMITS: JSON.stringify(this.state.suite.providerConcurrency),
    };
  }

  private latestRun(key: string): RunEntry | undefined {
    return this.state.runs.filter(entry => entry.key === key).at(-1);
  }

  private async execute(entry: PlanEntry, attempt: RunEntry["attempt"], environment: Record<string, string>, options: { resume?: RunEntry; stoppedProviders?: Record<string, string> } = {}): Promise<void> {
    const resumeFrom = options.resume?.runDirectory ?? null;
    const outDirectory = options.resume?.outDirectory ?? join(this.directory, "runs", attempt === "retry" && entry.kind === "trajectory" ? `${entry.key}-retry` : entry.key);
    await mkdir(outDirectory, { recursive: true });
    const run: RunEntry = { key: entry.key, attempt, outDirectory, runDirectory: resumeFrom, exitCode: null, status: "running", startedAt: now(), finishedAt: null };
    this.state.runs.push(run);
    await this.save();
    await this.note(`${attempt === "retry" ? "Retry" : "Launch"}: ${entry.key}${resumeFrom ? ` (resuming ${relative(this.directory, resumeFrom)})` : ""}`);
    run.exitCode = await this.executor.run(this.state.worktree, entry.path, outDirectory, this.logPath(`${attempt}-${entry.key}`),
      { ...(resumeFrom ? { resume: resumeFrom } : {}), ...(options.stoppedProviders ? { stoppedProviders: options.stoppedProviders } : {}), environment });
    run.runDirectory ??= (await runDirectoriesIn(outDirectory)).at(-1) ?? null;
    run.status = "finished";
    run.finishedAt = now();
    await this.save();
    await this.note(`Finished: ${entry.key} with exit code ${run.exitCode}${run.runDirectory ? ` in ${relative(this.directory, run.runDirectory)}` : ", no run directory"}`);
    const family = this.family(entry.familyId);
    if (entry.kind === "visual" && run.runDirectory && await exists(join(run.runDirectory, "report.json"))) {
      await this.note(`Tournament: ${entry.key}`);
      const status = await this.executor.tournament(this.state.worktree, [run.runDirectory], family.visualPackage!, family.judges, this.logPath(`tournament-${entry.key}`));
      await this.note(`Tournament ${entry.key} ended with exit code ${status}`);
    }
  }

  /** A run is complete when its process wrote a report that is not marked incomplete by a crash. */
  private async runComplete(entry: RunEntry | undefined): Promise<boolean> {
    if (!entry?.runDirectory || entry.status !== "finished") return false;
    return exists(join(entry.runDirectory, "report.json"));
  }

  private async launch(): Promise<void> {
    const environment = this.environment("launch");
    const pending: Promise<void>[] = [];
    for (const entry of this.state.plans) {
      const latest = this.latestRun(entry.key);
      if (latest && latest.exitCode !== null && await this.runComplete(latest)) continue;
      // An interrupted single-run plan continues in its run directory; a trajectory starts again.
      const resume = latest?.runDirectory && entry.kind !== "trajectory" ? latest : undefined;
      pending.push(this.execute(entry, "launch", environment, { ...(resume ? { resume } : {}) }));
    }
    await Promise.all(pending);
    this.state.phases.launch = "done";
    await this.save();
  }

  /** Providers stopped for balance or authentication in a run: retrying them cannot succeed. */
  private async stoppedProviders(runDirectory: string): Promise<Record<string, string>> {
    const report = await readJson<{ batch?: { providerStops?: Record<string, string> } }>(join(runDirectory, "report.json")).catch(() => ({ batch: undefined }));
    return Object.fromEntries(Object.entries(report.batch?.providerStops ?? {}).filter(([, reason]) => STOPPING_PROVIDER_ERRORS.has(reason)));
  }

  /** Does a finished run need its one retry? Infrastructure failures of providers that can still answer, or a crash. */
  private async needsRetry(entry: PlanEntry, run: RunEntry | undefined): Promise<{ retry: boolean; stopped: Record<string, string>; reason: string }> {
    if (!run?.runDirectory || !(await exists(join(run.runDirectory, "report.json")))) return { retry: true, stopped: {}, reason: "no report" };
    const stopped = await this.stoppedProviders(run.runDirectory);
    const live = (model: string) => !stopped[model.split(":")[0]!];
    // Every trial of the run counts here, anchors outside the family score included.
    const contents = await this.contents(entry, run.runDirectory, false);
    const failures = contents.units.filter(unit => unit.infrastructure && live(unit.model)).length;
    const notRun = contents.notRun.filter(item => item.reason === "INFRASTRUCTURE_FAILURES" && live(item.model)).length;
    const report = await readJson<{ completed?: boolean }>(join(run.runDirectory, "report.json"));
    const crashed = run.exitCode !== 0 && report.completed === false && !contents.notRun.length && !failures;
    return { retry: failures > 0 || notRun > 0 || crashed, stopped, reason: `${failures} infrastructure failures, ${notRun} not run after repeated failures${crashed ? ", incomplete" : ""}` };
  }

  private async retry(): Promise<void> {
    const environment = this.environment("retry");
    const pending: Promise<void>[] = [];
    for (const entry of this.state.plans) {
      if (this.state.runs.some(run => run.key === entry.key && run.attempt === "retry")) continue;
      const latest = this.latestRun(entry.key);
      const { retry, stopped, reason } = await this.needsRetry(entry, latest);
      if (!retry) continue;
      await this.note(`Retry needed for ${entry.key}: ${reason}`);
      const resume = entry.kind !== "trajectory" && latest?.runDirectory ? latest : undefined;
      pending.push(this.execute(entry, "retry", environment, { ...(resume ? { resume } : {}), ...(Object.keys(stopped).length && resume ? { stoppedProviders: stopped } : {}) }));
    }
    await Promise.all(pending);
    this.state.phases.retry = "done";
    await this.save();
  }

  private async contents(entry: PlanEntry, runDirectory: string, scoredOnly = true): Promise<RunContents> {
    const family = this.family(entry.familyId);
    if (entry.kind === "trajectory") {
      const plan = await readJson<EvaluationPlan>(entry.path);
      return loadTrajectoryRun(family, runDirectory, await trajectoryCheckIds(this.state.worktree, plan.cases[0]!.packagePath!));
    }
    return loadSingleRun(family, runDirectory, scoredOnly);
  }

  private async graderReason(unit: FamilyUnit, checkId: string): Promise<string | null> {
    try {
      const record = await readJson<{ scoreRunId?: string }>(join(unit.runDirectory, unit.trialId, "result.json"));
      const runs = await readdir(join(unit.runDirectory, unit.trialId, "score-runs"));
      const scoreRun = runs.includes(record.scoreRunId ?? "") ? record.scoreRunId! : runs.at(-1);
      if (!scoreRun) return null;
      const grader = join(unit.runDirectory, unit.trialId, "score-runs", scoreRun, "grader");
      const result = await readJson<{ reason?: string | null; checks?: Array<{ id: string; evidenceRefs?: string[] }> }>(join(grader, "result.json"));
      if (result.reason) return result.reason;
      // Check entries carry no text; some graders record a detail under the check's id in an evidence file.
      for (const reference of result.checks?.find(entry => entry.id === checkId)?.evidenceRefs ?? []) {
        const evidence = await readJson<unknown>(join(grader, "evidence", reference)).catch(() => null);
        const detail = findKey(evidence, checkId, 3);
        if (detail !== undefined && typeof detail !== "boolean") return (typeof detail === "string" ? detail : JSON.stringify(detail)).slice(0, 200);
      }
      return null;
    } catch {
      return null;
    }
  }

  private async report(): Promise<SuiteReport> {
    const families: FamilyReport[] = [];
    const tokens: Record<string, Record<string, number>> = {};
    let failed = false;
    for (const familyId of this.state.familyIds) {
      const family = this.family(familyId);
      const entries = this.state.plans.filter(entry => entry.familyId === familyId);
      const units: FamilyUnit[] = [];
      const notRun: NotRunUnit[] = [];
      const providerStops: Record<string, string> = {};
      const runDirectories: string[] = [];
      for (const entry of entries) {
        const run = this.latestRun(entry.key);
        if (!run?.runDirectory || !(await exists(join(run.runDirectory, "report.json")))) { failed = true; continue; }
        runDirectories.push(relative(this.options.repoRoot, run.runDirectory));
        const contents = await this.contents(entry, run.runDirectory);
        units.push(...contents.units);
        notRun.push(...contents.notRun);
        Object.assign(providerStops, contents.providerStops);
      }
      const results = familyResults(familyId, this.state.models, units, notRun);
      let tournament: FamilyReport["tournament"];
      if (family.kind === "visual") {
        const run = this.latestRun(entries[0]!.key);
        const path = run?.runDirectory ? join(run.runDirectory, "visual", "tournament.json") : null;
        const data = path ? await readJson<{ byModel: Array<{ model: string; winRate: number }> }>(path).catch(() => null) : null;
        tournament = { path: data ? relative(this.options.repoRoot, path!) : null, error: data ? null : "no tournament.json" };
        for (const result of results) {
          result.winRate = data?.byModel.find(entry => entry.model === result.label)?.winRate ?? null;
        }
      }
      for (const unit of units) {
        tokens[unit.label] ??= {};
        tokens[unit.label]![familyId] = (tokens[unit.label]![familyId] ?? 0) + (unit.tokens ?? 0);
      }
      const reasons = new Map<string, string | null>();
      for (const unit of units) for (const checkId of unit.failedChecks) {
        const key = `${unit.trialId}\u0000${checkId}`;
        if (!reasons.has(key) && reasons.size < 400) reasons.set(key, await this.graderReason(unit, checkId));
      }
      families.push({
        id: familyId, kind: family.kind, template: family.template, score: family.score ?? null,
        adjustments: [...new Set(entries.flatMap(entry => entry.adjustments))], results, notRun,
        infrastructure: units.filter(unit => unit.infrastructure).map(({ label, trialId, itemId, outcome, providerError, runDirectory }) =>
          ({ label, trialId, itemId, outcome, providerError, runDirectory: relative(this.options.repoRoot, runDirectory) })),
        providerStops, runDirectories,
        failedChecks: failedChecks(units, (unit, checkId) => reasons.get(`${unit.trialId}\u0000${checkId}`) ?? null)
          .map(check => ({ ...check, samples: check.samples.map(sample => ({ ...sample, trial: relative(this.options.repoRoot, sample.trial) })) })),
        ...(tournament ? { tournament } : {}),
      });
    }
    const flags = suiteFlags(this.state.suite, families, this.families);
    if (failed) flags.unshift({ kind: "family-failed", family: null, detail: "a planned run left no report; see suite.log and logs/" });
    this.state.phases.report = "done";
    const report: SuiteReport = {
      schemaVersion: 1, suite: this.state.suite.name, id: this.state.id, commit: this.state.commit, models: this.state.models.map(modelLabel),
      repetitions: this.state.repetitions, startedAt: this.state.createdAt, finishedAt: now(), status: failed ? "failed" : "completed",
      families, flags, tokens, phases: Object.fromEntries(PHASES.map(phase => [phase, this.state.phases[phase] ?? "not run"])),
      estimate: this.state.estimate ?? null, smoke: this.state.smoke ?? {}, uncommitted: this.state.uncommitted,
    };
    await writeFile(join(this.directory, "report.json"), JSON.stringify(report, null, 2));
    await writeFile(join(this.directory, "report.md"), markdownSuiteReport(report));
    await this.save();
    await this.note(`Report: ${relative(this.options.repoRoot, join(this.directory, "report.md"))} (${report.status}, ${flags.length} flags)`);
    return report;
  }
}
