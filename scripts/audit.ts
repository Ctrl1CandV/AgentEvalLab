// Success audits (VALIDATION §2, PLAN-007 WP0.4): re-check graded trials with an audit suite written from the task's
// public contract, independent of the grader, and record each finding as a true pass, a false pass, a false fail or a
// finding beyond the contract. Writes docs/audits/<family>/<date>.md and its JSON twin.
//
// Usage:
//   npm run audit -- --family T1 --runs runs/suites/<id>/runs/T1/<run> [--runs ...] [--select all|resolved] [--date 2026-10-24]
// --select resolved takes every resolved trial when there are at most ten, otherwise ten of them plus every trial with
// a perfect score (VALIDATION §2); --select all takes every graded trial.
import { spawnSync } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { loadRecordedTrials } from "../src/evaluation/regrade.js";
import { modelLabel } from "../src/evaluation/report.js";
import type { TrajectoryRecord, TrialRecord } from "../src/evaluation/types.js";

interface FamilyAudit {
  /** The audit suite: argv after the request and result paths are appended. */
  command: string[];
  package: string;
  description: string;
  /** Which trials go in: by default, those whose grading the suite can check. */
  kind: "single" | "trajectory";
}

const FAMILIES: Record<string, FamilyAudit> = {
  T1: { command: ["python3", "-I", "scripts/audits/t1_cases.py"], package: "task-library/calibration/t1-evidence-recovery", kind: "single",
    description: "An independent solver of the adjudication questions, written from the snapshot's docs/CONFIG.md and docs/RESPONSE.md, derives every answer field; the package's answer key and each trial's answer are compared with it." },
  T2: { command: ["python3", "-I", "scripts/audits/t2_books.py"], package: "task-library/calibration/t2-finance-desk", kind: "single",
    description: "Independent checks of the delivered books from MANUAL.md: double entry, open items, bank lines, deferred revenue and revaluation recomputed, invoice statuses against the manual's rules, and the payment plan re-validated and re-valued by an independent evaluator." },
  E3: { command: ["python3", "-I", "scripts/audits/e3_cli.py"], package: "task-library/candidates/eng-005-long-cycle-maintenance", kind: "trajectory",
    description: "Property and state-sequence tests of the final project, written from the stage briefs, on random stores the hidden checks never used: list filtering, sorting and pagination against an independent model; dependency and transition rules; atomicity of rejected commands; and plan validity and cost on random stores." },
  "E4-speedup": { command: ["python3", "-I", "scripts/audits/e4_speedup.py"], package: "task-library/calibration/e4-terminal-tasks", kind: "single",
    description: "The delivered analyze.py against the original on fresh generated days, normal and full of malformed rows, byte for byte, and its time on a fresh large day." },
  VIS: { command: ["node", "scripts/audits/vis_interactions.mjs"], package: "task-library/calibration/vis-001-original-landing", kind: "single",
    description: "The page rendered in headless Chromium and its form exercised: empty, invalid and valid submissions, the label of every field at run time, and horizontal overflow at 375 and 1280 pixels." },
};

export interface AuditFinding {
  trial: string;
  label: string;
  item: string | null;
  unit: string;
  grader: "pass" | "fail" | "n/a";
  verdict: "true pass" | "false pass" | "false fail" | "true fail" | "fail by the evidence rule" | "beyond contract" | "note";
  detail?: string;
}

const { values } = parseArgs({ options: {
  family: { type: "string" }, runs: { type: "string", multiple: true }, select: { type: "string" }, date: { type: "string" },
  items: { type: "string" },
} });
const family = values.family ?? "";
const audit = FAMILIES[family];
if (!audit || !values.runs?.length) {
  console.log(`npm run audit -- --family ${Object.keys(FAMILIES).join("|")} --runs <run directory> [--runs ...] [--select all|resolved] [--items a,b] [--date YYYY-MM-DD]`);
  process.exit(2);
}
const repoRoot = fileURLToPath(new URL("../", import.meta.url));
const date = values.date ?? new Date().toISOString().slice(0, 10);
const items = values.items ? new Set(values.items.split(",")) : null;

interface Selected { directory: string; itemId: string | null; label: string; score: number | null; status: string; runDirectory: string }

async function selectTrials(): Promise<Selected[]> {
  const chosen: Selected[] = [];
  for (const run of values.runs!) {
    const runDirectory = resolve(run);
    if (audit.kind === "trajectory") {
      const report = JSON.parse(await readFile(join(runDirectory, "report.json"), "utf8")) as { records: TrajectoryRecord[] };
      for (const record of report.records) {
        chosen.push({ directory: join(runDirectory, record.id), itemId: null, label: modelLabel(record.model), score: null, status: record.status, runDirectory });
      }
      continue;
    }
    const records: TrialRecord[] = await loadRecordedTrials(runDirectory);
    for (const record of records) {
      if (record.execution.failureKind === "infrastructure" || (record.evaluation.status !== "passed" && record.evaluation.status !== "failed")) continue;
      if (items && !items.has(record.itemId ?? "")) continue;
      chosen.push({ directory: join(runDirectory, record.id), itemId: record.itemId ?? null, label: modelLabel(record.model), score: record.evaluation.score,
        status: record.evaluation.status, runDirectory });
    }
  }
  if (values.select !== "resolved") return chosen;
  const resolved = chosen.filter(trial => trial.status === "passed");
  if (resolved.length <= 10) return resolved;
  const perfect = chosen.filter(trial => trial.score === 1);
  return [...new Set([...resolved.slice(0, 10), ...perfect])];
}

const trials = await selectTrials();
const scratch = mkdtempSync(join(tmpdir(), `audit-${family}-`));
const requestPath = join(scratch, "request.json");
const resultPath = join(scratch, "result.json");
await writeFile(requestPath, JSON.stringify({ package: audit.package, trials: trials.map(trial => ({ ...trial, directory: trial.directory })) }, null, 1));
const run = spawnSync(audit.command[0]!, [...audit.command.slice(1), requestPath, resultPath], { cwd: repoRoot, encoding: "utf8", timeout: 3 * 60 * 60 * 1000,
  maxBuffer: 64 * 1024 * 1024, env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" } });
if (run.status !== 0) {
  console.error(run.stdout.slice(-4000), run.stderr.slice(-4000));
  throw new Error(`AUDIT_SUITE_FAILED:${family}`);
}
const result = JSON.parse(await readFile(resultPath, "utf8")) as { findings: AuditFinding[]; oracle?: unknown[]; notes?: string[]; references?: unknown[] };

const counts = (findings: AuditFinding[]) => {
  const table: Record<string, number> = {};
  for (const finding of findings) table[finding.verdict] = (table[finding.verdict] ?? 0) + 1;
  return table;
};
const display = (path: string) => relative(repoRoot, path);
const findings = result.findings.map(finding => ({ ...finding, trial: display(finding.trial) }));
const verdicts = ["true pass", "false pass", "false fail", "true fail", "fail by the evidence rule", "beyond contract", "note"] as const;
const labels = [...new Set(findings.map(finding => finding.label))].sort();
const lines = [
  `# Success audit: ${family}, ${date}`, "",
  `Package \`${audit.package}\`. ${audit.description}`, "",
  `Trials audited: ${trials.length}, from ${values.runs!.map(path => `\`${path}\``).join(", ")} (selection: ${values.select ?? "all graded trials"}${items ? `, items ${[...items].join(", ")}` : ""}).`, "",
  "Verdicts (VALIDATION §2): **true pass**, the grader passed it and the audit agrees; **false pass**, the grader passed a defect; **false fail**, the grader failed a correct delivery; **true fail**; **fail by the evidence rule**, a right value the contract still fails because the trace did not show its evidence; **beyond contract**, the audit tests something the contract does not require, which never changes a score; **note**, an observation.", "",
  "## Summary", "",
  `| Model | ${verdicts.join(" | ")} |`, `| --- | ${verdicts.map(() => "---:").join(" | ")} |`,
  ...labels.map(label => { const table = counts(findings.filter(finding => finding.label === label)); return `| ${label} | ${verdicts.map(verdict => table[verdict] ?? 0).join(" | ")} |`; }),
  "",
];
if (result.notes?.length) lines.push("## Notes", "", ...result.notes.map(note => `- ${note}`), "");
const notable = findings.filter(finding => finding.verdict !== "true pass" && finding.verdict !== "true fail");
lines.push("## Findings other than true passes and true fails", "");
if (!notable.length) lines.push("None.", "");
else lines.push("| Trial | Model | Item | Unit | Grader | Verdict | Detail |", "| --- | --- | --- | --- | --- | --- | --- |",
  ...notable.map(finding => `| ${finding.trial.split("/").at(-1)!.slice(0, 8)} | ${finding.label} | ${finding.item ?? "—"} | ${finding.unit} | ${finding.grader} | ${finding.verdict} | ${(finding.detail ?? "").replace(/\|/g, "\\|").replace(/\n/g, " ")} |`), "");
lines.push("## Trials", "", "| Trial | Model | Item | Grader status | Score | Findings |", "| --- | --- | --- | --- | ---: | --- |",
  ...trials.map(trial => {
    const own = findings.filter(finding => finding.trial === display(trial.directory));
    const table = counts(own);
    return `| ${display(trial.directory)} | ${trial.label} | ${trial.itemId ?? "—"} | ${trial.status} | ${trial.score === null ? "—" : `${(trial.score * 100).toFixed(1)}%`} | ${Object.entries(table).map(([verdict, count]) => `${verdict} ${count}`).join(", ") || "—"} |`;
  }), "");
const directory = join(repoRoot, "docs", "audits", family);
await mkdir(directory, { recursive: true });
await writeFile(join(directory, `${date}.md`), lines.join("\n"));
await writeFile(join(directory, `${date}.json`), JSON.stringify({ family, date, package: audit.package, runs: values.runs, selection: values.select ?? "all",
  trials: trials.map(trial => ({ ...trial, directory: display(trial.directory), runDirectory: display(trial.runDirectory) })), summary: counts(findings),
  notes: result.notes ?? [], oracle: result.oracle ?? null, references: result.references ?? null, findings }, null, 1) + "\n");
console.log(JSON.stringify({ family, trials: trials.length, summary: counts(findings), out: `docs/audits/${family}/${date}.md` }, null, 2));
