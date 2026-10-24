import { createHash } from "node:crypto";
import { lstat, mkdir, mkdtemp, readFile, realpath, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { command } from "../command.js";
import type { ManifestItem, PackageDescriptor } from "./manifest.js";
import { PackageManifestError } from "./manifest.js";

/**
 * Repository workspaces (CODE §5, PLAN-007 WP2.4). An item's repository is a trusted archive of the working tree at the
 * base commit, without history. At projection it is unpacked into the workspace and committed once under a fixed author
 * and date, so the model sees a clean single-commit history. A bare copy of that commit stays outside the workspace, so
 * the delivered change is read against it whatever the model does to the workspace's own `.git`.
 */

export interface RepositoryWorkspace {
  /** The repository's directory inside the workspace. */
  path: string;
  /** The single commit the model starts from. */
  commit: string;
  /** The harness's own bare copy, outside the workspace. */
  gitDir: string;
  cleanup(): Promise<void>;
}

/** The fixed identity and date of the single commit: the same tree always gives the same commit. */
const COMMIT_ENV = {
  GIT_AUTHOR_NAME: "agenteval", GIT_AUTHOR_EMAIL: "agenteval@invalid", GIT_AUTHOR_DATE: "2000-01-01T00:00:00Z",
  GIT_COMMITTER_NAME: "agenteval", GIT_COMMITTER_EMAIL: "agenteval@invalid", GIT_COMMITTER_DATE: "2000-01-01T00:00:00Z",
};
/** The largest delivered change read back; a larger one is a resource-limit failure of the delivery. */
export const MAX_PATCH_BYTES = 10 * 1024 * 1024;

export class PatchLimitError extends Error {
  constructor() {
    super("PATCH_SIZE_LIMIT");
    this.name = "PatchLimitError";
  }
}

async function run(executable: string, args: string[], cwd: string, maxBytes = 2_000_000): Promise<string> {
  const result = await command(executable, args, cwd, 120_000, maxBytes, undefined, COMMIT_ENV);
  if (result.status === "output_limit") throw new PatchLimitError();
  if (result.status !== "completed" || result.exitCode !== 0) throw new Error(`REPOSITORY_${executable.toUpperCase()}_FAILED`);
  return result.stdout;
}

const gitArgs = (args: string[]) => ["-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false", ...args];

/** Unpack an item's repository into the workspace as a fresh single-commit history. */
export async function projectRepository(descriptor: PackageDescriptor, item: ManifestItem, workspace: string): Promise<RepositoryWorkspace> {
  const spec = item.repository;
  if (!spec) throw new PackageManifestError("PACKAGE_ITEM_HAS_NO_REPOSITORY");
  const trusted = descriptor.manifest?.files.trusted.find(file => file.path === spec.archive);
  if (!trusted) throw new PackageManifestError("PACKAGE_REPOSITORY_ARCHIVE_UNDECLARED");
  const archive = join(descriptor.root, ...spec.archive.split("/"));
  const info = await lstat(archive);
  if (!info.isFile() || info.isSymbolicLink()) throw new PackageManifestError("PACKAGE_REPOSITORY_ARCHIVE_INVALID");
  if (createHash("sha256").update(await readFile(archive)).digest("hex") !== trusted.sha256.toLowerCase()) throw new PackageManifestError("PACKAGE_FILE_HASH_MISMATCH");

  const path = join(workspace, spec.directory);
  await mkdir(path, { recursive: false });
  await run("tar", ["--no-same-owner", "-xf", archive, "-C", path], workspace);
  await run("git", gitArgs(["init", "--quiet"]), path);
  // Every file of the archive is tracked, also those its own .gitignore names: the commit is the archive.
  await run("git", gitArgs(["add", "--all", "--force", "."]), path);
  await run("git", gitArgs(["commit", "--quiet", "--no-verify", "--allow-empty", "-m", "Repository at the task's base commit"]), path);
  const commit = (await run("git", gitArgs(["rev-parse", "HEAD"]), path)).trim();
  const root = await realpath(await mkdtemp(join(tmpdir(), "agenteval-repository-")));
  const gitDir = join(root, "base.git");
  await run("git", gitArgs(["clone", "--bare", "--quiet", "--", path, gitDir]), root);
  return { path, commit, gitDir, cleanup: () => rm(root, { recursive: true, force: true }) };
}

/**
 * The delivered change: the working tree against the single commit, read through the harness's own copy. New files are
 * included, files ignored by the repository's .gitignore are not (as in SWE-bench), and the model's own commits count.
 */
export async function collectRepositoryPatch(repository: RepositoryWorkspace): Promise<string> {
  const git = (args: string[], maxBytes?: number) => run("git", gitArgs([`--git-dir=${repository.gitDir}`, `--work-tree=${repository.path}`, ...args]), repository.path, maxBytes);
  // The base index first, so tracked files that the .gitignore names stay tracked.
  await git(["read-tree", repository.commit]);
  await git(["add", "--all", "."]);
  return git(["diff", "--cached", "--binary", "--no-ext-diff", "--no-textconv", repository.commit, "--"], MAX_PATCH_BYTES);
}
