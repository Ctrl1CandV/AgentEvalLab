// Item-level analysis of generated-family calibration runs (PLAN-005 WP5). Combines several run directories; when
// one model and item appear in more than one run, the later run on the command line wins. Prints, per case and
// level: mean score, resolved rate and median tokens per model, and how many items separate the models.
//
// Usage: node --import tsx scripts/item-analysis.ts --run runs/<a> [--run runs/<b> ...] [--levels L3,L4]
import { parseArgs } from "node:util";
import { loadRecordedTrials } from "../src/evaluation/regrade.js";
import { modelLabel } from "../src/evaluation/report.js";
import { wilsonInterval } from "../src/evaluation/statistics.js";
import type { TrialRecord } from "../src/evaluation/types.js";

const { values } = parseArgs({ options: { run: { type: "string", multiple: true }, levels: { type: "string" } } });
if (!values.run?.length) throw new Error("usage: --run runs/<id> [--run ...]");
const levels = values.levels ? new Set(values.levels.split(",")) : null;
const latest = new Map<string, TrialRecord>();
for (const directory of values.run) {
  for (const record of await loadRecordedTrials(directory)) {
    if (!record.itemId || (levels && !levels.has(record.itemLevel ?? ""))) continue;
    if (record.execution.failureKind === "infrastructure") continue;
    latest.set(`${modelLabel(record.model)}|${record.caseId}|${record.itemId}|${record.repetition ?? 1}`, record);
  }
}
const records = [...latest.values()];
const percent = (value: number | null) => value === null ? "n/a" : `${(value * 100).toFixed(0)}%`;
const median = (values: number[]) => { const sorted = [...values].sort((a, b) => a - b); return sorted.length ? sorted[Math.floor(sorted.length / 2)]! : null; };
const tokens = (record: TrialRecord) => (record.execution.requestUsage ?? []).reduce((sum, request) => sum + (request.totalTokens ?? 0), 0);
const models = [...new Set(records.map(record => modelLabel(record.model)))].sort();
const groups = [...new Set(records.map(record => `${record.caseId}|${record.itemLevel}`))].sort();
const lines = [`# Item analysis`, "", `Runs: ${values.run.join(", ")}. Trials: ${records.length}. Infrastructure failures are excluded.`, ""];
for (const group of groups) {
  const [caseId, level] = group.split("|");
  const own = records.filter(record => record.caseId === caseId && record.itemLevel === level);
  lines.push(`## ${caseId} ${level}`, "", "| Model | Trials | Mean score | Resolved | 95% interval | Median tokens | Budget stops |", "| --- | ---: | ---: | ---: | --- | ---: | ---: |");
  for (const model of models) {
    const rows = own.filter(record => modelLabel(record.model) === model);
    if (!rows.length) continue;
    const scores = rows.map(record => record.evaluation.score).filter((score): score is number => typeof score === "number");
    const resolved = rows.filter(record => record.evaluation.status === "passed").length;
    const decided = rows.filter(record => record.evaluation.status === "passed" || record.evaluation.status === "failed").length;
    const interval = wilsonInterval(resolved, decided);
    lines.push(`| ${model} | ${rows.length} | ${percent(scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : null)} | ${resolved}/${decided} | ` +
      `${interval ? `${percent(interval[0])}–${percent(interval[1])}` : "n/a"} | ${median(rows.map(tokens))?.toLocaleString("en-US") ?? "n/a"} | ${rows.filter(record => record.execution.failureKind === "budget").length} |`);
  }
  const items = [...new Set(own.map(record => record.itemId!))].sort();
  let allSolved = 0, noneSolved = 0, separating = 0, complete = 0;
  for (const item of items) {
    const resolvedBy = models.map(model => own.filter(record => record.itemId === item && modelLabel(record.model) === model));
    if (resolvedBy.some(rows => rows.length === 0)) continue;
    complete++;
    const solved = resolvedBy.map(rows => rows.every(record => record.evaluation.status === "passed"));
    if (solved.every(Boolean)) allSolved++;
    else if (!solved.some(Boolean)) noneSolved++;
    else separating++;
  }
  lines.push("", `Items with every model: ${complete} of ${items.length}; resolved by all: ${allSolved}; by none: ${noneSolved}; separating: ${separating}.`, "");
}
console.log(lines.join("\n"));
