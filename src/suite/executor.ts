import { spawn } from "node:child_process";
import { createWriteStream } from "node:fs";
import { mkdir, symlink } from "node:fs/promises";
import { dirname, join } from "node:path";
import { git } from "../command.js";
import type { RunOptions, SuiteExecutor } from "./run.js";

/** Run a command to completion with its output appended to a log file; resolves to the exit code (null if killed). */
export async function logged(executable: string, args: string[], cwd: string, log: string, environment: Record<string, string> = {}): Promise<number | null> {
  await mkdir(dirname(log), { recursive: true });
  const stream = createWriteStream(log, { flags: "a" });
  stream.write(`$ ${[executable, ...args].join(" ")}\n`);
  return new Promise((resolve, reject) => {
    const child = spawn(executable, args, { cwd, env: { ...process.env, ...environment }, stdio: ["ignore", "pipe", "pipe"] });
    child.stdout.pipe(stream, { end: false });
    child.stderr.pipe(stream, { end: false });
    child.on("error", error => { stream.end(); reject(error); });
    child.on("close", code => { stream.end(`\n[exit ${code}]\n`, () => resolve(code)); });
  });
}

/**
 * The executor for real suites: a detached Git worktree of the chosen commit with node_modules, .env and runs linked
 * from the main tree, and every step a child process inside it, so each plan runs from a clean, pinned tree.
 */
export function processExecutor(repoRoot: string): SuiteExecutor {
  const node = process.execPath;
  const tsx = ["--import", "tsx"];
  return {
    async freeze(root, commit) {
      const head = commit ?? (await git(repoRoot, ["rev-parse", "HEAD"])).trim();
      const uncommitted = (await git(repoRoot, ["status", "--porcelain"])).split("\n").filter(Boolean).map(line => line.slice(3));
      await git(repoRoot, ["worktree", "prune"]);
      await mkdir(dirname(root), { recursive: true });
      await git(repoRoot, ["worktree", "add", "--detach", root, head]);
      for (const name of ["node_modules", ".env", "runs"]) await symlink(join(repoRoot, name), join(root, name));
      const status = await logged(node, ["scripts/prepare-baselines.mjs"], root, join(dirname(root), "logs", "freeze.log"));
      if (status !== 0) throw new Error("FREEZE_BASELINES_FAILED");
      const dirty = (await git(root, ["status", "--porcelain"])).trim();
      if (dirty) throw new Error("FREEZE_WORKTREE_DIRTY");
      return { commit: head, uncommitted };
    },
    async packageCheck(root, plans, log) {
      return (await logged("python3", ["scripts/task_packages.py", "check", "--plans", ...plans], root, log)) === 0;
    },
    async validate(root, plan, log) {
      return (await logged(node, [...tsx, "src/main.ts", "--plan", plan, "--validate-only"], root, log)) === 0;
    },
    async smoke(root, plan, outDirectory, log) {
      await logged(node, [...tsx, "scripts/null-agent-baseline.ts", plan, "--out", outDirectory], root, log);
    },
    async run(root, plan, outDirectory, log, options: RunOptions) {
      const args = [...tsx, "src/main.ts", "--plan", plan, "--out", outDirectory];
      if (options.resume) args.push("--resume", options.resume);
      if (options.stoppedProviders && Object.keys(options.stoppedProviders).length) {
        args.push("--stopped-providers", Object.entries(options.stoppedProviders).map(([provider, reason]) => `${provider}=${reason}`).join(","));
      }
      return logged(node, args, root, log, { NODE_USE_ENV_PROXY: "1", ...options.environment });
    },
    async tournament(root, runDirectories, visualPackage, judges, log) {
      const args = [...tsx, "scripts/judge-tournament.ts", ...runDirectories.flatMap(directory => ["--run", directory]), "--package", visualPackage];
      if (judges?.length) args.push("--judges", judges.join(","));
      return logged(node, args, root, log, { NODE_USE_ENV_PROXY: "1" });
    },
  };
}
