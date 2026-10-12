import { spawn } from "node:child_process";

export interface CommandResult {
  status: "completed" | "timeout" | "output_limit" | "error";
  exitCode: number | null;
  stdout: string;
  stderr: string;
  outputBytes: number;
}

/*
- Runs trusted host commands; this is not a security sandbox
- Passes only allowlisted environment variables and omits credential variables
- Stops the direct child on timeout or output overflow; descendant processes may remain
*/
export function command(
  executable: string,
  args: string[],
  cwd: string,
  timeoutMs = 10_000,
  maxBytes = 1_000_000,
  input?: string,
): Promise<CommandResult> {
  return new Promise(resolve => {
    // Keep only a small set of path and system variables.
    const env: NodeJS.ProcessEnv = {};
    for (const name of [
      "PATH", "Path", "SystemRoot", "WINDIR",
      "TEMP", "TMP", "HOME", "USERPROFILE"
    ]) {
      if (process.env[name]) env[name] = process.env[name];
    }

    // Disable interactive Git prompts and external configuration.
    env.GIT_TERMINAL_PROMPT = "0";
    env.GIT_CONFIG_NOSYSTEM = "1";
    env.GIT_CONFIG_GLOBAL = process.platform === "win32" ? "NUL" : "/dev/null";

    const child = spawn(executable, args, {
      cwd,
      shell: false,
      env,
      windowsHide: true,
      stdio: ["pipe", "pipe", "pipe"],
    });

    let status: CommandResult["status"] = "completed";
    let outputBytes = 0;
    const chunks: Buffer[] = [];
    const errors: Buffer[] = [];

    let settled = false;
    let escalation: ReturnType<typeof setTimeout> | undefined;
    let exitDrain: ReturnType<typeof setTimeout> | undefined;
    const finish = (exitCode: number | null) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      clearTimeout(escalation);
      clearTimeout(exitDrain);
      resolve({ status, exitCode, stdout: Buffer.concat(chunks).toString("utf8"), stderr: Buffer.concat(errors).toString("utf8"), outputBytes });
    };
    const stop = () => {
      if (escalation || settled) return;
      child.kill();
      escalation = setTimeout(() => {
        child.kill("SIGKILL");
        child.stdout.destroy();
        child.stderr.destroy();
        child.stdin.destroy();
      }, 250);
      escalation.unref();
    };
    const timer = setTimeout(() => {
      status = "timeout";
      stop();
    }, timeoutMs);

    // Capture stdout; count stderr toward the output limit without returning it.
    const collect = (chunk: Buffer, stdout: boolean) => {
      outputBytes += chunk.length;
      if (outputBytes > maxBytes) {
        status = "output_limit";
        stop();
        return;
      }
      if (stdout) chunks.push(chunk);
      else errors.push(chunk);
    };
    child.stdout.on("data", chunk => collect(chunk, true));
    child.stderr.on("data", chunk => collect(chunk, false));
    child.stdin.on("error", () => { }); // Ignore stdin errors after input has been discarded.

    child.on("error", () => {
      status = "error";
      finish(null);
    });
    child.on("exit", exitCode => {
      if (status === "completed" || settled) return;
      exitDrain = setTimeout(() => {
        child.stdout.destroy();
        child.stderr.destroy();
        child.stdin.destroy();
        finish(exitCode);
      }, 250);
      exitDrain.unref();
    });
    child.on("close", finish);

    child.stdin.end(input);
  });
}

// Git wrapper that disables hooks and reports a stable error.
export async function git(
  cwd: string, args: string[], input?: string
): Promise<string> {
  const r = await command(
    "git", ["-c", "core.hooksPath=/dev/null", ...args],
    cwd, 30_000, 2_000_000, input
  );
  if (r.status !== "completed" || r.exitCode !== 0)
    throw new Error("GIT_OPERATION_FAILED");
  return r.stdout;
}
