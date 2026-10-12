import { createHash } from "node:crypto";
import { lstat, mkdir, mkdtemp, readFile, realpath, rename, rm } from "node:fs/promises";
import { basename, dirname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { copyArtifacts, defaultArtifactLimits } from "./artifacts.js";
import type { ArtifactLimits, ArtifactManifest } from "./types.js";

const MAX_TRAJECTORY_JSON_BYTES = 16 * 1024 * 1024;
const MAX_MANIFEST_FILES = 100_000;

function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("TRAJECTORY_RECORD_INVALID");
  return value as Record<string, unknown>;
}

function within(parent: string, target: string): boolean {
  const fromParent = relative(parent, target);
  return fromParent === "" || (fromParent !== ".." && !fromParent.startsWith(`..${sep}`) && !isAbsolute(fromParent));
}

function validateManifest(value: unknown): ArtifactManifest {
  const manifest = object(value);
  if (manifest.schemaVersion !== 1 || !Array.isArray(manifest.files) || manifest.files.length > MAX_MANIFEST_FILES ||
      typeof manifest.totalBytes !== "number" || !Number.isSafeInteger(manifest.totalBytes) || manifest.totalBytes < 0 ||
      typeof manifest.sha256 !== "string" || !/^[a-f0-9]{64}$/.test(manifest.sha256)) throw new Error("TRAJECTORY_SNAPSHOT_MANIFEST_INVALID");
  const files: ArtifactManifest["files"] = [];
  const seen = new Set<string>();
  let totalBytes = 0;
  for (const raw of manifest.files) {
    const file = object(raw);
    if (typeof file.path !== "string" || !file.path || file.path.includes("\\") || file.path.includes("\0") ||
        isAbsolute(file.path) || /^[A-Za-z]:/.test(file.path) || file.path.split("/").some(part => !part || part === "." || part === "..") ||
        seen.has(file.path) || typeof file.sizeBytes !== "number" || !Number.isSafeInteger(file.sizeBytes) || file.sizeBytes < 0 ||
        typeof file.sha256 !== "string" || !/^[a-f0-9]{64}$/.test(file.sha256)) throw new Error("TRAJECTORY_SNAPSHOT_MANIFEST_INVALID");
    seen.add(file.path);
    totalBytes += file.sizeBytes;
    if (!Number.isSafeInteger(totalBytes)) throw new Error("TRAJECTORY_SNAPSHOT_MANIFEST_INVALID");
    files.push({ path: file.path, sizeBytes: file.sizeBytes, sha256: file.sha256 });
  }
  const sorted = [...files].sort((left, right) => left.path.localeCompare(right.path));
  const digest = createHash("sha256").update(JSON.stringify(sorted)).digest("hex");
  if (totalBytes !== manifest.totalBytes || JSON.stringify(files) !== JSON.stringify(sorted) || digest !== manifest.sha256) {
    throw new Error("TRAJECTORY_SNAPSHOT_MANIFEST_INVALID");
  }
  return { schemaVersion: 1, files, totalBytes, sha256: digest };
}

function parseLimits(value: unknown, manifest: ArtifactManifest): ArtifactLimits {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("TRAJECTORY_ARTIFACT_LIMITS_INVALID");
  const input = value as Record<string, unknown>;
  const limits: ArtifactLimits = {
    maxFiles: input.maxFiles as number,
    maxFileBytes: input.maxFileBytes as number,
    maxTrialBytes: input.maxTrialBytes as number,
    graderResultMaxBytes: input.graderResultMaxBytes as number,
    toolEvidenceMaxBytes: (input.toolEvidenceMaxBytes as number | undefined) ?? defaultArtifactLimits.toolEvidenceMaxBytes,
  };
  if (Object.values(limits).some(limit => !Number.isSafeInteger(limit) || limit <= 0 || limit > 2_147_483_647) ||
      manifest.files.length > limits.maxFiles || manifest.totalBytes > limits.maxTrialBytes ||
      manifest.files.some(file => file.sizeBytes > limits.maxFileBytes)) throw new Error("TRAJECTORY_ARTIFACT_LIMITS_INVALID");
  return limits;
}

/** Restores one immutable trajectory checkpoint into a new directory outside its run. */
export async function restoreTrajectorySnapshot(
  trialDirectory: string,
  stageId: string,
  cycleId: "cycle-1" | "cycle-2",
  destinationPath: string,
): Promise<{ destination: string; sha256: string; stageId: string; cycleId: string }> {
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(stageId)) throw new Error("TRAJECTORY_STAGE_ID_INVALID");
  if (cycleId !== "cycle-1" && cycleId !== "cycle-2") throw new Error("TRAJECTORY_CYCLE_ID_INVALID");
  if (typeof destinationPath !== "string" || !destinationPath.trim()) throw new Error("RESTORE_DESTINATION_REQUIRED");

  const trial = resolve(trialDirectory);
  const trialInfo = await lstat(trial).catch(() => null);
  if (!trialInfo?.isDirectory() || trialInfo.isSymbolicLink()) throw new Error("TRAJECTORY_TRIAL_DIRECTORY_INVALID");
  const experimentRoot = await realpath(dirname(trial));
  const resolvedTrial = await realpath(trial);
  if (!within(experimentRoot, resolvedTrial)) throw new Error("TRAJECTORY_TRIAL_DIRECTORY_INVALID");

  const trajectoryPath = join(trial, "trajectory.json");
  const recordInfo = await lstat(trajectoryPath).catch(() => null);
  if (!recordInfo?.isFile() || recordInfo.isSymbolicLink() || recordInfo.size > MAX_TRAJECTORY_JSON_BYTES) {
    throw new Error("TRAJECTORY_RECORD_INVALID");
  }
  let rawRecord: unknown;
  try { rawRecord = JSON.parse(await readFile(trajectoryPath, "utf8")) as unknown; }
  catch { throw new Error("TRAJECTORY_RECORD_INVALID_JSON"); }
  const record = object(rawRecord);
  if (typeof record.id !== "string" || record.id !== basename(trial) || !Array.isArray(record.stages)) throw new Error("TRAJECTORY_RECORD_INVALID");
  const stage = record.stages.map(object).find(value => value.stageId === stageId);
  if (!stage || !Array.isArray(stage.cycles)) throw new Error("TRAJECTORY_SNAPSHOT_NOT_FOUND");
  const cycle = stage.cycles.map(object).find(value => value.cycleId === cycleId);
  if (!cycle || !cycle.snapshot) throw new Error("TRAJECTORY_SNAPSHOT_NOT_FOUND");
  const snapshot = object(cycle.snapshot);
  const expectedRelativePath = `snapshots/${stageId}-${cycleId}`;
  if (snapshot.path !== expectedRelativePath) throw new Error("TRAJECTORY_SNAPSHOT_PATH_INVALID");
  const manifest = validateManifest(snapshot.manifest);

  const snapshotsDirectory = join(trial, "snapshots");
  const snapshotsInfo = await lstat(snapshotsDirectory).catch(() => null);
  if (!snapshotsInfo?.isDirectory() || snapshotsInfo.isSymbolicLink()) throw new Error("TRAJECTORY_SNAPSHOT_DIRECTORY_INVALID");
  const source = join(snapshotsDirectory, `${stageId}-${cycleId}`);
  const sourceInfo = await lstat(source).catch(() => null);
  if (!sourceInfo?.isDirectory() || sourceInfo.isSymbolicLink()) throw new Error("TRAJECTORY_SNAPSHOT_DIRECTORY_INVALID");
  if (!within(resolvedTrial, await realpath(source))) throw new Error("TRAJECTORY_SNAPSHOT_PATH_INVALID");

  const experimentPath = join(experimentRoot, "experiment.json");
  const experimentInfo = await lstat(experimentPath).catch(() => null);
  if (!experimentInfo?.isFile() || experimentInfo.isSymbolicLink() || experimentInfo.size > MAX_TRAJECTORY_JSON_BYTES) {
    throw new Error("TRAJECTORY_EXPERIMENT_INVALID");
  }
  let artifactLimits: ArtifactLimits;
  try {
    const experiment = object(JSON.parse(await readFile(experimentPath, "utf8")) as unknown);
    artifactLimits = parseLimits(experiment.artifactLimits, manifest);
  } catch (error) {
    if (error instanceof Error && error.message === "TRAJECTORY_ARTIFACT_LIMITS_INVALID") throw error;
    throw new Error("TRAJECTORY_EXPERIMENT_INVALID");
  }

  const destination = resolve(destinationPath);
  if (within(experimentRoot, destination)) throw new Error("RESTORE_DESTINATION_INSIDE_RUN");
  await mkdir(dirname(destination), { recursive: true });
  const resolvedParent = await realpath(dirname(destination));
  const resolvedDestination = resolve(resolvedParent, basename(destination));
  if (within(experimentRoot, resolvedDestination)) throw new Error("RESTORE_DESTINATION_INSIDE_RUN");
  if (await lstat(resolvedDestination).catch(() => null)) throw new Error("RESTORE_DESTINATION_EXISTS");

  const temporary = await mkdtemp(join(resolvedParent, ".agent-eval-trajectory-restore-"));
  let restored = false;
  try {
    const copied = await copyArtifacts(source, temporary, artifactLimits);
    if (copied.sha256 !== manifest.sha256 || copied.totalBytes !== manifest.totalBytes ||
        JSON.stringify(copied.files) !== JSON.stringify(manifest.files)) throw new Error("RESTORE_SNAPSHOT_HASH_MISMATCH");
    if (await lstat(resolvedDestination).catch(() => null)) throw new Error("RESTORE_DESTINATION_EXISTS");
    await rename(temporary, resolvedDestination);
    restored = true;
    return { destination: resolvedDestination, sha256: copied.sha256, stageId, cycleId };
  } finally {
    if (!restored) {
      const temporaryInfo = await lstat(temporary).catch(() => null);
      const actualParent = await realpath(dirname(temporary)).catch(() => "");
      if (temporaryInfo?.isDirectory() && !temporaryInfo.isSymbolicLink() && actualParent === resolvedParent &&
          basename(temporary).startsWith(".agent-eval-trajectory-restore-")) {
        await rm(temporary, { recursive: true, force: true });
      }
    }
  }
}
