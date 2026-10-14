import { readFile, readdir, realpath, writeFile, mkdir, lstat } from "node:fs/promises";
import { dirname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { Type } from "typebox";
import type { AgentTool } from "@earendil-works/pi-agent-core";
import { command } from "../command.js";
import { workspaceTools, type ToolProfile, type WorkspaceToolOptions } from "./tools.js";

const MAX_WORKSPACE_TEXT = 100_000;
const MAX_SEARCH_RESULTS = 50;
const MAX_SEARCH_PATTERN_CHARS = 200;
const MAX_MATCH_PREVIEW_CHARS = 200;
const MAX_SEARCH_FILE_BYTES = 2_000_000;
const MAX_PAGE_LINES = 200;
const MAX_PAGE_BYTES = 20_000;
const DOC_READ_LIMIT = 400;

function textResult(value: unknown) {
  return { content: [{ type: "text" as const, text: JSON.stringify(value) }], details: {} };
}

function checkedRelativePath(value: unknown, allowRoot = false): string {
  if (typeof value !== "string" || value.includes("\\") || value.includes("\0") ||
      isAbsolute(value) || /^[A-Za-z]:/.test(value)) throw new Error("PATH_DENIED");
  if (allowRoot && (value === "." || value === "")) return "";
  const segments = value.split("/");
  if (!segments.length || segments.some(segment => !segment || segment === "." || segment === ".." || segment.includes(":"))) {
    throw new Error("PATH_DENIED");
  }
  return segments.join("/");
}

async function contained(root: string, path: string, allowRoot = false, writing = false): Promise<{ relativePath: string; absolutePath: string }> {
  const relativePath = checkedRelativePath(path, allowRoot);
  const canonicalRoot = await realpath(root);
  const absolutePath = resolve(canonicalRoot, ...relativePath.split("/").filter(Boolean));
  const inside = (candidate: string) => {
    const fromRoot = relative(canonicalRoot, candidate);
    return fromRoot !== ".." && !fromRoot.startsWith(`..${sep}`) && !isAbsolute(fromRoot);
  };
  if (!inside(absolutePath) || relative(canonicalRoot, absolutePath).split(/[\\/]/).includes(".git")) throw new Error("PATH_DENIED");

  let cursor = absolutePath;
  while (true) {
    try {
      if (!inside(await realpath(cursor))) throw new Error("PATH_DENIED");
      break;
    } catch (error) {
      if (!writing || (error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
      const parent = dirname(cursor);
      if (parent === cursor) throw new Error("PATH_DENIED");
      cursor = parent;
    }
  }
  return { relativePath, absolutePath };
}

function envelope(status: "success" | "warning" | "error", summary: string, data: Record<string, unknown>, artifacts: string[] = []) {
  return { status, summary, next_actions: [], artifacts, ...data };
}

/** Explicit tool conditions used by evaluation plans. No automatic dependency installation occurs. */
export function evaluationTools(root: string, profile: ToolProfile, options: WorkspaceToolOptions = {}): AgentTool[] {
  if (profile === "workspace-basic") return workspaceTools(root, options);
  if (profile === "doc-evidence") return docEvidenceTools(root);

  const base = workspaceTools(root, options);
  return [
    ...base,
    createPagedReadTool(root),
    createSearchFilesTool(root),
    ...(!options.readOnly ? [createExactEditTool(root)] : []),
  ];
}

function createPagedReadTool(root: string): AgentTool {
  const pageParameters = Type.Object({
    path: Type.String(),
    startLine: Type.Integer({ minimum: 1, maximum: 1_000_000 }),
    lineCount: Type.Integer({ minimum: 1, maximum: MAX_PAGE_LINES }),
  });
  const readPage: AgentTool<typeof pageParameters> = {
    name: "read_file_page", label: "Read file page",
    description: "Read a bounded, 1-based line range from a workspace file. Returns explicit truncation and next-line information.",
    parameters: pageParameters,
    async execute(_id, args) {
      const { absolutePath } = await contained(root, args.path);
      const content = await readFile(absolutePath, "utf8");
      if (Buffer.byteLength(content) > MAX_WORKSPACE_TEXT) throw new Error("FILE_TOO_LARGE");
      const lines = content.split(/\r?\n/);
      const start = args.startLine - 1;
      const selected = lines.slice(start, start + args.lineCount);
      const numbered = selected.map((line, index) => ({ line: start + index + 1, text: line }));
      const serialized = JSON.stringify(numbered);
      if (Buffer.byteLength(serialized) > MAX_PAGE_BYTES) throw new Error("PAGE_TOO_LARGE");
      const nextStartLine = start + selected.length < lines.length ? start + selected.length + 1 : null;
      return textResult(envelope(nextStartLine === null ? "success" : "warning", `Read ${selected.length} line(s) from ${args.path}.`, {
        path: args.path, startLine: args.startLine, lines: numbered, truncated: nextStartLine !== null, nextStartLine,
      }, [args.path]));
    },
  };
  return readPage;
}

function createSearchFilesTool(root: string): AgentTool {
  const searchParameters = Type.Object({
    pattern: Type.String({ minLength: 1, maxLength: MAX_SEARCH_PATTERN_CHARS }),
    glob: Type.Optional(Type.String({ maxLength: MAX_SEARCH_PATTERN_CHARS })),
  });
  const searchFiles: AgentTool<typeof searchParameters> = {
    name: "search_files", label: "Search files",
    description: "Search text files in the workspace using a literal, case-insensitive substring and an optional * path filter. Returns paths and 1-based line numbers.",
    parameters: searchParameters,
    async execute(_id, args) {
      const query = args.pattern.toLocaleLowerCase("en-US");
      const glob = args.glob === undefined ? null : globMatcher(args.glob);
      const matches: Array<{ path: string; line: number; text: string }> = [];
      let truncated = false;
      const visit = async (directory: string): Promise<void> => {
        const entries = await readdir(directory, { withFileTypes: true });
        entries.sort((left, right) => left.name < right.name ? -1 : left.name > right.name ? 1 : 0);
        for (const entry of entries) {
          if (entry.name === ".git" || entry.name === "node_modules") continue;
          const path = join(directory, entry.name);
          if (entry.isDirectory()) await visit(path);
          else if (entry.isFile()) {
            const relativePath = relative(root, path).split(sep).join("/");
            if (glob && !glob.test(relativePath)) continue;
            const info = await lstat(path);
            if (info.size > MAX_SEARCH_FILE_BYTES) continue;
            const body = (await readFile(path, "utf8")).split(/\r?\n/);
            for (let index = 0; index < body.length; index++) {
              if (body[index]!.toLocaleLowerCase("en-US").includes(query)) {
                matches.push({ path: relativePath, line: index + 1, text: body[index]!.slice(0, MAX_MATCH_PREVIEW_CHARS) });
                if (matches.length > MAX_SEARCH_RESULTS) { truncated = true; return; }
              }
            }
          }
          if (truncated) return;
        }
      };
      await visit(await realpath(root));
      const visibleMatches = matches.slice(0, MAX_SEARCH_RESULTS);
      const summary = truncated
        ? `Found more than ${MAX_SEARCH_RESULTS} matching line(s).`
        : `Found ${matches.length} matching line(s).`;
      return textResult(envelope(truncated ? "warning" : "success", summary, {
        pattern: args.pattern, glob: args.glob ?? null, matches: visibleMatches, truncated,
      }, [...new Set(visibleMatches.map(match => match.path))]));
    },
  };
  return searchFiles;
}

function createExactEditTool(root: string): AgentTool {
  const editParameters = Type.Object({ path: Type.String(), oldText: Type.String({ minLength: 1 }), newText: Type.String() });
  const editFile: AgentTool<typeof editParameters> = {
    name: "edit_file", label: "Edit file",
    description: "Replace one exact, unique text block in a workspace file. Fails without writing when the old text is absent or ambiguous.",
    parameters: editParameters,
    async execute(_id, args) {
      if (Buffer.byteLength(args.oldText) > MAX_WORKSPACE_TEXT || Buffer.byteLength(args.newText) > MAX_WORKSPACE_TEXT) throw new Error("FILE_TOO_LARGE");
      const { absolutePath } = await contained(root, args.path, false, true);
      const original = await readFile(absolutePath, "utf8");
      const first = original.indexOf(args.oldText);
      if (first < 0) throw new Error("EDIT_TEXT_NOT_FOUND");
      if (original.indexOf(args.oldText, first + args.oldText.length) >= 0) throw new Error("EDIT_TEXT_AMBIGUOUS");
      await writeFile(absolutePath, original.slice(0, first) + args.newText + original.slice(first + args.oldText.length), "utf8");
      return textResult(envelope("success", `Applied one exact edit to ${args.path}.`, { path: args.path, replacements: 1 }, [args.path]));
    },
  };
  return editFile;
}

function globMatcher(glob: string): RegExp {
  const escaped = glob.replace(/[|\\{}()[\]^$+?.]/g, "\\$&").replace(/\*/g, ".*");
  return new RegExp(`^${escaped}$`);
}

/** Read-only 0-based character paging adapter for the synthetic tool-001 document set. */
export function docEvidenceTools(root: string): AgentTool[] {
  const listParameters = Type.Object({ path: Type.Optional(Type.String()) });
  const list: AgentTool<typeof listParameters> = {
    name: "list", label: "List evidence files",
    description: "List a directory in the read-only evidence snapshot. Paths are relative; the default is the snapshot root.",
    parameters: listParameters,
    async execute(_id, args) {
      const path = args.path ?? ".";
      try {
        const { absolutePath } = await contained(root, path, true);
        const info = await lstat(absolutePath);
        if (!info.isDirectory()) return textResult({ ok: false, error: "not_found" });
        const entries = [];
        for (const entry of await readdir(absolutePath, { withFileTypes: true })) {
          entries.push({ name: entry.name, type: entry.isDirectory() ? "dir" : "file" });
        }
        entries.sort((left, right) => left.name < right.name ? -1 : left.name > right.name ? 1 : 0);
        return textResult({ ok: true, entries });
      } catch (error) {
        if (error instanceof Error && error.message === "PATH_DENIED") return textResult({ ok: false, error: "not_found" });
        if ((error as NodeJS.ErrnoException).code === "ENOENT") return textResult({ ok: false, error: "not_found" });
        throw error;
      }
    },
  };

  const readParameters = Type.Object({ path: Type.String(), offset: Type.Integer({ minimum: 0 }), limit: Type.Integer({ minimum: 1, maximum: 10_000 }) });
  const read: AgentTool<typeof readParameters> = {
    name: "read", label: "Read evidence page",
    description: "Read a read-only snapshot file using 0-based character offsets. At most 400 Unicode characters are returned; use next_offset when truncated.",
    parameters: readParameters,
    async execute(_id, args) {
      if (!Number.isSafeInteger(args.offset) || !Number.isSafeInteger(args.limit) || args.offset < 0 || args.limit < 1) return textResult({ ok: false, error: "invalid_range" });
      const relativePath = checkedRelativePath(args.path);
      if (relativePath === "secrets" || relativePath.startsWith("secrets/")) return textResult({ ok: false, error: "permission_denied" });
      try {
        const { absolutePath } = await contained(root, relativePath);
        const info = await lstat(absolutePath);
        if (!info.isFile()) return textResult({ ok: false, error: "not_found" });
        const data = await readFile(absolutePath, "utf8");
        const chars = Array.from(data);
        const content = chars.slice(args.offset, args.offset + Math.min(args.limit, DOC_READ_LIMIT)).join("");
        const nextOffset = args.offset + Array.from(content).length;
        return textResult({ ok: true, content, truncated: nextOffset < chars.length, next_offset: nextOffset, size: chars.length });
      } catch (error) {
        if (error instanceof Error && error.message === "PATH_DENIED") return textResult({ ok: false, error: "not_found" });
        if ((error as NodeJS.ErrnoException).code === "ENOENT") return textResult({ ok: false, error: "not_found" });
        throw error;
      }
    },
  };

  const searchParameters = Type.Object({
    pattern: Type.String({ minLength: 1, maxLength: MAX_SEARCH_PATTERN_CHARS }),
    glob: Type.Optional(Type.String({ maxLength: MAX_SEARCH_PATTERN_CHARS })),
  });
  const search: AgentTool<typeof searchParameters> = {
    name: "search", label: "Search evidence",
    description: "Search text in the read-only snapshot with a regular expression and an optional * path filter. Results include path and 1-based line number.",
    parameters: searchParameters,
    async execute(_id, args) {
      let expression: RegExp;
      try {
        if (/\([^)]*[+*][^)]*\)[+*{]|\\[1-9]|\(\?<([=!])/.test(args.pattern)) throw new Error("UNSAFE_PATTERN");
        expression = new RegExp(args.pattern);
      } catch {
        return textResult({ ok: false, error: "bad_pattern" });
      }
      const matcher = args.glob === undefined ? null : globMatcher(args.glob);
      const matches: Array<{ path: string; line: number; text: string }> = [];
      let truncated = false;
      const visit = async (directory: string): Promise<void> => {
        const entries = await readdir(directory, { withFileTypes: true });
        entries.sort((left, right) => left.name < right.name ? -1 : left.name > right.name ? 1 : 0);
        for (const entry of entries) {
          const path = join(directory, entry.name);
          if (entry.isDirectory()) await visit(path);
          else if (entry.isFile()) {
            const relativePath = relative(root, path).split(sep).join("/");
            if (relativePath === "secrets" || relativePath.startsWith("secrets/") || (matcher && !matcher.test(relativePath))) continue;
            const info = await lstat(path);
            if (info.size > MAX_SEARCH_FILE_BYTES) continue;
            const lines = (await readFile(path, "utf8")).split(/\r?\n/);
            for (let index = 0; index < lines.length; index++) {
              expression.lastIndex = 0;
              if (expression.test(lines[index]!)) {
                matches.push({ path: relativePath, line: index + 1, text: lines[index]!.replace(/\r$/, "").slice(0, MAX_MATCH_PREVIEW_CHARS) });
                if (matches.length > MAX_SEARCH_RESULTS) { truncated = true; return; }
              }
            }
          }
          if (truncated) return;
        }
      };
      await visit(await realpath(root));
      matches.sort((left, right) => left.path < right.path ? -1 : left.path > right.path ? 1 : left.line - right.line);
      return textResult({ ok: true, matches: matches.slice(0, MAX_SEARCH_RESULTS), truncated });
    },
  };
  return [list, read, search];
}
