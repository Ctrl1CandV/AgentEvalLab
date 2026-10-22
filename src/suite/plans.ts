import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { modelLabel } from "../evaluation/report.js";
import { resolveCaseItems } from "../evaluation/items.js";
import type { ManifestItem, PackageDescriptor } from "../evaluation/manifest.js";
import type { EvaluationPlan } from "../evaluation/types.js";
import type { Budget, ModelSelection } from "../types.js";
import type { FamilyKind, FamilySpec } from "./spec.js";

/** Only the task budget may stop a model (PLAN-005): one response may hold this many output tokens and characters. */
export const RESPONSE_TOKENS = 131_072;
export const RESPONSE_CHARS = 524_288;
/** The per-model token ceiling allows each trial this multiple of its budget. */
export const CEILING_SLACK = 1.25;

export interface GeneratedPlan {
  /** Unique within the suite: the family id, plus the model and repetition for trajectory plans. */
  key: string;
  familyId: string;
  kind: FamilyKind;
  plan: EvaluationPlan;
  /** Trajectory plans run one model each. */
  model?: string;
  repetition?: number;
  /** Changes made to the template to satisfy the standing rules, for the record. */
  adjustments: string[];
}

/** Objects merge key by key; arrays and other values replace. */
export function mergeOverrides<T>(base: T, overrides: Record<string, unknown> | undefined): T {
  if (!overrides) return base;
  const merged: Record<string, unknown> = { ...(base as Record<string, unknown>) };
  for (const [key, value] of Object.entries(overrides)) {
    const current = merged[key];
    merged[key] = value && typeof value === "object" && !Array.isArray(value) && current && typeof current === "object" && !Array.isArray(current)
      ? mergeOverrides(current, value as Record<string, unknown>) : value;
  }
  return merged as T;
}

/** Raise per-response limits to the standing values; returns what changed. */
function applyResponseLimits(budget: Budget, scope: string): string[] {
  const changes: string[] = [];
  if (budget.maxOutputTokensPerCall < RESPONSE_TOKENS) {
    changes.push(`${scope}.maxOutputTokensPerCall ${budget.maxOutputTokensPerCall} -> ${RESPONSE_TOKENS}`);
    budget.maxOutputTokensPerCall = RESPONSE_TOKENS;
  }
  if (budget.maxOutputChars < RESPONSE_CHARS) {
    changes.push(`${scope}.maxOutputChars ${budget.maxOutputChars} -> ${RESPONSE_CHARS}`);
    budget.maxOutputChars = RESPONSE_CHARS;
  }
  return changes;
}

const slug = (value: string) => value.replace(/[^A-Za-z0-9._-]+/g, "-");

/**
 * The plans one family runs: its template with the suite's models and repetitions, the overrides applied, the
 * standing rules enforced (stated budget, response limits), and a per-model token ceiling above the worst case, so that
 * the ceiling never leaves a planned trial unrun. `trialsPerModel` counts one model's trials in a plan.
 */
export function generateFamilyPlans(family: FamilySpec, template: EvaluationPlan, models: ModelSelection[], repetitions: number,
  suiteId: string, trialsPerModel: (plan: EvaluationPlan) => number): GeneratedPlan[] {
  const base = mergeOverrides(structuredClone(template), family.overrides);
  delete base.seed;
  const adjustments: string[] = [];
  if (!base.budgetNotice) {
    base.budgetNotice = true;
    adjustments.push("budgetNotice -> true");
  }
  base.budget = { ...base.budget };
  adjustments.push(...applyResponseLimits(base.budget, "budget"));
  if (base.execution?.kind === "trajectory") {
    base.execution = { ...base.execution, stageBudget: { ...base.execution.stageBudget } };
    adjustments.push(...applyResponseLimits(base.execution.stageBudget, "stageBudget"));
  }
  // A trial may pass its token budget by its last request, so the ceiling, a spending fuse, leaves a quarter of a
  // budget per trial on top: with the bare product, one trial's overshoot kept the next from starting.
  const finish = (plan: EvaluationPlan): EvaluationPlan => {
    const perTrial = plan.budget.maxTrialTokens;
    if (typeof perTrial === "number") plan.batch = { ...plan.batch, maxTotalTokensPerModel: Math.ceil(perTrial * CEILING_SLACK) * trialsPerModel(plan) };
    return plan;
  };
  if (family.kind === "trajectory") {
    if (base.execution?.kind !== "trajectory") throw new Error(`SUITE_TEMPLATE_KIND:${family.id}`);
    const plans: GeneratedPlan[] = [];
    for (let repetition = 1; repetition <= repetitions; repetition++) {
      for (const model of models) {
        const label = modelLabel(model);
        const suffix = `${slug(label)}${repetitions > 1 ? `-r${repetition}` : ""}`;
        const plan = finish({ ...structuredClone(base), name: `suite-${suiteId}-${family.id}-${suffix}`, models: [model] });
        delete plan.repetitions;
        plans.push({ key: `${family.id}-${suffix}`, familyId: family.id, kind: family.kind, plan, model: label, repetition, adjustments });
      }
    }
    return plans;
  }
  if (base.execution?.kind === "trajectory") throw new Error(`SUITE_TEMPLATE_KIND:${family.id}`);
  const plan = finish({ ...base, name: `suite-${suiteId}-${family.id}`, models, repetitions });
  return [{ key: family.id, familyId: family.id, kind: family.kind, plan, adjustments }];
}

/** Read a package's generated items from its manifest, or null for a package without items. */
export async function packageItems(root: string, packagePath: string): Promise<ManifestItem[] | null> {
  const manifest = JSON.parse(await readFile(resolve(root, packagePath, "manifest.json"), "utf8")) as { items?: ManifestItem[] };
  return manifest.items ?? null;
}

/** The items a plan case runs, resolved as the harness resolves them. */
export function caseItems(plan: EvaluationPlan, items: Map<string, ManifestItem[] | null>): ManifestItem[] | null {
  const item = plan.cases[0]!;
  const descriptor = { manifest: { items: items.get(item.packagePath ?? "") ?? undefined } } as unknown as PackageDescriptor;
  return resolveCaseItems(item, descriptor);
}

/** Does a trial's item count toward the family score? */
export function inScore(family: FamilySpec, itemId: string | undefined | null, level: string | undefined | null): boolean {
  if (!family.score) return true;
  if (family.score.items) return !!itemId && family.score.items.includes(itemId);
  return !!level && family.score.levels!.includes(level);
}

/**
 * The zero-token smoke plan for a family: one model (the null agent sends nothing), one repetition and one item, the
 * first scored item of the plan.
 */
export function smokePlan(generated: GeneratedPlan, family: FamilySpec, items: ManifestItem[] | null): EvaluationPlan {
  const plan: EvaluationPlan = { ...structuredClone(generated.plan), name: `${generated.plan.name}-smoke`, models: [generated.plan.models[0]!] };
  if (generated.kind !== "trajectory") plan.repetitions = 1;
  if (items) {
    const first = items.find(item => inScore(family, item.id, item.level)) ?? items[0]!;
    plan.cases = plan.cases.map(item => ({ ...item, items: [first.id] }));
  }
  return plan;
}
