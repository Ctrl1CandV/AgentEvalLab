import { AppError, invalid } from "./errors.ts";
import { findOrder, readStore, saveMutation } from "./store.ts";
import type { Store, WorkOrder, WorkOrderStatus } from "./types.ts";
import type { ListPage, ListQuery } from "./service-types.ts";

class WorkOrderService {
  async list(query: ListQuery): Promise<ListPage> {
    const { workOrders } = await readStore();
    const rows = workOrders.filter(order => !query.status || order.status === query.status);
    const value = (row: WorkOrder): string => row[query.sort];
    rows.sort((left, right) => {
      const a = value(left);
      const b = value(right);
      const primary = a === b ? 0 : a < b ? -1 : 1;
      const ordered = query.order === "asc" ? primary : -primary;
      return ordered || left.id.localeCompare(right.id, "en");
    });
    const total = rows.length;
    const offset = (query.page - 1) * query.pageSize;
    return { total, page: query.page, pageSize: query.pageSize, pages: Math.ceil(total / query.pageSize),
      items: rows.slice(offset, offset + query.pageSize) };
  }

  async show(id: string): Promise<WorkOrder> {
    return findOrder(await readStore(), id);
  }

  async update(id: string, changes: { status?: string; title?: string; description?: string }): Promise<WorkOrder> {
    const store = await readStore();
    const original = findOrder(store, id);
    const nextStatus = changes.status;
    if (nextStatus !== undefined) {
      if (!["OPEN", "IN_PROGRESS", "DONE"].includes(nextStatus)) invalid("Unknown work-order status.");
      const target = nextStatus as WorkOrderStatus;
      const progression: Record<WorkOrderStatus, WorkOrderStatus | null> = { OPEN: "IN_PROGRESS", IN_PROGRESS: "DONE", DONE: null };
      if (target !== original.status && progression[original.status] !== target) {
        throw new AppError("INVALID_STATUS_TRANSITION", "Status can only advance OPEN → IN_PROGRESS → DONE.");
      }
      const statusOf = new Map(store.workOrders.map(row => [row.id, row.status]));
      if (target === "DONE" && (original.dependsOn ?? []).some(prerequisite => statusOf.get(prerequisite) !== "DONE")) {
        throw new AppError("DEPENDENCY_NOT_COMPLETE", "Every prerequisite must be DONE first.");
      }
    }
    const updated = { ...original,
      ...(changes.status !== undefined ? { status: changes.status as WorkOrderStatus } : {}),
      ...(changes.title !== undefined ? { title: changes.title } : {}),
      ...(changes.description !== undefined ? { description: changes.description } : {}),
    };
    store.workOrders = store.workOrders.map(row => row.id === id ? updated : row);
    await saveMutation(store, "updated", id);
    return updated;
  }

  async create(id: string, title: string): Promise<WorkOrder> {
    const store = await readStore();
    if (store.workOrders.some(row => row.id === id)) throw new AppError("DUPLICATE_ID", "Work-order ID already exists.");
    const created: WorkOrder = { id, title, status: "OPEN", createdAt: new Date().toISOString(), description: "", dependsOn: [] };
    store.workOrders = [...store.workOrders, created];
    await saveMutation(store, "created", id);
    return created;
  }

  async addDependency(id: string, prerequisiteId: string): Promise<WorkOrder> {
    const store = await readStore();
    const original = findOrder(store, id);
    findOrder(store, prerequisiteId);
    if (id === prerequisiteId) throw new AppError("SELF_DEPENDENCY", "A work order cannot depend on itself.");
    if (original.dependsOn?.includes(prerequisiteId)) invalid("That dependency already exists.");
    if (this.hasPath(store, prerequisiteId, id)) throw new AppError("DEPENDENCY_CYCLE", "The dependency would create a cycle.");
    const updated = { ...original, dependsOn: [...(original.dependsOn ?? []), prerequisiteId] };
    store.workOrders = store.workOrders.map(row => row.id === id ? updated : row);
    await saveMutation(store, "dependency_added", id);
    return updated;
  }

  /** Breadth-first search over dependsOn edges, each order visited once. */
  private hasPath(store: Store, from: string, target: string): boolean {
    const edges = new Map(store.workOrders.map(row => [row.id, row.dependsOn ?? []]));
    const visited = new Set<string>([from]);
    let frontier = [from];
    while (frontier.length) {
      if (frontier.includes(target)) return true;
      const next: string[] = [];
      for (const id of frontier) {
        for (const prerequisite of edges.get(id) ?? []) {
          if (!visited.has(prerequisite)) {
            visited.add(prerequisite);
            next.push(prerequisite);
          }
        }
      }
      frontier = next;
    }
    return false;
  }

  async exportJSON(): Promise<string> {
    return JSON.stringify((await readStore()).workOrders, null, 2);
  }
}

const workOrders = new WorkOrderService();
export const listOrders = (query: ListQuery) => workOrders.list(query);
export const showOrder = (id: string) => workOrders.show(id);
export const updateOrder = (id: string, changes: { status?: string; title?: string; description?: string }) => workOrders.update(id, changes);
export const createOrder = (id: string, title: string) => workOrders.create(id, title);
export const addDependency = (id: string, prerequisiteId: string) => workOrders.addDependency(id, prerequisiteId);
export const exportOrders = () => workOrders.exportJSON();
