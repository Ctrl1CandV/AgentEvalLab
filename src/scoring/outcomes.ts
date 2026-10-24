import { readFile, readdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import type { PackageDescriptor } from "../evaluation/manifest.js";
import type { EvaluationResult } from "../evaluation/types.js";
import { modelLabel } from "../evaluation/report.js";
import type { ExecutionResult, ModelSelection } from "../types.js";
import { buildOutcome, type OutcomeRecord } from "./model.js";

/**
 * outcome.json (CODE §3.5, PLAN-007 WP1.4): the task outcome record, written beside score.json in the score run it was
 * computed from. Only v2 packages (with a score model) get one; a re-grade appends a new score run and so a new outcome,
 * and the old ones stay readable.
 */

export interface OutcomeContext {
  trialId: string;
  model: ModelSelection;
  descriptor: PackageDescriptor;
  itemId: string | null;
  repetition?: number;
  evaluation: EvaluationResult;
  execution: ExecutionResult;
  scoreRunId: string;
}

/** Builds the outcome and writes it into the score run directory; does nothing for a v1 package. */
export async function writeOutcome(scoreRunDirectory: string, context: OutcomeContext): Promise<OutcomeRecord | null> {
  const manifest = context.descriptor.manifest;
  if (!manifest?.scoreModel) return null;
  const item = context.itemId ? manifest.items?.find(candidate => candidate.id === context.itemId) : undefined;
  const placement = item ?? manifest.task;
  const outcome = buildOutcome({
    trialId: context.trialId, model: modelLabel(context.model), taskId: manifest.id, taskVersion: manifest.version, graderVersion: manifest.grader.version,
    itemId: context.itemId, split: placement?.split ?? null, structure: placement?.structure ?? null, repetition: context.repetition ?? 1,
    evaluation: context.evaluation, ...(context.evaluation.metrics ? { metrics: context.evaluation.metrics } : {}), execution: context.execution,
    scoreModel: manifest.scoreModel, ...(placement?.anchors ? { anchors: placement.anchors } : {}), scoreRunId: context.scoreRunId,
  });
  await writeFile(join(scoreRunDirectory, "outcome.json"), JSON.stringify(outcome, null, 2), { encoding: "utf8", flag: "wx" });
  return outcome;
}

/**
 * Every trial's latest outcome in a run directory: for each trial, the outcome of its most recent score run that has
 * one (a trajectory's outcome sits in the score run of its last graded snapshot).
 */
export async function loadOutcomes(runDirectory: string): Promise<OutcomeRecord[]> {
  const outcomes: OutcomeRecord[] = [];
  const entries = await readdir(runDirectory, { withFileTypes: true }).catch(() => []);
  for (const entry of entries) {
    if (!entry.isDirectory() || entry.name.startsWith(".")) continue;
    const scoreRuns = join(runDirectory, entry.name, "score-runs");
    const found: Array<{ createdAt: string; outcome: OutcomeRecord }> = [];
    for (const run of await readdir(scoreRuns, { withFileTypes: true }).catch(() => [])) {
      if (!run.isDirectory() || run.name.startsWith(".")) continue;
      const outcome = await readFile(join(scoreRuns, run.name, "outcome.json"), "utf8").then(text => JSON.parse(text) as OutcomeRecord, () => null);
      if (!outcome) continue;
      const score = await readFile(join(scoreRuns, run.name, "score.json"), "utf8").then(text => JSON.parse(text) as { createdAt?: string }, () => ({ createdAt: "" }));
      found.push({ createdAt: score.createdAt ?? "", outcome });
    }
    const latest = found.sort((left, right) => left.createdAt.localeCompare(right.createdAt)).at(-1);
    if (latest) outcomes.push(latest.outcome);
  }
  // A trial a resumed batch replaced keeps its files but is not an outcome of the run.
  const superseded = new Set<string>();
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const record = await readFile(join(runDirectory, entry.name, "result.json"), "utf8").then(text => JSON.parse(text) as { supersedes?: string | null }, () => null);
    if (record?.supersedes) superseded.add(record.supersedes);
  }
  return outcomes.filter(outcome => !superseded.has(outcome.trialId)).sort((left, right) => left.trialId.localeCompare(right.trialId));
}
