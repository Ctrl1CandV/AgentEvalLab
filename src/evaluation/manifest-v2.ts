import type { ScoreModel } from "../scoring/model.js";

/**
 * Manifest v2 (CODE §3.1, PLAN-007 WP1.1): every v1 field stays, plus the tier, capabilities, the capability card, the
 * score model, per-task splits, structure groups, provenance and anchor values, and read-only runtime mounts. These
 * fields are checked as strictly as the v1 ones: unknown keys are refused, ranges checked, identifiers enforced.
 */

export type Tier = "basic" | "core" | "frontier";
export type V2Capability = "engineering" | "reasoning" | "agentic" | "visual";
export type Split = "dev" | "validation" | "holdout";
export type Exposure = "public" | "private-to-runs" | "generated";

export interface Provenance {
  source: string;
  /** The date the material was published or created, YYYY-MM-DD or YYYY-MM. */
  published: string;
  license: string;
  exposure: Exposure;
}

/** One task's place in the library: its split, structure group, provenance and raw anchor values. */
export interface TaskPlacement {
  split: Split;
  structure: string;
  provenance: Provenance;
  /** Per metric, the raw value of each anchor the score model names. */
  anchors?: Record<string, Record<string, number>>;
}

export interface RuntimeMount {
  /** A directory of the package, such as runtime/py, bound read-only into the sandbox. */
  path: string;
  /** Environment variables to set; "{mount}" is replaced by the mount's path inside the sandbox. */
  env: Record<string, string>;
}

export interface ManifestV2Fields {
  tier: Tier;
  capabilities: V2Capability[];
  card: string;
  scoreModel: ScoreModel;
  /** A package without items is one task; its placement is here. */
  task?: TaskPlacement;
  runtime?: { mounts: RuntimeMount[] };
}

export class ManifestV2Error extends Error {
  constructor(code: string) {
    super(code);
    this.name = "PackageManifestError";
  }
}

const IDENTIFIER = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;
// "generator" records how a generated package was built (R3, T1); v1 manifests carry it without validation.
const V1_KEYS = ["schemaVersion", "id", "version", "familyId", "capability", "usage", "source", "license", "entryPoint", "files", "requirements", "stages",
  "items", "dimensions", "scoring", "toolProfiles", "baseline", "grader", "environment", "generator"];
const V2_KEYS = ["tier", "capabilities", "card", "scoreModel", "task", "runtime"];
const ITEM_KEYS = ["id", "level", "files", "activeRequirementIds", "split", "structure", "provenance", "anchors"];

function fail(code: string): never {
  throw new ManifestV2Error(code);
}

function object(value: unknown, code: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) fail(code);
  return value as Record<string, unknown>;
}

function onlyKeys(value: Record<string, unknown>, allowed: string[], code: string): void {
  if (Object.keys(value).some(key => !allowed.includes(key))) fail(code);
}

function text(value: unknown, maximum = 200): value is string {
  return typeof value === "string" && value.trim().length > 0 && value.length <= maximum;
}

function safeRelative(path: unknown): path is string {
  return typeof path === "string" && path.length > 0 && !path.startsWith("/") && !path.includes("\\") && !path.includes("\0") &&
    path.split("/").every(segment => segment && segment !== "." && segment !== ".." && !segment.includes(":"));
}

function validatePlacement(value: unknown, anchored: Map<string, string[]>, code: string): TaskPlacement {
  const placement = object(value, code);
  onlyKeys(placement, ["split", "structure", "provenance", "anchors"], code);
  if (!["dev", "validation", "holdout"].includes(String(placement.split))) fail(`${code}_SPLIT`);
  if (!text(placement.structure)) fail(`${code}_STRUCTURE`);
  const provenance = object(placement.provenance, `${code}_PROVENANCE`);
  onlyKeys(provenance, ["source", "published", "license", "exposure"], `${code}_PROVENANCE`);
  if (!text(provenance.source, 500) || typeof provenance.published !== "string" || !/^\d{4}-\d{2}(-\d{2})?$/.test(provenance.published) ||
      !text(provenance.license) || !["public", "private-to-runs", "generated"].includes(String(provenance.exposure))) fail(`${code}_PROVENANCE`);
  if (placement.anchors !== undefined) {
    const anchors = object(placement.anchors, `${code}_ANCHORS`);
    for (const [metric, values] of Object.entries(anchors)) {
      if (!anchored.has(metric)) fail(`${code}_ANCHORS`);
      const points = object(values, `${code}_ANCHORS`);
      onlyKeys(points, anchored.get(metric)!, `${code}_ANCHORS`);
      if (Object.values(points).some(point => typeof point !== "number" || !Number.isFinite(point))) fail(`${code}_ANCHORS`);
    }
  }
  // Every anchored metric needs a raw value for every anchor, for every task.
  for (const [metric, names] of anchored) {
    const values = (placement.anchors as Record<string, Record<string, number>> | undefined)?.[metric];
    if (!values || names.some(name => typeof values[name] !== "number")) fail(`${code}_ANCHORS_INCOMPLETE`);
  }
  return placement as unknown as TaskPlacement;
}

function validateScoreModel(value: unknown, checkIds: Map<string, { critical: boolean }>): ScoreModel {
  const model = object(value, "INVALID_SCORE_MODEL");
  onlyKeys(model, ["primary", "groups", "metrics", "format", "structureCap"], "INVALID_SCORE_MODEL");
  const metrics = new Map<string, Record<string, unknown>>();
  if (model.metrics !== undefined) {
    if (!Array.isArray(model.metrics)) fail("INVALID_SCORE_METRICS");
    for (const raw of model.metrics) {
      const metric = object(raw, "INVALID_SCORE_METRICS");
      onlyKeys(metric, ["id", "unit", "direction", "anchors"], "INVALID_SCORE_METRICS");
      if (typeof metric.id !== "string" || !IDENTIFIER.test(metric.id) || metrics.has(metric.id) || !text(metric.unit) ||
          !["higher", "lower"].includes(String(metric.direction))) fail("INVALID_SCORE_METRICS");
      if (metric.anchors !== undefined) {
        const anchors = object(metric.anchors, "INVALID_SCORE_ANCHORS");
        onlyKeys(anchors, ["version", "points"], "INVALID_SCORE_ANCHORS");
        if (!text(anchors.version, 40) || !Array.isArray(anchors.points) || anchors.points.length < 2) fail("INVALID_SCORE_ANCHORS");
        const names = new Set<string>();
        let previous = -Infinity;
        for (const rawPoint of anchors.points) {
          const point = object(rawPoint, "INVALID_SCORE_ANCHORS");
          onlyKeys(point, ["name", "maps"], "INVALID_SCORE_ANCHORS");
          if (typeof point.name !== "string" || !IDENTIFIER.test(point.name) || names.has(point.name) || typeof point.maps !== "number" ||
              !Number.isFinite(point.maps) || point.maps <= previous) fail("INVALID_SCORE_ANCHORS");
          names.add(point.name);
          previous = point.maps;
        }
      }
      metrics.set(metric.id, metric);
    }
  }
  const primary = object(model.primary, "INVALID_SCORE_PRIMARY");
  if (primary.kind === "metric") {
    onlyKeys(primary, ["kind", "metric"], "INVALID_SCORE_PRIMARY");
    if (typeof primary.metric !== "string" || !metrics.has(primary.metric) || !metrics.get(primary.metric)!.anchors) fail("INVALID_SCORE_PRIMARY");
  } else if (primary.kind === "resolved" || primary.kind === "rating") onlyKeys(primary, ["kind"], "INVALID_SCORE_PRIMARY");
  else fail("INVALID_SCORE_PRIMARY");
  if (!Array.isArray(model.groups) || model.groups.length === 0) fail("INVALID_SCORE_GROUPS");
  const groupIds = new Set<string>();
  const grouped = new Set<string>();
  for (const raw of model.groups) {
    const group = object(raw, "INVALID_SCORE_GROUPS");
    onlyKeys(group, ["id", "weight", "critical", "rule", "checkIds", "metric"], "INVALID_SCORE_GROUPS");
    if (typeof group.id !== "string" || !IDENTIFIER.test(group.id) || groupIds.has(group.id) || typeof group.weight !== "number" ||
        !Number.isFinite(group.weight) || group.weight <= 0 || typeof group.critical !== "boolean" ||
        !["all", "fraction", "metric"].includes(String(group.rule)) || !Array.isArray(group.checkIds)) fail("INVALID_SCORE_GROUPS");
    if (group.rule === "metric") {
      if (typeof group.metric !== "string" || !metrics.get(group.metric)?.anchors || group.checkIds.length !== 0) fail("INVALID_SCORE_GROUPS");
    } else if (group.metric !== undefined || group.checkIds.length === 0) fail("INVALID_SCORE_GROUPS");
    for (const checkId of group.checkIds) {
      // Each check counts in exactly one group.
      if (typeof checkId !== "string" || !checkIds.has(checkId) || grouped.has(checkId)) fail("INVALID_SCORE_GROUP_CHECKS");
      grouped.add(checkId);
    }
    groupIds.add(group.id);
  }
  if (model.format !== undefined) {
    const format = object(model.format, "INVALID_SCORE_FORMAT");
    onlyKeys(format, ["checkId", "penalty"], "INVALID_SCORE_FORMAT");
    if (typeof format.checkId !== "string" || !checkIds.has(format.checkId) || checkIds.get(format.checkId)!.critical || grouped.has(format.checkId) ||
        typeof format.penalty !== "number" || !(format.penalty >= 0 && format.penalty <= 1)) fail("INVALID_SCORE_FORMAT");
  }
  if (model.structureCap !== undefined && (typeof model.structureCap !== "number" || !(model.structureCap > 0 && model.structureCap <= 1))) {
    fail("INVALID_SCORE_STRUCTURE_CAP");
  }
  return model as unknown as ScoreModel;
}

/** The v2 checks of a manifest whose v1 fields have already passed validateTaskPackageManifest. */
export function validateManifestV2(manifest: Record<string, unknown>): void {
  onlyKeys(manifest, [...V1_KEYS, ...V2_KEYS], "INVALID_PACKAGE_V2_KEYS");
  if (manifest.scoring !== undefined) fail("INVALID_PACKAGE_V2_SCORING");  // scoring (v1) and scoreModel (v2) never together
  if (!["basic", "core", "frontier"].includes(String(manifest.tier))) fail("INVALID_PACKAGE_TIER");
  const capabilities = manifest.capabilities;
  if (!Array.isArray(capabilities) || capabilities.length === 0 || new Set(capabilities).size !== capabilities.length ||
      !capabilities.every(capability => ["engineering", "reasoning", "agentic", "visual"].includes(String(capability)))) fail("INVALID_PACKAGE_CAPABILITIES");
  const files = manifest.files as { trusted: Array<{ path: string }> };
  if (!safeRelative(manifest.card) || !manifest.card.endsWith(".md") || !files.trusted.some(file => file.path === manifest.card)) fail("INVALID_PACKAGE_CARD");
  const requirements = manifest.requirements as Array<{ id: string; critical: boolean; checkIds: string[] }>;
  const checks = new Map<string, { critical: boolean }>();
  for (const requirement of requirements) for (const checkId of requirement.checkIds) checks.set(checkId, { critical: requirement.critical });
  const scoreModel = validateScoreModel(manifest.scoreModel, checks);
  const anchored = new Map((scoreModel.metrics ?? []).filter(metric => metric.anchors).map(metric => [metric.id, metric.anchors!.points.map(point => point.name)]));
  // Every check a task is graded on is in some group, or is the format check.
  const covered = (activeRequirementIds: string[], code: string) => {
    const grouped = new Set([...scoreModel.groups.flatMap(group => group.checkIds), ...(scoreModel.format ? [scoreModel.format.checkId] : [])]);
    const active = new Set(activeRequirementIds);
    for (const requirement of requirements) {
      if (active.has(requirement.id) && requirement.checkIds.some(checkId => !grouped.has(checkId))) fail(code);
    }
  };
  const structures = new Map<string, string>();
  const place = (placement: TaskPlacement) => {
    const seen = structures.get(placement.structure);
    if (seen && seen !== placement.split) fail("INVALID_PACKAGE_SPLITS_OVERLAP");  // splits are drawn by structure group
    structures.set(placement.structure, placement.split);
  };
  const items = manifest.items as Array<Record<string, unknown>> | undefined;
  if (items) {
    if (manifest.task !== undefined) fail("INVALID_PACKAGE_TASK");
    for (const item of items) {
      onlyKeys(item, ITEM_KEYS, "INVALID_PACKAGE_ITEM_V2");
      place(validatePlacement({ split: item.split, structure: item.structure, provenance: item.provenance, ...(item.anchors !== undefined ? { anchors: item.anchors } : {}) },
        anchored, "INVALID_PACKAGE_ITEM_V2"));
      covered(item.activeRequirementIds as string[], "SCORE_GROUPS_DO_NOT_COVER_CHECKS");
    }
  } else {
    place(validatePlacement(manifest.task, anchored, "INVALID_PACKAGE_TASK"));
    const stages = manifest.stages as Array<{ activeRequirementIds: string[] }> | undefined;
    covered(stages ? stages.at(-1)!.activeRequirementIds : requirements.map(requirement => requirement.id), "SCORE_GROUPS_DO_NOT_COVER_CHECKS");
  }
  if (manifest.runtime !== undefined) {
    const runtime = object(manifest.runtime, "INVALID_PACKAGE_RUNTIME");
    onlyKeys(runtime, ["mounts"], "INVALID_PACKAGE_RUNTIME");
    if (!Array.isArray(runtime.mounts) || runtime.mounts.length === 0) fail("INVALID_PACKAGE_RUNTIME");
    const paths = new Set<string>();
    for (const raw of runtime.mounts) {
      const mount = object(raw, "INVALID_PACKAGE_RUNTIME");
      onlyKeys(mount, ["path", "env"], "INVALID_PACKAGE_RUNTIME");
      if (!safeRelative(mount.path) || !mount.path.startsWith("runtime/") || paths.has(mount.path)) fail("INVALID_PACKAGE_RUNTIME");
      const env = object(mount.env, "INVALID_PACKAGE_RUNTIME");
      if (Object.entries(env).some(([key, value]) => !/^[A-Z_][A-Z0-9_]{0,63}$/.test(key) || typeof value !== "string" || value.length > 1000)) fail("INVALID_PACKAGE_RUNTIME");
      paths.add(mount.path);
    }
  }
}
