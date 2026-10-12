import type { Resource } from "./types.ts";

function compareIds(left: string, right: string): number {
  const li = left[Symbol.iterator]();
  const ri = right[Symbol.iterator]();
  while (true) {
    const a = li.next();
    const b = ri.next();
    if (a.done || b.done) return a.done === b.done ? 0 : a.done ? -1 : 1;
    const ac = a.value.codePointAt(0)!;
    const bc = b.value.codePointAt(0)!;
    if (ac !== bc) return ac < bc ? -1 : 1;
  }
}

export function searchResources(resources: readonly Resource[], query: string, offset: number, limit: number) {
  const needle = query.trim().toLocaleLowerCase("en-US");
  const matching: Resource[] = [];
  for (const resource of resources) {
    const titleMatch = resource.title.toLocaleLowerCase("en-US").includes(needle);
    let tagMatch = false;
    for (const tag of resource.tags) {
      if (tag.toLocaleLowerCase("en-US").includes(needle)) { tagMatch = true; break; }
    }
    if (titleMatch || tagMatch) matching.push(resource);
  }
  matching.sort((a, b) => compareIds(a.id, b.id));
  const total = matching.length;
  const items = matching.slice(Math.min(offset, total), Math.min(offset + limit, total));
  const consumed = offset + items.length;
  return { items, total, offset, limit, nextOffset: consumed < total ? consumed : null };
}
