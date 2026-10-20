import { existsSync, readdirSync, rmdirSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

// Task baselines kept as Git bundles in the repository and restored as pinned clones before checks and runs.
const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const baselines = [
  { name: "ENG-005", packageRoot: join(repoRoot, "task-library", "candidates", "eng-005-long-cycle-maintenance"),
    commit: "679119874c31d2cff12cc48f57c86a1fcec6bcbc" },
  { name: "ENG-004", packageRoot: join(repoRoot, "task-library", "calibration", "eng-004-resource-index"),
    commit: "0bd1eda866f64c4cdd990e7636cead1ebd2a6cd2" },
];

function git(cwd, args) {
  const result = spawnSync("git", ["-C", cwd, ...args], { encoding: "utf8", windowsHide: true });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error((result.stderr || result.stdout || `git exited with ${result.status}`).trim());
  }
  return result.stdout.trim();
}

for (const { name, packageRoot, commit } of baselines) {
  const baselinePath = join(packageRoot, "baseline");
  const bundlePath = join(packageRoot, "baseline.bundle");
  if (existsSync(join(baselinePath, ".git"))) {
    const current = git(baselinePath, ["rev-parse", "--verify", "HEAD"]);
    if (current !== commit) throw new Error(`${name}_BASELINE_COMMIT_MISMATCH:${current}`);
    console.log(`${name} baseline is ready at ${current}.`);
    continue;
  }
  if (existsSync(baselinePath) && readdirSync(baselinePath).length) {
    throw new Error(`${name}_BASELINE_PATH_EXISTS_WITHOUT_GIT_METADATA; remove that local folder and rerun setup`);
  }
  if (!existsSync(bundlePath)) throw new Error(`${name}_BASELINE_BUNDLE_MISSING`);
  if (existsSync(baselinePath)) rmdirSync(baselinePath);
  const clone = spawnSync("git", ["clone", "--quiet", bundlePath, baselinePath], { encoding: "utf8", windowsHide: true });
  if (clone.error) throw clone.error;
  if (clone.status !== 0) {
    throw new Error((clone.stderr || clone.stdout || `git clone exited with ${clone.status}`).trim());
  }
  git(baselinePath, ["checkout", "--quiet", "--detach", commit]);
  const current = git(baselinePath, ["rev-parse", "--verify", "HEAD"]);
  if (current !== commit) throw new Error(`${name}_BASELINE_COMMIT_MISMATCH:${current}`);
  console.log(`Restored ${name} baseline at ${current}.`);
}
