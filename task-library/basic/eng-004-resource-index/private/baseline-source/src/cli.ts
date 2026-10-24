import { readFile } from "node:fs/promises";
import { stdin } from "node:process";
import { parseCatalog } from "./catalog.ts";
import { toCsv, toJson } from "./export.ts";
import { buildIndex } from "./index.ts";
import type { Resource } from "./types.ts";

function option(args: string[], name: string, fallback?: string): string | undefined {
  const position = args.indexOf(name);
  if (position === -1) return fallback;
  const value = args[position + 1];
  if (!value || value.startsWith("--")) throw new Error("OPTION_VALUE_REQUIRED");
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
  throw new Error("UNKNOWN_COMMAND");
}

main(process.argv.slice(2)).catch(error => {
  const message = error instanceof Error && /^[A-Z][A-Z0-9_]{1,79}$/.test(error.message) ? error.message : "INPUT_OR_IO_ERROR";
  process.stderr.write(`${message}\n`);
  process.exitCode = 2;
});
