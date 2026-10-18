import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { resolveModel } from "../harness/pi.js";
import { apiKeyEnvFor, lookupModelConfig } from "../providers.js";
import type { ModelSelection } from "../types.js";

export const criteria = ["fit", "hierarchy", "layout", "typography", "color", "responsive", "form", "polish"] as const;
export type Choice = "A" | "B" | "tie";
export interface Verdict {
  criteria: Record<(typeof criteria)[number], Choice>;
  overall: Choice;
  confidence: "low" | "medium" | "high";
  reasons: string;
}

/** A rendered design as the judge sees it: screenshots and a source excerpt. */
export interface Design {
  label: string;
  directory: string;
  screenshots: string[];
  source: string;
}

const choices = new Set(["A", "B", "tie"]);
const SOURCE_LIMIT = 6_000;

/** The vendor behind a model, so that no judge rates a page from its own vendor. */
export function vendorOf(model: ModelSelection): string {
  const id = model.id.toLowerCase();
  if (id.startsWith("gpt") || model.provider === "openai") return "openai";
  if (id.startsWith("glm")) return "zhipu";
  if (id.startsWith("step")) return "stepfun";
  if (id.startsWith("kimi")) return "moonshot";
  if (id.startsWith("deepseek")) return "deepseek";
  if (id.startsWith("qwen")) return "alibaba";
  if (id.startsWith("claude") || model.provider === "anthropic") return "anthropic";
  return model.id;
}

/** Collect a design's screenshots (in a fixed order) and a bounded excerpt of its HTML and CSS. */
export async function loadDesign(label: string, renderDirectory: string, site: string): Promise<Design> {
  const render = JSON.parse(await readFile(join(renderDirectory, "render.json"), "utf8")) as { screenshots: Record<string, { file: string }> };
  const screenshots = ["desktop", "phone", "form-error", "form-success"].filter(name => render.screenshots[name]).map(name => join(renderDirectory, render.screenshots[name]!.file));
  const excerpt = async (file: string) => (await readFile(join(site, file), "utf8").catch(() => "(missing)")).slice(0, SOURCE_LIMIT);
  return { label, directory: renderDirectory, screenshots, source: `index.html:\n${await excerpt("index.html")}\n\nstyle.css:\n${await excerpt("style.css")}` };
}

/** Exactly one JSON object, strict or recovered from prose or one fence, as the graders accept answers. */
export function parseVerdict(text: string): Verdict | null {
  const candidates: unknown[] = [];
  try { candidates.push(JSON.parse(text)); } catch {
    for (let start = text.indexOf("{"); start >= 0; start = text.indexOf("{", start + 1)) {
      for (let end = text.lastIndexOf("}"); end > start; end = text.lastIndexOf("}", end - 1)) {
        try { candidates.push(JSON.parse(text.slice(start, end + 1))); start = end; break; } catch { /* keep looking */ }
      }
    }
  }
  const objects = candidates.filter(value => value && typeof value === "object" && !Array.isArray(value)) as Array<Record<string, unknown>>;
  if (objects.length !== 1) return null;
  const value = objects[0]!;
  const given = value.criteria as Record<string, unknown> | undefined;
  if (!given || !criteria.every(name => choices.has(String(given[name]))) || !choices.has(String(value.overall))) return null;
  return {
    criteria: Object.fromEntries(criteria.map(name => [name, given[name] as Choice])) as Verdict["criteria"],
    overall: value.overall as Choice,
    confidence: ["low", "medium", "high"].includes(String(value.confidence)) ? value.confidence as Verdict["confidence"] : "low",
    reasons: typeof value.reasons === "string" ? value.reasons.slice(0, 1_000) : "",
  };
}

/** Ask one judge to compare design A with design B; one retry when the verdict cannot be parsed. */
export async function judgePair(judge: ModelSelection, skill: string, a: Design, b: Design): Promise<{ verdict: Verdict | null; usage: { input: number; output: number }; raw: string }> {
  if (!lookupModelConfig(judge.provider, judge.id)?.vision) throw new Error("JUDGE_VISION_UNVERIFIED");
  const { models, model } = resolveModel(judge);
  const image = async (path: string) => ({ type: "image" as const, data: (await readFile(path)).toString("base64"), mimeType: "image/png" });
  const content = [];
  for (const design of [a, b]) {
    content.push({ type: "text" as const, text: `Design ${design.label}: screenshots in this order: desktop, phone, form error state, form success state.` });
    for (const path of design.screenshots) content.push(await image(path));
    content.push({ type: "text" as const, text: `Design ${design.label} source excerpt:\n${design.source}` });
  }
  content.push({ type: "text" as const, text: "Compare design A with design B as the judging skill describes, and reply with the JSON object only." });
  const usage = { input: 0, output: 0 };
  let raw = "";
  for (let attempt = 0; attempt < 2; attempt++) {
    const message = await models.streamSimple(model, { systemPrompt: skill, messages: [{ role: "user", content, timestamp: Date.now() }] } as never,
      { apiKey: process.env[apiKeyEnvFor(judge.provider)!], maxTokens: 16_384, ...(judge.thinkingLevel && judge.thinkingLevel !== "provider-default" ? { reasoning: judge.thinkingLevel } : {}) } as never).result();
    usage.input += message.usage.input + message.usage.cacheRead;
    usage.output += message.usage.output;
    raw = (message.content as Array<{ type: string; text?: string }>).filter(block => block.type === "text").map(block => block.text).join("");
    const verdict = parseVerdict(raw);
    if (verdict) return { verdict, usage, raw };
  }
  return { verdict: null, usage, raw };
}

/**
 * Outcome for one design over both orders: it is A in the first order and B in the second. Only a result that holds in
 * both orders counts as a win or loss; any disagreement counts as a tie, as in MT-Bench. A win in one order and a loss
 * in the other is flagged as position-inconsistent, a measure of the judge's position bias.
 */
export function combineOrders(first: Choice | null, second: Choice | null): { outcome: "win" | "loss" | "tie" | "missing"; inconsistent: boolean } {
  if (!first || !second) return { outcome: "missing", inconsistent: false };
  const asA = first === "A" ? "win" : first === "B" ? "loss" : "tie";
  const asB = second === "B" ? "win" : second === "A" ? "loss" : "tie";
  if (asA === asB) return { outcome: asA, inconsistent: false };
  return { outcome: "tie", inconsistent: asA !== "tie" && asB !== "tie" };
}

export const outcomeScore = { win: 1, tie: 0.5, loss: 0 } as const;
