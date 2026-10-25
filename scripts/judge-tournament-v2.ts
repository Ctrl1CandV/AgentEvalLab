// Pairwise design tournament for VIS v2 runs (PLAN-007 WP3.4, TASK_LIBRARY §3.5). Per brief, every delivered page
// meets the brief's two anchor pages (plain and reference) and every page of another model, in both orders, judged by
// every exam-passing judge whose vendor made neither page. Judges see screenshots only (desktop, phone, the brief's
// states) and the brief. Bradley–Terry strengths per brief give each page a rating with the plain anchor at 0 and the
// reference at 1 on the log-strength scale, uncapped; a model's rating is the mean over briefs, with a 95% interval by
// bootstrap over briefs. Before judging, each judge sits an exam of pairs whose better page is known: the reference
// against the plain anchor on every brief, and the reference against copies degraded in spacing, contrast, type or
// phone layout on two dev briefs.
//
// A trial that delivered no site/index.html loses each of its pairings without a judge call. A page that exists but
// could not be rendered is left out and listed.
//
// --dry-run renders the anchors, the exam pages and every delivered page (offline, in the sandbox) and counts the
// judge calls, without credentials or any model call. With no --run, only the anchors and the exam are prepared.
//
// Usage: node --import tsx scripts/judge-tournament-v2.ts [--run runs/<id> ...] --package task-library/core/vis-v2
//        [--out DIR] [--judges a,b,c] [--concurrency 4] [--dry-run]
// Writes tournament.json, tournament.md and calibration-pairs.{md,csv} under DIR (default: <first run>/visual).
import { access, cp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { join, relative, resolve } from "node:path";
import { parseArgs } from "node:util";
import { command } from "../src/command.js";
import { loadCredentials } from "../src/providers.js";
import { loadRecordedTrials } from "../src/evaluation/regrade.js";
import { modelLabel } from "../src/evaluation/report.js";
import { sandboxLauncher } from "../src/sandbox.js";
import { combineOrders, criteria, vendorOf, type Choice, type Design, type Verdict } from "../src/visual/judge.js";
import { bradleyTerry, callJudge, DEFAULT_JUDGES, DEGRADATIONS, degradeHtml, EXAM_MAX_INCONSISTENT, EXAM_PASS_SCORE, judgeLabel, judgeSelection, pool } from "../src/visual/panel.js";
import type { ModelSelection } from "../src/types.js";

const { values } = parseArgs({ options: { run: { type: "string", multiple: true }, package: { type: "string" }, out: { type: "string" }, judges: { type: "string" },
  concurrency: { type: "string", default: "4" }, "dry-run": { type: "boolean" } } });
if (!values.package || (!values.run?.length && !values.out)) throw new Error("usage: [--run runs/<id> ...] --package <vis v2 package> [--out DIR]");
const runDirectories = (values.run ?? []).map(run => resolve(run));
const packageDirectory = resolve(values.package);
const judges = (values.judges ? values.judges.split(",") : DEFAULT_JUDGES).map(judgeSelection);
const concurrency = Number(values.concurrency);
const root = resolve(values.out ?? join(runDirectories[0]!, "visual"));
const exists = (path: string) => access(path).then(() => true, () => false);
const grader = join(packageDirectory, "private", "grader.py");

type Item = { id: string; split: string };
const manifest = JSON.parse(await readFile(join(packageDirectory, "manifest.json"), "utf8")) as { id: string; version: string; items: Item[] };
const briefs = manifest.items.map(item => item.id);
const splitOf = Object.fromEntries(manifest.items.map(item => [item.id, item.split]));
const template = await readFile(join(packageDirectory, "private", "judge", "SKILL.md"), "utf8");
const STATE_NAMES: Record<string, string> = { unsaved: "the editor after an edit (unsaved)", error: "the error state", review: "the review step",
  "form-error": "the form after an invalid address", "form-success": "the form after a valid address", yearly: "the yearly prices", "phone-saved": "the phone page with one session saved",
  empty: "the empty state" };
const DEGRADED_BRIEFS = ["landing-fernwood", "dashboard"];

/** One page as the judges see it: its screenshots in the order the scenario took them. */
type Page = { id: string; brief: string; site: string; render: string; shots: string[] };
async function render(page: Omit<Page, "shots">, anchor?: "reference" | "plain"): Promise<Page> {
  const args = anchor ? [grader, "--anchor", anchor, "--brief", page.brief, "--out", resolve(page.render, ".."), "--launcher", sandboxLauncher]
    : [grader, "--render", page.site, "--brief", page.brief, "--out", page.render, "--launcher", sandboxLauncher];
  await mkdir(page.render, { recursive: true });
  await command("python3", args, packageDirectory, 300_000, 64_000);
  const shots = JSON.parse(await readFile(join(page.render, "screenshots.json"), "utf8").catch(() => "[]")) as string[];
  return { ...page, shots };
}
const rendered = (page: Page) => page.shots.includes("desktop");
const caption = (shots: string[]) => shots.map(name => name === "desktop" ? "desktop" : name === "phone" ? "phone" : STATE_NAMES[name] ?? name).join(", ");
const design = (page: Page) => (label: "A" | "B"): Design => ({ label, directory: page.render, screenshots: page.shots.map(name => join(page.render, `${name}.png`)), source: "",
  caption: caption(page.shots) });
async function skillFor(brief: string, shots: string[]): Promise<string> {
  const prompt = await readFile(join(packageDirectory, "items", brief, "prompt.md"), "utf8");
  return template.replace("{{BRIEF}}", `${prompt.trim()}\n\nStates shown: ${caption(shots.filter(name => name !== "desktop" && name !== "phone")) || "none"}.`);
}

// The anchors of every brief.
const anchors: Record<string, { reference: Page; plain: Page }> = {};
for (const brief of briefs) {
  const pages = {} as { reference: Page; plain: Page };
  for (const kind of ["reference", "plain"] as const) {
    const base = join(root, "anchors", brief, kind);
    pages[kind] = await render({ id: `anchor:${kind}`, brief, site: join(base, "site"), render: join(base, "render") }, kind);
    if (!rendered(pages[kind])) throw new Error(`ANCHOR_RENDER_FAILED:${brief}:${kind}`);
  }
  anchors[brief] = pages;
}

// The exam: the reference against the plain anchor on every brief; the reference against degraded copies on two briefs.
type ExamCase = { name: string; brief: string; good: Page; bad: Page };
const examCases: ExamCase[] = briefs.map(brief => ({ name: `${brief}:reference-vs-plain`, brief, good: anchors[brief]!.reference, bad: anchors[brief]!.plain }));
for (const brief of DEGRADED_BRIEFS.filter(name => briefs.includes(name))) {
  for (const kind of Object.keys(DEGRADATIONS)) {
    const base = join(root, "exam", `${brief}-${kind}`);
    await rm(base, { recursive: true, force: true });
    await cp(anchors[brief]!.reference.site, join(base, "site"), { recursive: true });
    await writeFile(join(base, "site", "index.html"), degradeHtml(await readFile(join(base, "site", "index.html"), "utf8"), kind));
    const bad = await render({ id: `exam:${kind}`, brief, site: join(base, "site"), render: join(base, "render") });
    if (rendered(bad)) examCases.push({ name: `${brief}:${kind}`, brief, good: anchors[brief]!.reference, bad });
  }
}

// The trials: one page per trial of a VIS v2 item.
type Trial = Page & { model: ModelSelection; label: string; delivered: boolean };
const trials: Trial[] = [];
for (const directory of runDirectories) {
  for (const record of await loadRecordedTrials(directory)) {
    if (!record.artifactManifest || record.execution.failureKind === "infrastructure" || !record.itemId || !briefs.includes(record.itemId)) continue;
    const site = join(directory, record.id, "artifacts", "site");
    const delivered = await exists(join(site, "index.html"));
    const page = { id: record.id, brief: record.itemId, site, render: join(root, "pages", record.id) };
    trials.push({ ...(delivered ? await render(page) : { ...page, shots: [] }), model: record.model, label: modelLabel(record.model), delivered });
  }
}
const sameModel = (left: Trial, right: Trial) => left.model.provider === right.model.provider && left.model.id === right.model.id;
const panelFor = (...models: ModelSelection[]) => judges.filter(judge => models.every(model => vendorOf(judge) !== vendorOf(model)));
type Pairing = { brief: string; a: Page; b: Page; aTrial: Trial | null; bTrial: Trial | null };
const pairings: Pairing[] = [];
for (const brief of briefs) {
  const own = trials.filter(trial => trial.brief === brief);
  for (const trial of own) for (const kind of ["plain", "reference"] as const) pairings.push({ brief, a: trial, b: anchors[brief]![kind], aTrial: trial, bTrial: null });
  for (let left = 0; left < own.length; left++) for (let right = left + 1; right < own.length; right++) {
    if (!sameModel(own[left]!, own[right]!)) pairings.push({ brief, a: own[left]!, b: own[right]!, aTrial: own[left]!, bTrial: own[right]! });
  }
}
const judgedPairing = (pairing: Pairing) => (!pairing.aTrial || pairing.aTrial.delivered) && (!pairing.bTrial || pairing.bTrial.delivered);
const panelOf = (pairing: Pairing) => panelFor(...[pairing.aTrial, pairing.bTrial].filter(Boolean).map(trial => trial!.model));
const examCalls = judges.length * examCases.length * 2;
const gameCalls = pairings.filter(judgedPairing).reduce((sum, pairing) => sum + panelOf(pairing).length * 2, 0);
const unrendered = trials.filter(trial => trial.delivered && !rendered(trial));
console.log(`briefs ${briefs.length}, anchors rendered ${briefs.length * 2}, exam cases ${examCases.length}, trials ${trials.length} ` +
  `(${trials.filter(trial => !trial.delivered).length} without a page, ${unrendered.length} not rendered), pairings ${pairings.length}, ` +
  `judge calls at most ${examCalls + gameCalls} (exam ${examCalls}, games ${gameCalls})`);
await mkdir(root, { recursive: true });
if (values["dry-run"]) {
  await writeFile(join(root, "tournament-dry-run.json"), JSON.stringify({ package: `${manifest.id} ${manifest.version}`, briefs, examCases: examCases.map(entry => entry.name),
    trials: trials.map(trial => ({ id: trial.id, brief: trial.brief, model: trial.label, delivered: trial.delivered, shots: trial.shots })), pairings: pairings.length,
    calls: { exam: examCalls, games: gameCalls }, anchors: Object.fromEntries(briefs.map(brief => [brief, { reference: anchors[brief]!.reference.shots, plain: anchors[brief]!.plain.shots }])) }, null, 1) + "\n");
  process.exit(0);
}
loadCredentials();

// The exam, per judge; only judges that pass it judge the games.
const examRows = await pool(judges.flatMap(judge => examCases.map(entry => async () => {
  const skill = await skillFor(entry.brief, entry.good.shots);
  const one = await callJudge(judge, skill, design(entry.good)("A"), design(entry.bad)("B"));
  const two = await callJudge(judge, skill, design(entry.bad)("A"), design(entry.good)("B"));
  return { judge: judgeLabel(judge), name: entry.name, ...combineOrders(one.verdict?.overall ?? null, two.verdict?.overall ?? null), usage: [one.usage, two.usage] };
})), concurrency);
const exam = judges.map(judge => {
  const own = examRows.filter(row => row.judge === judgeLabel(judge));
  const score = own.reduce((sum, row) => sum + (row.outcome === "win" ? 1 : row.outcome === "tie" ? 0.5 : 0), 0) / Math.max(1, own.length);
  const inconsistent = own.filter(row => row.inconsistent).length / Math.max(1, own.length);
  return { judge: judgeLabel(judge), score, inconsistent, passed: score >= EXAM_PASS_SCORE && inconsistent <= EXAM_MAX_INCONSISTENT,
    outcomes: Object.fromEntries(own.map(row => [row.name, row.outcome])), usage: own.flatMap(row => row.usage) };
});
const trusted = judges.filter(judge => exam.some(entry => entry.judge === judgeLabel(judge) && entry.passed));

// The games.
type Game = { brief: string; a: string; b: string; judge: string | null; outcome: "win" | "loss" | "tie" | "missing"; inconsistent: boolean;
  criteria: Record<string, string>; verdicts: Array<Verdict | null>; usage: Array<{ input: number; output: number }> };
const tasks: Array<() => Promise<Game>> = [];
for (const pairing of pairings) {
  const base = { brief: pairing.brief, a: pairing.a.id, b: pairing.b.id };
  if (!judgedPairing(pairing)) {
    const aMissing = pairing.aTrial && !pairing.aTrial.delivered, bMissing = pairing.bTrial && !pairing.bTrial.delivered;
    if (aMissing && bMissing) continue;
    tasks.push(async () => ({ ...base, judge: null, outcome: aMissing ? "loss" : "win", inconsistent: false, criteria: {}, verdicts: [], usage: [] }));
    continue;
  }
  if (!rendered(pairing.a) || !rendered(pairing.b)) continue;
  for (const judge of panelOf(pairing).filter(candidate => trusted.includes(candidate))) tasks.push(async () => {
    const skill = await skillFor(pairing.brief, pairing.b.shots.length >= pairing.a.shots.length ? pairing.b.shots : pairing.a.shots);
    const one = await callJudge(judge, skill, design(pairing.a)("A"), design(pairing.b)("B"));
    const two = await callJudge(judge, skill, design(pairing.b)("A"), design(pairing.a)("B"));
    const combined = combineOrders(one.verdict?.overall ?? null, two.verdict?.overall ?? null);
    const perCriterion = Object.fromEntries(criteria.map(name => [name, combineOrders(one.verdict?.criteria[name] as Choice ?? null, two.verdict?.criteria[name] as Choice ?? null).outcome]));
    return { ...base, judge: judgeLabel(judge), outcome: combined.outcome, inconsistent: combined.inconsistent, criteria: perCriterion, verdicts: [one.verdict, two.verdict],
      usage: [one.usage, two.usage] };
  });
}
const games = (await pool(tasks, concurrency)).filter(game => game.outcome !== "missing");
const SCORE = { win: 1, tie: 0.5, loss: 0 } as const;

/** 95% bootstrap interval of a mean, from 2,000 resamples with a fixed seed, so reruns report the same interval. */
function bootstrapInterval(values: number[]): [number, number] | null {
  if (values.length < 2) return null;
  let seed = 20261025;
  const random = () => { seed = (seed * 1103515245 + 12345) % 2147483648; return seed / 2147483648; };
  const means = Array.from({ length: 2000 }, () => {
    let sum = 0;
    for (let index = 0; index < values.length; index++) sum += values[Math.floor(random() * values.length)]!;
    return sum / values.length;
  }).sort((left, right) => left - right);
  return [means[50]!, means[1949]!];
}

// Per brief: Bradley–Terry over the brief's pages and anchors; ratings on the anchors' log-strength scale.
const perBrief = Object.fromEntries(briefs.map(brief => {
  const own = games.filter(game => game.brief === brief);
  const players = ["anchor:plain", "anchor:reference", ...trials.filter(trial => trial.brief === brief && trial.delivered && rendered(trial)).map(trial => trial.id),
    ...trials.filter(trial => trial.brief === brief && !trial.delivered).map(trial => trial.id)];
  const strength = bradleyTerry(players, own.map(game => ({ a: game.a, b: game.b, scoreA: SCORE[game.outcome as keyof typeof SCORE] })));
  const low = Math.log(strength["anchor:plain"]!), high = Math.log(strength["anchor:reference"]!);
  const scaleValid = high > low;
  const rating = Object.fromEntries(players.filter(player => !player.startsWith("anchor:")).map(player => [player, scaleValid ? (Math.log(strength[player]!) - low) / (high - low) : null]));
  return [brief, { split: splitOf[brief], games: own.length, strength, scaleValid, rating }];
}));

// Per model: the mean over repetitions per brief, then over briefs, per split; intervals by bootstrap over briefs.
const models = [...new Set(trials.map(trial => trial.label))].sort();
const byModel = models.map(model => {
  const ratingFor = (brief: string) => {
    const values = trials.filter(trial => trial.label === model && trial.brief === brief).map(trial => perBrief[brief]!.rating[trial.id]).filter((value): value is number => typeof value === "number");
    return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
  };
  const splits = Object.fromEntries(["dev", "validation"].map(split => {
    const values = briefs.filter(brief => splitOf[brief] === split).map(ratingFor).filter((value): value is number => value !== null);
    return [split, { briefs: values.length, rating: values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null, interval: bootstrapInterval(values) }];
  }));
  return { model, perBrief: Object.fromEntries(briefs.map(brief => [brief, ratingFor(brief)])), splits };
});

// Judge behaviour: order inconsistency per judge, and agreement between judges on the same pairing.
const judgeStats = trusted.map(judge => {
  const own = games.filter(game => game.judge === judgeLabel(judge));
  return { judge: judgeLabel(judge), games: own.length, inconsistent: own.filter(game => game.inconsistent).length / Math.max(1, own.length) };
});
const byPairing = new Map<string, Game[]>();
for (const game of games.filter(entry => entry.judge)) byPairing.set(`${game.a}|${game.b}`, [...(byPairing.get(`${game.a}|${game.b}`) ?? []), game]);
let agreeing = 0, compared = 0;
for (const group of byPairing.values()) for (let left = 0; left < group.length; left++) for (let right = left + 1; right < group.length; right++) {
  compared++;
  if (group[left]!.outcome === group[right]!.outcome) agreeing++;
}
const agreement = compared ? agreeing / compared : null;

// The user's calibration set (decision D5): up to 20 judged pairings spread over the briefs, contested ones first.
const contested = [...byPairing.values()].map(group => ({ group, split: new Set(group.map(game => game.outcome)).size }))
  .sort((left, right) => right.split - left.split || left.group[0]!.a.localeCompare(right.group[0]!.a));
const calibration: Array<{ brief: string; a: string; b: string; judges: Record<string, string> }> = [];
for (let round = 0; calibration.length < 20 && round < 20; round++) {
  for (const brief of briefs) {
    const next = contested.filter(entry => entry.group[0]!.brief === brief)[round];
    if (next && calibration.length < 20) calibration.push({ brief, a: next.group[0]!.a, b: next.group[0]!.b, judges: Object.fromEntries(next.group.map(game => [game.judge!, game.outcome])) });
  }
}
const pageById = new Map<string, Page>([...trials.map(trial => [trial.id, trial] as [string, Page])]);
const pagePath = (brief: string, id: string) => relative(root, (id.startsWith("anchor:") ? anchors[brief]![id.slice(7) as "plain" | "reference"] : pageById.get(id)!).render);

const usage = [...exam.flatMap(entry => entry.usage), ...games.flatMap(game => game.usage)].reduce((sum, entry) => ({ input: sum.input + entry.input, output: sum.output + entry.output }), { input: 0, output: 0 });
const report = { schema: "vis-v2-tournament", package: `${manifest.id} ${manifest.version}`, generatedAt: new Date().toISOString(), runs: runDirectories, exam, trusted: trusted.map(judgeLabel),
  perBrief, byModel, judges: judgeStats, agreement, calibration, unrendered: unrendered.map(trial => trial.id), games, usage };
await writeFile(join(root, "tournament.json"), JSON.stringify(report, null, 1) + "\n");
const fixed = (value: number | null) => value === null ? "—" : value.toFixed(2);
const lines = [`# VIS v2 tournament`, "", `Package ${manifest.id} ${manifest.version}; ${games.length} games; judges passing the exam: ${trusted.map(judgeLabel).join(", ") || "none"}; ` +
  `agreement between judges ${agreement === null ? "—" : `${(agreement * 100).toFixed(0)}%`}; judge tokens ${usage.input} in, ${usage.output} out.`, "",
  "Rating: plain anchor 0, reference anchor 1 (Bradley–Terry log-strength), uncapped; mean over briefs with a 95% bootstrap interval over briefs.", "",
  "| Model | Dev | Dev interval | Validation | Validation interval |", "| --- | ---: | --- | ---: | --- |",
  ...byModel.map(row => `| ${row.model} | ${fixed(row.splits.dev!.rating)} | ${row.splits.dev!.interval ? row.splits.dev!.interval.map(fixed).join("–") : "—"} | ` +
    `${fixed(row.splits.validation!.rating)} | ${row.splits.validation!.interval ? row.splits.validation!.interval.map(fixed).join("–") : "—"} |`), "",
  "## Per brief", "", `| Model | ${briefs.join(" | ")} |`, `| --- |${briefs.map(() => " ---: |").join("")}`,
  ...byModel.map(row => `| ${row.model} | ${briefs.map(brief => fixed(row.perBrief[brief] ?? null)).join(" | ")} |`), "",
  ...briefs.filter(brief => !perBrief[brief]!.scaleValid).map(brief => `- ${brief}: the judges did not prefer the reference over the plain anchor; no rating.`), "",
  "## Judge exam", "", "| Judge | Score | Order flips | Passed |", "| --- | ---: | ---: | --- |",
  ...exam.map(entry => `| ${entry.judge} | ${entry.score.toFixed(2)} | ${(entry.inconsistent * 100).toFixed(0)}% | ${entry.passed ? "yes" : "no"} |`), ""];
await writeFile(join(root, "tournament.md"), lines.join("\n"));
await writeFile(join(root, "calibration-pairs.csv"), ["pair,brief,a,b,a_screens,b_screens,your_verdict(A|B|tie)",
  ...calibration.map((entry, index) => `${index + 1},${entry.brief},${entry.a},${entry.b},${pagePath(entry.brief, entry.a)},${pagePath(entry.brief, entry.b)},`)].join("\n") + "\n");
await writeFile(join(root, "calibration-pairs.md"), ["# VIS v2 calibration pairs", "", "For each pair, open both pages' screenshots (paths relative to this file) and write A, B or tie in `calibration-pairs.csv`. Judges' combined verdicts are in `tournament.json`.", "",
  ...calibration.map((entry, index) => `${index + 1}. ${entry.brief}: A = \`${pagePath(entry.brief, entry.a)}\`, B = \`${pagePath(entry.brief, entry.b)}\``), ""].join("\n"));
console.log(`wrote ${relative(process.cwd(), join(root, "tournament.md"))}`);
