import { existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const packageRoot = join(repoRoot, "task-library", "candidates", "eng-005-long-cycle-maintenance");
const baselinePath = join(packageRoot, "baseline");
const bundlePath = join(packageRoot, "baseline.bundle");
const expectedCommit = "679119874c31d2cff12cc48f57c86a1fcec6bcbc";

function git(cwd, args) {
  const result = spawnSync("git", ["-C", cwd, ...args], { encoding: "utf8", windowsHide: true });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error((result.stderr || result.stdout || `git exited with ${result.status}`).trim());
  }
  return result.stdout.trim();
}

if (existsSync(join(baselinePath, ".git"))) {
  const current = git(baselinePath, ["rev-parse", "--verify", "HEAD"]);
  if (current !== expectedCommit) throw new Error(`ENG005_BASELINE_COMMIT_MISMATCH:${current}`);
  console.log(`ENG-005 baseline is ready at ${current}.`);
} else {
  if (existsSync(baselinePath)) {
    throw new Error("ENG005_BASELINE_PATH_EXISTS_WITHOUT_GIT_METADATA; remove that local folder and rerun setup");
  }
  if (!existsSync(bundlePath)) throw new Error("ENG005_BASELINE_BUNDLE_MISSING");
  const clone = spawnSync("git", ["clone", "--quiet", bundlePath, baselinePath], { encoding: "utf8", windowsHide: true });
  if (clone.error) throw clone.error;
  if (clone.status !== 0) {
    throw new Error((clone.stderr || clone.stdout || `git clone exited with ${clone.status}`).trim());
  }
  git(baselinePath, ["checkout", "--quiet", "--detach", expectedCommit]);
  const current = git(baselinePath, ["rev-parse", "--verify", "HEAD"]);
  if (current !== expectedCommit) throw new Error(`ENG005_BASELINE_COMMIT_MISMATCH:${current}`);
  console.log(`Restored ENG-005 baseline at ${current}.`);
}