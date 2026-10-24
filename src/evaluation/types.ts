import type { Budget, ExecutionResult, InteractionClass, ModelSelection, Runner, RunInput } from "../types.js";
import type { TaskPackageManifest } from "./manifest.js";
import type { ToolProfile } from "../harness/tools.js";
import type { Isolation } from "../sandbox.js";
import type { BatchPolicy } from "./batch.js";

export interface CommandCheck {
  id: string;
  executable: string;
  args: string[];
}

export type EvaluatorSpec =
  | { kind: "exact-match"; expected: string }
  | { kind: "commands"; checks: CommandCheck[]; timeoutMs?: number }
  | { kind: "task-package"; timeoutMs?: number; maxOutputBytes?: number }
  | { kind: "human"; dimensions: string[] };

export interface EvaluationCase {
  id: string;
  input: RunInput;
  repository?: { path: string; commit: string };
  evaluator: EvaluatorSpec;
  packagePath?: string;
  packageManifestSha256?: string;
  readOnly?: boolean;
  toolProfile?: ToolProfile;
  interactionClass?: InteractionClass;
  /**
   * For a package with generated items (Task Set v2): which items to run, one trial per item. "all" takes every item,
   * a list names items, and { levels } takes every item of those levels. Required for item packages.
   */
  items?: CaseItems;
}

export type CaseItems = "all" | string[] | { levels: string[] };

export interface EvaluationPlan {
  /** Omitted plans use the original single-run schema; version 3 requires pinned task manifests and a tool-result limit. */
  schemaVersion?: 3;
  name: string;
  models: ModelSelection[];
  budget: Budget;
  execution?: ExecutionPolicy;
  artifactLimits?: ArtifactLimits;
  cases: EvaluationCase[];
  trustedLocalExecution: boolean;
  /** Candidate-code isolation; omitted means "sandbox". "host" must be chosen explicitly. */
  isolation?: Isolation;
  /** Limits of one execute_command call (default 10 s and 16,000 bytes of output); the tool's description states them. */
  commandLimits?: CommandLimits;
  /** Retries, failure containment and spending ceilings for the whole batch (see src/evaluation/batch.ts). */
  batch?: Partial<BatchPolicy>;
  /** Independent trials per model and case (default 1). */
  repetitions?: number;
  /** Seed for the interleaved trial order; defaults to a value derived from the run fingerprint. */
  seed?: number;
  /**
   * State the budget to the model (PLAN-005 WP3): a fixed paragraph appended to the task prompt, and one status
   * message after usage passes each reminder threshold (default 50%, 75% and 90% of any limit). Single runs only.
   */
  budgetNotice?: boolean | { reminders: number[] };
  /**
   * The run protocol (CODE §3.3): the budget track and the split every task of the plan belongs to. A plan whose v2
   * tasks mix splits is refused at preflight, and a holdout plan must run on the fixed track.
   */
  protocol?: { track: "fixed" | "curve"; split: "dev" | "validation" | "holdout"; label?: string };
}

export type ExecutionPolicy =
  | { kind: "single" }
  | {
      kind: "trajectory";
      /**
       * "continuous": one session for every stage, so the conversation grows with the task.
       * "per-stage": a fresh session per stage, which keeps the project but not the conversation, so that each stage
       * starts from a comparable context and its budget means the same at the first stage and the last.
       */
      contextPolicy: "continuous" | "per-stage";
      stageBudget: Budget;
      publicRepairMax: 1;
    };

export interface TrajectoryStageResult {
  stageId: string;
  status: "completed" | "stopped" | "not_reached";
  /** Why a stage stopped while the trajectory went on: it used up its own budget. */
  stopReason?: string;
  cycles: Array<{
    cycleId: "cycle-1" | "cycle-2";
    execution: ExecutionResult;
    publicCheck: PublicCheckResult | null;
    snapshot: { path: string; manifest: ArtifactManifest } | null;
    privateGrade?: EvaluationResult;
  }>;
  activeRequirementIds: string[];
  durationMs: number;
}

export interface PublicCheckResult {
  schemaVersion: 1;
  stageId: string;
  status: "passed" | "failed";
  checks: Array<{ id: string; passed: boolean; reasonCode: string; feedback: string }>;
}

export interface TrajectoryRecord {
  id: string;
  caseId: string;
  model: ModelSelection;
  status: "completed" | "stopped";
  stopReason: string | null;
  stages: TrajectoryStageResult[];
  metrics?: TrajectoryMetrics;
  aggregateExecution: ExecutionResult;
  cleanup: "cleaned" | "error";
  durationMs: number;
  packageManifest: { version: string; sha256: string } | null;
  budget: {
    trajectory: Budget;
    stage: Budget;
    used: { timeoutMs: number; maxTurns: number; maxModelCalls: number; maxToolCalls: number };
  };
}

export interface TrajectoryMetrics {
  stageCompletion: { completed: number; planned: number };
  finalDeliveryAccepted: boolean | null;
  allStageStableDelivery: boolean | null;
  snapshots: Array<{ stageId: string; cycleId: "cycle-1" | "cycle-2"; requirements: Record<string, "pass" | "fail" | "unknown"> }>;
  newRequirementCompletion: Array<{ stageId: string; requirementId: string; status: "pass" | "fail" | "unknown" }>;
  regressions: Array<{ fromStageId: string; toStageId: string; requirementId: string; firstCycle: "fail"; finalCycle: "pass" | "fail" | "unknown" }>;
  retention: Array<{ fromStageId: string; toStageId: string; eligible: number; judged: number; retained: number; rate: number | null; coverage: number | null }>;
  publicRepair: { initialFailures: number; repairPrompts: number; attemptedFailures: number; judged: number; repaired: number; rate: number | null; coverage: number | null };
}

export interface TrajectorySession {
  send(input: WorkspaceInput, budget: Budget, emit: import("../types.js").EventSink, context: { stageId: string; cycleId: string }): Promise<ExecutionResult>;
  dispose(): Promise<void>;
}

export type TrajectorySessionFactory = (
  model: ModelSelection,
  trialId: string,
  toolProfile: ToolProfile,
  createTools: () => import("@earendil-works/pi-agent-core").AgentTool[],
) => TrajectorySession;

export interface WorkspaceInput extends RunInput {
  workspacePath: string;
}

export interface EvaluationResult {
  status: "passed" | "failed" | "error" | "unscored" | "resource_limit" | "skipped" | "pending";
  score: number | null;
  checks: { id: string; passed: boolean | null }[];
  error: string | null;
  /**
   * Human review of non-critical checks, kept apart from the objective verdict above.
   * Absent when the task has no unscored non-critical checks.
   */
  review?: ReviewStatus;
  /** Raw metric values a v2 grader reported (CODE §3.2), such as a contest score or a size in bytes. */
  metrics?: Array<{ id: string; value: number; unit?: string }>;
}

export interface ReviewStatus {
  status: "pending" | "complete";
  /** Non-critical checks still awaiting a human judgment. */
  pendingCheckIds: string[];
  reason: string | null;
}

export interface TrialRecord {
  id: string;
  caseId: string;
  model: ModelSelection;
  execution: ExecutionResult;
  evaluation: EvaluationResult;
  cleanup: "cleaned" | "error";
  durationMs: number;
  baseline: string | null;
  scoreRunId?: string | null;
  packageManifest?: { version: string; sha256: string } | null;
  artifactManifest?: Pick<ArtifactManifest, "totalBytes" | "sha256"> | null;
  toolProfile?: ToolProfile;
  interactionClass?: InteractionClass;
  toolTrace?: { path: string; bytes: number; sha256: string; truncated: boolean } | null;
  /** 1-based repetition of this model and case within the plan. */
  repetition?: number;
  /** The generated item this trial received, and its difficulty level (item packages only). */
  itemId?: string;
  itemLevel?: string;
  /** Earlier trial of the same model, case and repetition that this one replaces after a resumed batch. */
  supersedes?: string | null;
}

export interface EvaluationOptions {
  outputRoot: string;
  /** Continue an interrupted run directory instead of creating a new one (single-run plans only). */
  resumeDirectory?: string;
  runner?: Runner<WorkspaceInput>;
  sessionFactory?: TrajectorySessionFactory;
  /** Providers to treat as stopped from the start, with the reason (a resumed run skipping exhausted balances). */
  stoppedProviders?: Record<string, string>;
  /** Cross-process cap on concurrent trials per provider endpoint; defaults to the one the environment configures. */
  providerSlots?: import("./provider-slots.js").ProviderSlots;
}

export type { TaskPackageManifest };

export interface ArtifactLimits {
  maxFiles: number;
  maxFileBytes: number;
  maxTrialBytes: number;
  graderResultMaxBytes: number;
  toolEvidenceMaxBytes: number;
}

export interface ArtifactFileRecord {
  path: string;
  sizeBytes: number;
  sha256: string;
}

export interface CommandLimits {
  timeoutMs: number;
  maxOutputBytes: number;
}

export interface ArtifactManifest {
  schemaVersion: 1;
  files: ArtifactFileRecord[];
  totalBytes: number;
  sha256: string;
  /** Links and special files the workspace held: never followed or copied, only listed (absent when there were none). */
  skipped?: Array<{ path: string; kind: "link" | "special" }>;
}
