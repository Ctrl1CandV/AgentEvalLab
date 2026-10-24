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
  /** 1: the v1 suites (dev.json, full.json). 2: suite v2 (CODE §3.4): a split, tiers, capability weights, no target. */
  schemaVersion: 1 | 2;
  name: string;
  description?: string;
  /** v1 only: the model the hardening aimed at; a family where it scored above maxScore was flagged. */
  target?: { model: string; maxScore: number };
  /** v2: the release this suite belongs to, such as v2.0-rc1. */
  release?: string;
  /** v2: the split every v2 family runs; its plans hold only that split's tasks. */
  split?: "dev" | "validation" | "holdout";
  /** v2: frozen weights of each core capability's families. */
  capabilityWeights?: Record<string, Record<string, number>>;
  /** v2: a composite score; none in v2.0 (decision D3), so null. */
  composite?: null;
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
  /** v2 suites: the family's tier and capability (the package's manifest says the same for a v2 package). */
  tier?: "basic" | "core" | "frontier";
  capability?: "engineering" | "reasoning" | "agentic" | "visual";
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
  if (suite.schemaVersion !== 1 && suite.schemaVersion !== 2) fail("schemaVersion");
  const v2 = suite.schemaVersion === 2;
  if (v2) {
    if (suite.target !== undefined) fail("target");  // suite v2 drops the score target (CODE §3.4)
    if (suite.split !== undefined && !["dev", "validation", "holdout"].includes(suite.split)) fail("split");
    if (suite.release !== undefined && (typeof suite.release !== "string" || !identifier.test(suite.release))) fail("release");
    if (suite.composite !== undefined && suite.composite !== null) fail("composite");
  } else if (suite.release !== undefined || suite.split !== undefined || suite.capabilityWeights !== undefined || suite.composite !== undefined) fail("v2-fields");
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
    if (v2 && (!["basic", "core", "frontier"].includes(String(family.tier)) || !["engineering", "reasoning", "agentic", "visual"].includes(String(family.capability)))) {
      fail(`${family.id}.tier`);
    }
    if (!v2 && (family.tier !== undefined || family.capability !== undefined)) fail(`${family.id}.v2-fields`);
  }
  if (v2 && suite.capabilityWeights !== undefined) {
    if (!suite.capabilityWeights || typeof suite.capabilityWeights !== "object") fail("capabilityWeights");
    for (const [capability, weights] of Object.entries(suite.capabilityWeights)) {
      for (const [familyId, weight] of Object.entries(weights ?? {})) {
        const family = suite.families.find(entry => entry.id === familyId);
        if (!family || family.tier !== "core" || family.capability !== capability || typeof weight !== "number" || !(weight > 0) || !Number.isFinite(weight)) {
          fail(`capabilityWeights.${capability}.${familyId}`);
        }
      }
    }
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
