import type { Resource } from "./types.ts";

/** The resources in ascending id order; records with equal ids keep their input order. */
export function buildIndex(resources: readonly Resource[]): Resource[] {
  return resources
    .map((resource, position) => ({ resource, position }))
    .sort((a, b) => (a.resource.id < b.resource.id ? -1 : a.resource.id > b.resource.id ? 1 : a.position - b.position))
    .map(entry => entry.resource);
}
