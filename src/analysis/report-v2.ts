import { createHash } from "node:crypto";
import type { OutcomeRecord, Stop } from "../scoring/model.js";
import { capabilityMean, familyMean, saturation, taskScores, taskWeights, type Saturation, type TaskScore } from "../scoring/aggregate.js";
import { combineResamples, familyResamples, intervalOf, pairedComparison, type Interval } from "../scoring/bootstrap.js";

/**
 * The suite report v2 (MEASUREMENT §7, PLAN-007 WP1.5): a capability profile per model, family tables, pairwise
 * comparisons, saturation and headroom, efficiency and audit status, every number from the trials' outcome records.
 * A dry run is never a result; the report is labelled exploratory where the sample is small.
 */

export interface V2FamilyData {
  id: string;
  tier: "basic" | "core" | "frontier";
  capability: "engineering" | "reasoning" | "agentic" | "visual";
  openEnded: boolean;
  structureCap: number;
  packageId: string;
  taskVersion: string;
  primaryKind: "resolved" | "metric" | "rating";
  /** A core family reported as its own row and never averaged into its capability (AR with code beside AR answer-only). */
  ownRow?: boolean;
  outcomes: OutcomeRecord[];
  /** Tasks the plan gives each model, by model label. */
  plannedTasks: Record<string, number>;
  notRun: Record<string, number>;
  protocol: { budget: string; contextPolicy: string; tools: string; commandLimits: string };
  runDirectories: string[];
}

export interface ReportV2Input {
  suite: string;
  id: string;
  release: string | null;
  split: string | null;
  track: string;
  commit: string;
  startedAt: string;
  finishedAt: string;
  status: "completed" | "failed";
  models: Array<{ label: string; thinking: string; temperature: number | null }>;
  repetitions: number;
  capabilityWeights: Record<string, Record<string, number>>;
  families: V2FamilyData[];
  /** The latest audit per family: date and verdict counts (docs/audits/<family>/<date>.json). */
  audits: Record<string, { date: string; summary: Record<string, number> } | null>;
}

export interface FamilyModelRow {
  label: string;
  tasks: number;
  trials: number;
  coverage: { scored: number; unscored: number; notRun: number; planned: number; share: number | null };
  complete: boolean;
  resolvedRate: number | null;
  primary: number | null;
  interval: Interval;
  diagnostic: number | null;
  metrics: Record<string, number | null>;
  format: { strict: number; recovered: number; missing: number; penalised: number | null };
  stops: Partial<Record<Stop, number>>;
  infrastructure: number;
  refusals: number;
  efficiency: { medianTokens: number | null; medianWallMs: number | null; medianModelCalls: number | null; tokensPerResolved: number | null };
}

export interface ReportV2 {
  schemaVersion: 1;
  suite: string;
  id: string;
  release: string | null;
  split: string | null;
  track: string;
  commit: string;
  startedAt: string;
  finishedAt: string;
  status: "completed" | "failed";
  exploratory: boolean;
  models: ReportV2Input["models"];
  repetitions: number;
  profile: Array<{ label: string; capabilities: Record<string, { primary: number | null; interval: Interval; tasks: number; families: string[] }>;
    rows: Record<string, { tier: string; primary: number | null; interval: Interval; tasks: number }> }>;
  families: Array<{ id: string; tier: string; capability: string; openEnded: boolean; packageId: string; taskVersion: string; primaryKind: string;
    protocol: V2FamilyData["protocol"]; rows: FamilyModelRow[]; saturation: Saturation; runDirectories: string[];
    audit: { date: string; summary: Record<string, number> } | null }>;
  comparisons: Array<{ capability: string; modelA: string; modelB: string; tasks: number; meanDifference: number | null; interval: Interval;
    ahead: { a: number; b: number; tie: number } }>;
}

const COVERAGE_REQUIRED = 0.9;

/** Seeds derive from the suite id, family and models, so a rebuilt report gives the same intervals. */
function seedOf(...parts: string[]): number {
  return createHash("sha256").update(parts.join("\u0000")).digest().readUInt32BE(0);
}

const median = (values: number[]) => {
  if (!values.length) return null;
  const sorted = [...values].sort((left, right) => left - right);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle]! : (sorted[middle - 1]! + sorted[middle]!) / 2;
};
const mean = (values: number[]) => values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;

function familyRow(family: V2FamilyData, label: string, tasks: TaskScore[], seed: string): FamilyModelRow {
  const own = family.outcomes.filter(outcome => outcome.model === label);
  const scored = own.filter(outcome => outcome.coverage === "scored");
  const mine = tasks.filter(task => task.model === label);
  const withScore = mine.filter(task => task.primary !== null);
  const planned = family.plannedTasks[label] ?? mine.length;
  const metricIds = [...new Set(own.flatMap(outcome => outcome.metrics.map(metric => metric.id)))].sort();
  const stops: Partial<Record<Stop, number>> = {};
  for (const outcome of own) stops[outcome.stop] = (stops[outcome.stop] ?? 0) + 1;
  const resolvedTasks = withScore.filter(task => task.resolvedRate === 1).length;
  const tokens = scored.map(outcome => outcome.usage.totalTokens).filter((value): value is number => value !== null);
  return {
    label, tasks: mine.length, trials: own.length,
    coverage: { scored: scored.length, unscored: own.length - scored.length, notRun: family.notRun[label] ?? 0, planned, share: planned ? withScore.length / planned : null },
    complete: planned > 0 && withScore.length / planned >= COVERAGE_REQUIRED,
    // Weighted like the primary (equal tasks, structure groups capped), so that for a resolved-primary family the two agree.
    resolvedRate: withScore.length ? (() => { const weights = taskWeights(withScore, family.structureCap);
      return withScore.reduce((sum, task) => sum + weights.get(task.task)! * (task.resolvedRate ?? 0), 0); })() : null,
    primary: familyMean(mine, family.structureCap),
    interval: intervalOf(familyResamples(mine, seedOf(seed, family.id, label), family.structureCap)),
    diagnostic: mean(scored.map(outcome => outcome.diagnostic).filter((value): value is number => value !== null)),
    metrics: Object.fromEntries(metricIds.map(id => [id, median(scored.flatMap(outcome => outcome.metrics.filter(metric => metric.id === id).map(metric => metric.value)))])),
    format: { strict: scored.filter(outcome => outcome.format.status === "strict").length, recovered: scored.filter(outcome => outcome.format.status === "recovered").length,
      missing: scored.filter(outcome => outcome.format.status === "missing").length,
      penalised: mean(scored.map(outcome => outcome.format.penalised).filter((value): value is number => value !== null)) },
    stops, infrastructure: own.filter(outcome => outcome.coverageReason === "infrastructure").length,
    refusals: own.filter(outcome => outcome.coverageReason === "provider_refusal").length,
    efficiency: { medianTokens: median(tokens), medianWallMs: median(scored.map(outcome => outcome.usage.wallMs)), medianModelCalls: median(scored.map(outcome => outcome.usage.modelCalls)),
      tokensPerResolved: resolvedTasks ? tokens.reduce((sum, value) => sum + value, 0) / resolvedTasks : null },
  };
}

export function buildReportV2(input: ReportV2Input): ReportV2 {
  const labels = input.models.map(model => model.label);
  const scores = new Map(input.families.map(family => [family.id, taskScores(family.outcomes.filter(outcome => outcome.coverage !== "not_run"))]));
  const families = input.families.map(family => ({
    id: family.id, tier: family.tier, capability: family.capability, openEnded: family.openEnded, packageId: family.packageId, taskVersion: family.taskVersion,
    primaryKind: family.primaryKind, protocol: family.protocol, runDirectories: family.runDirectories,
    // A model that neither ran nor was planned on a family (a reference pseudo-model, say) has no row there.
    rows: labels.filter(label => family.outcomes.some(outcome => outcome.model === label) || (family.plannedTasks[label] ?? 0) > 0)
      .map(label => familyRow(family, label, scores.get(family.id)!, input.id)),
    // Saturation reads the models that took part in the family.
    saturation: saturation(scores.get(family.id)!, labels.filter(label => family.outcomes.some(outcome => outcome.model === label)), family.openEnded, family.structureCap),
    audit: input.audits[family.id] ?? null,
  }));
  const core = input.families.filter(family => family.tier === "core" && !family.ownRow);
  const capabilities = [...new Set(core.map(family => family.capability))].sort();
  const weightsOf = (capability: string) => {
    const declared = input.capabilityWeights[capability] ?? {};
    const members = core.filter(family => family.capability === capability);
    return Object.fromEntries(members.map(family => [family.id, declared[family.id] ?? 1 / members.length]));
  };
  const profile = labels.map(label => {
    const byCapability: ReportV2["profile"][number]["capabilities"] = {};
    for (const capability of capabilities) {
      const weights = weightsOf(capability);
      const members = core.filter(family => family.capability === capability);
      const means = Object.fromEntries(members.map(family => [family.id, familyMean(scores.get(family.id)!.filter(task => task.model === label), family.structureCap)]));
      const parts = members.filter(family => means[family.id] !== null).map(family => ({ weight: weights[family.id]!,
        values: familyResamples(scores.get(family.id)!.filter(task => task.model === label), seedOf(input.id, family.id, label), family.structureCap) }));
      byCapability[capability] = { primary: capabilityMean(means, weights), interval: intervalOf(combineResamples(parts)), families: members.map(family => family.id),
        tasks: members.reduce((sum, family) => sum + scores.get(family.id)!.filter(task => task.model === label && task.primary !== null).length, 0) };
    }
    const rows: ReportV2["profile"][number]["rows"] = {};
    for (const family of input.families.filter(entry => entry.tier !== "core" || entry.ownRow)) {
      const row = families.find(entry => entry.id === family.id)!.rows.find(entry => entry.label === label);
      if (row) rows[family.id] = { tier: family.tier, primary: row.primary, interval: row.interval, tasks: row.tasks };
    }
    return { label, capabilities: byCapability, rows };
  });
  const comparisons: ReportV2["comparisons"] = [];
  for (const capability of capabilities) {
    const weights = weightsOf(capability);
    const members = core.filter(family => family.capability === capability);
    for (let left = 0; left < labels.length; left++) {
      for (let right = left + 1; right < labels.length; right++) {
        const parts = members.map(family => ({ family, comparison: pairedComparison(scores.get(family.id)!, labels[left]!, labels[right]!,
          seedOf(input.id, family.id, labels[left]!, labels[right]!), family.structureCap) })).filter(part => part.comparison.tasks > 0);
        const tasks = parts.reduce((sum, part) => sum + part.comparison.tasks, 0);
        if (!tasks) continue;  // the two models share no task of this capability
        const total = parts.reduce((sum, part) => sum + weights[part.family.id]!, 0);
        const ahead = (key: "a" | "b" | "tie") => tasks ? parts.reduce((sum, part) => sum + part.comparison.ahead[key] * part.comparison.tasks, 0) / tasks : 0;
        comparisons.push({
          capability, modelA: labels[left]!, modelB: labels[right]!, tasks,
          meanDifference: total ? parts.reduce((sum, part) => sum + weights[part.family.id]! * part.comparison.meanDifference!, 0) / total : null,
          interval: intervalOf(combineResamples(parts.map(part => ({ weight: weights[part.family.id]!, values: part.comparison.resamples })))),
          ahead: { a: ahead("a"), b: ahead("b"), tie: ahead("tie") },
        });
      }
    }
  }
  const exploratory = input.split !== "validation" && input.split !== "holdout" ||
    families.some(family => family.rows.some(row => row.primary !== null && row.interval === "n too small"));
  return {
    schemaVersion: 1, suite: input.suite, id: input.id, release: input.release, split: input.split, track: input.track, commit: input.commit,
    startedAt: input.startedAt, finishedAt: input.finishedAt, status: input.status, exploratory, models: input.models, repetitions: input.repetitions,
    profile, families, comparisons,
  };
}

// Markdown.

const percent = (value: number | null | undefined) => value === null || value === undefined ? "n/a" : `${(value * 100).toFixed(1)}%`;
const number = (value: number | null | undefined, digits = 3) => value === null || value === undefined ? "n/a" : `${+value.toFixed(digits)}`;
const thousands = (value: number | null) => value === null ? "n/a" : `${Math.round(value / 1000)}k`;
const span = (interval: Interval, format: (value: number) => string) => interval === "n too small" ? "n too small" : `${format(interval.low)}–${format(interval.high)}`;

/** Resolved-primary families read as percentages; open-ended ones as normalised values, which may pass 1. */
function primaryText(kind: string, value: number | null): string {
  return kind === "resolved" ? percent(value) : number(value);
}

export function markdownReportV2(report: ReportV2): string {
  const lines: string[] = [
    `# Suite report v2: ${report.suite}${report.release ? ` (${report.release})` : ""}`, "",
    ...(report.exploratory ? ["**Exploratory.** Dev split or fewer than five structure groups in some family: differences here are not conclusions.", ""] : []),
    `Suite run \`${report.id}\` at commit \`${report.commit.slice(0, 12)}\`; split ${report.split ?? "unspecified"}; track ${report.track}; ${report.repetitions} repetition(s); ${report.startedAt} to ${report.finishedAt}; status **${report.status}**.`, "",
    "| Model | Thinking | Temperature |", "| --- | --- | --- |",
    ...report.models.map(model => `| ${model.label} | ${model.thinking} | ${model.temperature ?? "provider default"} |`), "",
    "| Family | Tier | Capability | Package | Budget | Context | Tools | Command limits |", "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ...report.families.map(family => `| ${family.id} | ${family.tier} | ${family.capability} | ${family.packageId}@${family.taskVersion} | ${family.protocol.budget} | ${family.protocol.contextPolicy} | ${family.protocol.tools} | ${family.protocol.commandLimits} |`), "",
    "Every number below comes from the trials' outcome records (MEASUREMENT §2). A task is the sample: intervals resample structure groups (2,000 seeded resamples, 95% percentile) and are not given below five groups. Resolved-primary families read as the share of tasks resolved; open-ended families as a normalised value through the family's anchors, which is not capped at 1. Efficiency is reported, never scored.", "",
    "## Capability profile", "",
  ];
  const capabilities = [...new Set(report.profile.flatMap(entry => Object.keys(entry.capabilities)))];
  if (capabilities.length) {
    lines.push(`| Model | ${capabilities.map(capability => `${capability} (core)`).join(" | ")} |`, `| --- |${capabilities.map(() => " --- |").join("")}`,
      ...report.profile.filter(entry => capabilities.some(capability => entry.capabilities[capability]!.tasks > 0)).map(entry => `| ${entry.label} | ${capabilities.map(capability => {
        const value = entry.capabilities[capability]!;
        return `${number(value.primary)} [${span(value.interval, value => number(value))}], ${value.tasks} tasks`;
      }).join(" | ")} |`), "");
  } else lines.push("No core family in this suite.", "");
  const others = [...new Set(report.profile.flatMap(entry => Object.keys(entry.rows)))];
  if (others.length) {
    lines.push("Families reported as their own rows and never averaged into the core (basic, frontier, and core families of a second protocol):", "",
      `| Model | ${others.map(id => `${id} (${report.families.find(family => family.id === id)!.tier})`).join(" | ")} |`, `| --- |${others.map(() => " --- |").join("")}`,
      ...report.profile.map(entry => `| ${entry.label} | ${others.map(id => {
        const row = entry.rows[id];
        const kind = report.families.find(family => family.id === id)!.primaryKind;
        return row ? `${primaryText(kind, row.primary)} [${span(row.interval, value => primaryText(kind, value))}]` : "—";
      }).join(" | ")} |`), "");
  }
  lines.push("## Families", "");
  for (const family of report.families) {
    const metricIds = [...new Set(family.rows.flatMap(row => Object.keys(row.metrics)))];
    lines.push(`### ${family.id} (${family.tier}, ${family.capability})`, "",
      `Primary: ${family.primaryKind === "resolved" ? "resolved rate" : family.primaryKind === "metric" ? "normalised metric, uncapped" : "rating"}. Runs: ${family.runDirectories.map(path => `\`${path}\``).join(", ") || "none"}.`, "",
      `| Model | Tasks | Trials | Coverage | Resolved | Primary | 95% interval | Diagnostic |${metricIds.map(id => ` ${id} (median) |`).join("")} Format strict / recovered / missing | Penalised | Stops | Infra / refusals |`,
      `| --- | ---: | ---: | --- | ---: | ---: | --- | ---: |${metricIds.map(() => " ---: |").join("")} --- | ---: | --- | --- |`,
      ...family.rows.map(row => `| ${row.label} | ${row.tasks} | ${row.trials} | ${row.coverage.scored} scored, ${row.coverage.unscored} unscored, ${row.coverage.notRun} not run of ${row.coverage.planned} planned${row.complete ? "" : " **(incomplete)**"} | ${percent(row.resolvedRate)} | ${primaryText(family.primaryKind, row.primary)} | ${span(row.interval, value => primaryText(family.primaryKind, value))} | ${percent(row.diagnostic)} |${metricIds.map(id => ` ${number(row.metrics[id] ?? null, 3)} |`).join("")} ${row.format.strict} / ${row.format.recovered} / ${row.format.missing} | ${primaryText(family.primaryKind, row.format.penalised)} | ${Object.entries(row.stops).map(([stop, count]) => `${stop} ${count}`).join(", ") || "—"} | ${row.infrastructure} / ${row.refusals} |`), "");
  }
  lines.push("## Pairwise comparisons", "", "Per core capability, paired by task: A − B in the capability's primary, with a stratified cluster-bootstrap interval and the share of tasks each model is ahead.", "");
  if (report.comparisons.length) {
    lines.push("| Capability | A | B | Tasks | A − B | 95% interval | A ahead | B ahead | Tied |", "| --- | --- | --- | ---: | ---: | --- | ---: | ---: | ---: |",
      ...report.comparisons.map(entry => `| ${entry.capability} | ${entry.modelA} | ${entry.modelB} | ${entry.tasks} | ${number(entry.meanDifference)} | ${span(entry.interval, value => number(value))} | ${percent(entry.ahead.a)} | ${percent(entry.ahead.b)} | ${percent(entry.ahead.tie)} |`), "");
  } else lines.push("None (no core family, or a single model).", "");
  lines.push("## Saturation and headroom", "", "| Family | Tasks scored for every model | Solved by all | Solved by none | Best above the strong anchor | Spread |", "| --- | ---: | ---: | ---: | ---: | ---: |",
    ...report.families.map(family => `| ${family.id} | ${family.saturation.tasks} | ${family.openEnded ? "—" : family.saturation.solvedByAll} | ${family.openEnded ? "—" : family.saturation.solvedByNone} | ${family.openEnded ? family.saturation.bestAboveStrong : "—"} | ${number(family.saturation.spread)} |`), "");
  lines.push("## Efficiency", "", "Medians per scored trial; tokens are fixed units without prices, cached input counted in full. Reported, never scored.", "",
    "| Family | Model | Tokens | Wall time (s) | Model calls | Tokens per resolved task |", "| --- | --- | ---: | ---: | ---: | ---: |",
    ...report.families.flatMap(family => family.rows.map(row => `| ${family.id} | ${row.label} | ${thousands(row.efficiency.medianTokens)} | ${row.efficiency.medianWallMs === null ? "n/a" : (row.efficiency.medianWallMs / 1000).toFixed(0)} | ${number(row.efficiency.medianModelCalls, 0)} | ${thousands(row.efficiency.tokensPerResolved)} |`)), "");
  lines.push("## Audit status", "", "| Family | Latest success audit | Verdicts |", "| --- | --- | --- |",
    ...report.families.map(family => `| ${family.id} | ${family.audit?.date ?? "none"} | ${family.audit ? Object.entries(family.audit.summary).map(([verdict, count]) => `${verdict} ${count}`).join(", ") : "—"} |`), "");
  return lines.join("\n");
}
