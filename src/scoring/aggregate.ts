import type { OutcomeRecord } from "./model.js";

/**
 * Aggregation (MEASUREMENT §4, §6): repetitions average within a task, tasks weigh equally within a family except that
 * no structure group weighs more than its cap, capabilities average their core families with declared weights, and
 * saturation and headroom are read per family and pool.
 */

export interface TaskScore {
  model: string;
  taskId: string;
  /** The task within the family: a package item, or the package itself. */
  task: string;
  structure: string;
  /** Mean primary over the task's scored trials; null when none was scored. */
  primary: number | null;
  resolvedRate: number | null;
  trials: number;
  scored: number;
}

const taskKey = (outcome: OutcomeRecord) => outcome.task.itemId ? `${outcome.task.id}@${outcome.task.itemId}` : outcome.task.id;

/** Per model and task: the mean primary and resolved rate over scored repetitions. */
export function taskScores(outcomes: OutcomeRecord[]): TaskScore[] {
  const groups = new Map<string, OutcomeRecord[]>();
  for (const outcome of outcomes) {
    const key = `${outcome.model}\u0000${taskKey(outcome)}`;
    groups.set(key, [...(groups.get(key) ?? []), outcome]);
  }
  return [...groups.values()].map(group => {
    const first = group[0]!;
    const scored = group.filter(outcome => outcome.coverage === "scored" && outcome.primary !== null);
    const mean = (values: number[]) => values.length ? values.reduce((total, value) => total + value, 0) / values.length : null;
    return {
      model: first.model, taskId: first.task.id, task: taskKey(first), structure: first.task.structure ?? taskKey(first),
      primary: mean(scored.map(outcome => outcome.primary!)), resolvedRate: mean(scored.map(outcome => outcome.resolved ? 1 : 0)),
      trials: group.length, scored: scored.length,
    };
  }).sort((left, right) => left.model.localeCompare(right.model) || left.task.localeCompare(right.task));
}

/**
 * Task weights within a family: equal, except that a structure group whose share of the tasks exceeds the cap is
 * brought down to it and the weight it loses goes to the other groups in proportion to their tasks. When there are
 * too few groups for the cap to hold (groups × cap < 1), every group weighs the same instead.
 */
export function taskWeights(tasks: Array<{ task: string; structure: string }>, cap = 0.2): Map<string, number> {
  const byGroup = new Map<string, string[]>();
  for (const entry of tasks) byGroup.set(entry.structure, [...(byGroup.get(entry.structure) ?? []), entry.task]);
  const groups = [...byGroup.keys()];
  const shares = new Map<string, number>();
  if (groups.length * cap < 1 - 1e-12) {
    for (const group of groups) shares.set(group, 1 / groups.length);
  } else {
    const fixed = new Set<string>();
    for (;;) {
      const freeTasks = groups.filter(group => !fixed.has(group)).reduce((total, group) => total + byGroup.get(group)!.length, 0);
      const freeShare = 1 - fixed.size * cap;
      const over = groups.filter(group => !fixed.has(group) && byGroup.get(group)!.length / freeTasks * freeShare > cap + 1e-12);
      if (!over.length) {
        for (const group of groups) shares.set(group, fixed.has(group) ? cap : byGroup.get(group)!.length / freeTasks * freeShare);
        break;
      }
      for (const group of over) fixed.add(group);
    }
  }
  const weights = new Map<string, number>();
  for (const [group, members] of byGroup) for (const task of members) weights.set(task, shares.get(group)! / members.length);
  return weights;
}

/** The weighted mean of task primaries for one model, over tasks with a score; null when there are none. */
export function familyMean(tasks: TaskScore[], cap = 0.2): number | null {
  const scored = tasks.filter(task => task.primary !== null);
  if (!scored.length) return null;
  const weights = taskWeights(scored, cap);
  return scored.reduce((total, task) => total + weights.get(task.task)! * task.primary!, 0);
}

/** A capability's score: its core families' means with frozen weights; families without a score are left out. */
export function capabilityMean(families: Record<string, number | null>, weights: Record<string, number>): number | null {
  const present = Object.entries(weights).filter(([family]) => families[family] !== null && families[family] !== undefined);
  const total = present.reduce((sum, [, weight]) => sum + weight, 0);
  return total > 0 ? present.reduce((sum, [family, weight]) => sum + weight * families[family]!, 0) / total : null;
}

export interface Saturation {
  tasks: number;
  /** Tasks every model resolved, and tasks none resolved (contract families). */
  solvedByAll: number;
  solvedByNone: number;
  /** Open-ended tasks where the best model reaches the strong anchor (normalised at least 1). */
  bestAboveStrong: number;
  /** The best model's family score minus the worst's. */
  spread: number | null;
}

/** Saturation and headroom over the tasks every model of the pool has a score on. */
export function saturation(tasks: TaskScore[], models: string[], openEnded: boolean, cap = 0.2): Saturation {
  const byTask = new Map<string, TaskScore[]>();
  for (const task of tasks) byTask.set(task.task, [...(byTask.get(task.task) ?? []), task]);
  const complete = [...byTask.values()].filter(group => models.every(model => group.some(task => task.model === model && task.primary !== null)));
  const solved = (task: TaskScore) => openEnded ? (task.primary ?? 0) >= 1 : task.resolvedRate === 1;
  const means = models.map(model => familyMean(tasks.filter(task => task.model === model), cap)).filter((value): value is number => value !== null);
  return {
    tasks: complete.length,
    solvedByAll: openEnded ? 0 : complete.filter(group => group.every(solved)).length,
    solvedByNone: openEnded ? 0 : complete.filter(group => group.every(task => (task.resolvedRate ?? 0) === 0)).length,
    bestAboveStrong: openEnded ? complete.filter(group => Math.max(...group.map(task => task.primary ?? 0)) >= 1).length : 0,
    spread: means.length >= 2 ? Math.max(...means) - Math.min(...means) : null,
  };
}
