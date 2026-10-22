import { AppError } from "./errors.ts";
import { readStore } from "./store.ts";
import type { WorkOrder } from "./types.ts";

interface Job { id: string; hours: number; priority: number; before: string[] }
interface Row { id: string; crew: number; start: number; end: number }

/** A binary heap ordered by `less`. */
class Heap<T> {
  items: T[] = [];
  less: (a: T, b: T) => boolean;
  constructor(less: (a: T, b: T) => boolean) { this.less = less; }
  get size(): number { return this.items.length; }
  peek(): T | undefined { return this.items[0]; }
  push(item: T): void {
    const items = this.items;
    items.push(item);
    let index = items.length - 1;
    while (index > 0) {
      const parent = (index - 1) >> 1;
      if (!this.less(items[index]!, items[parent]!)) break;
      [items[index], items[parent]] = [items[parent]!, items[index]!];
      index = parent;
    }
  }
  pop(): T | undefined {
    const items = this.items;
    const top = items[0];
    const last = items.pop();
    if (items.length && last !== undefined) {
      items[0] = last;
      let index = 0;
      for (;;) {
        const left = 2 * index + 1, right = left + 1;
        let smallest = index;
        if (left < items.length && this.less(items[left]!, items[smallest]!)) smallest = left;
        if (right < items.length && this.less(items[right]!, items[smallest]!)) smallest = right;
        if (smallest === index) break;
        [items[index], items[smallest]] = [items[smallest]!, items[index]!];
        index = smallest;
      }
    }
    return top;
  }
}

function jobsOf(orders: WorkOrder[]): Map<string, Job> {
  const status = new Map(orders.map(order => [order.id, order.status]));
  const jobs = new Map<string, Job>();
  for (const order of orders) {
    const { hours = 1, priority = 1 } = order as WorkOrder & { hours?: unknown; priority?: unknown };
    if (!Number.isSafeInteger(hours) || (hours as number) < 1 || !Number.isSafeInteger(priority) || (priority as number) < 1 || (priority as number) > 5) {
      throw new AppError("STORE_INVALID", "A work order has invalid hours or priority.");
    }
    if (order.status === "DONE") continue;
    jobs.set(order.id, { id: order.id, hours: hours as number, priority: priority as number,
      before: (order.dependsOn ?? []).filter(id => status.get(id) !== "DONE") });
  }
  return jobs;
}

/** Whenever a crew is free, the ready order with the highest priority per hour starts on it (ties by id). */
function greedy(jobs: Map<string, Job>, crews: number): Row[] {
  const waiting = new Map<string, number>();
  const dependents = new Map<string, string[]>();
  for (const job of jobs.values()) {
    waiting.set(job.id, job.before.length);
    for (const other of job.before) dependents.set(other, [...(dependents.get(other) ?? []), job.id]);
  }
  const ratio = (id: string) => jobs.get(id)!.priority / jobs.get(id)!.hours;
  const ready = new Heap<string>((a, b) => ratio(a) > ratio(b) || (ratio(a) === ratio(b) && a < b));
  for (const [id, count] of waiting) if (count === 0) ready.push(id);
  const free = new Heap<number>((a, b) => a < b);
  for (let crew = 1; crew <= crews; crew++) free.push(crew);
  const running = new Heap<[number, number, string]>((a, b) => a[0] < b[0] || (a[0] === b[0] && a[1] < b[1]));
  const rows: Row[] = [];
  let now = 0;
  while (ready.size || running.size) {
    while (free.size && ready.size) {
      const id = ready.pop()!;
      const crew = free.pop()!;
      const end = now + jobs.get(id)!.hours;
      rows.push({ id, crew, start: now, end });
      running.push([end, crew, id]);
    }
    if (!running.size) break;
    now = running.peek()![0];
    while (running.size && running.peek()![0] === now) {
      const [, crew, id] = running.pop()!;
      free.push(crew);
      for (const other of dependents.get(id) ?? []) {
        const left = waiting.get(other)! - 1;
        waiting.set(other, left);
        if (left === 0) ready.push(other);
      }
    }
  }
  return rows;
}

export async function planOrders(crews: number): Promise<{ crews: number; cost: number; schedule: Row[] }> {
  const store = await readStore();
  const jobs = jobsOf(store.workOrders);
  const schedule = greedy(jobs, crews).sort((a, b) => a.start - b.start || a.crew - b.crew || (a.id < b.id ? -1 : 1));
  const cost = schedule.reduce((sum, row) => sum + jobs.get(row.id)!.priority * row.end, 0);
  return { crews, cost, schedule };
}
