import { readFile } from "node:fs/promises";
import { stdin } from "node:process";
import { parseCatalog } from "./catalog.ts";
import { toCsv, toJson } from "./export.ts";
import { buildIndex } from "./index.ts";
import { searchResources } from "./search.ts";
import type { Resource } from "./types.ts";

function option(args: string[], name: string, fallback?: string): string | undefined {
  const positions = args.flatMap((value, index) => value === name ? [index] : []);
  if (positions.length > 1) throw new Error("DUPLICATE_OPTION");
  if (!positions.length) return fallback;
  const value = args[positions[0]! + 1];
  if (!value || value.startsWith("--")) throw new Error("OPTION_VALUE_REQUIRED");
  return value;
}

function strictOptions(args: string[], allowed: string[]): void {
  const seen = new Set<string>();
  for (let i = 0; i < args.length;) {
    const name = args[i]!;
    if (!allowed.includes(name)) throw new Error("UNKNOWN_OPTION");
    if (seen.has(name)) throw new Error("DUPLICATE_OPTION");
    seen.add(name);
    const value = args[i + 1];
    if (!value || value.startsWith("--")) throw new Error("OPTION_VALUE_REQUIRED");
    i += 2;
  }
}

function integerOption(args: string[], name: string, fallback: number, minimum: number): number {
  const raw = option(args, name, String(fallback))!;
  if (!/^(0|[1-9]\d*)$/.test(raw)) throw new Error("INVALID_INTEGER");
  const value = Number(raw);
  if (!Number.isSafeInteger(value) || value < minimum) throw new Error("INVALID_INTEGER");
  return value;
}

async function readStdin(): Promise<string> {
  const chunks: Buffer[] = [];
  for await (const chunk of stdin) chunks.push(Buffer.from(chunk));
  return Buffer.concat(chunks).toString("utf8");
}

async function loadResources(args: string[]): Promise<Resource[]> {
  const path = option(args, "--input");
  if (!path) throw new Error("INPUT_REQUIRED");
  const source = path === "-" ? await readStdin() : await readFile(path, "utf8");
  return parseCatalog(JSON.parse(source)).resources;
}

async function main(argv: string[]): Promise<void> {
  const [command, ...args] = argv;
  if (command === "index") {
    process.stdout.write(toJson(buildIndex(await loadResources(args))));
    return;
  }
  if (command === "export") {
    const resources = buildIndex(await loadResources(args));
    const format = option(args, "--format", "json");
    if (format === "json") process.stdout.write(toJson(resources));
    else if (format === "csv") process.stdout.write(toCsv(resources));
    else throw new Error("INVALID_FORMAT");
    return;
  }
  if (command === "search") {
    strictOptions(args, ["--input", "--query", "--offset", "--limit"]);
    const query = option(args, "--query");
    if (!query?.trim()) throw new Error("QUERY_REQUIRED");
    const offset = integerOption(args, "--offset", 0, 0);
    const limit = integerOption(args, "--limit", 20, 1);
    const result = searchResources(await loadResources(args), query, offset, limit);
    process.stdout.write(JSON.stringify(result, null, 2) + "\n");
    return;
  }
  throw new Error("UNKNOWN_COMMAND");
}

main(process.argv.slice(2)).catch(error => {
  const message = error instanceof Error && /^[A-Z][A-Z0-9_]{1,79}$/.test(error.message) ? error.message : "INPUT_OR_IO_ERROR";
  process.stderr.write(`${message}\n`);
  process.exitCode = 2;
});
