import { getSupportedThinkingLevels } from "@earendil-works/pi-ai";
import { validateBudget, parseModel } from "../config.js";
import { thinkingLevels } from "../types.js";
import { validateBatchPolicy } from "./batch.js";
import { validReminderThresholds } from "../harness/budget-notice.js";
import { validCaseItems } from "./items.js";
import { lookupModelConfig } from "../providers.js";
import { resolveModel } from "../harness/pi.js";
import { defaultArtifactLimits } from "./artifacts.js";
import type { EvaluationPlan } from "./types.js";

function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("INVALID_OBJECT");
  return value as Record<string, unknown>;
}

function identifier(value: unknown): value is string {
  return typeof value === "string" && /^[\w.-]+$/.test(value);
}

/** Validates external JSON before any credentials, directories or requests are used. */
export function validatePlan(value: unknown): asserts value is EvaluationPlan {
  const plan = object(value);
  if (plan.schemaVersion !== undefined && plan.schemaVersion !== 3) throw new Error("UNSUPPORTED_PLAN_VERSION");
  if (typeof plan.name !== "string" || !plan.name.trim()) throw new Error("INVALID_PLAN");
  if (typeof plan.trustedLocalExecution !== "boolean") throw new Error("INVALID_TRUST_SETTING");
  if (plan.isolation !== undefined && plan.isolation !== "sandbox" && plan.isolation !== "host") throw new Error("INVALID_ISOLATION");
  const notice = plan.budgetNotice as unknown;
  if (notice !== undefined && typeof notice !== "boolean" &&
      !(notice && typeof notice === "object" && !Array.isArray(notice) && Object.keys(notice).every(key => key === "reminders") &&
        validReminderThresholds((notice as { reminders?: unknown }).reminders))) throw new Error("INVALID_BUDGET_NOTICE");
  validateBatchPolicy(plan.batch);
  if (plan.repetitions !== undefined && (typeof plan.repetitions !== "number" || !Number.isSafeInteger(plan.repetitions) || plan.repetitions < 1 || plan.repetitions > 50)) {
    throw new Error("INVALID_REPETITIONS");
  }
  if (plan.seed !== undefined && (typeof plan.seed !== "number" || !Number.isSafeInteger(plan.seed) || plan.seed < 0 || plan.seed > 0xffffffff)) throw new Error("INVALID_SEED");
  validateBudget(object(plan.budget) as unknown as EvaluationPlan["budget"]);
  if (plan.execution !== undefined) {
    const execution = object(plan.execution);
    if (execution.kind === "single") {
      // Explicit legacy-compatible form.
    } else if (execution.kind === "trajectory") {
      if (plan.schemaVersion !== 3 || execution.contextPolicy !== "continuous" || execution.publicRepairMax !== 1) {
        throw new Error("INVALID_TRAJECTORY_POLICY");
      }
      validateBudget(object(execution.stageBudget) as unknown as EvaluationPlan["budget"]);
      if (plan.repetitions !== undefined && plan.repetitions !== 1) throw new Error("TRAJECTORY_REPETITIONS_UNSUPPORTED");
    } else throw new Error("UNKNOWN_EXECUTION_POLICY");
  }
  if (plan.artifactLimits !== undefined) {
    const limits = object(plan.artifactLimits);
    for (const key of Object.keys(defaultArtifactLimits)) {
      const value = limits[key];
      if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 1 || value > 2_147_483_647) throw new Error(`INVALID_ARTIFACT_LIMIT:${key}`);
    }
  } else if (plan.schemaVersion === 3) throw new Error("ARTIFACT_LIMITS_REQUIRED");
  if (!Array.isArray(plan.models) || !plan.models.length || !Array.isArray(plan.cases) || !plan.cases.length) throw new Error("EMPTY_PLAN");
  const identities = new Set<string>();
  for (const value of plan.models) {
    const model = object(value);
    if (typeof model.provider !== "string" || typeof model.id !== "string") throw new Error("INVALID_MODEL");
    const identity = `${model.provider}:${model.id}`;
    const selection = parseModel(identity);
    const { model: resolved } = resolveModel(selection);
    if (identities.has(identity)) throw new Error("DUPLICATE_MODEL");
    if (model.thinkingLevel !== undefined && !thinkingLevels.includes(model.thinkingLevel as never)) throw new Error("INVALID_THINKING_LEVEL");
    // Refuse conditions a model cannot run under, so a plan never records a thinking level that was not applied:
    // Pi silently clamps an unsupported level to the nearest supported one, and sends nothing for non-reasoning models.
    const control = lookupModelConfig(selection.provider, selection.id)?.thinking;
    const level = (model.thinkingLevel ?? "off") as string;
    if (control === "always-on" && level === "off") throw new Error("THINKING_OFF_UNSUPPORTED");
    if (level !== "provider-default" && !(getSupportedThinkingLevels(resolved) as string[]).includes(level)) throw new Error("THINKING_LEVEL_UNSUPPORTED");
    if (model.temperature !== undefined && model.temperature !== null &&
        (typeof model.temperature !== "number" || !Number.isFinite(model.temperature) || model.temperature < 0 || model.temperature > 2)) {
      throw new Error("INVALID_TEMPERATURE");
    }
    identities.add(identity);
  }
  const ids = new Set<string>();
  for (const value of plan.cases) {
    const item = object(value);
    if (!identifier(item.id) || ids.has(item.id)) throw new Error("INVALID_CASE_ID");
    ids.add(item.id);
    const input = object(item.input);
    if (typeof input.prompt !== "string" || !input.prompt.trim()) throw new Error("INVALID_INPUT");
    if (input.systemPrompt !== undefined && typeof input.systemPrompt !== "string") throw new Error("INVALID_SYSTEM_PROMPT");
    if (item.readOnly !== undefined && typeof item.readOnly !== "boolean") throw new Error("INVALID_READ_ONLY");
    if (item.items !== undefined && (!validCaseItems(item.items) || typeof item.packagePath !== "string" ||
        object(item.evaluator).kind !== "task-package" || (plan.execution as { kind?: unknown } | undefined)?.kind === "trajectory")) throw new Error("INVALID_CASE_ITEMS");
    if (item.toolProfile !== undefined && !["workspace-basic", "workspace-augmented", "doc-evidence"].includes(String(item.toolProfile))) throw new Error("INVALID_TOOL_PROFILE");
    if (item.toolProfile !== undefined && !plan.trustedLocalExecution) throw new Error("TRUST_REQUIRED");
    if (item.toolProfile === "doc-evidence" && typeof item.packagePath !== "string") throw new Error("DOC_EVIDENCE_PACKAGE_REQUIRED");
    if (item.interactionClass !== undefined && !["candidate", "probe"].includes(String(item.interactionClass))) throw new Error("INVALID_INTERACTION_CLASS");
    if (item.repository !== undefined) {
      const repo = object(item.repository);
      if (typeof repo.path !== "string" || !repo.path.trim() || typeof repo.commit !== "string" || !repo.commit.trim()) throw new Error("INVALID_REPOSITORY");
      if (!plan.trustedLocalExecution) throw new Error("TRUST_REQUIRED");
    }
    if (item.packagePath !== undefined && (typeof item.packagePath !== "string" || !item.packagePath.trim() || !plan.trustedLocalExecution)) throw new Error("INVALID_PACKAGE");
    if (item.packageManifestSha256 !== undefined && (typeof item.packageManifestSha256 !== "string" || !/^[a-f0-9]{64}$/i.test(item.packageManifestSha256) || typeof item.packagePath !== "string")) throw new Error("INVALID_PACKAGE_MANIFEST_HASH");
    if (plan.schemaVersion === 3 && typeof item.packagePath === "string" && item.packageManifestSha256 === undefined) throw new Error("PACKAGE_MANIFEST_PIN_REQUIRED");
    const evaluator = object(item.evaluator);
    if (object(plan.execution ?? { kind: "single" }).kind === "trajectory" &&
        (evaluator.kind !== "task-package" || typeof item.packagePath !== "string" || item.repository === undefined ||
          item.toolProfile === "doc-evidence" || item.readOnly === true)) {
      throw new Error("TRAJECTORY_CASE_REQUIREMENTS_INVALID");
    }
    if (evaluator.kind === "exact-match") {
      if (typeof evaluator.expected !== "string") throw new Error("INVALID_EXPECTED");
    } else if (evaluator.kind === "commands") {
      if (!plan.trustedLocalExecution) throw new Error("TRUST_REQUIRED");
      if (!Array.isArray(evaluator.checks) || !evaluator.checks.length) throw new Error("EMPTY_CHECKS");
      const checkIds = new Set<string>();
      for (const value of evaluator.checks) {
        const check = object(value);
        if (!identifier(check.id) || checkIds.has(check.id) || typeof check.executable !== "string" || !check.executable.trim() || !Array.isArray(check.args) || !check.args.every(arg => typeof arg === "string")) throw new Error("INVALID_CHECK");
        checkIds.add(check.id);
      }
      if (evaluator.timeoutMs !== undefined && (typeof evaluator.timeoutMs !== "number" || !Number.isSafeInteger(evaluator.timeoutMs) || evaluator.timeoutMs < 1 || evaluator.timeoutMs > 2_147_483_647)) throw new Error("INVALID_CHECK_TIMEOUT");
    } else if (evaluator.kind === "task-package") {
      if (!plan.trustedLocalExecution || typeof item.packagePath !== "string" || plan.schemaVersion !== 3) throw new Error("TASK_PACKAGE_GRADER_REQUIRES_V2_PACKAGE");
      if (evaluator.timeoutMs !== undefined && (typeof evaluator.timeoutMs !== "number" || !Number.isSafeInteger(evaluator.timeoutMs) || evaluator.timeoutMs < 1 || evaluator.timeoutMs > 2_147_483_647)) throw new Error("INVALID_CHECK_TIMEOUT");
      if (evaluator.maxOutputBytes !== undefined && (typeof evaluator.maxOutputBytes !== "number" || !Number.isSafeInteger(evaluator.maxOutputBytes) || evaluator.maxOutputBytes < 1 || evaluator.maxOutputBytes > 2_147_483_647)) throw new Error("INVALID_GRADER_OUTPUT_LIMIT");
    } else if (evaluator.kind === "human") {
      if (!Array.isArray(evaluator.dimensions) || !evaluator.dimensions.length || !evaluator.dimensions.every(identifier) || new Set(evaluator.dimensions).size !== evaluator.dimensions.length) throw new Error("INVALID_DIMENSIONS");
    } else throw new Error("UNKNOWN_EVALUATOR");
  }
}
