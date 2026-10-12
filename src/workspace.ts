import { mkdtemp, realpath, rmdir, lstat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { git } from "./command.js";

// Expose a workspace handle while keeping ownership metadata private in a WeakMap.
export interface Workspace {
  readonly path: string;
  readonly repository: string;
  readonly commit: string;
}

// Track workspaces created by this process so cleanup can verify ownership.
interface Owned {
  root: string;
  path: string;
  repository: string;
  commit: string;
  common: string;
}
const owned = new WeakMap<Workspace, Owned>();

// Create a detached worktree at the requested commit without checking out or resetting the source worktree.
export async function createWorkspace(repository: string, commit: string): Promise<Workspace> {
  if (!/^[A-Za-z0-9][A-Za-z0-9._/-]*$/.test(commit))
    throw new Error("INVALID_COMMIT");

  const repo = await realpath(repository);
  const sha = (
    await git(repo, ["rev-parse", "--verify", `${commit}^{commit}`])
  ).trim();
  if (!/^[a-f0-9]{40,64}$/.test(sha)) throw new Error("INVALID_COMMIT");

  const common = await realpath(
    (await git(
      repo, ["rev-parse", "--path-format=absolute", "--git-common-dir"]
    )).trim(),
  );

  const root = await mkdtemp(join(tmpdir(), "agent-eval-"));
  const path = join(root, "worktree");
  try {
    await git(repo, ["worktree", "add", "--detach", path, sha]);
  } catch {
    // Do not blindly delete a partially created worktree.
    throw new Error("WORKTREE_CREATE_FAILED");
  }

  const workspace = Object.freeze({
    path, repository: repo, commit: sha
  });
  owned.set(workspace, {
    root, path, repository: repo, commit: sha, common
  });
  return workspace;
}

// Before cleanup, accept only a workspace created by this process and not replaced or modified.
async function verify(workspace: Workspace): Promise<Owned> {
  const state = owned.get(workspace);
  if (!state || resolve(workspace.path) !== resolve(state.path))
    throw new Error("UNOWNED_WORKSPACE");

  // Treat a symlink or a path pointing elsewhere as a replaced workspace.
  if ((await lstat(state.root)).isSymbolicLink() || (await lstat(state.path)).isSymbolicLink()) {
    throw new Error("WORKSPACE_REPLACED");
  }
  if (await realpath(state.path) !== resolve(state.path)) throw new Error("WORKSPACE_REPLACED");

  // Treat moved Git metadata or a changed HEAD as a replaced workspace.
  const common = await realpath(
    (await git(state.path, ["rev-parse", "--path-format=absolute", "--git-common-dir"])).trim(),
  );
  if (common !== state.common || (await git(state.path, ["rev-parse", "HEAD"])).trim() !== state.commit) {
    throw new Error("WORKSPACE_REPLACED");
  }

  return state;
}

// Collect tracked changes and non-ignored files as a binary-safe patch.
export async function collectPatch(workspace: Workspace): Promise<string> {
  await verify(workspace);
  // Stage new files in the temporary worktree index without changing the source repository index.
  await git(workspace.path, ["add", "--all", "--", "."]);
  return git(
    workspace.path,
    ["diff", "--cached", "--binary", "--no-ext-diff", "--no-textconv", workspace.commit, "--"],
  );
}

// Remove the worktree and temporary root created by this process.
export async function cleanupWorkspace(workspace: Workspace): Promise<void> {
  const state = await verify(workspace);
  await git(state.repository, ["worktree", "remove", "--force", state.path]);
  owned.delete(workspace);
  // Remove only the unique temporary root created by this process; never recursively delete an arbitrary path.
  await rmdir(state.root);
}
