import { parseModel } from "../config.js";
import { lookupModelConfig } from "../providers.js";
import { providerHost } from "../evaluation/provider-slots.js";
import { thinkingLevels, type ModelSelection, type PlanThinkingLevel } from "../types.js";

/**
 * A suite file (suites/<name>.json, PLAN-006 Part A): the families to run and how each is scored. Models and
 * repetitions are not part of it; they come from the command line, so the same suite serves a dev round and the
 * real evaluation.
 */
export interface SuiteFile {
  schemaVersion: 1;
  name: string;
  description?: string;
  /** The model the hardening aims at; a family where it scores above maxScore is flagged. */
  target?: { model: string; maxScore: number };
  /** Concurrent trials per provider endpoint host across every process of a launch; "*" is the default. */
  providerConcurrency: Record<string, number>;
  /** Spending rules a launch must satisfy before anything runs (the dev-run policy). */
  policy?: SuitePolicy;
  families: FamilySpec[];
}

export interface SuitePolicy {
  maxModels?: number;
  maxRepetitions?: number;
  /** At most this many models per endpoint host, such as the airy.work relay with its small balance. */
  maxModelsPerHost?: Record<string, number>;
  /** Regular expressions over model ids that may not run, such as "-pro$". */
  forbiddenModels?: string[];
}

export type FamilyKind = "single" | "trajectory" | "visual";

export interface FamilySpec {
  id: string;
  kind: FamilyKind;
  /** Repository-relative template plan: package, items or levels, budget, batch and artifact limits. */
  template: string;
  /** The items or levels that make up the family score; omitted means every trial of the plan. */
  score?: { items?: string[]; levels?: string[] };
  /** Merged into the generated plan: objects key by key, anything else replaced. */
  overrides?: Record<string, unknown>;
  /** Open-ended items always use their whole budget (their time limit), so budget stops are not flagged. */
  openEnded?: boolean;
  /** The most a null agent may score in the smoke step; default 0. */
  smokeMaxScore?: number;
  /** Visual families: the tournament's judges, in model syntax; omitted means the tournament's defaults. */
  judges?: string[];
  /** Visual families: the package the tournament reads its judging skill from. */
  visualPackage?: string;
}

const identifier = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/;

export function validateSuite(value: unknown): SuiteFile {
  const fail = (detail: string): never => { throw new Error(`SUITE_INVALID:${detail}`); };
  if (!value || typeof value !== "object" || Array.isArray(value)) fail("root");
  const suite = value as SuiteFile;
  if (suite.schemaVersion !== 1) fail("schemaVersion");
  if (typeof suite.name !== "string" || !identifier.test(suite.name)) fail("name");
  if (!suite.providerConcurrency || typeof suite.providerConcurrency !== "object" ||
      Object.values(suite.providerConcurrency).some(limit => !Number.isSafeInteger(limit) || limit < 1 || limit > 32)) fail("providerConcurrency");
  if (suite.target && (typeof suite.target.model !== "string" || typeof suite.target.maxScore !== "number")) fail("target");
  if (!Array.isArray(suite.families) || !suite.families.length) fail("families");
  const ids = new Set<string>();
  for (const family of suite.families) {
    if (!family || typeof family.id !== "string" || !identifier.test(family.id) || ids.has(family.id)) fail("family.id");
    ids.add(family.id);
    if (!["single", "trajectory", "visual"].includes(family.kind)) fail(`${family.id}.kind`);
    if (typeof family.template !== "string" || !family.template.endsWith(".eval.json") || family.template.startsWith("/") ||
        family.template.split("/").includes("..")) fail(`${family.id}.template`);
    const lists = [family.score?.items, family.score?.levels].filter(list => list !== undefined);
    if (family.score && (lists.length !== 1 || !lists.every(list => Array.isArray(list) && list.length && list.every(entry => typeof entry === "string")))) {
      fail(`${family.id}.score`);
    }
    if (family.overrides !== undefined && (typeof family.overrides !== "object" || Array.isArray(family.overrides))) fail(`${family.id}.overrides`);
    if (family.kind === "visual" && !family.visualPackage) fail(`${family.id}.visualPackage`);
  }
  return suite;
}

/**
 * Parse a model in plan syntax with optional request options, for example deepseek:deepseek-flash?thinking=high or
 * aliplan:qwen3.8-flash?thinking=provider-default&temperature=0. Without a thinking level the model's declared middle
 * level applies; temperature defaults to 0, the same for every model.
 */
export function parseModelSpec(spec: string): ModelSelection {
  const [base, query = ""] = spec.split("?", 2) as [string, string?];
  const selection: ModelSelection = parseModel(base);
  const options = new URLSearchParams(query);
  for (const key of options.keys()) if (key !== "thinking" && key !== "temperature") throw new Error(`MODEL_OPTION_UNKNOWN:${key}`);
  const thinking = options.get("thinking") ?? lookupModelConfig(selection.provider, selection.id)?.middleThinking;
  if (!thinking) throw new Error(`MODEL_THINKING_REQUIRED:${base}`);
  if (!thinkingLevels.includes(thinking as PlanThinkingLevel)) throw new Error(`MODEL_THINKING_INVALID:${base}`);
  selection.thinkingLevel = thinking as PlanThinkingLevel;
  const temperature = options.get("temperature");
  if (temperature === null) selection.temperature = 0;
  else if (temperature === "provider-default") selection.temperature = null;
  else {
    const value = Number(temperature);
    if (!Number.isFinite(value) || value < 0 || value > 2) throw new Error(`MODEL_TEMPERATURE_INVALID:${base}`);
    selection.temperature = value;
  }
  return selection;
}

/** Refuse a launch that breaks the suite's spending policy; returns nothing when it holds. */
export function checkPolicy(policy: SuitePolicy | undefined, models: ModelSelection[], repetitions: number): void {
  if (!policy) return;
  if (policy.maxModels !== undefined && models.length > policy.maxModels) throw new Error(`SUITE_POLICY:at most ${policy.maxModels} models`);
  if (policy.maxRepetitions !== undefined && repetitions > policy.maxRepetitions) throw new Error(`SUITE_POLICY:at most ${policy.maxRepetitions} repetitions`);
  for (const [host, limit] of Object.entries(policy.maxModelsPerHost ?? {})) {
    const count = models.filter(model => providerHost(model.provider) === host).length;
    if (count > limit) throw new Error(`SUITE_POLICY:at most ${limit} models from ${host}`);
  }
  for (const pattern of policy.forbiddenModels ?? []) {
    const forbidden = models.find(model => new RegExp(pattern).test(model.id));
    if (forbidden) throw new Error(`SUITE_POLICY:${forbidden.id} matches ${pattern}`);
  }
}
