import { fileURLToPath } from "node:url";
import { command } from "./command.js";

/** "sandbox" runs candidate code through bubblewrap; "host" is an explicit, recorded opt-out. */
export type Isolation = "sandbox" | "host";

/** Launcher shared by the harness, task graders and public checkers. */
export const sandboxLauncher = fileURLToPath(new URL("../scripts/sandbox_exec.py", import.meta.url));

/**
 * Wrap a candidate command so only `writable` directories can be modified and the
 * host home directory, task packages and network are unreachable.
 */
export function isolatedCommand(executable: string, args: string[], writable: string[], isolation: Isolation = "sandbox") {
  if (isolation === "host") return { executable, args };
  return {
    executable: "python3",
    args: [sandboxLauncher, ...writable.flatMap(path => ["--rw", path]), "--", executable, ...args],
  };
}

/** Confirm bubblewrap can create a sandbox on this host before any trial starts. */
export async function sandboxAvailable(cwd: string): Promise<boolean> {
  const result = await command("python3", [sandboxLauncher, "--check"], cwd, 10_000, 4_000);
  return result.status === "completed" && result.exitCode === 0;
}
