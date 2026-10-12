import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { cleanupWorkspace, createWorkspace } from "../workspace.js";
import type { Workspace } from "../workspace.js";
import type { EvaluationCase } from "./types.js";

export interface TrialWorkspace {
  path: string;
  git?: Workspace;
  cleanup(): Promise<void>;
}

export async function prepareWorkspace(repository?: EvaluationCase["repository"]): Promise<TrialWorkspace> {
  if (repository) {
    const workspace = await createWorkspace(repository.path, repository.commit);
    return { path: workspace.path, git: workspace, cleanup: () => cleanupWorkspace(workspace) };
  }
  const path = await mkdtemp(join(tmpdir(), "evaluation-"));
  return { path, cleanup: () => rm(path, { recursive: true, force: true }) };
}
