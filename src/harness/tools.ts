import { readFile, writeFile, mkdir, realpath, readdir } from "node:fs/promises";
import { command } from "../command.js";
import { isolatedCommand, type Isolation, type RuntimeMounts } from "../sandbox.js";
import { dirname, isAbsolute, relative, resolve } from "node:path";
import { Type } from "typebox";
import type { AgentTool } from "@earendil-works/pi-agent-core";

/** "none" is answer-only: the model gets no tools and answers in its reply (PLAN-007 WP2.4). */
export type ToolProfile = "workspace-basic" | "workspace-augmented" | "doc-evidence" | "none";

export interface WorkspaceToolOptions {
  readOnly?: boolean;
  execute?: boolean;
  /** How execute_command runs candidate commands; defaults to the bubblewrap sandbox. */
  isolation?: Isolation;
  /** Limits of one execute_command call; defaults to 10 seconds and 16,000 bytes of output. */
  commandLimits?: { timeoutMs: number; maxOutputBytes: number };
  /** The task's runtime mounts, bound read-only into every command with their environment. */
  runtime?: RuntimeMounts;
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
      const sandboxed = isolatedCommand(args.executable, args.args, [await realpath(root)], options.isolation, options.runtime);
      const result = await command(sandboxed.executable, sandboxed.args, root, limits.timeoutMs, limits.maxOutputBytes, undefined, sandboxed.env);
      return { content: [{ type: "text", text: JSON.stringify(result) }], details: {} };
    },
  };
  return [read, list, ...(!options.readOnly ? [write] : []), ...(options.execute ? [execute] : [])];
}
