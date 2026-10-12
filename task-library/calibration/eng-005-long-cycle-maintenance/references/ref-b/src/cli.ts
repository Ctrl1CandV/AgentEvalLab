import { AppError, invalid } from "./errors.ts";
import { addDependency, createOrder, exportOrders, listOrders, showOrder, updateOrder } from "./service.ts";
import type { WorkOrderStatus } from "./types.ts";

type Handler = (args: string[]) => Promise<unknown>;

function options(args: string[], allowed: string[]): Map<string, string> {
  const values = new Map<string, string>();
  for (let i = 0; i < args.length; i += 2) {
    const name = args[i];
    const value = args[i + 1];
    if (!name?.startsWith("--") || !allowed.includes(name) || !value || values.has(name)) invalid("Invalid or repeated option.");
    values.set(name, value);
  }
  return values;
}

function positive(value: string | undefined, fallback: number, ceiling: number): number {
  if (value === undefined) return fallback;
  if (!/^[1-9]\d*$/.test(value)) invalid("Expected a positive integer.");
  const number = Number(value);
  if (!Number.isSafeInteger(number) || number > ceiling) invalid("Integer option is outside its allowed range.");
  return number;
}

const commands = new Map<string, Handler>();

commands.set("list", async args => {
  const values = options(args, ["--status", "--sort", "--order", "--page", "--page-size"]);
  const status = values.get("--status");
  const sort = values.get("--sort") ?? "createdAt";
  const order = values.get("--order") ?? "asc";
  if (status !== undefined && !["OPEN", "IN_PROGRESS", "DONE"].includes(status)) invalid("Unknown status filter.");
  if (!["createdAt", "title", "id"].includes(sort) || !["asc", "desc"].includes(order)) invalid("Unknown sort option.");
  return listOrders({ status: status as WorkOrderStatus | undefined, sort: sort as "createdAt" | "title" | "id",
    order: order as "asc" | "desc", page: positive(values.get("--page"), 1, Number.MAX_SAFE_INTEGER),
    pageSize: positive(values.get("--page-size"), 2, 100) });
});
commands.set("show", async args => {
  if (args.length !== 1 || !args[0]) invalid("Expected one work-order ID.");
  return showOrder(args[0]!);
});
commands.set("create", async args => {
  if (args.length !== 2 || !args[0] || !args[1]) invalid("Expected an ID and title.");
  return createOrder(args[0], args[1]);
});
commands.set("update", async args => {
  const id = args[0];
  if (!id) invalid("Expected a work-order ID.");
  const values = options(args.slice(1), ["--status", "--title", "--description"]);
  if (values.size === 0) invalid("At least one update field is required.");
  return updateOrder(id, { status: values.get("--status"), title: values.get("--title"), description: values.get("--description") });
});
commands.set("depends", async args => {
  if (args.length !== 3 || args[0] !== "add" || !args[1] || !args[2]) invalid("Usage: depends add <ID> <PREREQUISITE-ID>.");
  return addDependency(args[1]!, args[2]!);
});
commands.set("export", async args => {
  if (args.length > 1 || (args[0] !== undefined && args[0] !== "json")) invalid("Only JSON export is supported.");
  return exportOrders();
});

async function dispatch(argv: string[]): Promise<void> {
  const [name, ...args] = argv;
  const handler = commands.get(name ?? "");
  if (!handler) throw new AppError("UNKNOWN_COMMAND", "Unknown or incomplete command.");
  const output = await handler(args);
  console.log(typeof output === "string" ? output : JSON.stringify(output));
}

dispatch(process.argv.slice(2)).catch(error => {
  const normalized = error instanceof AppError ? error : new AppError("STORE_INVALID", "The command could not be completed.");
  console.log(JSON.stringify({ ok: false, error: { code: normalized.code, message: normalized.message } }));
  process.exitCode = 2;
});
