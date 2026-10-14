import { mkdtemp, realpath, rm, rmdir, lstat } from "node:fs/promises";
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
  gitDir: string;
}
const owned = new WeakMap<Workspace, Owned>();

// Clone the pinned commit into a private repository so candidate Git operations
// (commits, branches, resets) never touch the source repository or other trials.
export async function createWorkspace(repository: string, commit: string): Promise<Workspace> {
  if (!/^[A-Za-z0-9][A-Za-z0-9._/-]*$/.test(commit))
    throw new Error("INVALID_COMMIT");

  const repo = await realpath(repository);
  const sha = (
    await git(repo, ["rev-parse", "--verify", `${commit}^{commit}`])
  ).trim();
  if (!/^[a-f0-9]{40,64}$/.test(sha)) throw new Error("INVALID_COMMIT");

  const root = await realpath(await mkdtemp(join(tmpdir(), "agent-eval-")));
  const path = join(root, "workspace");
  try {
    await git(root, ["clone", "--quiet", "--no-hardlinks", "--no-checkout", "--", repo, path]);
    await git(path, ["checkout", "--quiet", "--detach", sha]);
    // Without a remote the candidate cannot push back into the source repository.
    await git(path, ["remote", "remove", "origin"]);
  } catch {
    // Leave a partially created clone in place for inspection rather than deleting blindly.
    throw new Error("WORKSPACE_CREATE_FAILED");
  }

  const workspace = Object.freeze({
    path, repository: repo, commit: sha
  });
  owned.set(workspace, {
    root, path, repository: repo, commit: sha, gitDir: join(path, ".git")
  });
  return workspace;
}

// Before collection or cleanup, accept only a workspace created by this process whose
// directories and Git metadata have not been replaced. HEAD may move: candidates may commit.
async function verify(workspace: Workspace): Promise<Owned> {
  const state = owned.get(workspace);
  if (!state || resolve(workspace.path) !== resolve(state.path))
    throw new Error("UNOWNED_WORKSPACE");

  // Treat a symlink or a path pointing elsewhere as a replaced workspace.
  for (const path of [state.root, state.path, state.gitDir]) {
    const info = await lstat(path);
    if (info.isSymbolicLink() || !info.isDirectory()) throw new Error("WORKSPACE_REPLACED");
  }
  if (await realpath(state.path) !== state.path) throw new Error("WORKSPACE_REPLACED");

  // Treat Git metadata that resolves outside the private clone as a replaced workspace.
  const gitDir = (await git(state.path, ["rev-parse", "--absolute-git-dir"])).trim();
  if (await realpath(gitDir) !== state.gitDir) throw new Error("WORKSPACE_REPLACED");

  return state;
}

// Collect every change from the pinned commit to the final working tree as a binary-safe
// patch, including changes the candidate committed itself.
export async function collectPatch(workspace: Workspace): Promise<string> {
  const state = await verify(workspace);
  // Stage new files in the private clone's index; the source repository is never touched.
  await git(state.path, ["add", "--all", "--", "."]);
  return git(
    state.path,
    ["diff", "--cached", "--binary", "--no-ext-diff", "--no-textconv", state.commit, "--"],
  );
}

// Remove the private clone, then the temporary root created by this process.
export async function cleanupWorkspace(workspace: Workspace): Promise<void> {
  const state = await verify(workspace);
  await rm(state.path, { recursive: true, force: true });
  owned.delete(workspace);
  // Remove only the unique temporary root; unexpected extra files make cleanup fail visibly.
  await rmdir(state.root);
}
