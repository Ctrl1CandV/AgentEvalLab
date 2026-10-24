import { metricsOf, type ScoreModel } from "../scoring/model.js";

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
  /** A directory of the package, such as runtime/py, bound read-only into the sandbox at /runtime/py. */
  path: string;
  /** Environment variables to set; "{mount}" is replaced by the mount's path inside the sandbox. */
  env: Record<string, string>;
  /**
   * Instead of files under `path`: a tar archive among the package's external assets (`assets/...`), unpacked once into
   * a cache keyed by its hash and bound read-only in its place (large runtimes, PLAN-007 WP3.2).
   */
  archive?: string;
}

/** An item's repository (CODE §5): a trusted archive of the working tree at the base commit, unpacked into `directory`. */
export interface RepositoryArchive {
  archive: string;
  directory: string;
}

/** Per-item v2 fields beside the placement. */
export interface ItemV2Fields {
  repository?: RepositoryArchive;
  /** The runtime mounts this item binds (paths of `runtime.mounts`); every mount when omitted. */
  mounts?: string[];
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
const ITEM_KEYS = ["id", "level", "files", "activeRequirementIds", "split", "structure", "provenance", "anchors", "repository", "mounts"];

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

function validatePlacement(value: unknown, anchored: Map<string, string[]>, code: string, needed: Set<string>): TaskPlacement {
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
  // Every anchored metric this task uses needs a raw value for every anchor.
  for (const [metric, names] of anchored) {
    if (!needed.has(metric)) continue;
    const values = (placement.anchors as Record<string, Record<string, number>> | undefined)?.[metric];
    if (!values || names.some(name => typeof values[name] !== "number")) fail(`${code}_ANCHORS_INCOMPLETE`);
  }
  return placement as unknown as TaskPlacement;
}

function validateScoreModel(value: unknown, checkIds: Map<string, { critical: boolean }>): ScoreModel {
  const model = object(value, "INVALID_SCORE_MODEL");
  onlyKeys(model, ["primary", "primaryByItem", "groups", "metrics", "format", "structureCap"], "INVALID_SCORE_MODEL");
  const metrics = new Map<string, Record<string, unknown>>();
  if (model.metrics !== undefined) {
    if (!Array.isArray(model.metrics)) fail("INVALID_SCORE_METRICS");
    for (const raw of model.metrics) {
      const metric = object(raw, "INVALID_SCORE_METRICS");
      onlyKeys(metric, ["id", "unit", "direction", "anchors", "items"], "INVALID_SCORE_METRICS");
      if (metric.items !== undefined && (!Array.isArray(metric.items) || metric.items.length === 0 || metric.items.some(id => typeof id !== "string"))) fail("INVALID_SCORE_METRICS");
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
  const checkPrimary = (value: unknown) => {
    const primary = object(value, "INVALID_SCORE_PRIMARY");
    if (primary.kind === "metric") {
      onlyKeys(primary, ["kind", "metric"], "INVALID_SCORE_PRIMARY");
      if (typeof primary.metric !== "string" || !metrics.has(primary.metric) || !metrics.get(primary.metric)!.anchors) fail("INVALID_SCORE_PRIMARY");
    } else if (primary.kind === "resolved" || primary.kind === "rating") onlyKeys(primary, ["kind"], "INVALID_SCORE_PRIMARY");
    else fail("INVALID_SCORE_PRIMARY");
  };
  checkPrimary(model.primary);
  if (model.primaryByItem !== undefined) for (const value of Object.values(object(model.primaryByItem, "INVALID_SCORE_PRIMARY"))) checkPrimary(value);
  if (!Array.isArray(model.groups) || model.groups.length === 0) fail("INVALID_SCORE_GROUPS");
  const groupIds = new Set<string>();
  const grouped = new Set<string>();
  for (const raw of model.groups) {
    const group = object(raw, "INVALID_SCORE_GROUPS");
    onlyKeys(group, ["id", "weight", "critical", "rule", "checkIds", "metric", "items"], "INVALID_SCORE_GROUPS");
    if (typeof group.id !== "string" || !IDENTIFIER.test(group.id) || groupIds.has(group.id) || typeof group.weight !== "number" ||
        !Number.isFinite(group.weight) || group.weight <= 0 || typeof group.critical !== "boolean" ||
        !["all", "fraction", "metric"].includes(String(group.rule)) || !Array.isArray(group.checkIds)) fail("INVALID_SCORE_GROUPS");
    if (group.rule === "metric") {
      if (typeof group.metric !== "string" || !metrics.get(group.metric)?.anchors || group.checkIds.length !== 0) fail("INVALID_SCORE_GROUPS");
      if (group.items !== undefined && (!Array.isArray(group.items) || group.items.length === 0 || group.items.some(id => typeof id !== "string"))) fail("INVALID_SCORE_GROUPS");
    } else if (group.metric !== undefined || group.items !== undefined || group.checkIds.length === 0) fail("INVALID_SCORE_GROUPS");
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
  const mountPaths = new Set<string>();
  if (manifest.runtime !== undefined) {
    const runtime = object(manifest.runtime, "INVALID_PACKAGE_RUNTIME");
    onlyKeys(runtime, ["mounts"], "INVALID_PACKAGE_RUNTIME");
    if (!Array.isArray(runtime.mounts) || runtime.mounts.length === 0) fail("INVALID_PACKAGE_RUNTIME");
    for (const raw of runtime.mounts) {
      const mount = object(raw, "INVALID_PACKAGE_RUNTIME");
      onlyKeys(mount, ["path", "env", "archive"], "INVALID_PACKAGE_RUNTIME");
      // runtime/<name>: one directory per mount, bound at /runtime/<name> in the sandbox.
      if (!safeRelative(mount.path) || !/^runtime\/[A-Za-z0-9._-]+$/.test(mount.path) || mountPaths.has(mount.path)) fail("INVALID_PACKAGE_RUNTIME");
      const env = object(mount.env, "INVALID_PACKAGE_RUNTIME");
      if (Object.entries(env).some(([key, value]) => !/^[A-Z_][A-Z0-9_]{0,63}$/.test(key) || ["HOME", "TMPDIR", "TMP", "TEMP"].includes(key) ||
          typeof value !== "string" || value.length > 1000)) fail("INVALID_PACKAGE_RUNTIME");
      // A mount's files are hashed as trusted files, or it is one hashed archive among the external assets.
      if (mount.archive !== undefined) {
        if (!safeRelative(mount.archive) || !/^assets\/[^/]+\.tar$/.test(mount.archive) || !files.trusted.some(file => file.path === mount.archive) ||
            files.trusted.some(file => file.path.startsWith(`${mount.path}/`))) fail("INVALID_PACKAGE_RUNTIME_FILES");
      } else if (!files.trusted.some(file => file.path.startsWith(`${mount.path}/`))) fail("INVALID_PACKAGE_RUNTIME_FILES");
      mountPaths.add(mount.path);
    }
  }
  const validateItemRuntime = (item: Record<string, unknown>) => {
    if (item.repository !== undefined) {
      const repository = object(item.repository, "INVALID_PACKAGE_ITEM_REPOSITORY");
      onlyKeys(repository, ["archive", "directory"], "INVALID_PACKAGE_ITEM_REPOSITORY");
      if (!safeRelative(repository.archive) || !/^(private|assets)\//.test(repository.archive) || !/\.tar(\.gz)?$/.test(repository.archive) ||
          !files.trusted.some(file => file.path === repository.archive) || typeof repository.directory !== "string" ||
          !IDENTIFIER.test(repository.directory) || repository.directory === ".git") fail("INVALID_PACKAGE_ITEM_REPOSITORY");
    }
    if (item.mounts !== undefined && (!Array.isArray(item.mounts) || item.mounts.length === 0 || new Set(item.mounts).size !== item.mounts.length ||
        item.mounts.some(path => typeof path !== "string" || !mountPaths.has(path)))) fail("INVALID_PACKAGE_ITEM_MOUNTS");
  };
  const structures = new Map<string, string>();
  const place = (placement: TaskPlacement) => {
    const seen = structures.get(placement.structure);
    if (seen && seen !== placement.split) fail("INVALID_PACKAGE_SPLITS_OVERLAP");  // splits are drawn by structure group
    structures.set(placement.structure, placement.split);
  };
  const items = manifest.items as Array<Record<string, unknown>> | undefined;
  // Per-item headlines and metric groups name items of the package.
  const itemIds = new Set((items ?? []).map(item => item.id));
  if (Object.keys(scoreModel.primaryByItem ?? {}).some(id => !itemIds.has(id)) ||
      scoreModel.groups.some(group => group.items?.some(id => !itemIds.has(id))) ||
      (scoreModel.metrics ?? []).some(metric => metric.items?.some(id => !itemIds.has(id)))) fail("INVALID_SCORE_ITEMS");
  // A task is scored only on metrics its grading reports.
  const reported = (itemId: string | null, metric: string) => {
    const declared = (scoreModel.metrics ?? []).find(entry => entry.id === metric);
    return !declared?.items || (itemId !== null && declared.items.includes(itemId));
  };
  for (const itemId of items ? [...itemIds] as string[] : [null]) {
    if ([...metricsOf(scoreModel, itemId)].some(metric => !reported(itemId, metric))) fail("INVALID_SCORE_ITEMS");
  }
  if (items) {
    if (manifest.task !== undefined) fail("INVALID_PACKAGE_TASK");
    for (const item of items) {
      onlyKeys(item, ITEM_KEYS, "INVALID_PACKAGE_ITEM_V2");
      validateItemRuntime(item);
      place(validatePlacement({ split: item.split, structure: item.structure, provenance: item.provenance, ...(item.anchors !== undefined ? { anchors: item.anchors } : {}) },
        anchored, "INVALID_PACKAGE_ITEM_V2", metricsOf(scoreModel, item.id as string)));
      covered(item.activeRequirementIds as string[], "SCORE_GROUPS_DO_NOT_COVER_CHECKS");
    }
  } else {
    place(validatePlacement(manifest.task, anchored, "INVALID_PACKAGE_TASK", metricsOf(scoreModel, null)));
    const stages = manifest.stages as Array<{ activeRequirementIds: string[] }> | undefined;
    covered(stages ? stages.at(-1)!.activeRequirementIds : requirements.map(requirement => requirement.id), "SCORE_GROUPS_DO_NOT_COVER_CHECKS");
  }
}
