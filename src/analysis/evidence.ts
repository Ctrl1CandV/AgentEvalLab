import { execFile } from "node:child_process";
import { createHash } from "node:crypto";
import { lstat, readFile, readdir } from "node:fs/promises";
import { join, relative, resolve } from "node:path";
import { promisify } from "node:util";
import { loadRecordedTrials } from "../evaluation/regrade.js";
import { loadTrajectoryRecords, snapshotScores } from "../evaluation/trajectory-regrade.js";
import { modelLabel } from "../evaluation/report.js";
import type { NotRunEntry } from "../evaluation/batch.js";
import type { EvaluationPlan, EvaluationResult, TrajectoryRecord, TrialRecord } from "../evaluation/types.js";
import type { ModelSelection } from "../types.js";
import { inScore } from "../suite/plans.js";
import { familyResults, trajectoryUnit, trialUnit, type FamilyUnit, type NotRunUnit } from "../suite/score.js";
import type { FamilySpec, SuiteFile } from "../suite/spec.js";

const exec = promisify(execFile);

/**
 * The evidence table (PLAN-007 WP0.2): every recorded v1 result with its task and grader version, protocol, coverage
 * and run directory. A row is one model on one task package in one run directory, under one grader version: a run
 * re-graded under a later grader gets a second row, so that numbers keep their version (MEASUREMENT §8).
 */
export interface EvidenceRow {
  family: string;
  packageId: string;
  taskVersion: string;
  /** The grader version of the score runs this row reads; null when no trial was graded. */
  graderVersion: string | null;
  kind: "single" | "trajectory" | "visual";
  model: string;
  label: string;
  thinking: string;
  temperature: number | null;
  contextPolicy: string;
  /** Tokens per trial (single) or per stage and per trajectory. */
  budget: { trial: number | null; stage: number | null };
  budgetNotice: boolean | null;
  repetitions: number;
  /** The items or levels the score counts (suite runs), or every item and level the run held. */
  scope: string[];
  /** Mean score per item, level or last stage reached, for locating a number. */
  breakdown: Array<{ key: string; score: number | null; trials: number }>;
  trials: number;
  scored: number;
  infrastructure: number;
  notRun: number;
  unscored: number;
  /** Trials of the run that have score runs, but none under this grader version. */
  ungraded: number;
  budgetStops: number;
  meanScore: number | null;
  resolved: number;
  decided: number;
  medianTokens: number | null;
  tournament: { path: string; winRate: number | null } | null;
  status: "completed" | "incomplete";
  /** v1 partial credit, or, for a re-grade on manifest v2, the mean v2 primary of the outcomes (MEASUREMENT §8). */
  scoreKind: "v1 partial credit" | "v2 primary";
  source: "suite" | "run";
  suite: string | null;
  runDirectory: string;
  startedAt: string;
  commit: string | null;
}

export interface SuiteEntry {
  id: string;
  suitePath: string;
  families: string[];
  models: string[];
  commit: string;
  createdAt: string;
  status: "completed" | "failed" | "dry run" | "interrupted";
  phases: Record<string, string>;
  report: string | null;
  smoke: Record<string, string>;
}

export interface ConfigurationEntry {
  suite: string;
  family: string;
  template: string;
  packageId: string | null;
  taskVersion: string | null;
  contextPolicy: string;
  budget: { trial: number | null; stage: number | null };
  matchingRows: number;
}

export interface ExcludedRun { runDirectory: string; reason: string }

export interface Evidence {
  generatedAt: string;
  rows: EvidenceRow[];
  suites: SuiteEntry[];
  configurations: ConfigurationEntry[];
  excluded: ExcludedRun[];
}

/** Family codes of the v1 packages, as the reviews name them. */
export const FAMILY_CODES: Record<string, string> = {
  "r3-logic-grid": "R3", "r1-rostering": "R1", "t1-evidence-recovery": "T1", "t2-finance-desk": "T2", "t2-service-desk": "T2-service",
  "eng-005-long-cycle-maintenance": "E3", "e4-terminal-tasks": "E4", "e2-spec-implementation": "E2", "vis-001-original-landing": "VIS",
  "ae-heuristic-contests": "AE", "rsn-001-shift-scheduling": "rsn-001", "rsn-002-derivation-check": "rsn-002",
  "tool-001-doc-evidence-recovery": "tool-001", "eng-001-import-validator": "eng-001", "eng-004-resource-index": "eng-004",
};

interface ScoreRun {
  id: string;
  createdAt: string;
  graderVersion: string | null;
  evaluation: EvaluationResult;
  /** A v2 score run's outcome (outcome.json): its numbers are v2 numbers, never read as v1 partial credit. */
  outcome: { primary: number | null; resolved: boolean | null; coverage: string } | null;
}

async function readJson<T>(path: string): Promise<T> {
  return JSON.parse(await readFile(path, "utf8")) as T;
}

async function exists(path: string): Promise<boolean> {
  return lstat(path).then(() => true, () => false);
}

async function directories(path: string): Promise<string[]> {
  const entries = await readdir(path, { withFileTypes: true }).catch(() => []);
  // Hidden entries are sandbox placeholders or tool caches, never runs.
  return entries.filter(entry => entry.isDirectory() && !entry.name.startsWith(".")).map(entry => join(path, entry.name)).sort();
}

/** A trial's append-only score runs in order, each with the grader version that produced it. */
async function scoreRuns(trialDirectory: string): Promise<ScoreRun[]> {
  const runs: ScoreRun[] = [];
  for (const directory of await directories(join(trialDirectory, "score-runs"))) {
    const score = await readJson<{ scoreRunId?: string; createdAt: string; scorer?: { graderVersion?: string }; evaluation?: EvaluationResult }>(join(directory, "score.json")).catch(() => null);
    if (!score?.evaluation) continue;
    const grader = await readJson<{ graderVersion?: string }>(join(directory, "grader", "result.json")).catch(() => null);
    const outcome = await readJson<{ primary: number | null; resolved: boolean | null; coverage: string }>(join(directory, "outcome.json")).catch(() => null);
    runs.push({ id: score.scoreRunId ?? directory, createdAt: score.createdAt, graderVersion: score.scorer?.graderVersion ?? grader?.graderVersion ?? null,
      evaluation: score.evaluation, outcome });
  }
  return runs.sort((left, right) => left.createdAt.localeCompare(right.createdAt));
}

/** Grader versions of a trajectory's snapshot grades (their score runs carry the grader's own result). */
async function trajectoryGraderVersions(trialDirectory: string): Promise<string[]> {
  const versions = new Set<string>();
  for (const directory of await directories(join(trialDirectory, "score-runs"))) {
    const grader = await readJson<{ graderVersion?: string }>(join(directory, "grader", "result.json")).catch(() => null);
    if (grader?.graderVersion) versions.add(grader.graderVersion);
  }
  return [...versions];
}

const modelKey = (model: ModelSelection) => `${model.provider}:${model.id}`;

interface Experiment {
  name?: string;
  packageFingerprints?: Array<{ caseId: string; id: string; version: string; sha256: string }>;
  condition?: { git?: { commit?: string; dirty?: boolean } };
  execution?: { kind: string; contextPolicy?: string; stageBudget?: { maxTrialTokens?: number } };
  models?: ModelSelection[];
  budget?: { maxTrialTokens?: number };
  repetitions?: number;
  startedAt?: string;
  plannedRuns?: number;
}

interface RunContext {
  repoRoot: string;
  /** Suite runs: the family the run belongs to, its suite, frozen worktree and generated plan. */
  family?: FamilySpec;
  suite?: string;
  worktree?: string;
  plan?: EvaluationPlan;
  /** The suite report's status for this run; plain runs use their own report. */
  suiteStatus?: "completed" | "failed";
  tournaments: Map<string, { path: string; byModel: Array<{ model: string; winRate: number }> }>;
}

/** A manifest as the run saw it: the frozen worktree's copy, or the file at the run's commit. */
async function manifestAt(context: RunContext, commit: string | null, packageId: string, sha256: string | null): Promise<{ manifest: Record<string, unknown>; path: string } | null> {
  const packagePath = context.plan?.cases[0]?.packagePath;
  if (context.worktree && packagePath) {
    const text = await readFile(join(context.worktree, packagePath, "manifest.json"), "utf8").catch(() => null);
    if (text !== null && (!sha256 || createHash("sha256").update(text).digest("hex") === sha256)) return { manifest: JSON.parse(text) as Record<string, unknown>, path: packagePath };
  }
  if (!commit) return null;
  const listing = await exec("git", ["ls-tree", "-r", "--name-only", commit, "--", "task-library"], { cwd: context.repoRoot, maxBuffer: 64 * 1024 * 1024 }).catch(() => null);
  for (const path of (listing?.stdout ?? "").split("\n").filter(line => line.endsWith("/manifest.json"))) {
    const shown = await exec("git", ["show", `${commit}:${path}`], { cwd: context.repoRoot, maxBuffer: 64 * 1024 * 1024 }).catch(() => null);
    if (!shown) continue;
    const manifest = JSON.parse(shown.stdout) as Record<string, unknown>;
    if (manifest.id !== packageId) continue;
    if (sha256 && createHash("sha256").update(shown.stdout).digest("hex") !== sha256) continue;
    return { manifest, path: path.replace(/\/manifest\.json$/, "") };
  }
  return null;
}

function trajectoryChecksOf(manifest: Record<string, unknown>): { checkIds: string[]; weights: Record<string, number> } {
  const typed = manifest as { requirements: Array<{ id: string; checkIds: string[] }>; stages: Array<{ activeRequirementIds: string[] }>; scoring?: { weights?: Record<string, number> } };
  const final = new Set(typed.stages.at(-1)!.activeRequirementIds);
  return { checkIds: typed.requirements.filter(requirement => final.has(requirement.id)).flatMap(requirement => requirement.checkIds), weights: typed.scoring?.weights ?? {} };
}

const mean = (values: number[]) => values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;

function breakdown(units: FamilyUnit[], key: (unit: FamilyUnit) => string | null): EvidenceRow["breakdown"] {
  const groups = new Map<string, FamilyUnit[]>();
  for (const unit of units) {
    const name = key(unit);
    if (name === null) continue;
    groups.set(name, [...(groups.get(name) ?? []), unit]);
  }
  return [...groups.entries()].sort(([left], [right]) => left.localeCompare(right, undefined, { numeric: true })).map(([name, group]) => {
    const counted = group.filter(unit => !unit.infrastructure && unit.score !== null);
    return { key: name, score: mean(counted.map(unit => unit.score!)), trials: group.length };
  });
}

function protocolOf(experiment: Experiment, plan: EvaluationPlan | undefined) {
  const trajectory = experiment.execution?.kind === "trajectory";
  return {
    contextPolicy: trajectory ? experiment.execution?.contextPolicy ?? "continuous" : "single",
    budget: { trial: experiment.budget?.maxTrialTokens ?? null, stage: trajectory ? experiment.execution?.stageBudget?.maxTrialTokens ?? null : null },
    budgetNotice: plan ? plan.budgetNotice !== undefined && plan.budgetNotice !== false : null,
    repetitions: experiment.repetitions ?? 1,
  };
}

/** Rows of one run directory: per package, model and grader version. */
export async function runRows(runDirectory: string, context: RunContext): Promise<{ rows: EvidenceRow[]; excluded: ExcludedRun[] }> {
  const display = relative(context.repoRoot, runDirectory);
  const experiment = await readJson<Experiment>(join(runDirectory, "experiment.json")).catch(() => null);
  if (!experiment) return { rows: [], excluded: [{ runDirectory: display, reason: "no experiment.json" }] };
  const report = await readJson<{ completed?: boolean; records?: TrajectoryRecord[]; batch?: { notRun?: NotRunEntry[] } }>(join(runDirectory, "report.json")).catch(() => null);
  const commit = experiment.condition?.git?.commit ?? null;
  const status: EvidenceRow["status"] = context.suiteStatus ? (context.suiteStatus === "completed" && report ? "completed" : "incomplete")
    : report?.completed ? "completed" : "incomplete";
  const protocol = protocolOf(experiment, context.plan);
  const fingerprints = experiment.packageFingerprints ?? [];
  const familyFor = (packageId: string) => context.family?.id ?? FAMILY_CODES[packageId] ?? packageId;
  const tournament = context.tournaments.get(resolve(runDirectory)) ?? null;
  const common = {
    ...protocol, source: context.suite ? "suite" as const : "run" as const, suite: context.suite ?? null, runDirectory: display,
    startedAt: experiment.startedAt ?? "", commit,
  };
  const notRun: NotRunUnit[] = (report?.batch?.notRun ?? []).map(entry => ({ ...entry, familyId: "", runDirectory }));
  const rows: EvidenceRow[] = [];

  if (experiment.execution?.kind === "trajectory") {
    if (!report?.records) return { rows: [], excluded: [{ runDirectory: display, reason: "trajectory run without report.json (interrupted)" }] };
    const fingerprint = fingerprints[0];
    if (!fingerprint) return { rows: [], excluded: [{ runDirectory: display, reason: "no package fingerprint" }] };
    const found = await manifestAt(context, commit, fingerprint.id, fingerprint.sha256);
    if (!found) return { rows: [], excluded: [{ runDirectory: display, reason: `manifest ${fingerprint.id}@${fingerprint.version} not found at ${commit}` }] };
    const { checkIds, weights } = trajectoryChecksOf(found.manifest);
    const family = familyFor(fingerprint.id);
    // One row per grader version: the original grading, then each append-only re-grade, which overlays the snapshots
    // it graded again (a re-grade of the final snapshot changes the score, which reads that snapshot).
    const scores = await Promise.all(report.records.map(record => snapshotScores(join(runDirectory, record.id))));
    const firstSeen = new Map<string, string>();
    for (const score of scores.flat()) if (score.graderVersion && !firstSeen.has(score.graderVersion)) firstSeen.set(score.graderVersion, score.createdAt);
    const ordered = [...firstSeen.entries()].sort((left, right) => left[1].localeCompare(right[1])).map(([version]) => version);
    const versions: Array<string | undefined> = ordered.length > 1 ? ordered : [undefined];
    for (const version of versions) {
      const overlaid = await loadTrajectoryRecords(runDirectory, version);
      for (const model of experiment.models ?? []) {
        const records = overlaid.filter(record => modelKey(record.model) === modelKey(model));
        const units = records.map(record => trajectoryUnit(family, runDirectory, record, checkIds, weights));
        const recordVersions = new Set<string>(version ? [version] : []);
        if (!version) for (const record of records) for (const found of await trajectoryGraderVersions(join(runDirectory, record.id))) recordVersions.add(found);
        const [result] = familyResults(family, [model], units, notRun.filter(entry => entry.model === modelKey(model)));
        rows.push({
          ...common, family, packageId: fingerprint.id, taskVersion: fingerprint.version, graderVersion: [...recordVersions].sort().join(", ") || null, kind: "trajectory",
          model: modelKey(model), label: modelLabel(model), thinking: model.thinkingLevel ?? "provider-default", temperature: model.temperature ?? null,
          scope: ["final-stage checks"], breakdown: breakdown(units, unit => unit.level ? `last graded ${unit.level}` : null),
          trials: result!.units, scored: result!.scored, infrastructure: result!.infrastructureFailures, notRun: result!.notRun, unscored: result!.unscored,
          ungraded: 0, budgetStops: result!.budgetStops, meanScore: result!.meanScore, resolved: result!.resolved, decided: result!.decided,
          medianTokens: result!.medianTokens, tournament: null, status, scoreKind: "v1 partial credit",
        });
      }
    }
    return { rows, excluded: [] };
  }

  let records: TrialRecord[];
  try { records = await loadRecordedTrials(runDirectory); }
  catch (error) { return { rows: [], excluded: [{ runDirectory: display, reason: `trials unreadable: ${error instanceof Error ? error.message : String(error)}` }] }; }
  if (!records.length) return { rows: [], excluded: [{ runDirectory: display, reason: "no trial recorded" }] };
  const runs = new Map<string, ScoreRun[]>();
  for (const record of records) runs.set(record.id, await scoreRuns(join(runDirectory, record.id)));
  const versions = [...new Set([...runs.values()].flat().map(run => run.graderVersion ?? "unknown"))]
    .sort((left, right) => Math.min(...[...runs.values()].flat().filter(run => (run.graderVersion ?? "unknown") === left).map(run => Date.parse(run.createdAt))) -
      Math.min(...[...runs.values()].flat().filter(run => (run.graderVersion ?? "unknown") === right).map(run => Date.parse(run.createdAt))));
  if (!versions.length) versions.push("none");
  const scored = context.family ? records.filter(record => inScore(context.family!, record.itemId, record.itemLevel)) : records;
  for (const version of versions) {
    const graded: TrialRecord[] = [];
    const ungraded: TrialRecord[] = [];
    for (const record of scored) {
      const own = runs.get(record.id) ?? [];
      if (!own.length) { graded.push(record); continue; }
      const latest = own.filter(run => (run.graderVersion ?? "unknown") === version).at(-1);
      if (!latest) { ungraded.push(record); continue; }
      // A v2 score run counts by its outcome: the primary as the score, resolved as the verdict (MEASUREMENT §8).
      graded.push({ ...record, evaluation: latest.outcome && latest.outcome.coverage === "scored"
        ? { ...latest.evaluation, score: latest.outcome.primary, status: latest.outcome.resolved ? "passed" : "failed" } : latest.evaluation });
    }
    const v2 = [...runs.values()].flat().some(run => (run.graderVersion ?? "unknown") === version && run.outcome);
    const levelOf = new Map(records.map(record => [record.itemId ?? "", record.itemLevel ?? null]));
    for (const fingerprint of fingerprints) {
      const caseRecords = graded.filter(record => record.caseId === fingerprint.caseId);
      const family = familyFor(fingerprint.id);
      for (const model of experiment.models ?? []) {
        const own = caseRecords.filter(record => modelKey(record.model) === modelKey(model));
        const ownNotRun = notRun.filter(entry => entry.model === modelKey(model) && entry.caseId === fingerprint.caseId &&
          (!context.family || inScore(context.family, entry.itemId ?? null, levelOf.get(entry.itemId ?? "") ?? null)));
        const ownUngraded = ungraded.filter(record => record.caseId === fingerprint.caseId && modelKey(record.model) === modelKey(model)).length;
        if (!own.length && !ownNotRun.length && !ownUngraded) continue;
        const units = own.map(record => trialUnit(family, runDirectory, record));
        const [result] = familyResults(family, [model], units, ownNotRun);
        const levels = [...new Set(own.map(record => record.itemLevel).filter((level): level is string => !!level))];
        const items = [...new Set(own.map(record => record.itemId).filter((item): item is string => !!item))];
        const byLevel = levels.length > 1;
        const byItem = !byLevel && items.length <= 12 && (items.length > 1 || (context.family?.score?.items?.length ?? 0) > 1);
        const winRate = tournament?.byModel.find(entry => entry.model === modelLabel(model))?.winRate ?? null;
        rows.push({
          ...common, family, packageId: fingerprint.id, taskVersion: fingerprint.version, graderVersion: version === "none" ? null : version,
          kind: tournament ? "visual" : "single", model: modelKey(model), label: modelLabel(model), thinking: model.thinkingLevel ?? "provider-default",
          temperature: model.temperature ?? null,
          scope: context.family?.score?.items ?? context.family?.score?.levels ?? (levels.length ? levels : items),
          breakdown: breakdown(units, unit => byLevel ? unit.level : byItem ? unit.itemId : null),
          trials: result!.units, scored: result!.scored, infrastructure: result!.infrastructureFailures, notRun: result!.notRun, unscored: result!.unscored,
          ungraded: ownUngraded, budgetStops: result!.budgetStops, meanScore: result!.meanScore,
          resolved: result!.resolved, decided: result!.decided, medianTokens: result!.medianTokens,
          tournament: tournament ? { path: tournament.path, winRate } : null, status, scoreKind: v2 ? "v2 primary" : "v1 partial credit",
        });
      }
    }
  }
  return { rows, excluded: [] };
}

interface SuiteState {
  id: string;
  suitePath: string;
  suite: SuiteFile;
  models: ModelSelection[];
  familyIds: string[];
  dryRun: boolean;
  commit: string;
  worktree: string;
  createdAt: string;
  phases: Record<string, string>;
  plans: Array<{ key: string; familyId: string; path: string }>;
  runs: Array<{ key: string; runDirectory: string | null }>;
  smoke?: Record<string, { ok: boolean; detail: string }>;
}

async function loadTournaments(repoRoot: string, runDirectories: string[]): Promise<RunContext["tournaments"]> {
  const tournaments: RunContext["tournaments"] = new Map();
  for (const directory of runDirectories) {
    const path = join(directory, "visual", "tournament.json");
    const data = await readJson<{ runs?: string[]; byModel?: Array<{ model: string; winRate: number }> }>(path).catch(() => null);
    if (!data?.byModel) continue;
    for (const run of data.runs ?? [relative(repoRoot, directory)]) {
      tournaments.set(resolve(repoRoot, run), { path: relative(repoRoot, path), byModel: data.byModel });
    }
  }
  return tournaments;
}

/** Collects every suite and plain run under `<repoRoot>/runs`. */
export async function collectEvidence(repoRoot: string, suiteFiles: string[] = ["suites/dev.json", "suites/full.json"]): Promise<Evidence> {
  const runsRoot = join(repoRoot, "runs");
  const plain = (await directories(runsRoot)).filter(directory => !directory.endsWith("/suites"));
  const suiteDirectories = await directories(join(runsRoot, "suites"));
  const suiteRuns = (await Promise.all(suiteDirectories.map(async suite => (await Promise.all((await directories(join(suite, "runs"))).map(directories))).flat()))).flat();
  const tournaments = await loadTournaments(repoRoot, [...plain, ...suiteRuns]);
  const rows: EvidenceRow[] = [];
  const excluded: ExcludedRun[] = [];
  const suites: SuiteEntry[] = [];

  for (const directory of suiteDirectories) {
    const state = await readJson<SuiteState>(join(directory, "suite.json")).catch(() => null);
    if (!state) { excluded.push({ runDirectory: relative(repoRoot, directory), reason: "no suite.json" }); continue; }
    const report = await readJson<{ status: "completed" | "failed" }>(join(directory, "report.json")).catch(() => null);
    const dry = state.dryRun || String(state.phases.launch ?? "").startsWith("skipped");
    const status: SuiteEntry["status"] = dry ? "dry run" : report ? report.status : "interrupted";
    suites.push({
      id: state.id, suitePath: state.suitePath, families: state.familyIds, models: state.models.map(modelLabel), commit: state.commit, createdAt: state.createdAt,
      status, phases: state.phases, report: report ? relative(repoRoot, join(directory, "report.md")) : null,
      smoke: Object.fromEntries(Object.entries(state.smoke ?? {}).map(([family, result]) => [family, `${result.ok ? "passed" : "failed"} (${result.detail})`])),
    });
    if (dry) continue;
    const latest = new Map<string, string>();
    for (const run of state.runs) if (run.runDirectory) latest.set(run.key, run.runDirectory);
    const used = new Set<string>();
    for (const plan of state.plans) {
      const runDirectory = latest.get(plan.key);
      if (!runDirectory) continue;
      used.add(resolve(runDirectory));
      const family = state.suite.families.find(candidate => candidate.id === plan.familyId)!;
      const generated = await readJson<EvaluationPlan>(plan.path).catch(() => undefined);
      const result = await runRows(runDirectory, { repoRoot, family, suite: state.id, worktree: state.worktree, ...(generated ? { plan: generated } : {}),
        suiteStatus: report?.status ?? "failed", tournaments });
      rows.push(...result.rows);
      excluded.push(...result.excluded);
    }
    for (const runDirectory of (await Promise.all((await directories(join(directory, "runs"))).map(directories))).flat()) {
      if (!used.has(resolve(runDirectory))) excluded.push({ runDirectory: relative(repoRoot, runDirectory), reason: "an earlier attempt superseded by a later run of the same plan" });
    }
  }
  for (const directory of plain) {
    const result = await runRows(directory, { repoRoot, tournaments });
    rows.push(...result.rows);
    excluded.push(...result.excluded);
  }
  rows.sort((left, right) => left.startedAt.localeCompare(right.startedAt) || left.runDirectory.localeCompare(right.runDirectory) || left.label.localeCompare(right.label));

  const configurations: ConfigurationEntry[] = [];
  for (const suitePath of suiteFiles) {
    const suite = await readJson<SuiteFile>(join(repoRoot, suitePath)).catch(() => null);
    if (!suite) continue;
    for (const family of suite.families) {
      const template = await readJson<EvaluationPlan>(join(repoRoot, family.template)).catch(() => null);
      const packagePath = template?.cases[0]?.packagePath;
      const manifest = packagePath ? await readJson<{ id: string; version: string }>(join(repoRoot, packagePath, "manifest.json")).catch(() => null) : null;
      const trajectory = template?.execution?.kind === "trajectory";
      const contextPolicy = trajectory ? (template!.execution as { contextPolicy: string }).contextPolicy : "single";
      const budget = { trial: template?.budget.maxTrialTokens ?? null, stage: trajectory ? (template!.execution as { stageBudget: { maxTrialTokens?: number } }).stageBudget.maxTrialTokens ?? null : null };
      const matching = rows.filter(row => row.packageId === manifest?.id && row.taskVersion === manifest?.version && row.contextPolicy === contextPolicy &&
        row.budget.trial === budget.trial && row.budget.stage === budget.stage);
      configurations.push({ suite: suitePath, family: family.id, template: family.template, packageId: manifest?.id ?? null, taskVersion: manifest?.version ?? null,
        contextPolicy, budget, matchingRows: matching.length });
    }
  }
  return { generatedAt: new Date().toISOString(), rows, suites, configurations, excluded };
}

// Markdown.

const percent = (value: number | null) => value === null ? "n/a" : `${(value * 100).toFixed(1)}%`;
const millions = (value: number | null) => value === null ? "—" : `${+(value / 1_000_000).toFixed(2)}M`;
const budgetText = (budget: EvidenceRow["budget"]) => budget.stage !== null ? `${millions(budget.stage)}/stage, ${millions(budget.trial)}/trajectory` : `${millions(budget.trial)}/trial`;
const link = (path: string) => `[${path.replace(/^runs\//, "")}](../../${path})`;

/** A claim in a review, with the rows that carry its numbers. */
export interface ReviewReference {
  claim: string;
  /** Rows from this run directory (a suffix match) or suite, optionally one family. */
  runDirectory?: string;
  suite?: string;
  family?: string;
  /** A configuration in the current suites that has no run. */
  configuration?: string;
  note?: string;
}

/** The numbers of the third-party review's §2 table (docs/reviews/2026-10-24-third-party-evaluation-review.md). */
export const REVIEW_REFERENCES: ReviewReference[] = [
  { claim: "T1 0.6.0 F4/F5: DeepSeek 94.3%, Qwen 85% (content all correct, losses from format), MiMo Flash 20%", suite: "20261022-102932-dev-87d3", family: "T1" },
  { claim: "T2 finance 0.3.0 at 6M per day: DeepSeek 98.0%, Qwen 67.6%, MiMo Flash 8.8%; fn1 and fn2 once per model", suite: "20261023-050438-dev-9f16", family: "T2" },
  { claim: "T2 at 10M per day and 4 hours: no completed report", configuration: "T2" },
  { claim: "E3 0.5.0 at 5M per stage, 25M per trajectory: DeepSeek 90%, Qwen 94%, one trajectory each, stage budget stops", suite: "20261023-113824-dev-b319", family: "E3" },
  { claim: "R3 0.3.0 L5–L7: DeepSeek about 72%, Qwen 24%, MiMo Pro 42%, MiMo Flash 28%", runDirectory: "e3b89e80-676e-4b9b-a3dc-f5e2ddff6bfb" },
  { claim: "E2 routes 0.5.0: DeepSeek about 71%, Qwen 17%, MiMo (two configurations) about 56–58%", runDirectory: "a69d9886-bc15-4c80-95c6-c187a1cec105" },
  { claim: "E4 0.5.0 speedup: 87.5% / 100% / 87.5% (DeepSeek / Qwen / MiMo Flash)", suite: "20261021-123806-dev-d275", family: "E4", note: "the speedup entry of the per-item breakdown" },
  { claim: "E4 compress at 4M: DeepSeek 83.3%, Qwen 66.7%", suite: "20261022-050033-dev-0cdf", family: "E4-compress" },
  { claim: "VIS tournament win rates: DeepSeek 83%, Qwen 74%, Luna 57%, Step 26%, GLM 18% (2 pages per model; Qwen from its own run)", runDirectory: "eb491788-9108-41f1-9a32-e671f00873dd", note: "the win rates are in the tournament column; Qwen's row is under run 54429f1e" },
  { claim: "AE 0.1.0: package and offline calibration only; the latest suite is a dry run", suite: "20261023-192640-dev-87c1" },
];

function referenceRows(evidence: Evidence, reference: ReviewReference): EvidenceRow[] {
  return evidence.rows.filter(row => (!reference.suite || row.suite === reference.suite) && (!reference.runDirectory || row.runDirectory.endsWith(reference.runDirectory)) &&
    (!reference.family || row.family === reference.family) && (reference.suite || reference.runDirectory));
}

const shortLabel = (label: string) => label.replace(/^[a-z]+:/, "");
const breakdownText = (row: EvidenceRow) => row.breakdown.length > 1 || (row.breakdown[0] && row.breakdown[0].key !== row.scope.join(", "))
  ? row.breakdown.map(entry => `${entry.key} ${percent(entry.score)}${entry.trials > 1 ? ` (${entry.trials})` : ""}`).join("; ") : "";

export function markdownEvidence(evidence: Evidence): string {
  const lines: string[] = [
    "# v1 Evidence Table", "",
    `Generated ${evidence.generatedAt.slice(0, 10)} by \`npm run evidence\` from \`runs/\`. Do not edit by hand; see [README](README.md).`, "",
    "Each row is one model on one task package in one run directory, under one grader version. Scores are **v1 partial-credit scores** under the row's own task version, grader version and protocol; they are not v2 scores and are never compared across rows with different protocols. A run re-graded under a later grader has one row per grader version.", "",
    "A row re-graded on a v2 manifest (its score runs carry outcome.json) shows the mean v2 primary of its outcomes instead, marked \"v2 primary\" (a resolved rate for contract families, a normalised value for open-ended ones); it is never read as v1 partial credit.", "",
    "Columns: *Trials* is scored / recorded trials (superseded retries left out). *Coverage* lists infrastructure failures (excluded, never zero), trials not run, unscored trials and budget stops (graded as delivered). *Status* is the run's completion: `incomplete` means the run or its suite did not finish its plan.", "",
    "## Review cross-reference", "",
    "Every number in the §2 table of the third-party review, with the rows that carry it.", "",
    "| Claim in the review | Evidence | Source |", "| --- | --- | --- |",
  ];
  for (const reference of REVIEW_REFERENCES) {
    if (reference.configuration) {
      const configurations = evidence.configurations.filter(entry => entry.family === reference.configuration);
      lines.push(`| ${reference.claim} | ${configurations.map(entry => `${entry.suite} ${entry.family}: ${entry.packageId}@${entry.taskVersion}, ${budgetText(entry.budget)}, ${entry.matchingRows ? `${entry.matchingRows} matching rows` : "**never run**"}`).join("; ")} | Configurations below |`);
      continue;
    }
    const suite = reference.suite ? evidence.suites.find(entry => entry.id === reference.suite) : undefined;
    if (suite?.status === "dry run") {
      lines.push(`| ${reference.claim} | **dry run** (no model trials): ${Object.entries(suite.smoke).map(([family, result]) => `${family} smoke ${result}`).join("; ")} | suite ${suite.id} |`);
      continue;
    }
    const found = referenceRows(evidence, reference).filter(row => row.trials > row.infrastructure || row.tournament?.winRate != null);
    const versions = [...new Set(found.map(row => row.graderVersion))];
    const values = versions.map(version => {
      const shown = found.filter(row => row.graderVersion === version);
      const text = shown.map(row => `${shortLabel(row.label)} ${row.tournament ? `win rate ${percent(row.tournament.winRate)}` : percent(row.meanScore)}${breakdownText(row) ? ` [${breakdownText(row)}]` : ""}`).join("; ");
      const kind = shown[0]?.scoreKind === "v2 primary" ? " (v2 primary)" : "";
      return versions.length > 1 ? `grader ${version}${kind}: ${text}` : text;
    }).reverse().join(" — ");
    const first = found[0];
    const source = first ? `${first.suite ? `suite ${first.suite}, ` : ""}${link(first.runDirectory)}; ${first.packageId}@${first.taskVersion}, grader ${versions.join(" then ")}` : "not found";
    lines.push(`| ${reference.claim} | ${values || "**not found**"}${reference.note ? ` (${reference.note})` : ""}. | ${source} |`);
  }

  lines.push("", "## Configurations in the current suites", "",
    "The family templates the suite files point to now, and whether any recorded row ran exactly that package version, context policy and budget.", "",
    "| Suite | Family | Package | Context | Budget | Recorded rows |", "| --- | --- | --- | --- | --- | --- |",
    ...evidence.configurations.map(entry => `| ${entry.suite} | ${entry.family} | ${entry.packageId ?? "?"}@${entry.taskVersion ?? "?"} | ${entry.contextPolicy} | ${budgetText(entry.budget)} | ${entry.matchingRows || "**never run**"} |`));

  const families = [...new Set(evidence.rows.map(row => row.family))].sort((left, right) => {
    const order = ["R3", "T1", "T2", "E2", "E3", "E4", "E4-speedup", "E4-compress", "VIS", "AE"];
    const rank = (family: string) => order.includes(family) ? order.indexOf(family) : order.length;
    return rank(left) - rank(right) || left.localeCompare(right);
  });
  lines.push("", "## Results by family", "");
  for (const family of families) {
    const own = evidence.rows.filter(row => row.family === family);
    lines.push(`### ${family}`, "",
      "| Date | Source | Task | Grader | Protocol | Model | Scope | Trials | Coverage | Score | Resolved | Status |",
      "| --- | --- | --- | --- | --- | --- | --- | ---: | --- | ---: | ---: | --- |");
    for (const row of own) {
      const coverage = [row.infrastructure && `${row.infrastructure} infra`, row.notRun && `${row.notRun} not run`, row.unscored && `${row.unscored} unscored`,
        row.ungraded && `${row.ungraded} not graded under this grader`, row.budgetStops && `${row.budgetStops} budget stops`].filter(Boolean).join(", ") || "—";
      const score = row.tournament ? `win rate ${percent(row.tournament.winRate)}; functional ${percent(row.meanScore)}` :
        row.scoreKind === "v2 primary" ? `v2 primary ${row.meanScore === null ? "n/a" : +row.meanScore.toFixed(3)}` : percent(row.meanScore);
      const scope = `${row.scope.join(", ")}${breakdownText(row) ? `: ${breakdownText(row)}` : ""}`;
      lines.push(`| ${row.startedAt.slice(0, 10)} | ${row.suite ? `suite ${row.suite.slice(0, 15)}… ` : ""}${link(row.runDirectory)} | ${row.packageId.replace(/-.*/, "")}@${row.taskVersion} | ${row.graderVersion ?? "—"} | ${budgetText(row.budget)}; ${row.contextPolicy}${row.budgetNotice === true ? "; stated" : ""} | ${row.label} | ${scope} | ${row.scored}/${row.trials} | ${coverage} | ${score} | ${row.resolved}/${row.decided} | ${row.status} |`);
    }
    lines.push("");
  }

  lines.push("## Suite runs", "", "| Suite | Date | Families | Models | Status | Report |", "| --- | --- | --- | --- | --- | --- |",
    ...evidence.suites.map(suite => `| ${suite.id} | ${suite.createdAt.slice(0, 10)} | ${suite.families.join(", ")} | ${suite.models.map(shortLabel).join(", ")} | ${suite.status} | ${suite.report ? `[report](../../${suite.report})` : "—"} |`),
    "", "Dry runs ran the preflight and a null-agent smoke only; they have no model results:", "",
    ...evidence.suites.filter(suite => suite.status === "dry run").map(suite => `- ${suite.id} (${suite.families.join(", ")}): ${Object.entries(suite.smoke).map(([family, result]) => `${family} smoke ${result}`).join("; ") || "no smoke recorded"}`),
    "", "## Run directories without rows", "",
    "Interrupted runs, superseded attempts and directories without trials. Their trials, if any, are not results.", "",
    "| Run directory | Reason |", "| --- | --- |",
    ...evidence.excluded.map(entry => `| ${entry.runDirectory} | ${entry.reason} |`), "");
  return lines.join("\n");
}
