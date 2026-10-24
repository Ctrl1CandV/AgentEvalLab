// The evidence table (PLAN-007 WP0.2): every run and suite run under runs/, with its task and grader version, protocol,
// coverage and status, written to docs/evidence/V1_EVIDENCE.md (and a JSON twin). Dry runs are listed, never scored.
//
// Usage: npm run evidence [-- --out docs/evidence/V1_EVIDENCE.md]
import { writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { join } from "node:path";
import { parseArgs } from "node:util";
import { collectEvidence, markdownEvidence } from "../src/analysis/evidence.js";

const { values } = parseArgs({ options: { out: { type: "string" } } });
const repoRoot = fileURLToPath(new URL("../", import.meta.url));
const out = values.out ?? "docs/evidence/V1_EVIDENCE.md";
const evidence = await collectEvidence(repoRoot);
await writeFile(join(repoRoot, out), markdownEvidence(evidence));
await writeFile(join(repoRoot, out.replace(/\.md$/, ".json")), JSON.stringify(evidence, null, 1) + "\n");
console.log(JSON.stringify({ out, rows: evidence.rows.length, suites: evidence.suites.length, excluded: evidence.excluded.length,
  neverRun: evidence.configurations.filter(entry => !entry.matchingRows).map(entry => `${entry.suite}:${entry.family}`) }, null, 2));
