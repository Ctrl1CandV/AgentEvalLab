import type { Resource } from "./types.ts";
export function searchResources(resources: readonly Resource[], query: string, offset: number, limit: number) {
  const needle = query.trim().toLocaleLowerCase("en-US");
  const matches = resources.filter(r => r.title.toLocaleLowerCase("en-US").includes(needle) || r.tags.some(t => t.toLocaleLowerCase("en-US").includes(needle)))
    .sort((a, b) => a.id < b.id ? -1 : a.id > b.id ? 1 : 0);
  const items = matches.slice(offset, offset + limit);
  return { items, total: matches.length, offset, limit, nextOffset: offset + items.length };
}
