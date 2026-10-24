import { existsSync } from "node:fs";
import { resolve } from "node:path";

/** A library package by its directory name, whichever tier it sits in (PLAN-007 WP2.1). */
export function libraryPackage(name: string): string {
  for (const tier of ["basic", "core", "frontier", "retired"]) {
    const path = resolve("task-library", tier, name);
    if (existsSync(path)) return path;
  }
  throw new Error(`no library package ${name}`);
}
