import type { Resource } from "./types.ts";
export function toJson(resources: readonly Resource[]): string { return JSON.stringify({ resources }, null, 2) + "\n"; }
export function toCsv(resources: readonly Resource[]): string {
  const rows = [["id", "title", "tags", "rank"], ...resources.map(r => [r.id, r.title, r.tags.join("|"), String(r.rank)])];
  return rows.map(row => row.join(",")).join("\r\n") + "\r\n";
}
