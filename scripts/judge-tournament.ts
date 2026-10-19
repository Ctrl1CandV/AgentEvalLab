// Pairwise visual tournament for vis-001 runs (PLAN-005 WP6). Anchor comparisons tell whether a page clears a fixed
// bar; once every model clears it they no longer separate models. Here every submission meets every submission from
// another model, in both orders, judged by every gate-passing judge whose vendor made neither page, and the results
// give per-model win rates and Bradley–Terry strengths, as in arena-style web-design evaluations.
//
// A trial that delivered no index.html loses each of its pairings without a judge call: the missing page is the
// model's own failure. A page that exists but could not be rendered is left out and listed.
//
// Usage: node --import tsx scripts/judge-tournament.ts --run runs/<id> [--run runs/<id> ...] --package <vis package>
//        [--judges a,b,c] [--concurrency 4] [--dry-run]
// Writes visual/tournament.json and visual/tournament.md under the first run directory.
import { access, mkdir, readFile, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { parseArgs } from "node:util";
import { loadCredentials } from "../src/providers.js";
import { loadRecordedTrials } from "../src/evaluation/regrade.js";
import { modelLabel } from "../src/evaluation/report.js";
import { renderSubmission, type RenderResult } from "../src/visual/render.js";
import { combineOrders, criteria, loadDesign, outcomeScore, vendorOf, type Choice, type Verdict } from "../src/visual/judge.js";
import { anchorGate, bradleyTerry, callJudge, DEFAULT_JUDGES, judgeLabel, judgeSelection, pool } from "../src/visual/panel.js";
import type { ModelSelection } from "../src/types.js";

const { values } = parseArgs({ options: { run: { type: "string", multiple: true }, package: { type: "string" }, judges: { type: "string" },
  concurrency: { type: "string", default: "4" }, "dry-run": { type: "boolean" } } });
if (!values.run?.length || !values.package) throw new Error("usage: --run runs/<id> [--run ...] --package <vis package>");
const runDirectories = values.run.map(run => resolve(run));
const packageDirectory = resolve(values.package);
const judges = (values.judges ? values.judges.split(",") : DEFAULT_JUDGES).map(judgeSelection);
const concurrency = Number(values.concurrency);
const skill = await readFile(join(packageDirectory, "private", "judge", "SKILL.md"), "utf8");
const states = (JSON.parse(await readFile(join(packageDirectory, "public", "content.json"), "utf8")) as { form: { states: { error: string; success: string } } }).form.states;
const visualRoot = join(runDirectories[0]!, "visual");
await mkdir(visualRoot, { recursive: true });
const exists = (path: string) => access(path).then(() => true, () => false);

type Trial = { id: string; model: ModelSelection; label: string; site: string; render: string; delivered: boolean; result?: RenderResult };
const trials: Trial[] = [];
for (const directory of runDirectories) {
  for (const record of await loadRecordedTrials(directory)) {
    if (!record.artifactManifest || record.execution.failureKind === "infrastructure") continue;
    const site = join(directory, record.id, "artifacts");
    trials.push({ id: record.id, model: record.model, label: modelLabel(record.model), site, render: join(directory, record.id, "visual", "render"),
      delivered: await exists(join(site, "index.html")) });
  }
}
const sameModel = (left: Trial, right: Trial) => left.model.provider === right.model.provider && left.model.id === right.model.id;
const pairs: Array<[Trial, Trial]> = [];
for (let left = 0; left < trials.length; left++) for (let right = left + 1; right < trials.length; right++) {
  if (!sameModel(trials[left]!, trials[right]!)) pairs.push([trials[left]!, trials[right]!]);
}
const panelFor = (left: Trial, right: Trial) => judges.filter(judge => vendorOf(judge) !== vendorOf(left.model) && vendorOf(judge) !== vendorOf(right.model));
const calls = judges.length * 2 + pairs.filter(([left, right]) => left.delivered && right.delivered).reduce((sum, [left, right]) => sum + panelFor(left, right).length * 2, 0);
console.log(`trials ${trials.length} (${trials.filter(trial => !trial.delivered).length} without a page), pairs ${pairs.length}, judge calls at most ${calls}`);
if (values["dry-run"]) process.exit(0);
loadCredentials();

// Render the anchors (for the gate) and every delivered page with the current renderer.
const anchorDirectories = { reference: join(packageDirectory, "private", "frontend"), plain: join(packageDirectory, "private", "judge", "anchors", "plain") };
for (const [name, site] of Object.entries(anchorDirectories)) await renderSubmission(site, join(visualRoot, "anchors", name), states);
for (const trial of trials.filter(trial => trial.delivered)) {
  try { trial.result = await renderSubmission(trial.site, trial.render, states); }
  catch { trial.result = { screenshots: {}, overflow: {}, rolesPresent: [], formStates: {}, errors: ["render failed"] }; }
}
const rendered = (trial: Trial) => Boolean(trial.result?.screenshots.desktop);
const gate = await anchorGate(judges, skill, (label, anchor) => loadDesign(label, join(visualRoot, "anchors", anchor), anchorDirectories[anchor]), concurrency);
const trusted = judges.filter(judge => gate.some(entry => entry.judge === judgeLabel(judge) && entry.passed));

// Every cross-model pair: judged when both pages rendered, decided without a judge when one side delivered nothing.
type Game = { a: string; b: string; judge: string | null; outcome: "win" | "loss" | "tie" | "missing"; inconsistent: boolean;
  criteria: Record<string, string>; verdicts: Array<Verdict | null>; usage: Array<{ input: number; output: number }> };
const tasks: Array<() => Promise<Game>> = [];
const excluded = new Set<string>();
for (const [left, right] of pairs) {
  if (!left.delivered || !right.delivered) {
    if (!left.delivered && !right.delivered) continue;
    const outcome = left.delivered ? "win" : "loss";
    tasks.push(async () => ({ a: left.id, b: right.id, judge: null, outcome, inconsistent: false, criteria: {}, verdicts: [], usage: [] }));
    continue;
  }
  if (!rendered(left) || !rendered(right)) { for (const trial of [left, right]) if (!rendered(trial)) excluded.add(trial.id); continue; }
  for (const judge of panelFor(left, right).filter(judge => trusted.includes(judge))) tasks.push(async () => {
    const one = await callJudge(judge, skill, await loadDesign("A", left.render, left.site), await loadDesign("B", right.render, right.site));
    const two = await callJudge(judge, skill, await loadDesign("A", right.render, right.site), await loadDesign("B", left.render, left.site));
    const combined = combineOrders(one.verdict?.overall ?? null, two.verdict?.overall ?? null);
    const perCriterion = Object.fromEntries(criteria.map(name => [name, combineOrders(one.verdict?.criteria[name] as Choice ?? null, two.verdict?.criteria[name] as Choice ?? null).outcome]));
    return { a: left.id, b: right.id, judge: judgeLabel(judge), outcome: combined.outcome, inconsistent: combined.inconsistent, criteria: perCriterion,
      verdicts: [one.verdict, two.verdict], usage: [one.usage, two.usage] };
  });
}
const games = (await pool(tasks, concurrency)).filter(game => game.outcome !== "missing");
const trialById = new Map(trials.map(trial => [trial.id, trial]));

// Model level: win rate over all games, Bradley–Terry strength, head-to-head matrix, and per-criterion win rates.
const models = [...new Set(trials.map(trial => trial.label))].sort();
const modelGames = games.map(game => ({ a: trialById.get(game.a)!.label, b: trialById.get(game.b)!.label, scoreA: outcomeScore[game.outcome as keyof typeof outcomeScore] }));
const strength = bradleyTerry(models, modelGames);
const scoreFor = (model: string, game: { a: string; b: string; scoreA: number }) => game.a === model ? game.scoreA : 1 - game.scoreA;
const byModel = models.map(model => {
  const own = modelGames.filter(game => game.a === model || game.b === model);
  const judged = games.filter(game => game.judge && [game.a, game.b].some(id => trialById.get(id)!.label === model));
  const criterionRate = Object.fromEntries(criteria.map(name => {
    const scores = judged.filter(game => game.criteria[name] && game.criteria[name] !== "missing").map(game => {
      const score = outcomeScore[game.criteria[name] as keyof typeof outcomeScore];
      return trialById.get(game.a)!.label === model ? score : 1 - score;
    });
    return [name, scores.length ? scores.reduce((sum, value) => sum + value, 0) / scores.length : null];
  }));
  return { model, trials: trials.filter(trial => trial.label === model).length, games: own.length,
    winRate: own.length ? own.reduce((sum, game) => sum + scoreFor(model, game), 0) / own.length : null, strength: strength[model]!, criteria: criterionRate };
}).sort((left, right) => right.strength - left.strength);
const headToHead = Object.fromEntries(models.map(row => [row, Object.fromEntries(models.filter(column => column !== row).map(column => {
  const own = modelGames.filter(game => (game.a === row && game.b === column) || (game.a === column && game.b === row));
  return [column, own.length ? own.reduce((sum, game) => sum + scoreFor(row, game), 0) / own.length : null];
}))]));
const judgedGames = games.filter(game => game.judge);
const inconsistentRate = judgedGames.length ? judgedGames.filter(game => game.inconsistent).length / judgedGames.length : null;
let agreements = 0, comparedPairs = 0;
for (const [left, right] of pairs) {
  const outcomes = judgedGames.filter(game => game.a === left.id && game.b === right.id).map(game => game.outcome);
  for (let one = 0; one < outcomes.length; one++) for (let two = one + 1; two < outcomes.length; two++) { comparedPairs++; agreements += Number(outcomes[one] === outcomes[two]); }
}
const tokens = judgedGames.reduce((sum, game) => sum + game.usage.reduce((total, usage) => total + usage.input + usage.output, 0), 0) +
  gate.reduce((sum, entry) => sum + entry.usage.reduce((total, usage) => total + usage.input + usage.output, 0), 0);
const report = { generatedAt: new Date().toISOString(), runs: values.run, judges: judges.map(judgeLabel), anchorGate: gate.map(({ usage: _usage, ...entry }) => entry),
  trials: trials.map(trial => ({ id: trial.id, model: trial.label, delivered: trial.delivered, rendered: rendered(trial), renderErrors: trial.result?.errors ?? [] })),
  excluded: [...excluded], positionInconsistentRate: inconsistentRate, interJudgeAgreement: comparedPairs ? agreements / comparedPairs : null, tokens,
  byModel, headToHead, games };
await writeFile(join(visualRoot, "tournament.json"), JSON.stringify(report, null, 2));

const percent = (value: number | null | undefined) => value === null || value === undefined ? "—" : `${(value * 100).toFixed(0)}%`;
const lines = ["# Visual tournament", "",
  `Runs: ${values.run.join(", ")}. Every page meets every page from another model, in both orders; a result counts only if it holds in both orders, otherwise it is a tie. Judges: ${report.judges.join(", ")}, each only on pairs where its vendor made neither page, and only after passing the anchor gate. A trial without index.html loses its pairings without a judge call.`, "",
  "## Anchor gate", "", "| Judge | Prefers reference over plain in both orders |", "| --- | --- |",
  ...report.anchorGate.map(entry => `| ${entry.judge} | ${entry.passed ? "yes" : `no (${entry.outcome})`} |`), "",
  `Judged games: ${judgedGames.length}; decided without a judge: ${games.length - judgedGames.length}. Position-inconsistent: ${percent(inconsistentRate)}. Agreement between judges on the same pair: ${percent(report.interJudgeAgreement)}. Judge tokens: ${tokens.toLocaleString("en-US")}.`, "",
  "## By model", "", `| Model | Trials | Games | Win rate | Strength (Bradley–Terry) | ${criteria.join(" | ")} |`, `| --- | ---: | ---: | ---: | ---: | ${criteria.map(() => "---:").join(" | ")} |`,
  ...byModel.map(row => `| ${row.model} | ${row.trials} | ${row.games} | ${percent(row.winRate)} | ${row.strength.toFixed(2)} | ${criteria.map(name => percent(row.criteria[name])).join(" | ")} |`), "",
  "## Head to head", "", "Score of the row model against the column model.", "", `| | ${models.join(" | ")} |`, `| --- | ${models.map(() => "---:").join(" | ")} |`,
  ...models.map(row => `| ${row} | ${models.map(column => column === row ? "—" : percent(headToHead[row]![column])).join(" | ")} |`), "",
  "## Trials", "", "| Trial | Model | Page | Rendered | Render errors |", "| --- | --- | --- | --- | --- |",
  ...report.trials.map(trial => `| ${trial.id.slice(0, 8)} | ${trial.model} | ${trial.delivered ? "yes" : "no"} | ${trial.rendered ? "yes" : "no"} | ${trial.renderErrors.join("; ") || "—"} |`), ""];
await writeFile(join(visualRoot, "tournament.md"), lines.join("\n"));
console.log(lines.join("\n"));
