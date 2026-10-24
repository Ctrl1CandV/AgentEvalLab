import type { Resource } from "./types.ts";

export function toJson(resources: readonly Resource[]): string {
  return JSON.stringify({ resources }, null, 2) + "\n";
}

function quote(value: string): string {
  if (!value.includes(",") && !value.includes('"') && !value.includes("\r") && !value.includes("\n")) return value;
  let escaped = "";
  for (const char of value) escaped += char === '"' ? '""' : char;
  return `"${escaped}"`;
}

export function toCsv(resources: readonly Resource[]): string {
  let output = "id,title,tags,rank\r\n";
  for (const resource of resources) {
    const row = [resource.id, resource.title, resource.tags.join("|"), String(resource.rank)];
    output += `${row.map(quote).join(",")}\r\n`;
  }
  return output;
}
