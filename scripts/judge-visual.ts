// Visual judging step for vis-001 runs (PLAN-005 WP6). Renders every submission and two anchor designs in headless
// Chromium (sandboxed), then asks a panel of vision-model judges to compare each submission with each anchor in both
// orders, following the package's judging skill. No judge rates a page from its own vendor.
//
// Usage: node --import tsx scripts/judge-visual.ts --run runs/<id> --package <vis package> [--judges a,b,c] [--panel 3]
//        [--concurrency 4] [--dry-run]
// Judges use the provider-check syntax provider:model?thinking=<level>. Credentials come from .env.
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { parseArgs } from "node:util";
import { parseModel } from "../src/config.js";
import { loadCredentials } from "../src/providers.js";
import { loadRecordedTrials } from "../src/evaluation/regrade.js";
import { modelLabel } from "../src/evaluation/report.js";
import { renderSubmission, type RenderResult } from "../src/visual/render.js";
import { combineOrders, criteria, judgePair, loadDesign, outcomeScore, vendorOf, type Choice, type Design, type Verdict } from "../src/visual/judge.js";
import type { ModelSelection, PlanThinkingLevel } from "../src/types.js";

const DEFAULT_JUDGES = ["supergpt:gpt-6-luna?thinking=medium", "supercn:step-5-preview?thinking=medium",
  "deepseek:deepseek-flash?thinking=high", "supercn:glm-5.3-flash?thinking=provider-default"];

function judgeSelection(spec: string): ModelSelection {
  const [model, query = ""] = spec.split("?", 2);
  const thinking = new URLSearchParams(query).get("thinking") ?? "provider-default";
  return { ...parseModel(model!), thinkingLevel: thinking as PlanThinkingLevel, temperature: 0 };
}

async function pool<T>(tasks: Array<() => Promise<T>>, limit: number): Promise<T[]> {
  const results: T[] = new Array(tasks.length);
  let next = 0;
  await Promise.all(Array.from({ length: Math.max(1, Math.min(limit, tasks.length)) }, async () => {
    while (next < tasks.length) { const index = next++; results[index] = await tasks[index]!(); }
  }));
  return results;
}

const { values } = parseArgs({ options: { run: { type: "string" }, package: { type: "string" }, judges: { type: "string" },
  panel: { type: "string", default: "3" }, concurrency: { type: "string", default: "4" }, "dry-run": { type: "boolean" } } });
if (!values.run || !values.package) throw new Error("usage: --run runs/<id> --package <vis package>");
const runDirectory = resolve(values.run);
const packageDirectory = resolve(values.package);
const judges = (values.judges ? values.judges.split(",") : DEFAULT_JUDGES).map(judgeSelection);
const panelSize = Number(values.panel);
const skill = await readFile(join(packageDirectory, "private", "judge", "SKILL.md"), "utf8");
const states = (JSON.parse(await readFile(join(packageDirectory, "public", "content.json"), "utf8")) as { form: { states: { error: string; success: string } } }).form.states;
const visualRoot = join(runDirectory, "visual");
await mkdir(visualRoot, { recursive: true });

// Render anchors and submissions.
const anchors: Array<{ name: string; site: string }> = [
  { name: "reference", site: join(packageDirectory, "private", "frontend") },
  { name: "plain", site: join(packageDirectory, "private", "judge", "anchors", "plain") },
];
const anchorDesigns = new Map<string, { site: string; render: string }>();
for (const anchor of anchors) {
  const render = join(visualRoot, "anchors", anchor.name);
  if (!values["dry-run"]) await renderSubmission(anchor.site, render, states);
  anchorDesigns.set(anchor.name, { site: anchor.site, render });
}
const records = (await loadRecordedTrials(runDirectory)).filter(record => record.artifactManifest);
const trials: Array<{ id: string; model: ModelSelection; site: string; render: string; result?: RenderResult; panel: ModelSelection[] }> = [];
for (const record of records) {
  const panel = judges.filter(judge => vendorOf(judge) !== vendorOf(record.model)).slice(0, panelSize);
  trials.push({ id: record.id, model: record.model, site: join(runDirectory, record.id, "artifacts"), render: join(runDirectory, record.id, "visual", "render"), panel });
}
const calls = judges.length * 2 + trials.reduce((sum, trial) => sum + trial.panel.length * anchors.length * 2, 0);
console.log(`trials ${trials.length}, judges ${judges.map(judge => `${judge.provider}:${judge.id}`).join(", ")}, judge calls ${calls}`);
if (values["dry-run"]) process.exit(0);
loadCredentials();
for (const trial of trials) {
  try { trial.result = await renderSubmission(trial.site, trial.render, states); }
  catch { trial.result = { screenshots: {}, overflow: {}, rolesPresent: [], formStates: {}, errors: ["render failed"] }; }
}

type Call = { judge: ModelSelection; first: Design; second: Design };
const runCall = async (call: Call) => {
  try { return await judgePair(call.judge, skill, call.first, call.second); }
  catch { return { verdict: null, usage: { input: 0, output: 0 }, raw: "" }; }
};
const designOf = (label: string, item: { site: string; render: string }) => loadDesign(label, item.render, item.site);
const reference = anchorDesigns.get("reference")!, plain = anchorDesigns.get("plain")!;

// Anchor gate: every judge must prefer the reference over the plain page in both orders.
const gate = await pool(judges.map(judge => async () => {
  const one = await runCall({ judge, first: await designOf("A", reference), second: await designOf("B", plain) });
  const two = await runCall({ judge, first: await designOf("A", plain), second: await designOf("B", reference) });
  const combined = combineOrders(one.verdict?.overall ?? null, two.verdict?.overall ?? null);
  return { judge: `${judge.provider}:${judge.id}`, passed: combined.outcome === "win", outcome: combined.outcome, usage: [one.usage, two.usage] };
}), Number(values.concurrency));
const trusted = new Set(gate.filter(entry => entry.passed).map(entry => entry.judge));

// Submission against each anchor, in both orders, for each judge of its panel.
type Comparison = { trial: string; judge: string; anchor: string; outcome: string; inconsistent: boolean;
  criteria: Record<string, string>; verdicts: Array<Verdict | null>; usage: Array<{ input: number; output: number }> };
const tasks: Array<() => Promise<Comparison>> = [];
for (const trial of trials) {
  if (!trial.result?.screenshots.desktop) continue;
  for (const judge of trial.panel) for (const anchor of anchors) tasks.push(async () => {
    const anchorItem = anchorDesigns.get(anchor.name)!;
    const one = await runCall({ judge, first: await designOf("A", trial), second: await designOf("B", anchorItem) });
    const two = await runCall({ judge, first: await designOf("A", anchorItem), second: await designOf("B", trial) });
    const combined = combineOrders(one.verdict?.overall ?? null, two.verdict?.overall ?? null);
    const perCriterion = Object.fromEntries(criteria.map(name => [name, combineOrders(one.verdict?.criteria[name] as Choice ?? null, two.verdict?.criteria[name] as Choice ?? null).outcome]));
    return { trial: trial.id, judge: `${judge.provider}:${judge.id}`, anchor: anchor.name, outcome: combined.outcome, inconsistent: combined.inconsistent,
      criteria: perCriterion, verdicts: [one.verdict, two.verdict], usage: [one.usage, two.usage] };
  });
}
const comparisons = await pool(tasks, Number(values.concurrency));

// Per-trial scores from trusted judges only, then per-model summaries.
const usable = comparisons.filter(comparison => trusted.has(comparison.judge) && comparison.outcome !== "missing");
const scored = trials.map(trial => {
  const own = usable.filter(comparison => comparison.trial === trial.id);
  const score = own.length ? own.reduce((sum, comparison) => sum + outcomeScore[comparison.outcome as keyof typeof outcomeScore], 0) / own.length : null;
  return { trial: trial.id, model: trial.model, label: modelLabel(trial.model), score, comparisons: own.length,
    overflow: trial.result?.overflow ?? {}, formStates: trial.result?.formStates ?? {}, renderErrors: trial.result?.errors ?? [] };
});
for (const trial of trials) {
  await writeFile(join(trial.render, "..", "judgments.json"), JSON.stringify(comparisons.filter(comparison => comparison.trial === trial.id), null, 2));
}
const models = [...new Map(trials.map(trial => [`${trial.model.provider}:${trial.model.id}`, trial.model])).values()];
const byModel = models.map(model => {
  const rows = scored.filter(row => row.model.provider === model.provider && row.model.id === model.id && row.score !== null);
  const own = usable.filter(comparison => rows.some(row => row.trial === comparison.trial));
  const criterionWin = Object.fromEntries(criteria.map(name => {
    const outcomes = own.map(comparison => comparison.criteria[name]).filter(outcome => outcome && outcome !== "missing") as Array<keyof typeof outcomeScore>;
    return [name, outcomes.length ? outcomes.reduce((sum, outcome) => sum + outcomeScore[outcome], 0) / outcomes.length : null];
  }));
  return { model: modelLabel(model), trials: rows.length, meanScore: rows.length ? rows.reduce((sum, row) => sum + row.score!, 0) / rows.length : null, criteria: criterionWin };
});
// Consistency: position-inconsistent comparisons, and agreement between judges on the same trial and anchor.
const inconsistentRate = comparisons.length ? comparisons.filter(comparison => comparison.inconsistent).length / comparisons.length : null;
let agreements = 0, pairs = 0;
for (const trial of trials) for (const anchor of anchors) {
  const outcomes = usable.filter(comparison => comparison.trial === trial.id && comparison.anchor === anchor.name).map(comparison => comparison.outcome);
  for (let left = 0; left < outcomes.length; left++) for (let right = left + 1; right < outcomes.length; right++) { pairs++; agreements += Number(outcomes[left] === outcomes[right]); }
}
const tokens = comparisons.concat().reduce((sum, comparison) => sum + comparison.usage.reduce((total, usage) => total + usage.input + usage.output, 0), 0) +
  gate.reduce((sum, entry) => sum + entry.usage.reduce((total, usage) => total + usage.input + usage.output, 0), 0);
const report = { generatedAt: new Date().toISOString(), skill: "private/judge/SKILL.md", judges: judges.map(judge => `${judge.provider}:${judge.id}`), panelSize,
  anchorGate: gate.map(({ usage: _usage, ...entry }) => entry), positionInconsistentRate: inconsistentRate, interJudgeAgreement: pairs ? agreements / pairs : null,
  tokens, byModel, trials: scored.map(({ model: _model, ...row }) => row) };
await writeFile(join(visualRoot, "visual-report.json"), JSON.stringify(report, null, 2));
const percent = (value: number | null) => value === null ? "n/a" : `${(value * 100).toFixed(0)}%`;
const lines = ["# Visual judging report", "",
  `Judges: ${report.judges.join(", ")}; panel of ${panelSize} per page, never the page's own vendor. Each page is compared with two anchors (reference and plain) in both orders; a result counts only if it holds in both orders. Score: win 1, tie 0.5, loss 0.`, "",
  "## Anchor gate", "", "| Judge | Prefers reference over plain in both orders |", "| --- | --- |",
  ...report.anchorGate.map(entry => `| ${entry.judge} | ${entry.passed ? "yes" : `no (${entry.outcome})`} |`), "",
  `Position-inconsistent comparisons: ${percent(inconsistentRate)}. Agreement between judges on the same page and anchor: ${percent(report.interJudgeAgreement)}. Judge tokens: ${tokens.toLocaleString("en-US")}.`, "",
  "## By model", "", `| Model | Trials | Visual score | ${criteria.join(" | ")} |`, `| --- | ---: | ---: | ${criteria.map(() => "---:").join(" | ")} |`,
  ...byModel.map(row => `| ${row.model} | ${row.trials} | ${percent(row.meanScore)} | ${criteria.map(name => percent(row.criteria[name] ?? null)).join(" | ")} |`), "",
  "## Trials", "", "| Trial | Model | Visual score | Comparisons | Overflow (desktop/phone) | Form states shown (error/success) | Render errors |", "| --- | --- | ---: | ---: | --- | --- | --- |",
  ...scored.map(row => `| ${row.trial.slice(0, 8)} | ${row.label} | ${percent(row.score)} | ${row.comparisons} | ${row.overflow.desktop ? "yes" : "no"}/${row.overflow.phone ? "yes" : "no"} | ${row.formStates["form-error"] ? "yes" : "no"}/${row.formStates["form-success"] ? "yes" : "no"} | ${row.renderErrors.join("; ") || "—"} |`), ""];
await writeFile(join(visualRoot, "visual-report.md"), lines.join("\n"));
console.log(lines.join("\n"));
