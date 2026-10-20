import type { Catalog, Resource } from "./types.ts";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseResource(value: unknown): Resource {
  if (!isRecord(value)) throw new Error("INVALID_RESOURCE");
  const { id, title, tags, rank } = value;
  if (typeof id !== "string" || id === "") throw new Error("INVALID_RESOURCE_ID");
  if (typeof title !== "string") throw new Error("INVALID_RESOURCE_TITLE");
  if (!Array.isArray(tags) || !tags.every(tag => typeof tag === "string")) throw new Error("INVALID_RESOURCE_TAGS");
  if (typeof rank !== "number" || !Number.isSafeInteger(rank) || rank < 0) throw new Error("INVALID_RESOURCE_RANK");
  return { ...value, id, title, tags: [...tags], rank } as Resource;
}

/** Validate a repository file: {"resources": [...]}, every record with id, title, tags and a non-negative integer rank. */
export function parseCatalog(value: unknown): Catalog {
  if (!isRecord(value) || !Array.isArray(value.resources)) throw new Error("INVALID_CATALOG");
  return { resources: value.resources.map(parseResource) };
}
