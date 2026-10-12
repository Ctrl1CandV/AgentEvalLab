import { AppError, invalid } from "./errors.ts";
import { addDependency, createOrder, exportOrders, listOrders, showOrder, updateOrder } from "./service.ts";
import type { WorkOrderStatus } from "./types.ts";

function options(args: string[], allowed: string[]): Map<string, string> {
  const result = new Map<string, string>();
  for (let index = 0; index < args.length; index += 2) {
    const key = args[index];
    const value = args[index + 1];
    if (!key?.startsWith("--") || !allowed.includes(key) || !value || result.has(key)) invalid("Invalid or repeated option.");
    result.set(key, value);
  }
  return result;
}

function positiveInteger(value: string | undefined, fallback: number, maximum: number): number {
  if (value === undefined) return fallback;
  if (!/^[1-9]\d*$/.test(value)) invalid("Expected a positive integer.");
  const number = Number(value);
  if (!Number.isSafeInteger(number) || number > maximum) invalid("Integer option is outside its allowed range.");
  return number;
}

async function main(args: string[]): Promise<void> {
  const [command, ...rest] = args;
  if (command === "list") {
    const parsed = options(rest, ["--status", "--sort", "--order", "--page", "--page-size"]);
    const status = parsed.get("--status");
    if (status !== undefined && !["OPEN", "IN_PROGRESS", "DONE"].includes(status)) invalid("Unknown status filter.");
    const sort = parsed.get("--sort") ?? "createdAt";
    const order = parsed.get("--order") ?? "asc";
    if (!["createdAt", "title", "id"].includes(sort) || !["asc", "desc"].includes(order)) invalid("Unknown sort option.");
    console.log(JSON.stringify(await listOrders({ status: status as WorkOrderStatus | undefined, sort: sort as "createdAt" | "title" | "id",
      order: order as "asc" | "desc", page: positiveInteger(parsed.get("--page"), 1, Number.MAX_SAFE_INTEGER),
      pageSize: positiveInteger(parsed.get("--page-size"), 2, 100) })));
    return;
  }
  if (command === "show" && rest[0]) {
    console.log(JSON.stringify(await showOrder(rest[0])));
    return;
  }
  if (command === "create" && rest[0] && rest[1]) {
    console.log(JSON.stringify(await createOrder(rest[0], rest[1])));
    return;
  }
  if (command === "update" && rest[0]) {
    const parsed = options(rest.slice(1), ["--status", "--title", "--description"]);
    if (parsed.size === 0) invalid("At least one update field is required.");
    const status = parsed.get("--status");
    const title = parsed.get("--title");
    const description = parsed.get("--description");
    console.log(JSON.stringify(await updateOrder(rest[0], { status, title, description })));
    return;
  }
  if (command === "depends" && rest[0] === "add" && rest[1] && rest[2] && rest.length === 3) {
    console.log(JSON.stringify(await addDependency(rest[1], rest[2])));
    return;
  }
  if (command === "export" && (rest[0] === "json" || rest[0] === undefined)) {
    console.log(await exportOrders());
    return;
  }
  throw new AppError("UNKNOWN_COMMAND", "Unknown or incomplete command.");
}

main(process.argv.slice(2)).catch(error => {
  const normalized = error instanceof AppError ? error : new AppError("STORE_INVALID", "The command could not be completed.");
  console.log(JSON.stringify({ ok: false, error: { code: normalized.code, message: normalized.message } }));
  process.exitCode = 2;
});
