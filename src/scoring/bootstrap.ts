import { pairedDifference, seededRandom } from "../evaluation/statistics.js";
import { familyMean, taskWeights, type TaskScore } from "./aggregate.js";

/**
 * Uncertainty over independent tasks (MEASUREMENT §5): a seeded cluster bootstrap that resamples structure groups,
 * never checks or repetitions, and paired comparisons by task. With fewer than five groups there is no interval.
 */

export const RESAMPLES = 2_000;
export const MIN_GROUPS = 5;

export type Interval = { low: number; high: number } | "n too small";

function percentile(sorted: number[], share: number): number {
  const position = (sorted.length - 1) * share;
  const lower = Math.floor(position);
  const upper = Math.ceil(position);
  return sorted[lower]! + (sorted[upper]! - sorted[lower]!) * (position - lower);
}

/** Groups resampled with replacement; each resample keeps every task of a drawn group, renamed so repeats stay apart. */
function resampleGroups<T extends { structure: string; task: string }>(items: T[], random: () => number): T[] {
  const groups = [...new Set(items.map(item => item.structure))].sort();
  const members = new Map(groups.map(group => [group, items.filter(item => item.structure === group)]));
  const drawn: T[] = [];
  for (let index = 0; index < groups.length; index++) {
    const group = groups[Math.floor(random() * groups.length)]!;
    for (const item of members.get(group)!) drawn.push({ ...item, structure: `${group}#${index}`, task: `${item.task}#${index}` });
  }
  return drawn;
}

/** The resampled family means of one model (seeded), or null with fewer than MIN_GROUPS structure groups. */
export function familyResamples(tasks: TaskScore[], seed: number, cap = 0.2, resamples = RESAMPLES): number[] | null {
  const scored = tasks.filter(task => task.primary !== null);
  if (new Set(scored.map(task => task.structure)).size < MIN_GROUPS) return null;
  const random = seededRandom(seed);
  const values: number[] = [];
  for (let index = 0; index < resamples; index++) values.push(familyMean(resampleGroups(scored, random), cap)!);
  return values;
}

/** The percentile 95% interval of resampled values. */
export function intervalOf(values: number[] | null): Interval {
  if (!values) return "n too small";
  const sorted = [...values].sort((left, right) => left - right);
  return { low: percentile(sorted, 0.025), high: percentile(sorted, 0.975) };
}

/**
 * Several families' resamples combined with weights, resample by resample (a stratified bootstrap: each family's
 * groups are resampled within the family). Null when any weighted family has too few groups.
 */
export function combineResamples(parts: Array<{ weight: number; values: number[] | null }>): number[] | null {
  if (!parts.length || parts.some(part => !part.values)) return null;
  const total = parts.reduce((sum, part) => sum + part.weight, 0);
  return parts[0]!.values!.map((_, index) => parts.reduce((sum, part) => sum + part.weight * part.values![index]!, 0) / total);
}

/** A percentile 95% interval of one model's family mean, by resampling structure groups (seeded, so reports repeat). */
export function familyInterval(tasks: TaskScore[], seed: number, cap = 0.2, resamples = RESAMPLES): Interval {
  return intervalOf(familyResamples(tasks, seed, cap, resamples));
}

export interface PairedComparison {
  modelA: string;
  modelB: string;
  /** Tasks both models have a score on. */
  tasks: number;
  meanDifference: number | null;
  interval: Interval;
  /** Shares of those tasks where A is ahead, B is ahead, and where they tie. */
  ahead: { a: number; b: number; tie: number };
  /** The task-level t interval of the existing pairedDifference, as a cross-check. */
  tInterval: [number, number] | null;
  /** The resampled differences behind the interval, for combining families; null with too few groups. */
  resamples: number[] | null;
}

/**
 * A against B, paired by task: the difference of their family means over the tasks both have (task weights with the
 * structure cap, as in the family mean), a cluster-bootstrap interval, and who is ahead how often.
 */
export function pairedComparison(tasks: TaskScore[], modelA: string, modelB: string, seed: number, cap = 0.2, resamples = RESAMPLES): PairedComparison {
  const pairs: Array<{ task: string; structure: string; difference: number }> = [];
  for (const left of tasks.filter(task => task.model === modelA && task.primary !== null)) {
    const right = tasks.find(task => task.model === modelB && task.task === left.task && task.primary !== null);
    if (right) pairs.push({ task: left.task, structure: left.structure, difference: left.primary! - right.primary! });
  }
  const n = pairs.length;
  const mean = (values: Array<{ task: string; structure: string; difference: number }>) => {
    const weights = taskWeights(values, cap);
    return values.reduce((total, value) => total + weights.get(value.task)! * value.difference, 0);
  };
  let values: number[] | null = null;
  if (new Set(pairs.map(pair => pair.structure)).size >= MIN_GROUPS) {
    const random = seededRandom(seed);
    values = [];
    for (let index = 0; index < resamples; index++) values.push(mean(resampleGroups(pairs, random)));
  }
  const t = pairedDifference(pairs.map(pair => pair.difference));
  return {
    modelA, modelB, tasks: n, meanDifference: n ? mean(pairs) : null, interval: intervalOf(values), resamples: values,
    ahead: { a: n ? pairs.filter(pair => pair.difference > 0).length / n : 0, b: n ? pairs.filter(pair => pair.difference < 0).length / n : 0,
      tie: n ? pairs.filter(pair => pair.difference === 0).length / n : 0 },
    tInterval: t.interval,
  };
}
