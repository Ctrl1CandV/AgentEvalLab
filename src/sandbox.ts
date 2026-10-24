import { fileURLToPath } from "node:url";
import { command } from "./command.js";

/** "sandbox" runs candidate code through bubblewrap; "host" is an explicit, recorded opt-out. */
export type Isolation = "sandbox" | "host";

/** Launcher shared by the harness, task graders and public checkers. */
export const sandboxLauncher = fileURLToPath(new URL("../scripts/sandbox_exec.py", import.meta.url));

/**
 * A task's runtime mounts (CODE §4): directories bound read-only at a fixed path under /runtime, and the environment that
 * goes with them, with `{mount}` already replaced by the path the command sees.
 */
export interface RuntimeMounts {
  mounts: Array<{ source: string; target: string }>;
  env: Record<string, string>;
}

/**
 * Wrap a candidate command so only `writable` directories can be modified and the
 * host home directory, task packages and network are unreachable.
 * Without the sandbox ("host"), a mount is not bound: its environment names the source directory instead, and is
 * returned for the caller to set.
 */
export function isolatedCommand(executable: string, args: string[], writable: string[], isolation: Isolation = "sandbox", runtime?: RuntimeMounts) {
  if (isolation === "host") return { executable, args, env: hostEnvironment(runtime) };
  return {
    executable: "python3",
    args: [sandboxLauncher, ...writable.flatMap(path => ["--rw", path]),
      ...(runtime?.mounts ?? []).flatMap(mount => ["--mount", `${mount.source}:${mount.target}`]),
      ...Object.entries(runtime?.env ?? {}).flatMap(([name, value]) => ["--env", `${name}=${value}`]),
      "--", executable, ...args],
    env: {} as Record<string, string>,
  };
}

/** A runtime's environment outside the sandbox: each mount's target path replaced by its source directory. */
export function hostEnvironment(runtime?: RuntimeMounts): Record<string, string> {
  return Object.fromEntries(Object.entries(runtime?.env ?? {}).map(([name, value]) =>
    [name, (runtime?.mounts ?? []).reduce((text, mount) => text.split(mount.target).join(mount.source), value)]));
}

/** Confirm bubblewrap can create a sandbox on this host before any trial starts. */
export async function sandboxAvailable(cwd: string): Promise<boolean> {
  const result = await command("python3", [sandboxLauncher, "--check"], cwd, 10_000, 4_000);
  return result.status === "completed" && result.exitCode === 0;
}
