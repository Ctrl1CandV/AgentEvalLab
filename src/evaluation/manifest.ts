import { createHash } from "node:crypto";
import { constants } from "node:fs";
import { copyFile, lstat, mkdir, readFile, readdir, realpath } from "node:fs/promises";
import { dirname, isAbsolute, join, relative, resolve, sep } from "node:path";
import type { ToolProfile } from "../harness/tools.js";
import { ManifestV2Error, validateManifestV2, type ManifestV2Fields, type TaskPlacement } from "./manifest-v2.js";

export type Capability = "engineering" | "reasoning" | "tool" | "aesthetics";
export type TaskUsage = "development" | "pilot" | "holdout" | "undecided";

export interface ManifestFile {
  path: string;
  sha256: string;
}

export interface ManifestRequirement {
  id: string;
  critical: boolean;
  introducedAt: string;
  checkIds: string[];
}

/**
 * How the harness turns a grader's checks into a trial score. Absent fields mean equal weights and no format check.
 * The score counts the grader's objective checks; human-review checks are recorded separately.
 */
export interface ManifestScoring {
  /** A non-critical check that passes only when the answer followed the instructed format exactly. */
  formatCheckId?: string;
  /** Fraction of the content score lost when the format check fails (0 to 1). */
  formatPenalty?: number;
  /** Relative weights of content checks; unlisted checks weigh 1. */
  weights?: Record<string, number>;
}

export interface ManifestDimension {
  id: string;
  minimum: number;
  maximum: number;
}

/**
 * One item of a generated task family (Task Set v2). A trial receives exactly one item: its `items/<id>/prompt.md` is
 * appended to the task prompt, and its `items/<id>/public/...` files are projected without the `items/<id>/` prefix.
 */
export interface ManifestItem extends Partial<TaskPlacement> {
  id: string;
  /** Difficulty level; reports group trials by case and level. */
  level: string;
  files: ManifestFile[];
  /** Requirements this item activates; their checks are the checks expected for the item. */
  activeRequirementIds: string[];
}

export interface ManifestTrajectoryStage {
  id: string;
  instruction: string;
  files: ManifestFile[];
  activeRequirementIds: string[];
  publicChecker: {
    entryPoint: string;
    executable: string;
    args: string[];
    timeoutMs: number;
    maxOutputBytes: number;
    checkIds: string[];
  };
}

/** A v1 manifest, or a v2 one (schemaVersion 2) with the fields of manifest-v2.ts beside every v1 field. */
export interface TaskPackageManifest extends Partial<ManifestV2Fields> {
  schemaVersion: 1 | 2;
  id: string;
  version: string;
  familyId: string;
  capability: Capability;
  usage: TaskUsage;
  source: { kind: "original-design" | "open-source" | "mixed"; references: string[] };
  license: { taskText: string; thirdPartyContent: string[] };
  entryPoint: { instruction: string };
  files: { public: ManifestFile[]; trusted: ManifestFile[] };
  requirements: ManifestRequirement[];
  stages?: ManifestTrajectoryStage[];
  items?: ManifestItem[];
  dimensions?: ManifestDimension[];
  scoring?: ManifestScoring;
  /** Profiles fixed for this task; omitted legacy manifests permit only workspace-basic. */
  toolProfiles?: ToolProfile[];
  /** A local git baseline pinned by its commit hash. */
  baseline?: { path: string; commit: string };
  grader: {
    id: string;
    version: string;
    entryPoint: string;
    executable: string;
    args: string[];
    answerSource?: "execution-output";
    requiresTrace?: boolean;
  };
  environment: {
    runtime: string;
    dependencies: string;
    network: false;
    runtimeCheck?: { executable: string; args: string[]; expectedSubstring: string };
  };
}

export interface PackageDescriptor {
  root: string;
  instruction: string;
  manifest: TaskPackageManifest | null;
  manifestSha256: string | null;
}

export class PackageManifestError extends Error {
  constructor(code: string) {
    super(code);
    this.name = "PackageManifestError";
  }
}

const V2_ONLY_KEYS = ["tier", "capabilities", "card", "scoreModel", "task", "runtime"];

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new PackageManifestError("INVALID_PACKAGE_MANIFEST");
  }
  return value as Record<string, unknown>;
}

function isIdentifier(value: unknown): value is string {
  return typeof value === "string" && /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(value);
}

function isSha256(value: unknown): value is string {
  return typeof value === "string" && /^[a-f0-9]{64}$/i.test(value);
}

function stringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every(item => typeof item === "string" && item.length > 0);
}

function validateFileList(value: unknown, kind: "public" | "trusted"): value is ManifestFile[] {
  if (!Array.isArray(value) || value.length === 0) return false;
  const paths = new Set<string>();
  for (const itemValue of value) {
    const item = record(itemValue);
    if (typeof item.path !== "string" || !isSha256(item.sha256) || paths.has(item.path)) return false;
    if (kind === "public" && item.path !== "instruction.md" && !item.path.startsWith("public/")) return false;
    if (kind === "trusted" && (item.path === "instruction.md" || item.path.startsWith("public/") || item.path === "manifest.json")) return false;
    paths.add(item.path);
  }
  return true;
}

function validateItemFileList(value: unknown, itemId: string): value is ManifestFile[] {
  if (!Array.isArray(value) || value.length === 0) return false;
  const paths = new Set<string>();
  const prefix = `items/${itemId}/`;
  for (const fileValue of value) {
    const file = record(fileValue);
    if (typeof file.path !== "string" || !file.path.startsWith(prefix) || !isSha256(file.sha256) || paths.has(file.path) ||
        (file.path !== `${prefix}prompt.md` && !file.path.startsWith(`${prefix}public/`))) return false;
    paths.add(file.path);
  }
  return true;
}

function validateStageFileList(value: unknown, stageId: string): value is ManifestFile[] {
  if (!Array.isArray(value) || value.length === 0) return false;
  const paths = new Set<string>();
  const prefix = `stages/${stageId}/`;
  for (const fileValue of value) {
    const file = record(fileValue);
    if (typeof file.path !== "string" || !file.path.startsWith(prefix) || !isSha256(file.sha256) || paths.has(file.path) ||
        (file.path !== `${prefix}instruction.md` && !file.path.startsWith(`${prefix}public/`))) return false;
    paths.add(file.path);
  }
  return paths.has(`${prefix}instruction.md`);
}

/** Runtime-validates package metadata read from disk; TypeScript types alone do not validate JSON. */
export function validateTaskPackageManifest(value: unknown): asserts value is TaskPackageManifest {
  const manifest = record(value);
  const source = record(manifest.source);
  const license = record(manifest.license);
  const entryPoint = record(manifest.entryPoint);
  const files = record(manifest.files);
  const grader = record(manifest.grader);
  const environment = record(manifest.environment);

  if ((manifest.schemaVersion !== 1 && manifest.schemaVersion !== 2) || !isIdentifier(manifest.id) || typeof manifest.version !== "string" || !manifest.version.trim() ||
      !isIdentifier(manifest.familyId) || !["engineering", "reasoning", "tool", "aesthetics"].includes(String(manifest.capability)) ||
      !["development", "pilot", "holdout", "undecided"].includes(String(manifest.usage))) {
    throw new PackageManifestError("INVALID_PACKAGE_IDENTITY");
  }
  if (!["original-design", "open-source", "mixed"].includes(String(source.kind)) || !stringArray(source.references) ||
      typeof license.taskText !== "string" || !license.taskText.trim() || !stringArray(license.thirdPartyContent) ||
      typeof entryPoint.instruction !== "string") {
    throw new PackageManifestError("INVALID_PACKAGE_PROVENANCE");
  }
  if (!validateFileList(files.public, "public") || !validateFileList(files.trusted, "trusted") ||
      !files.public.some(file => file.path === entryPoint.instruction) || !Array.isArray(manifest.requirements) || manifest.requirements.length === 0) {
    throw new PackageManifestError("INVALID_PACKAGE_FILES");
  }
  if (typeof grader.id !== "string" || !isIdentifier(grader.id) || typeof grader.version !== "string" || !grader.version.trim() ||
      typeof grader.entryPoint !== "string" || !files.trusted.some(file => file.path === grader.entryPoint) ||
      typeof grader.executable !== "string" || !grader.executable.trim() || !stringArray(grader.args) ||
      !(grader.args.includes(grader.entryPoint) || grader.args.includes("{entryPoint}")) ||
      !grader.args.includes("{request}") || !grader.args.includes("{result}") ||
      typeof environment.runtime !== "string" || !environment.runtime.trim() || typeof environment.dependencies !== "string" ||
      environment.network !== false) {
    throw new PackageManifestError("INVALID_PACKAGE_EXECUTION");
  }
  if (grader.answerSource !== undefined && grader.answerSource !== "execution-output") {
    throw new PackageManifestError("INVALID_PACKAGE_GRADER_ANSWER_SOURCE");
  }
  if (grader.requiresTrace !== undefined && typeof grader.requiresTrace !== "boolean") {
    throw new PackageManifestError("INVALID_PACKAGE_GRADER_TRACE_POLICY");
  }
  if (manifest.toolProfiles !== undefined && (!Array.isArray(manifest.toolProfiles) || manifest.toolProfiles.length === 0 ||
      !manifest.toolProfiles.every(profile => ["workspace-basic", "workspace-augmented", "doc-evidence"].includes(String(profile))) ||
      new Set(manifest.toolProfiles).size !== manifest.toolProfiles.length)) {
    throw new PackageManifestError("INVALID_PACKAGE_TOOL_PROFILES");
  }
  if (manifest.baseline !== undefined) {
    const baseline = record(manifest.baseline);
    if (typeof baseline.path !== "string" || !baseline.path.trim() || baseline.path.includes("\\") || baseline.path.includes("\0") ||
        isAbsolute(baseline.path) || /^[A-Za-z]:/.test(baseline.path) ||
        baseline.path.split("/").some(segment => !segment || segment === "." || segment === ".." || segment.includes(":")) ||
        baseline.path === "public" || baseline.path.startsWith("public/") || baseline.path === "private" || baseline.path.startsWith("private/") ||
        typeof baseline.commit !== "string" || !/^[a-f0-9]{40,64}$/i.test(baseline.commit)) {
      throw new PackageManifestError("INVALID_PACKAGE_BASELINE");
    }
  }
  if (environment.runtimeCheck !== undefined) {
    const runtimeCheck = record(environment.runtimeCheck);
    if (typeof runtimeCheck.executable !== "string" || !runtimeCheck.executable.trim() ||
        !stringArray(runtimeCheck.args) || typeof runtimeCheck.expectedSubstring !== "string" ||
        !runtimeCheck.expectedSubstring.trim()) {
      throw new PackageManifestError("INVALID_PACKAGE_RUNTIME_CHECK");
    }
  }

  const requirementIds = new Set<string>();
  const checkIds = new Set<string>();
  for (const requirementValue of manifest.requirements) {
    const requirement = record(requirementValue);
    if (!isIdentifier(requirement.id) || requirementIds.has(requirement.id) || typeof requirement.critical !== "boolean" ||
        typeof requirement.introducedAt !== "string" || !requirement.introducedAt.trim() ||
        !Array.isArray(requirement.checkIds) || requirement.checkIds.length === 0) {
      throw new PackageManifestError("INVALID_PACKAGE_REQUIREMENT");
    }
    requirementIds.add(requirement.id);
    for (const checkId of requirement.checkIds) {
      if (!isIdentifier(checkId) || checkIds.has(checkId)) throw new PackageManifestError("INVALID_PACKAGE_CHECK_ID");
      checkIds.add(checkId);
    }
  }
  if (!manifest.requirements.some(requirement => record(requirement).critical === true)) {
    throw new PackageManifestError("PACKAGE_HAS_NO_CRITICAL_REQUIREMENTS");
  }
  if (manifest.scoring !== undefined) {
    const scoring = record(manifest.scoring);
    const requirements = manifest.requirements as ManifestRequirement[];
    const formatOwner = requirements.find(requirement => requirement.checkIds.includes(String(scoring.formatCheckId)));
    const weights = scoring.weights === undefined ? {} : record(scoring.weights);
    if (Object.keys(scoring).some(key => !["formatCheckId", "formatPenalty", "weights"].includes(key)) ||
        (scoring.formatCheckId !== undefined && (!formatOwner || formatOwner.critical)) ||
        (scoring.formatPenalty !== undefined && (typeof scoring.formatPenalty !== "number" || !(scoring.formatPenalty >= 0 && scoring.formatPenalty <= 1) ||
          scoring.formatCheckId === undefined)) ||
        Object.entries(weights).some(([checkId, weight]) => !checkIds.has(checkId) || checkId === scoring.formatCheckId ||
          typeof weight !== "number" || !Number.isFinite(weight) || weight <= 0)) {
      throw new PackageManifestError("INVALID_PACKAGE_SCORING");
    }
  }
  if (manifest.dimensions !== undefined) {
    if (!Array.isArray(manifest.dimensions)) throw new PackageManifestError("INVALID_PACKAGE_DIMENSIONS");
    const dimensionIds = new Set<string>();
    for (const dimensionValue of manifest.dimensions) {
      const dimension = record(dimensionValue);
      if (!isIdentifier(dimension.id) || dimensionIds.has(dimension.id) || typeof dimension.minimum !== "number" || !Number.isFinite(dimension.minimum) ||
          typeof dimension.maximum !== "number" || !Number.isFinite(dimension.maximum) || dimension.maximum <= dimension.minimum) {
        throw new PackageManifestError("INVALID_PACKAGE_DIMENSIONS");
      }
      dimensionIds.add(dimension.id);
    }
  }
  if (manifest.items !== undefined) {
    if (manifest.stages !== undefined || !Array.isArray(manifest.items) || manifest.items.length === 0) throw new PackageManifestError("INVALID_PACKAGE_ITEMS");
    const requirements = new Map((manifest.requirements as ManifestRequirement[]).map(requirement => [requirement.id, requirement]));
    const itemIds = new Set<string>();
    for (const itemValue of manifest.items) {
      const item = record(itemValue);
      if (!isIdentifier(item.id) || itemIds.has(item.id) || !isIdentifier(item.level) || !validateItemFileList(item.files, item.id) ||
          !Array.isArray(item.activeRequirementIds) || item.activeRequirementIds.length === 0 ||
          new Set(item.activeRequirementIds).size !== item.activeRequirementIds.length ||
          !item.activeRequirementIds.every(id => requirements.has(String(id))) ||
          !item.activeRequirementIds.some(id => requirements.get(String(id))!.critical)) {
        throw new PackageManifestError("INVALID_PACKAGE_ITEM");
      }
      itemIds.add(item.id);
    }
  }
  if (manifest.stages !== undefined) {
    if (!Array.isArray(manifest.stages) || manifest.stages.length < 2) throw new PackageManifestError("INVALID_PACKAGE_STAGES");
    const stageIds = new Set<string>();
    const requirementOwner = new Map<string, ManifestRequirement>();
    for (const requirement of manifest.requirements as ManifestRequirement[]) requirementOwner.set(requirement.id, requirement);
    for (const stageValue of manifest.stages) {
      const stage = record(stageValue);
      const checker = record(stage.publicChecker);
      if (!isIdentifier(stage.id) || stageIds.has(stage.id) || stage.instruction !== `stages/${stage.id}/instruction.md` ||
          !validateStageFileList(stage.files, stage.id) || !Array.isArray(stage.activeRequirementIds) ||
          !stage.activeRequirementIds.length || !stage.activeRequirementIds.every(isIdentifier) ||
          new Set(stage.activeRequirementIds).size !== stage.activeRequirementIds.length ||
          typeof checker.entryPoint !== "string" || !stage.files.some(file => file.path === checker.entryPoint) ||
          !checker.entryPoint.startsWith(`stages/${stage.id}/public/`) ||
          typeof checker.executable !== "string" || !checker.executable.trim() || !stringArray(checker.args) ||
          !checker.args.includes("{entryPoint}") || !checker.args.includes("{submission}") ||
          !Number.isSafeInteger(checker.timeoutMs) || Number(checker.timeoutMs) < 1 ||
          !Number.isSafeInteger(checker.maxOutputBytes) || Number(checker.maxOutputBytes) < 1 ||
          !Array.isArray(checker.checkIds) || !checker.checkIds.length || !checker.checkIds.every(isIdentifier) ||
          new Set(checker.checkIds).size !== checker.checkIds.length) {
        throw new PackageManifestError("INVALID_PACKAGE_STAGE");
      }
      if (!stage.activeRequirementIds.every(id => requirementOwner.has(id))) throw new PackageManifestError("INVALID_STAGE_REQUIREMENTS");
      stageIds.add(stage.id);
    }
  }
  if (manifest.schemaVersion === 2) {
    try { validateManifestV2(manifest); }
    catch (error) { throw error instanceof ManifestV2Error ? new PackageManifestError(error.message) : error; }
  } else if (V2_ONLY_KEYS.some(key => key in manifest)) {
    throw new PackageManifestError("INVALID_PACKAGE_V1_HAS_V2_FIELDS");
  }
}

function safePackagePath(root: string, packageRelativePath: string): string {
  if (!packageRelativePath || packageRelativePath.includes("\\") || packageRelativePath.includes("\0") ||
      isAbsolute(packageRelativePath) || /^[A-Za-z]:/.test(packageRelativePath)) {
    throw new PackageManifestError("PACKAGE_PATH_DENIED");
  }
  const segments = packageRelativePath.split("/");
  if (segments.some(segment => !segment || segment === "." || segment === ".." || segment.includes(":"))) {
    throw new PackageManifestError("PACKAGE_PATH_DENIED");
  }
  const target = resolve(root, ...segments);
  const fromRoot = relative(root, target);
  if (!fromRoot || fromRoot === ".." || fromRoot.startsWith(`..${sep}`) || isAbsolute(fromRoot)) {
    throw new PackageManifestError("PACKAGE_PATH_DENIED");
  }
  return target;
}

async function assertRegularFile(root: string, packageRelativePath: string): Promise<string> {
  const target = safePackagePath(root, packageRelativePath);
  let current = root;
  const segments = packageRelativePath.split("/");
  for (const [index, segment] of segments.entries()) {
    current = join(current, segment);
    const info = await lstat(current).catch(() => null);
    if (!info || info.isSymbolicLink()) throw new PackageManifestError("PACKAGE_FILE_MISSING_OR_LINKED");
    if (index < segments.length - 1 && !info.isDirectory()) throw new PackageManifestError("PACKAGE_PATH_NOT_DIRECTORY");
    if (index === segments.length - 1 && !info.isFile()) throw new PackageManifestError("PACKAGE_NOT_REGULAR_FILE");
  }
  const resolvedTarget = await realpath(target);
  const fromRoot = relative(root, resolvedTarget);
  if (!fromRoot || fromRoot === ".." || fromRoot.startsWith(`..${sep}`) || isAbsolute(fromRoot)) {
    throw new PackageManifestError("PACKAGE_PATH_DENIED");
  }
  return target;
}

async function sha256(path: string): Promise<string> {
  return createHash("sha256").update(await readFile(path)).digest("hex");
}

async function listFilesUnder(root: string, directoryName: string, excludePythonCaches = false): Promise<string[]> {
  const results: string[] = [];
  const visit = async (directory: string): Promise<void> => {
    for (const name of await readdir(directory)) {
      // Hidden entries are never package material (tools and sandboxes leave such files behind); manifests may not
      // declare them.
      if (name.startsWith(".")) continue;
      const path = join(directory, name);
      const info = await lstat(path);
      if (info.isSymbolicLink()) throw new PackageManifestError("PACKAGE_SYMLINK_DENIED");
      if (excludePythonCaches && ((info.isDirectory() && name === "__pycache__") ||
          (info.isFile() && name.endsWith(".pyc")))) continue;
      if (info.isDirectory()) await visit(path);
      else if (info.isFile()) results.push(relative(root, path).split(sep).join("/"));
      else throw new PackageManifestError("PACKAGE_FILE_TYPE_DENIED");
    }
  };
  await visit(join(root, directoryName));
  return results.sort();
}

/** Public files shared by every trial; a package whose material is all in generated items may have none. */
async function listPublicFiles(root: string): Promise<string[]> {
  if (!await lstat(join(root, "public")).catch(() => null)) return [];
  return listFilesUnder(root, "public");
}

/** Reads, validates, and fingerprints a package before any model request starts. */
export async function inspectPackage(
  packagePath: string,
  expectedManifestSha256?: string,
  requireManifest = false,
): Promise<PackageDescriptor> {
  const root = await realpath(packagePath).catch(() => { throw new PackageManifestError("PACKAGE_NOT_FOUND"); });
  const instructionPath = join(root, "instruction.md");
  const instructionInfo = await lstat(instructionPath).catch(() => null);
  if (!instructionInfo?.isFile() || instructionInfo.isSymbolicLink()) throw new PackageManifestError("PACKAGE_INSTRUCTION_INVALID");
  const instruction = await readFile(instructionPath, "utf8");
  if (!instruction.trim()) throw new PackageManifestError("PACKAGE_INSTRUCTION_EMPTY");

  const manifestPath = join(root, "manifest.json");
  const manifestInfo = await lstat(manifestPath).catch(() => null);
  if (!manifestInfo) {
    if (requireManifest || expectedManifestSha256) throw new PackageManifestError("PACKAGE_MANIFEST_REQUIRED");
    await listPublicFiles(root);
    return { root, instruction, manifest: null, manifestSha256: null };
  }
  if (!manifestInfo.isFile() || manifestInfo.isSymbolicLink()) throw new PackageManifestError("PACKAGE_MANIFEST_INVALID");

  const manifestBytes = await readFile(manifestPath);
  const manifestSha256 = createHash("sha256").update(manifestBytes).digest("hex");
  if (expectedManifestSha256 && manifestSha256 !== expectedManifestSha256.toLowerCase()) {
    throw new PackageManifestError("PACKAGE_MANIFEST_HASH_MISMATCH");
  }

  let manifestValue: unknown;
  try { manifestValue = JSON.parse(manifestBytes.toString("utf8")) as unknown; }
  catch { throw new PackageManifestError("PACKAGE_MANIFEST_INVALID_JSON"); }
  validateTaskPackageManifest(manifestValue);
  const manifest = manifestValue;
  if (manifest.entryPoint.instruction !== "instruction.md") throw new PackageManifestError("PACKAGE_ENTRY_POINT_INVALID");

  for (const file of [...manifest.files.public, ...manifest.files.trusted]) {
    const path = await assertRegularFile(root, file.path);
    if (await sha256(path) !== file.sha256.toLowerCase()) throw new PackageManifestError("PACKAGE_FILE_HASH_MISMATCH");
  }
  if (manifest.stages) {
    const declaredStageFiles = manifest.stages.flatMap(stage => stage.files.map(file => file.path)).sort();
    for (const stage of manifest.stages) {
      for (const file of stage.files) {
        const path = await assertRegularFile(root, file.path);
        if (await sha256(path) !== file.sha256.toLowerCase()) throw new PackageManifestError("PACKAGE_FILE_HASH_MISMATCH");
      }
    }
    const stagesRoot = join(root, "stages");
    const stagesInfo = await lstat(stagesRoot).catch(() => null);
    if (!stagesInfo?.isDirectory() || stagesInfo.isSymbolicLink()) throw new PackageManifestError("PACKAGE_STAGE_DIRECTORY_INVALID");
    const actualStageFiles = await listFilesUnder(root, "stages");
    if (JSON.stringify(actualStageFiles) !== JSON.stringify(declaredStageFiles)) throw new PackageManifestError("PACKAGE_STAGE_FILE_SET_MISMATCH");
  } else if (await lstat(join(root, "stages")).catch(() => null)) {
    throw new PackageManifestError("UNDECLARED_PACKAGE_STAGES");
  }
  if (manifest.items) {
    for (const item of manifest.items) {
      for (const file of item.files) {
        const path = await assertRegularFile(root, file.path);
        if (await sha256(path) !== file.sha256.toLowerCase()) throw new PackageManifestError("PACKAGE_FILE_HASH_MISMATCH");
      }
    }
    const itemsInfo = await lstat(join(root, "items")).catch(() => null);
    if (!itemsInfo?.isDirectory() || itemsInfo.isSymbolicLink()) throw new PackageManifestError("PACKAGE_ITEM_DIRECTORY_INVALID");
    const declaredItemFiles = manifest.items.flatMap(item => item.files.map(file => file.path)).sort();
    if (JSON.stringify(await listFilesUnder(root, "items")) !== JSON.stringify(declaredItemFiles)) throw new PackageManifestError("PACKAGE_ITEM_FILE_SET_MISMATCH");
  } else if (await lstat(join(root, "items")).catch(() => null)) {
    throw new PackageManifestError("UNDECLARED_PACKAGE_ITEMS");
  }
  const declaredPublic = manifest.files.public.map(file => file.path).filter(path => path.startsWith("public/")).sort();
  if (JSON.stringify(await listPublicFiles(root)) !== JSON.stringify(declaredPublic)) {
    throw new PackageManifestError("PACKAGE_PUBLIC_FILE_SET_MISMATCH");
  }
  const declaredPrivate = manifest.files.trusted.map(file => file.path).filter(path => path.startsWith("private/")).sort();
  if (JSON.stringify(await listFilesUnder(root, "private", true)) !== JSON.stringify(declaredPrivate)) {
    throw new PackageManifestError("PACKAGE_TRUSTED_FILE_SET_MISMATCH");
  }
  return { root, instruction, manifest, manifestSha256 };
}

/** Releases exactly one pinned stage; later stage material stays out of the candidate workspace. */
export async function projectTrajectoryStage(
  descriptor: PackageDescriptor,
  workspace: string,
  stageId: string,
): Promise<string> {
  const manifest = descriptor.manifest;
  if (!manifest?.stages) throw new PackageManifestError("TRAJECTORY_STAGES_REQUIRED");
  const stage = manifest.stages.find(candidate => candidate.id === stageId);
  if (!stage) throw new PackageManifestError("UNKNOWN_TRAJECTORY_STAGE");
  for (const file of stage.files) {
    const source = await assertRegularFile(descriptor.root, file.path);
    if (await sha256(source) !== file.sha256.toLowerCase()) throw new PackageManifestError("PACKAGE_FILE_HASH_MISMATCH");
    const destination = join(workspace, ...file.path.split("/"));
    await mkdir(dirname(destination), { recursive: true });
    await copyFile(source, destination, constants.COPYFILE_EXCL);
  }
  return await readFile(await assertRegularFile(descriptor.root, stage.instruction), "utf8");
}

/**
 * Releases one item of a generated family: its public files land in the workspace without the `items/<id>/` prefix,
 * and its prompt text, if any, is returned for appending to the task prompt. Other items stay out of the workspace.
 */
export async function projectPackageItem(descriptor: PackageDescriptor, workspace: string, itemId: string): Promise<{ prompt: string; item: ManifestItem }> {
  const item = descriptor.manifest?.items?.find(candidate => candidate.id === itemId);
  if (!item) throw new PackageManifestError("UNKNOWN_PACKAGE_ITEM");
  let prompt = "";
  for (const file of item.files) {
    const source = await assertRegularFile(descriptor.root, file.path);
    if (await sha256(source) !== file.sha256.toLowerCase()) throw new PackageManifestError("PACKAGE_FILE_HASH_MISMATCH");
    const relativePath = file.path.slice(`items/${item.id}/`.length);
    if (relativePath === "prompt.md") {
      prompt = await readFile(source, "utf8");
      continue;
    }
    const destination = join(workspace, ...relativePath.split("/"));
    await mkdir(dirname(destination), { recursive: true });
    await copyFile(source, destination, constants.COPYFILE_EXCL);
  }
  return { prompt, item };
}

/** Projects only instruction and explicitly hashed public files into the candidate workspace. */
export async function projectPackage(
  packagePath: string,
  workspace: string,
  expectedManifestSha256?: string,
  requireManifest = false,
): Promise<PackageDescriptor> {
  const descriptor = await inspectPackage(packagePath, expectedManifestSha256, requireManifest);
  const entries = descriptor.manifest?.files.public.map(file => file.path) ?? [
    "instruction.md",
    ...(await listPublicFiles(descriptor.root)),
  ];
  for (const packageRelativePath of entries) {
    if (packageRelativePath === "instruction.md") continue;
    const source = await assertRegularFile(descriptor.root, packageRelativePath);
    const destination = join(workspace, ...packageRelativePath.split("/"));
    await mkdir(dirname(destination), { recursive: true });
    await copyFile(source, destination, constants.COPYFILE_EXCL);
  }
  return descriptor;
}
