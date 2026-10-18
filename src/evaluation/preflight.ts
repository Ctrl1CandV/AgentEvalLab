import { inspectPackage, type PackageDescriptor } from "./manifest.js";
import { resolveCaseItems } from "./items.js";
import { command } from "../command.js";
import { sandboxAvailable } from "../sandbox.js";
import type { EvaluationPlan } from "./types.js";
import { realpath } from "node:fs/promises";
import { join, resolve } from "node:path";
import { tmpdir } from "node:os";

/** Verifies every task package before credentials are loaded or an experiment is created. */
export async function preflightPlan(plan: EvaluationPlan): Promise<Map<string, PackageDescriptor>> {
  const packages = new Map<string, PackageDescriptor>();
  // Candidate code runs only under trusted local execution; refuse to run it unconfined by accident.
  if (plan.trustedLocalExecution && (plan.isolation ?? "sandbox") === "sandbox" && !(await sandboxAvailable(tmpdir()))) {
    throw new Error("SANDBOX_UNAVAILABLE");
  }
  for (const item of plan.cases) {
    if (!item.packagePath) continue;
    const descriptor = await inspectPackage(
      item.packagePath,
      item.packageManifestSha256,
      plan.schemaVersion === 3,
    );
    const runtimeCheck = descriptor.manifest?.environment.runtimeCheck;
    if (runtimeCheck) {
      const result = await command(
        runtimeCheck.executable,
        runtimeCheck.args,
        descriptor.root,
        5_000,
        2_000,
      );
      const output = result.stdout + result.stderr;
      if (result.status !== "completed" || result.exitCode !== 0 ||
          !output.includes(runtimeCheck.expectedSubstring)) {
        throw new Error("PACKAGE_RUNTIME_UNSUPPORTED");
      }
    }
    const manifest = descriptor.manifest;
    if (plan.execution?.kind === "trajectory" && (!manifest?.stages || !manifest.stages.length || item.evaluator.kind !== "task-package")) {
      throw new Error("TRAJECTORY_PACKAGE_REQUIRED");
    }
    if (manifest?.baseline) {
      if (!item.repository) throw new Error("PACKAGE_BASELINE_REPOSITORY_REQUIRED");
      const expectedRoot = await realpath(resolve(descriptor.root, ...manifest.baseline.path.split("/")));
      const suppliedRoot = await realpath(item.repository.path);
      if (expectedRoot !== suppliedRoot) throw new Error("PACKAGE_BASELINE_PATH_MISMATCH");
      const baseline = await command("git", ["rev-parse", "--verify", `${item.repository.commit}^{commit}`], suppliedRoot, 5_000, 2_000);
      if (baseline.status !== "completed" || baseline.exitCode !== 0 || baseline.stdout.trim().toLowerCase() !== manifest.baseline.commit.toLowerCase()) {
        throw new Error("PACKAGE_BASELINE_COMMIT_MISMATCH");
      }
    }
    const supportedProfiles = manifest?.toolProfiles ?? ["workspace-basic"];
    if (item.toolProfile && !supportedProfiles.includes(item.toolProfile)) throw new Error("PACKAGE_TOOL_PROFILE_UNSUPPORTED");
    if (!item.toolProfile && supportedProfiles.length > 1) throw new Error("PACKAGE_TOOL_PROFILE_REQUIRED");
    if (manifest?.grader.requiresTrace && !descriptor.manifest?.grader.answerSource) {
      throw new Error("PACKAGE_TRACE_GRADER_REQUIRES_ANSWER_SOURCE");
    }
    resolveCaseItems(item, descriptor);
    packages.set(item.id, descriptor);
  }
  return packages;
}
