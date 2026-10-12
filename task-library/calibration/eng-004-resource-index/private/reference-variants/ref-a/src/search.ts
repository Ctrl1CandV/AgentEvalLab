import type { Resource } from "./types.ts";

function compareCodePoints(left: string, right: string): number {
  const a = Array.from(left, char => char.codePointAt(0)!);
  const b = Array.from(right, char => char.codePointAt(0)!);
  for (let i = 0; i < Math.min(a.length, b.length); i++) {
    if (a[i] !== b[i]) return a[i]! - b[i]!;
  }
  return a.length - b.length;
}

export function searchResources(resources: readonly Resource[], query: string, offset: number, limit: number) {
  const needle = query.trim().toLocaleLowerCase("en-US");
  const matches = resources
    .filter(resource => resource.title.toLocaleLowerCase("en-US").includes(needle) ||
      resource.tags.some(tag => tag.toLocaleLowerCase("en-US").includes(needle)))
    .sort((a, b) => compareCodePoints(a.id, b.id));
  const items = matches.slice(offset, offset + limit);
  return { items, total: matches.length, offset, limit, nextOffset: offset + items.length < matches.length ? offset + items.length : null };
}
