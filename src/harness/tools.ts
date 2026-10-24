import { readFile, writeFile, mkdir, realpath, readdir } from "node:fs/promises";
import { command } from "../command.js";
import { isolatedCommand, type Isolation, type RuntimeMounts } from "../sandbox.js";
import { dirname, isAbsolute, relative, resolve } from "node:path";
import { Type } from "typebox";
import type { AgentTool } from "@earendil-works/pi-agent-core";

/**
 * "none" is answer-only: the model gets no tools and answers in its reply (PLAN-007 WP2.4). "workspace-simulator" is
 * workspace-basic plus the `simulator` tool of a package's trusted simulator (PLAN-007 WP3.3).
 */
export type ToolProfile = "workspace-basic" | "workspace-augmented" | "doc-evidence" | "none" | "workspace-simulator";

/** How the `simulator` tool reaches a package's simulator: one process per command, its state in a private directory. */
export interface SimulatorToolOptions {
  executable: string;
  args: string[];
  stateDirectory: string;
  description: string;
  timeoutMs: number;
}

export interface WorkspaceToolOptions {
  readOnly?: boolean;
  execute?: boolean;
  /** How execute_command runs candidate commands; defaults to the bubblewrap sandbox. */
  isolation?: Isolation;
  /** Limits of one execute_command call; defaults to 10 seconds and 16,000 bytes of output. */
  commandLimits?: { timeoutMs: number; maxOutputBytes: number };
  /** The task's runtime mounts, bound read-only into every command with their environment. */
  runtime?: RuntimeMounts;
  /** The package's simulator, for the workspace-simulator profile. */
  simulator?: SimulatorToolOptions;
}

export const defaultCommandLimits = Object.freeze({ timeoutMs: 10_000, maxOutputBytes: 16_000 });

/** File tools are path-contained; execute_command relies on the sandbox for containment. */
export function workspaceTools(root: string, options: WorkspaceToolOptions = {}): AgentTool[] {
  async function contained(path: string, writing: boolean): Promise<string> {
    const target = resolve(root, path);
    const inside = (value: string) => {
      const suffix = relative(root, value);
      return suffix !== ".." && !suffix.startsWith(`..${process.platform === "win32" ? "\\" : "/"}`) && !isAbsolute(suffix);
    };
    if (!inside(target) || relative(root, target).split(/[\\/]/).includes(".git")) throw new Error("PATH_DENIED");
    const canonicalRoot = await realpath(root);
    const canonicallyInside = (value: string) => {
      const suffix = relative(canonicalRoot, value);
      return suffix !== ".." && !suffix.startsWith("../") && !suffix.startsWith("..\\") && !isAbsolute(suffix);
    };
    let cursor = target;
    while (true) {
      try {
        if (!canonicallyInside(await realpath(cursor))) throw new Error("PATH_DENIED");
        break;
      } catch (error) {
        if (!writing || (error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
        const parent = dirname(cursor);
        if (parent === cursor) throw new Error("PATH_DENIED");
        cursor = parent;
      }
    }
    return target;
  }
  const readParameters = Type.Object({ path: Type.String() });
  const writeParameters = Type.Object({ path: Type.String(), content: Type.String() });
  const read: AgentTool<typeof readParameters> = {
    name: "read_file", label: "Read file", description: "Read a UTF-8 file relative to the workspace.", parameters: readParameters,
    async execute(_id, args) {
      const text = await readFile(await contained(args.path, false), "utf8");
      if (Buffer.byteLength(text) > 100_000) throw new Error("FILE_TOO_LARGE");
      return { content: [{ type: "text", text }], details: {} };
    },
  };
  const write: AgentTool<typeof writeParameters> = {
    name: "write_file", label: "Write file", description: "Write a UTF-8 file relative to the workspace.", parameters: writeParameters,
    async execute(_id, args) {
      if (Buffer.byteLength(args.content) > 100_000) throw new Error("FILE_TOO_LARGE");
      const path = await contained(args.path, true);
      await mkdir(dirname(path), { recursive: true });
      await writeFile(path, args.content);
      return { content: [{ type: "text", text: "Written." }], details: {} };
    },
  };
  const list: AgentTool<typeof readParameters> = {
    name: "list_directory", label: "List directory", description: "List a directory relative to the workspace.", parameters: readParameters,
    async execute(_id, args) {
      const entries = await readdir(await contained(args.path, false), { withFileTypes: true });
      const text = JSON.stringify(entries.filter(entry => entry.name !== ".git").map(entry => ({ name: entry.name, directory: entry.isDirectory() })));
      return { content: [{ type: "text", text }], details: {} };
    },
  };
  const commandParameters = Type.Object({ executable: Type.String(), args: Type.Array(Type.String()) });
  const limits = options.commandLimits ?? defaultCommandLimits;
  const execute: AgentTool<typeof commandParameters> = {
    name: "execute_command", label: "Execute command", parameters: commandParameters,
    description: `Run a command in the workspace (no shell, no network). Each call may run for ${limits.timeoutMs / 1000} seconds and return ` +
      `${limits.maxOutputBytes} bytes of output; a longer command is stopped (status "timeout").`,
    async execute(_id, args) {
      const workspace = await realpath(root);
      // "{workspace}" in a runtime's environment is the workspace root (a repository item's code at {workspace}/repo).
      const runtime = options.runtime && { ...options.runtime, env: Object.fromEntries(Object.entries(options.runtime.env).map(([name, value]) => [name, value.split("{workspace}").join(workspace)])) };
      const sandboxed = isolatedCommand(args.executable, args.args, [workspace], options.isolation, runtime);
      const result = await command(sandboxed.executable, sandboxed.args, root, limits.timeoutMs, limits.maxOutputBytes, undefined, sandboxed.env);
      return { content: [{ type: "text", text: JSON.stringify(result) }], details: {} };
    },
  };
  return [read, list, ...(!options.readOnly ? [write] : []), ...(options.execute ? [execute] : [])];
}

const MAX_SIMULATOR_OUTPUT = 100_000;

/**
 * The `simulator` tool: sends one command to the package's simulator (trusted, run outside the sandbox, its state out of
 * the model's reach) and returns its JSON reply. The simulator decides what a command does; the harness only relays.
 */
export function simulatorTool(options: SimulatorToolOptions): AgentTool {
  const parameters = Type.Object({ command: Type.String({ minLength: 1, maxLength: 64 }), arguments: Type.Optional(Type.Record(Type.String(), Type.Unknown())) });
  const tool: AgentTool<typeof parameters> = {
    name: "simulator", label: "Simulator", description: options.description, parameters,
    async execute(_id, args) {
      const request = JSON.stringify({ command: args.command, arguments: args.arguments ?? {} });
      const result = await command(options.executable, options.args, options.stateDirectory, options.timeoutMs, MAX_SIMULATOR_OUTPUT, request + "\n");
      if (result.status !== "completed" || result.exitCode !== 0) throw new Error(`SIMULATOR_FAILED:${result.status}`);
      return { content: [{ type: "text", text: result.stdout.trim() || "{}" }], details: {} };
    },
  };
  return tool;
}
