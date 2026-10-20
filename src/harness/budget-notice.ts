import type { Budget } from "../types.js";

/** Fractions of a limit after which the model gets one budget status (PLAN-005 WP3; user decision, 2026-10-16). */
export const defaultReminderThresholds: readonly number[] = Object.freeze([0.5, 0.75, 0.9]);

export interface BudgetUse {
  tokens: number;
  modelCalls: number;
  toolCalls: number;
  elapsedMs: number;
}

const count = (value: number) => Math.round(value).toLocaleString("en-US");
const minutes = (ms: number) => Number((ms / 60_000).toFixed(1)).toString();
const percent = (fraction: number) => `${Math.round(fraction * 100)}%`;

/** Model responses a trial may make: both the turn and the model-call limits bind. */
const responseLimit = (budget: Budget) => Math.min(budget.maxTurns, budget.maxModelCalls);

/**
 * The fixed budget paragraph appended to a task prompt. One template serves every task and model, so the
 * statement itself is part of the evaluated condition.
 */
export function budgetStatement(budget: Budget, thresholds: readonly number[] = defaultReminderThresholds): string {
  const lines = ["Budget for this task, the same for every model:"];
  if (budget.maxTrialTokens != null) {
    lines.push(`- Tokens: at most ${count(budget.maxTrialTokens)} for the whole task, counting all input and output of every request, ` +
      "including your reasoning and the conversation context that is sent again with each request.");
  }
  lines.push(`- Model responses: at most ${count(responseLimit(budget))}, each with at most ${count(budget.maxOutputTokensPerCall)} output tokens.`);
  lines.push(`- Tool calls: at most ${count(budget.maxToolCalls)}.`);
  lines.push(`- Time: at most ${minutes(budget.timeoutMs)} minutes.`);
  lines.push(`- Final reply: at most ${count(budget.maxOutputChars)} characters.`);
  lines.push("When any limit is reached, the task stops at once and your work is graded as it stands." +
    (thresholds.length ? ` You will receive a short budget status after you pass ${thresholds.map(percent).join(", ").replace(/, ([^,]*)$/, " and $1")} of any limit.` : ""));
  return lines.join("\n");
}

/** The largest fraction of any limit that has been used. */
export function budgetFraction(budget: Budget, use: BudgetUse): number {
  const fractions = [use.modelCalls / responseLimit(budget), use.toolCalls / Math.max(1, budget.maxToolCalls), use.elapsedMs / budget.timeoutMs];
  if (budget.maxTrialTokens != null) fractions.push(use.tokens / budget.maxTrialTokens);
  return Math.max(...fractions);
}

/**
 * The budget paragraph of a multi-stage task: the limits of the whole task and of each stage. Reminders in a stage
 * count against what that stage started with, which is the smaller of the stage's limits and what the task has left.
 */
export function trajectoryBudgetStatement(total: Budget, stage: Budget, thresholds: readonly number[] = defaultReminderThresholds): string {
  const limits = (budget: Budget) => [
    ...(budget.maxTrialTokens != null ? [`${count(budget.maxTrialTokens)} tokens`] : []),
    `${count(responseLimit(budget))} model responses`,
    `${count(budget.maxToolCalls)} tool calls`,
    `${minutes(budget.timeoutMs)} minutes`,
  ].join(", ");
  const lines = ["Budget for this task, the same for every model:",
    `- The whole task, all stages together: at most ${limits(total)}. Tokens count all input and output of every request, including your reasoning and the conversation context that is sent again with each request.`,
    `- Each stage: at most ${limits(stage)}, and never more than the whole task has left.`,
    `- Every response: at most ${count(Math.min(total.maxOutputTokensPerCall, stage.maxOutputTokensPerCall))} output tokens.`,
    "When any limit is reached, the task stops at once and your work is graded as it stands." +
      (thresholds.length ? ` In each stage you will receive a short budget status after you pass ${thresholds.map(percent).join(", ").replace(/, ([^,]*)$/, " and $1")} of what that stage started with.` : "")];
  return lines.join("\n");
}

/** One budget status line, sent when usage passes a reminder threshold. */
export function budgetStatus(budget: Budget, use: BudgetUse, scope: "trial" | "stage" = "trial"): string {
  const parts = [];
  if (budget.maxTrialTokens != null) parts.push(`${count(use.tokens)} of ${count(budget.maxTrialTokens)} tokens (${percent(use.tokens / budget.maxTrialTokens)})`);
  parts.push(`${count(use.modelCalls)} of ${count(responseLimit(budget))} model responses`);
  parts.push(`${count(use.toolCalls)} of ${count(budget.maxToolCalls)} tool calls`);
  parts.push(`${minutes(use.elapsedMs)} of ${minutes(budget.timeoutMs)} minutes`);
  return scope === "stage" ? `[Budget status] Used so far in this stage, of what it started with: ${parts.join(", ")}.` : `[Budget status] Used so far: ${parts.join(", ")}.`;
}

/** Validate reminder thresholds: strictly increasing fractions between 0 and 1. */
export function validReminderThresholds(value: unknown): value is number[] {
  return Array.isArray(value) && value.length <= 10 && value.every((item, index) => typeof item === "number" && item > 0 && item < 1 &&
    (index === 0 || item > (value[index - 1] as number)));
}
