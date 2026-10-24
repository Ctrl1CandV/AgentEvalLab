import { inspectPackage, type ManifestItem, type PackageDescriptor } from "./manifest.js";
import { defaultArtifactLimits } from "./artifacts.js";
import { resolveCaseItems } from "./items.js";
import { command } from "../command.js";
import { sandboxAvailable } from "../sandbox.js";
import type { EvaluationPlan } from "./types.js";
import { realpath, stat } from "node:fs/promises";
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
    // Runtime mounts are bound in single-session trials only; no trajectory package uses them.
    if (plan.execution?.kind === "trajectory" && manifest?.runtime) throw new Error("TRAJECTORY_RUNTIME_UNSUPPORTED");
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
    const items = resolveCaseItems(item, descriptor);
    // A repository item brings its own repository; a plan's repository on top would be a second baseline.
    if (items?.some(entry => entry.repository) && item.repository) throw new Error("PACKAGE_REPOSITORY_CONFLICT");
    await checkProjectedArtifacts(plan, descriptor, items);
    checkSplits(plan, descriptor, items);
    packages.set(item.id, descriptor);
  }
  return packages;
}

/** A plan runs one split (VALIDATION §3): the v2 tasks it selects all carry the same split, the protocol's when given. */
function checkSplits(plan: EvaluationPlan, descriptor: PackageDescriptor, items: ManifestItem[] | null): void {
  const manifest = descriptor.manifest;
  if (manifest?.schemaVersion !== 2) return;
  const splits = new Set((items ?? [manifest.task]).map(entry => entry?.split));
  if (splits.size !== 1) throw new Error("PLAN_MIXES_SPLITS");
  if (plan.protocol && !splits.has(plan.protocol.split)) throw new Error("PLAN_SPLIT_MISMATCH");
}

/**
 * Refuse a plan whose artifact limits cannot hold even the files a trial starts with: the package's public files plus
 * the largest selected item's files. Such a plan would run every trial and then fail every artifact export.
 */
async function checkProjectedArtifacts(plan: EvaluationPlan, descriptor: PackageDescriptor, items: ManifestItem[] | null): Promise<void> {
  const limits = plan.artifactLimits ?? defaultArtifactLimits;
  const sizes = async (paths: string[]) => Promise.all(paths.map(async path => (await stat(join(descriptor.root, ...path.split("/")))).size));
  const shared = await sizes((descriptor.manifest?.files.public ?? []).map(file => file.path).filter(path => path !== "instruction.md"));
  const perItem = items ? await Promise.all(items.map(entry => sizes(entry.files.map(file => file.path).filter(path => !path.endsWith("/prompt.md"))))) : [[]];
  for (const own of perItem) {
    const files = [...shared, ...own];
    if (files.length > limits.maxFiles || files.some(size => size > limits.maxFileBytes) ||
        files.reduce((sum, size) => sum + size, 0) > limits.maxTrialBytes) throw new Error("PLAN_ARTIFACT_LIMIT_TOO_LOW");
  }
}
