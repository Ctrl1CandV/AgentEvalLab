import type { Resource } from "./types.ts";

export function toJson(resources: readonly Resource[]): string {
  return JSON.stringify({ resources }, null, 2) + "\n";
}

export function toCsv(resources: readonly Resource[]): string {
  const lines = ["id,title,tags,rank"];
  for (const resource of resources) {
    lines.push([resource.id, resource.title, resource.tags.join("|"), String(resource.rank)].join(","));
  }
  return lines.join("\n") + "\n";
}
