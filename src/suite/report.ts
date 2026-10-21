import type { FamilyModelResult, FamilyUnit, NotRunUnit } from "./score.js";
import type { FamilySpec, SuiteFile } from "./spec.js";

export interface FailedCheck {
  id: string;
  failed: number;
  judged: number;
  /** Up to two failing units, with a grader reason where the grader gives one. */
  samples: Array<{ label: string; trial: string; item: string | null; reason: string | null }>;
}

export interface FamilyReport {
  id: string;
  kind: FamilySpec["kind"];
  template: string;
  score: FamilySpec["score"] | null;
  adjustments: string[];
  results: FamilyModelResult[];
  notRun: NotRunUnit[];
  infrastructure: Array<Pick<FamilyUnit, "label" | "trialId" | "itemId" | "outcome" | "providerError" | "runDirectory">>;
  providerStops: Record<string, string>;
  failedChecks: FailedCheck[];
  runDirectories: string[];
  /** Visual families: where the tournament wrote its results, or why it did not run. */
  tournament?: { path: string | null; error: string | null };
}

export interface SuiteFlag { kind: "target-above" | "saturated" | "budget-stops" | "infrastructure" | "provider-stopped" | "unscored" | "family-failed"; family: string | null; detail: string }

export interface SuiteReport {
  schemaVersion: 1;
  suite: string;
  id: string;
  commit: string;
  models: string[];
  repetitions: number;
  startedAt: string;
  finishedAt: string;
  status: "completed" | "failed";
  families: FamilyReport[];
  flags: SuiteFlag[];
  tokens: Record<string, Record<string, number>>;
  phases: Record<string, string>;
  /** Worst-case tokens computed at preflight. */
  estimate: { byModel: Record<string, number>; byHost: Record<string, number>; notes: string[] } | null;
  smoke: Record<string, { ok: boolean; detail: string; directory: string | null }>;
  /** Main-tree changes left out of the frozen worktree. */
  uncommitted: string[];
}

const SATURATED = 0.9;
const INFRASTRUCTURE_RATE = 0.1;

/** The report flags of PLAN-006: what a reader must look at before trusting the numbers. */
export function suiteFlags(suite: Pick<SuiteFile, "target">, families: FamilyReport[], specs: Map<string, FamilySpec>): SuiteFlag[] {
  const flags: SuiteFlag[] = [];
  const percent = (value: number) => `${(value * 100).toFixed(1)}%`;
  for (const family of families) {
    const spec = specs.get(family.id);
    const scored = family.results.filter(result => result.meanScore !== null);
    const target = suite.target ? scored.find(result => result.model === suite.target!.model.split("?")[0]) : undefined;
    if (target && target.meanScore! > suite.target!.maxScore) {
      flags.push({ kind: "target-above", family: family.id, detail: `${target.label} scores ${percent(target.meanScore!)}, above ${percent(suite.target!.maxScore)}` });
    }
    if (scored.length && scored.every(result => result.meanScore! >= SATURATED)) {
      flags.push({ kind: "saturated", family: family.id, detail: `every model at or above ${percent(SATURATED)}` });
    }
    if (!spec?.openEnded) {
      for (const result of family.results) {
        const counted = result.units - result.infrastructureFailures;
        if (counted > 0 && result.budgetStops * 2 > counted) {
          flags.push({ kind: "budget-stops", family: family.id, detail: `${result.label}: ${result.budgetStops} of ${counted} trials stopped by a budget` });
        }
      }
    }
    const units = family.results.reduce((sum, result) => sum + result.units, 0);
    const infrastructure = family.results.reduce((sum, result) => sum + result.infrastructureFailures, 0);
    if (units && infrastructure / units > INFRASTRUCTURE_RATE) {
      flags.push({ kind: "infrastructure", family: family.id, detail: `${infrastructure} of ${units} trials failed on infrastructure (${percent(infrastructure / units)})` });
    }
    for (const result of family.results) {
      if (result.unscored) flags.push({ kind: "unscored", family: family.id, detail: `${result.label}: ${result.unscored} trials without a score (evaluator error or resource limit); audit them` });
    }
  }
  const stops = new Map<string, Set<string>>();
  for (const family of families) {
    for (const [provider, reason] of Object.entries(family.providerStops)) {
      const key = `${provider}: ${reason}`;
      stops.set(key, (stops.get(key) ?? new Set()).add(family.id));
    }
  }
  for (const [stop, ids] of stops) flags.push({ kind: "provider-stopped", family: null, detail: `${stop} (in ${[...ids].join(", ")})` });
  return flags;
}

/** The most-failed checks of a family across its scored units, with sample failing trials. */
export function failedChecks(units: FamilyUnit[], reason: (unit: FamilyUnit, checkId: string) => string | null, limit = 8): FailedCheck[] {
  const counted = units.filter(unit => !unit.infrastructure && unit.score !== null);
  const ids = [...new Set(counted.flatMap(unit => [...unit.failedChecks, ...unit.passedChecks]))];
  return ids.map(id => {
    const failing = counted.filter(unit => unit.failedChecks.includes(id));
    return {
      id, failed: failing.length, judged: counted.filter(unit => unit.failedChecks.includes(id) || unit.passedChecks.includes(id)).length,
      samples: failing.slice(0, 2).map(unit => ({ label: unit.label, trial: `${unit.runDirectory}/${unit.trialId}`, item: unit.itemId, reason: reason(unit, id) })),
    };
  }).filter(check => check.failed > 0).sort((left, right) => right.failed - left.failed || left.id.localeCompare(right.id)).slice(0, limit);
}

const percent = (value: number | null | undefined) => value === null || value === undefined ? "n/a" : `${(value * 100).toFixed(1)}%`;
const interval = (value: [number, number] | null) => value ? `${percent(value[0])}–${percent(value[1])}` : "n/a";
const thousands = (value: number | null) => value === null ? "n/a" : `${(value / 1000).toFixed(0)}k`;
const cell = (value: string | null | undefined) => (value ?? "").replace(/\|/g, "\\|").replace(/\s+/g, " ").slice(0, 300);

export function markdownSuiteReport(report: SuiteReport): string {
  const lines = [`# Suite report: ${report.suite}`, "",
    `Suite run \`${report.id}\` at commit \`${report.commit.slice(0, 12)}\`, ${report.repetitions} repetition(s) per model and item, ${report.startedAt} to ${report.finishedAt}. Status: **${report.status}**.`, "",
    `Models: ${report.models.join(", ")}.`, "",
    "A family score is the mean partial-credit score of its scored trials (for E3, of its trajectories; for the visual family, the tournament win rate). Infrastructure failures are excluded and listed below; trials without a score are counted, never treated as zero. The interval is the Wilson interval of the score sum.", ""];
  lines.push("## Flags", "");
  if (!report.flags.length) lines.push("None.", "");
  else lines.push(...report.flags.map(flag => `- **${flag.kind}**${flag.family ? ` (${flag.family})` : ""}: ${flag.detail}`), "");

  const labels = [...new Set(report.families.flatMap(family => family.results.map(result => result.label)))];
  lines.push("## Scores across families", "", `| Model | ${report.families.map(family => family.id).join(" | ")} |`, `| --- |${report.families.map(() => " ---: |").join("")}`);
  for (const label of labels) {
    lines.push(`| ${label} | ${report.families.map(family => {
      const result = family.results.find(entry => entry.label === label);
      const value = family.kind === "visual" ? result?.winRate : result?.meanScore;
      return result ? `${percent(value)}${result.scored !== result.units ? ` (${result.scored}/${result.units})` : ""}` : "—";
    }).join(" | ")} |`);
  }
  lines.push("", "Bracketed figures are scored trials out of recorded ones, where they differ.", "");

  for (const family of report.families) {
    lines.push(`## ${family.id} (${family.kind})`, "", `Template \`${family.template}\`; scored on ${family.score ? (family.score.items ? `items ${family.score.items.join(", ")}` : `levels ${family.score.levels!.join(", ")}`) : "every trial"}. Runs: ${family.runDirectories.map(directory => `\`${directory}\``).join(", ") || "none"}.`, "");
    if (family.adjustments.length) lines.push(`Template adjusted to the standing rules: ${family.adjustments.join("; ")}.`, "");
    lines.push("| Model | Score | 95% interval | Resolved | Median tokens | Budget stops | Infrastructure | Not run | Unscored |" + (family.kind === "visual" ? " Win rate |" : ""),
      "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |" + (family.kind === "visual" ? " ---: |" : ""),
      ...family.results.map(result => `| ${result.label} | ${percent(result.meanScore)} | ${interval(result.interval)} | ${result.resolved}/${result.decided} | ${thousands(result.medianTokens)} | ${result.budgetStops} | ${result.infrastructureFailures} | ${result.notRun} | ${result.unscored} |` +
        (family.kind === "visual" ? ` ${percent(result.winRate)} |` : "")), "");
    if (family.tournament?.error) lines.push(`Tournament: not available (${family.tournament.error}).`, "");
    if (family.failedChecks.length) {
      lines.push("Most-failed checks:", "", "| Check | Failed / judged | Samples |", "| --- | ---: | --- |",
        ...family.failedChecks.map(check => `| ${check.id} | ${check.failed}/${check.judged} | ${check.samples.map(sample => `${sample.label}${sample.item ? ` ${sample.item}` : ""}: ${sample.reason ? cell(sample.reason) : `\`${sample.trial}\``}`).join("; ")} |`), "");
    }
  }

  const notRun = report.families.flatMap(family => family.notRun);
  lines.push("## Not run", "");
  if (!notRun.length) lines.push("None.", "");
  else lines.push("| Family | Model | Item | Repetition | Reason |", "| --- | --- | --- | ---: | --- |",
    ...notRun.map(entry => `| ${entry.familyId} | ${entry.model} | ${entry.itemId ?? "—"} | ${entry.repetition} | ${entry.reason ?? "unknown"} |`), "");
  const infrastructure = report.families.flatMap(family => family.infrastructure.map(entry => ({ family: family.id, ...entry })));
  lines.push("## Infrastructure failures", "");
  if (!infrastructure.length) lines.push("None.", "");
  else lines.push("| Family | Model | Item | Outcome | Provider error |", "| --- | --- | --- | --- | --- |",
    ...infrastructure.map(entry => `| ${entry.family} | ${entry.label} | ${entry.itemId ?? "—"} | ${entry.outcome} | ${cell(entry.providerError) || "—"} |`), "");

  lines.push("## Tokens by model", "", "Reported tokens in thousands, every scored or failed trial included; fixed units without prices.", "",
    `| Model | ${report.families.map(family => family.id).join(" | ")} | Total |`, `| --- |${report.families.map(() => " ---: |").join("")} ---: |`);
  for (const [label, byFamily] of Object.entries(report.tokens)) {
    const total = Object.values(byFamily).reduce((sum, value) => sum + value, 0);
    lines.push(`| ${label} | ${report.families.map(family => thousands(byFamily[family.id] ?? 0)).join(" | ")} | ${thousands(total)} |`);
  }
  if (report.estimate) {
    lines.push("", `Worst-case estimate at preflight (every trial using its whole budget): ${Object.entries(report.estimate.byModel).map(([label, value]) => `${label} ${thousands(value)}`).join(", ")}.`);
  }
  lines.push("", "## Phases", "", ...Object.entries(report.phases).map(([phase, status]) => `- ${phase}: ${status}`), "");
  lines.push("Null-agent smoke:", "", ...Object.entries(report.smoke).map(([family, result]) => `- ${family}: ${result.ok ? "passed" : "failed"} (${result.detail})`), "");
  if (report.uncommitted.length) lines.push(`Uncommitted main-tree changes not in this suite: ${report.uncommitted.join(", ")}.`, "");
  return lines.join("\n");
}
