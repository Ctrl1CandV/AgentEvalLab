import { parseModel } from "../config.js";
import type { ModelSelection, PlanThinkingLevel } from "../types.js";
import { combineOrders, judgePair, type Design, type Verdict } from "./judge.js";

/** Vision-verified judges at their middle thinking levels, one per vendor. */
export const DEFAULT_JUDGES = ["supergpt:gpt-6-luna?thinking=medium", "supercn:step-5-preview?thinking=medium",
  "deepseek:deepseek-flash?thinking=high", "supercn:glm-5.3-flash?thinking=provider-default", "aliplan:qwen3.8-flash?thinking=provider-default"];

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

/**
 * Degradations for the judge exam: a style block appended to a page, each making it clearly worse in one respect
 * (spacing, contrast, type, phone layout). A competent judge prefers the original in both orders.
 */
export const DEGRADATIONS: Record<string, string> = {
  cramped: "*, *::before, *::after { margin: 0 !important; padding: 0 !important; gap: 0 !important; }",
  "low-contrast": "*, *::before, *::after { color: #c8c8c8 !important; }",
  "plain-type": "* { font-family: 'Courier New', monospace !important; font-size: 12px !important; line-height: 1.05 !important; font-weight: 400 !important; }",
  "phone-overflow": "body > * { min-width: 1500px !important; }",
};

/** The page's index.html with a degradation's style block appended at the end of the document. */
export function degradeHtml(html: string, kind: string): string {
  const style = `<style data-exam="${kind}">${DEGRADATIONS[kind]}</style>`;
  return html.includes("</body>") ? html.replace(/<\/body>(?![\s\S]*<\/body>)/, `${style}</body>`) : html + style;
}

export type ExamCase = { name: string; good: (label: "A" | "B") => Promise<Design>; bad: (label: "A" | "B") => Promise<Design> };
export type ExamResult = { judge: string; score: number; inconsistent: number; cases: number; passed: boolean;
  outcomes: Record<string, string>; usage: Array<{ input: number; output: number }> };

/** Pass marks of the judge exam: the better page wins at least this share (a tie counts half), and at most this
 * share of cases flips with the order. */
export const EXAM_PASS_SCORE = 0.75;
export const EXAM_MAX_INCONSISTENT = 0.25;

/**
 * Judge exam: each judge compares pairs whose better page is known, in both orders. A judge is used only if it
 * prefers the better page often enough and is not swayed by position too often.
 */
export async function judgeExam(judges: ModelSelection[], skill: string, cases: ExamCase[], concurrency: number): Promise<ExamResult[]> {
  const rows = await pool(judges.flatMap(judge => cases.map(item => async () => {
    const one = await callJudge(judge, skill, await item.good("A"), await item.bad("B"));
    const two = await callJudge(judge, skill, await item.bad("A"), await item.good("B"));
    return { judge: judgeLabel(judge), name: item.name, ...combineOrders(one.verdict?.overall ?? null, two.verdict?.overall ?? null), usage: [one.usage, two.usage] };
  })), concurrency);
  return judges.map(judge => {
    const own = rows.filter(row => row.judge === judgeLabel(judge));
    const score = own.reduce((sum, row) => sum + (row.outcome === "win" ? 1 : row.outcome === "tie" ? 0.5 : 0), 0) / Math.max(1, own.length);
    const inconsistent = own.filter(row => row.inconsistent).length / Math.max(1, own.length);
    return { judge: judgeLabel(judge), score, inconsistent, cases: own.length, passed: score >= EXAM_PASS_SCORE && inconsistent <= EXAM_MAX_INCONSISTENT,
      outcomes: Object.fromEntries(own.map(row => [row.name, row.outcome])), usage: own.flatMap(row => row.usage) };
  });
}
