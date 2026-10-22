import { AppError, invalid } from "./errors.ts";
import { findOrder, readStore, saveMutation } from "./store.ts";
import type { WorkOrder, WorkOrderStatus } from "./types.ts";

export interface ListQuery {
  status?: WorkOrderStatus;
  sort: "createdAt" | "title" | "id";
  order: "asc" | "desc";
  page: number;
  pageSize: number;
}

export interface ListPage {
  total: number;
  page: number;
  pageSize: number;
  pages: number;
  items: WorkOrder[];
}

export async function listOrders(query: ListQuery): Promise<ListPage> {
  const store = await readStore();
  const selected = store.workOrders.filter(item => query.status === undefined || item.status === query.status);
  selected.sort((left, right) => {
    const a = left[query.sort];
    const b = right[query.sort];
    let comparison = a < b ? -1 : a > b ? 1 : 0;
    if (query.order === "desc") comparison *= -1;
    return comparison || (left.id < right.id ? -1 : left.id > right.id ? 1 : 0);
  });
  const total = selected.length;
  const start = (query.page - 1) * query.pageSize;
  return { total, page: query.page, pageSize: query.pageSize, pages: Math.ceil(total / query.pageSize),
    items: selected.slice(start, start + query.pageSize) };
}

export async function showOrder(id: string): Promise<WorkOrder> {
  return findOrder(await readStore(), id);
}

export async function updateOrder(id: string, updates: { status?: string; title?: string; description?: string }): Promise<WorkOrder> {
  const store = await readStore();
  const order = findOrder(store, id);
  if (updates.status !== undefined) {
    if (!["OPEN", "IN_PROGRESS", "DONE"].includes(updates.status)) invalid("Unknown work-order status.");
    const next = updates.status as WorkOrderStatus;
    const allowed: Record<WorkOrderStatus, WorkOrderStatus[]> = { OPEN: ["IN_PROGRESS"], IN_PROGRESS: ["DONE"], DONE: [] };
    if (next !== order.status && !allowed[order.status].includes(next)) {
      throw new AppError("INVALID_STATUS_TRANSITION", "Status can only advance OPEN → IN_PROGRESS → DONE.");
    }
    if (next === "DONE") {
      const dependencies = order.dependsOn ?? [];
      const byId = index(store);
      if (dependencies.some(id => byId.get(id)?.status !== "DONE")) {
        throw new AppError("DEPENDENCY_NOT_COMPLETE", "Every prerequisite must be DONE first.");
      }
    }
    order.status = next;
  }
  if (updates.title !== undefined) order.title = updates.title;
  if (updates.description !== undefined) order.description = updates.description;
  await saveMutation(store, "updated", id);
  return order;
}

export async function createOrder(id: string, title: string): Promise<WorkOrder> {
  const store = await readStore();
  if (store.workOrders.some(order => order.id === id)) throw new AppError("DUPLICATE_ID", "Work-order ID already exists.");
  const order: WorkOrder = { id, title, status: "OPEN", createdAt: new Date().toISOString(), description: "", dependsOn: [] };
  store.workOrders.push(order);
  await saveMutation(store, "created", id);
  return order;
}

function index(store: Awaited<ReturnType<typeof readStore>>): Map<string, WorkOrder> {
  return new Map(store.workOrders.map(order => [order.id, order]));
}

/** Whether targetId is reachable from startId through dependsOn: an iterative search that visits each order once. */
function reaches(store: Awaited<ReturnType<typeof readStore>>, startId: string, targetId: string): boolean {
  const byId = index(store);
  const seen = new Set<string>([startId]);
  const pending = [startId];
  while (pending.length) {
    const currentId = pending.pop()!;
    if (currentId === targetId) return true;
    for (const next of byId.get(currentId)?.dependsOn ?? []) {
      if (!seen.has(next)) {
        seen.add(next);
        pending.push(next);
      }
    }
  }
  return false;
}

export async function addDependency(id: string, prerequisiteId: string): Promise<WorkOrder> {
  const store = await readStore();
  const order = findOrder(store, id);
  findOrder(store, prerequisiteId);
  if (id === prerequisiteId) throw new AppError("SELF_DEPENDENCY", "A work order cannot depend on itself.");
  if (order.dependsOn?.includes(prerequisiteId)) invalid("That dependency already exists.");
  if (reaches(store, prerequisiteId, id)) throw new AppError("DEPENDENCY_CYCLE", "The dependency would create a cycle.");
  order.dependsOn = [...(order.dependsOn ?? []), prerequisiteId];
  await saveMutation(store, "dependency_added", id);
  return order;
}

export async function exportOrders(): Promise<string> {
  return JSON.stringify((await readStore()).workOrders, null, 2);
}
