import { constants, createReadStream } from "node:fs";
import { createHash } from "node:crypto";
import { copyFile, mkdir, readdir, lstat } from "node:fs/promises";
import { dirname, join, relative, sep } from "node:path";
import type { ArtifactLimits, ArtifactManifest } from "./types.js";

export const defaultArtifactLimits: Readonly<ArtifactLimits> = Object.freeze({
  maxFiles: 1_000,
  maxFileBytes: 10 * 1024 * 1024,
  maxTrialBytes: 50 * 1024 * 1024,
  graderResultMaxBytes: 1024 * 1024,
  toolEvidenceMaxBytes: 1024 * 1024,
});

export class ArtifactLimitError extends Error {
  constructor(code: "ARTIFACT_FILE_LIMIT" | "ARTIFACT_FILE_SIZE_LIMIT" | "ARTIFACT_TRIAL_SIZE_LIMIT") {
    super(code);
    this.name = "ArtifactLimitError";
  }
}

/**
 * Hashes a snapshot without following links and enforces the same limits as export. Links and special files (a scratch
 * symlink, a socket) are not part of a deliverable: they are skipped, never followed, and listed in `skipped`.
 */
export async function inspectArtifacts(
  source: string,
  limits: ArtifactLimits = { ...defaultArtifactLimits },
): Promise<ArtifactManifest> {
  validateLimits(limits);
  const rootInfo = await lstat(source);
  if (!rootInfo.isDirectory() || rootInfo.isSymbolicLink()) throw new Error("ARTIFACT_ROOT_INVALID");

  const files: ArtifactManifest["files"] = [];
  const skipped: NonNullable<ArtifactManifest["skipped"]> = [];
  let totalBytes = 0;
  const visit = async (directory: string): Promise<void> => {
    for (const name of await readdir(directory)) {
      if (name === ".git" || name === "__pycache__") continue;
      const path = join(directory, name);
      const info = await lstat(path);
      if (info.isSymbolicLink() || (!info.isDirectory() && !info.isFile())) {
        skipped.push({ path: relative(source, path).split(sep).join("/"), kind: info.isSymbolicLink() ? "link" : "special" });
        continue;
      }
      if (info.isDirectory()) {
        await visit(path);
        continue;
      }
      if (files.length + 1 > limits.maxFiles) throw new ArtifactLimitError("ARTIFACT_FILE_LIMIT");
      if (info.size > limits.maxFileBytes) throw new ArtifactLimitError("ARTIFACT_FILE_SIZE_LIMIT");
      if (totalBytes + info.size > limits.maxTrialBytes) throw new ArtifactLimitError("ARTIFACT_TRIAL_SIZE_LIMIT");

      const hash = createHash("sha256");
      let sizeBytes = 0;
      for await (const chunk of createReadStream(path)) {
        sizeBytes += (chunk as Buffer).length;
        if (sizeBytes > limits.maxFileBytes || totalBytes + sizeBytes > limits.maxTrialBytes) {
          throw new ArtifactLimitError(sizeBytes > limits.maxFileBytes ? "ARTIFACT_FILE_SIZE_LIMIT" : "ARTIFACT_TRIAL_SIZE_LIMIT");
        }
        hash.update(chunk as Buffer);
      }
      if (sizeBytes !== info.size) throw new Error("ARTIFACT_CHANGED_DURING_READ");
      files.push({ path: relative(source, path).split(sep).join("/"), sizeBytes, sha256: hash.digest("hex") });
      totalBytes += sizeBytes;
    }
  };

  await visit(source);
  files.sort((left, right) => left.path.localeCompare(right.path));
  skipped.sort((left, right) => left.path.localeCompare(right.path));
  return { schemaVersion: 1, files, totalBytes, sha256: createHash("sha256").update(JSON.stringify(files)).digest("hex"), ...(skipped.length ? { skipped } : {}) };
}

function validateLimits(limits: ArtifactLimits): void {
  for (const [name, value] of Object.entries(limits)) {
    if (!Number.isSafeInteger(value) || value <= 0 || value > 2_147_483_647) {
      throw new Error(`INVALID_ARTIFACT_LIMIT:${name}`);
    }
  }
}

/** Retains regular files only; never follows links from generated submissions. */
export async function copyArtifacts(
  source: string,
  destination: string,
  limits: ArtifactLimits = { ...defaultArtifactLimits },
): Promise<ArtifactManifest> {
  const sourceManifest = await inspectArtifacts(source, limits);
  await mkdir(destination, { recursive: true });
  for (const file of sourceManifest.files) {
    const sourcePath = join(source, ...file.path.split("/"));
    const destinationPath = join(destination, ...file.path.split("/"));
    await mkdir(dirname(destinationPath), { recursive: true });
    await copyFile(sourcePath, destinationPath, constants.COPYFILE_EXCL);
  }
  const copiedManifest = await inspectArtifacts(destination, limits);
  if (copiedManifest.sha256 !== sourceManifest.sha256 || copiedManifest.totalBytes !== sourceManifest.totalBytes) throw new Error("ARTIFACT_CHANGED_DURING_COPY");
  return sourceManifest.skipped ? { ...copiedManifest, skipped: sourceManifest.skipped } : copiedManifest;
}
