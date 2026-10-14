import type { Budget, ExecutionResult, InteractionClass, ModelSelection, Runner, RunInput } from "../types.js";
import type { TaskPackageManifest } from "./manifest.js";
import type { ToolProfile } from "../harness/tools.js";
import type { Isolation } from "../sandbox.js";

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
}

export interface EvaluationPlan {
  /** Omitted plans use the original single-run schema; version 2 requires pinned task manifests. */
  schemaVersion?: 2;
  name: string;
  models: ModelSelection[];
  budget: Budget;
  execution?: ExecutionPolicy;
  artifactLimits?: ArtifactLimits;
  cases: EvaluationCase[];
  trustedLocalExecution: boolean;
  /** Candidate-code isolation; omitted means "sandbox". "host" must be chosen explicitly. */
  isolation?: Isolation;
}

export type ExecutionPolicy =
  | { kind: "single" }
  | {
      kind: "trajectory";
      contextPolicy: "continuous";
      stageBudget: Budget;
      publicRepairMax: 1;
    };

export interface TrajectoryStageResult {
  stageId: string;
  status: "completed" | "stopped" | "not_reached";
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
}

export interface EvaluationOptions {
  outputRoot: string;
  runner?: Runner<WorkspaceInput>;
  sessionFactory?: TrajectorySessionFactory;
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

export interface ArtifactManifest {
  schemaVersion: 1;
  files: ArtifactFileRecord[];
  totalBytes: number;
  sha256: string;
}
