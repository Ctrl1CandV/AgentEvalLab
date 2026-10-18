import type { ManifestItem, PackageDescriptor } from "./manifest.js";
import type { CaseItems, EvaluationCase } from "./types.js";

/** Validate the shape of a case's item selection; the package itself is checked by resolveCaseItems. */
export function validCaseItems(value: unknown): value is CaseItems {
  const identifierList = (list: unknown) => Array.isArray(list) && list.length > 0 && list.every(entry => typeof entry === "string" && /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(entry)) &&
    new Set(list).size === list.length;
  if (value === "all") return true;
  if (identifierList(value)) return true;
  return !!value && typeof value === "object" && !Array.isArray(value) && Object.keys(value).every(key => key === "levels") &&
    identifierList((value as { levels?: unknown }).levels);
}

/**
 * The items a case runs, in manifest order, or null for a package without items. A package with items requires a
 * selection, and every named item or level must exist; an empty selection is an error.
 */
export function resolveCaseItems(item: EvaluationCase, descriptor: PackageDescriptor | undefined): ManifestItem[] | null {
  const items = descriptor?.manifest?.items;
  if (!items) {
    if (item.items !== undefined) throw new Error("CASE_ITEMS_WITHOUT_PACKAGE_ITEMS");
    return null;
  }
  const selection = item.items;
  if (selection === undefined) throw new Error("CASE_ITEMS_REQUIRED");
  let chosen: ManifestItem[];
  if (selection === "all") chosen = items;
  else if (Array.isArray(selection)) {
    if (!selection.every(id => items.some(candidate => candidate.id === id))) throw new Error("UNKNOWN_CASE_ITEM");
    chosen = items.filter(candidate => selection.includes(candidate.id));
  } else {
    if (!selection.levels.every(level => items.some(candidate => candidate.level === level))) throw new Error("UNKNOWN_CASE_ITEM_LEVEL");
    chosen = items.filter(candidate => selection.levels.includes(candidate.level));
  }
  if (!chosen.length) throw new Error("EMPTY_CASE_ITEMS");
  return chosen;
}
