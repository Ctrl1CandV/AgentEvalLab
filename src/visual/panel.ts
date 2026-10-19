import { parseModel } from "../config.js";
import type { ModelSelection, PlanThinkingLevel } from "../types.js";
import { combineOrders, judgePair, type Design, type Verdict } from "./judge.js";

/** Vision-verified judges at their middle thinking levels, one per vendor. */
export const DEFAULT_JUDGES = ["supergpt:gpt-6-luna?thinking=medium", "supercn:step-5-preview?thinking=medium",
  "deepseek:deepseek-flash?thinking=high", "supercn:glm-5.3-flash?thinking=provider-default"];

/** A judge in provider-check syntax, provider:model?thinking=<level>. */
export function judgeSelection(spec: string): ModelSelection {
  const [model, query = ""] = spec.split("?", 2);
  const thinking = new URLSearchParams(query).get("thinking") ?? "provider-default";
  return { ...parseModel(model!), thinkingLevel: thinking as PlanThinkingLevel, temperature: 0 };
}

export const judgeLabel = (judge: ModelSelection) => `${judge.provider}:${judge.id}`;

/** Run tasks with at most `limit` in flight; results keep the task order. */
export async function pool<T>(tasks: Array<() => Promise<T>>, limit: number): Promise<T[]> {
  const results: T[] = new Array(tasks.length);
  let next = 0;
  await Promise.all(Array.from({ length: Math.max(1, Math.min(limit, tasks.length)) }, async () => {
    while (next < tasks.length) { const index = next++; results[index] = await tasks[index]!(); }
  }));
  return results;
}

export type JudgeCall = { verdict: Verdict | null; usage: { input: number; output: number }; raw: string };

/** One judge call; a provider failure counts as a missing verdict rather than stopping the run. */
export async function callJudge(judge: ModelSelection, skill: string, first: Design, second: Design): Promise<JudgeCall> {
  try { return await judgePair(judge, skill, first, second); }
  catch { return { verdict: null, usage: { input: 0, output: 0 }, raw: "" }; }
}

/** Anchor gate: a judge's verdicts count only if it prefers the reference over the plain anchor in both orders. */
export async function anchorGate(judges: ModelSelection[], skill: string, design: (label: "A" | "B", anchor: "reference" | "plain") => Promise<Design>, concurrency: number) {
  return pool(judges.map(judge => async () => {
    const one = await callJudge(judge, skill, await design("A", "reference"), await design("B", "plain"));
    const two = await callJudge(judge, skill, await design("A", "plain"), await design("B", "reference"));
    const combined = combineOrders(one.verdict?.overall ?? null, two.verdict?.overall ?? null);
    return { judge: judgeLabel(judge), passed: combined.outcome === "win", outcome: combined.outcome, usage: [one.usage, two.usage] };
  }), concurrency);
}

/**
 * Bradley–Terry strengths from pairwise results, by the MM algorithm (Hunter 2004). A tie counts as half a win for each
 * side. Strengths are normalised to a geometric mean of 1, so a strength ratio of 2 means 2:1 odds of being preferred.
 */
export function bradleyTerry(players: string[], games: Array<{ a: string; b: string; scoreA: number }>, iterations = 1_000): Record<string, number> {
  const strength = Object.fromEntries(players.map(player => [player, 1]));
  for (let round = 0; round < iterations; round++) {
    const next: Record<string, number> = {};
    for (const player of players) {
      let wins = 0, denominator = 0;
      for (const game of games) {
        if (game.a !== player && game.b !== player) continue;
        const other = game.a === player ? game.b : game.a;
        wins += game.a === player ? game.scoreA : 1 - game.scoreA;
        denominator += 1 / (strength[player]! + strength[other]!);
      }
      // A small prior (half a win against an average opponent) keeps an all-loss or all-win player finite.
      next[player] = (wins + 0.5) / (denominator + 1 / (strength[player]! + 1));
    }
    const logMean = players.reduce((sum, player) => sum + Math.log(next[player]!), 0) / players.length;
    for (const player of players) strength[player] = next[player]! / Math.exp(logMean);
  }
  return strength;
}
