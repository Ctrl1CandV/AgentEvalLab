import { readFile } from "node:fs/promises";
import { stdin } from "node:process";
import { parseCatalog } from "./catalog.ts";
import { toCsv, toJson } from "./export.ts";
import { buildIndex } from "./index.ts";
import { searchResources } from "./search.ts";
import type { Resource } from "./types.ts";

function option(args: string[], name: string, fallback?: string): string | undefined {
  const found: number[] = [];
  args.forEach((value, index) => { if (value === name) found.push(index); });
  if (found.length > 1) throw new Error("DUPLICATE_OPTION");
  if (found.length === 0) return fallback;
  const value = args[found[0]! + 1];
  if (value === undefined || value.startsWith("--")) throw new Error("OPTION_VALUE_REQUIRED");
  return value;
}

function checkOptionSet(args: string[]): void {
  const accepted = new Set(["--input", "--query", "--offset", "--limit"]);
  const seen = new Set<string>();
  for (let i = 0; i < args.length;) {
    const name = args[i]!;
    if (!accepted.has(name)) throw new Error("UNKNOWN_OPTION");
    if (seen.has(name)) throw new Error("DUPLICATE_OPTION");
    seen.add(name);
    if (!args[i + 1] || args[i + 1]!.startsWith("--")) throw new Error("OPTION_VALUE_REQUIRED");
    i += 2;
  }
}

function readInteger(args: string[], name: string, defaultValue: number, allowZero: boolean): number {
  const text = option(args, name, String(defaultValue))!;
  const parsed = Number(text);
  if (!/^(0|[1-9]\d*)$/.test(text) || !Number.isSafeInteger(parsed) || (allowZero ? parsed < 0 : parsed <= 0)) {
    throw new Error("INVALID_INTEGER");
  }
  return parsed;
}

async function stdinText(): Promise<string> {
  const parts: Buffer[] = [];
  for await (const part of stdin) parts.push(Buffer.from(part));
  return Buffer.concat(parts).toString("utf8");
}

async function resourcesFrom(args: string[]): Promise<Resource[]> {
  const input = option(args, "--input");
  if (!input) throw new Error("INPUT_REQUIRED");
  const text = input === "-" ? await stdinText() : await readFile(input, "utf8");
  return parseCatalog(JSON.parse(text)).resources;
}

async function main(argv: string[]): Promise<void> {
  const command = argv[0];
  const args = argv.slice(1);
  switch (command) {
    case "index":
      process.stdout.write(toJson(buildIndex(await resourcesFrom(args))));
      return;
    case "export": {
      const format = option(args, "--format", "json");
      const data = buildIndex(await resourcesFrom(args));
      if (format === "csv") process.stdout.write(toCsv(data));
      else if (format === "json") process.stdout.write(toJson(data));
      else throw new Error("INVALID_FORMAT");
      return;
    }
    case "search": {
      checkOptionSet(args);
      const query = option(args, "--query");
      if (query === undefined || query.trim().length === 0) throw new Error("QUERY_REQUIRED");
      const result = searchResources(await resourcesFrom(args), query, readInteger(args, "--offset", 0, true), readInteger(args, "--limit", 20, false));
      process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
      return;
    }
    default:
      throw new Error("UNKNOWN_COMMAND");
  }
}

main(process.argv.slice(2)).catch(error => {
  const code = error instanceof Error && /^[A-Z][A-Z0-9_]{1,79}$/.test(error.message) ? error.message : "INPUT_OR_IO_ERROR";
  process.stderr.write(`${code}\n`);
  process.exitCode = 2;
});
