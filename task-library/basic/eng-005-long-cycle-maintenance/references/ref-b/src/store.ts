import { readFile, rename, rm, writeFile } from "node:fs/promises";
import { randomUUID } from "node:crypto";
import { join } from "node:path";
import { AppError } from "./errors.ts";
import type { Store, StoreV1, StoreV2, WorkOrder, WorkOrderEvent } from "./types.ts";

export const STORE_PATH = join(process.cwd(), "data", "work-orders.json");

export async function readStore(): Promise<Store> {
  try {
    const value: unknown = JSON.parse(await readFile(STORE_PATH, "utf8"));
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("shape");
    const store = value as Partial<Store>;
    if ((store.version !== 1 && store.version !== 2) || !Array.isArray(store.workOrders) ||
        !store.workOrders.every(isWorkOrder) || (store.version === 2 && (!Array.isArray(store.events) || !store.events.every(isEvent)))) {
      throw new Error("shape");
    }
    return store as Store;
  } catch {
    throw new AppError("STORE_INVALID", "The work-order store is missing or invalid.");
  }
}

function isWorkOrder(value: unknown): value is WorkOrder {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const order = value as Record<string, unknown>;
  return typeof order.id === "string" && typeof order.title === "string" &&
    ["OPEN", "IN_PROGRESS", "DONE"].includes(String(order.status)) && typeof order.createdAt === "string" &&
    typeof order.description === "string" && (order.dependsOn === undefined ||
      (Array.isArray(order.dependsOn) && order.dependsOn.every(item => typeof item === "string")));
}

function isEvent(value: unknown): value is WorkOrderEvent {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const event = value as Record<string, unknown>;
  return Number.isSafeInteger(event.sequence) && typeof event.type === "string" &&
    (event.orderId === null || typeof event.orderId === "string") && typeof event.at === "string";
}

function appendEvent(store: StoreV2, type: string, orderId: string | null): void {
  store.events.push({ sequence: store.events.length + 1, type, orderId, at: new Date().toISOString() });
}

function forWrite(store: Store): StoreV2 {
  // Rejected operations never save, so a version 2 store is written as it is, without a copy.
  if (store.version === 2) return store;
  const migrated: StoreV2 = {
    version: 2,
    workOrders: store.workOrders.map(order => ({ ...order, dependsOn: [...(order.dependsOn ?? [])] })),
    events: [],
  };
  appendEvent(migrated, "state_migrated", null);
  return migrated;
}

/** Every successful mutation is one atomic replacement; rejected operations never call this. */
export async function saveMutation(store: Store, type: string, orderId: string | null): Promise<void> {
  const next = forWrite(store);
  appendEvent(next, type, orderId);
  const temporaryPath = `${STORE_PATH}.${randomUUID()}.tmp`;
  try {
    await writeFile(temporaryPath, `${JSON.stringify(next, null, 2)}\n`, { encoding: "utf8", flag: "wx" });
    await rename(temporaryPath, STORE_PATH);
  } catch {
    await rm(temporaryPath, { force: true }).catch(() => undefined);
    throw new AppError("STORE_INVALID", "The work-order store could not be saved.");
  }
}

export function asV1(store: Store): StoreV1 {
  if (store.version !== 1) throw new Error("unsupported store version");
  return store;
}

export function findOrder(store: Store, id: string): WorkOrder {
  const order = store.workOrders.find(candidate => candidate.id === id);
  if (!order) throw new AppError("NOT_FOUND", "Work order was not found.");
  return order;
}
