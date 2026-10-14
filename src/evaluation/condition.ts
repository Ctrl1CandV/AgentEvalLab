import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { command, git } from "../command.js";
import { resolveModel } from "../harness/pi.js";
import { evaluationTools } from "../harness/profiles.js";
import type { ToolProfile } from "../harness/tools.js";
import { lookupModelConfig } from "../providers.js";
import { sandboxLauncher } from "../sandbox.js";
import { modelOptions } from "../types.js";
import type { PackageDescriptor } from "./manifest.js";
import type { EvaluationPlan } from "./types.js";

const repositoryRoot = fileURLToPath(new URL("../../", import.meta.url));
const recordedPackages = ["@earendil-works/pi-agent-core", "@earendil-works/pi-ai"] as const;

export function sha256(value: unknown): string {
  const bytes = typeof value === "string" || Buffer.isBuffer(value) ? value : JSON.stringify(value);
  return createHash("sha256").update(bytes).digest("hex");
}

async function gitState(): Promise<{ commit: string | null; dirty: boolean | null }> {
  try {
    const commit = (await git(repositoryRoot, ["rev-parse", "HEAD"])).trim();
    const dirty = (await git(repositoryRoot, ["status", "--porcelain"])).trim().length > 0;
    return { commit, dirty };
  } catch {
    return { commit: null, dirty: null };
  }
}

async function pythonVersion(): Promise<string | null> {
  const result = await command("python3", ["--version"], tmpdir(), 5_000, 2_000);
  return result.status === "completed" && result.exitCode === 0 ? (result.stdout + result.stderr).trim() : null;
}

async function packageVersion(name: string): Promise<string | null> {
  try {
    const manifest = JSON.parse(await readFile(join(repositoryRoot, "node_modules", ...name.split("/"), "package.json"), "utf8")) as { version?: unknown };
    return typeof manifest.version === "string" ? manifest.version : null;
  } catch {
    return null;
  }
}

/**
 * Everything besides the plan and task packages that defines what a run measured: code revision,
 * runtimes, Pi version, resolved model metadata and request options, the exact tool definitions
 * each case receives, and candidate isolation. It is stored in experiment.json and fingerprinted.
 */
export async function evaluatedCondition(plan: EvaluationPlan, packages: Map<string, PackageDescriptor>) {
  const isolation = plan.isolation ?? "sandbox";
  const models = plan.models.map(selection => {
    const { model } = resolveModel(selection);
    const declared = lookupModelConfig(selection.provider, selection.id);
    return {
      provider: selection.provider,
      id: selection.id,
      ...modelOptions(selection),
      api: model.api,
      baseUrl: model.baseUrl,
      contextWindow: model.contextWindow,
      maxTokens: model.maxTokens,
      reasoning: model.reasoning,
      pricesDeclared: declared ? declared.prices !== null : null,
      // Built-in provider catalogs ship their own metadata; custom entries carry a verified flag.
      metadataVerified: declared ? declared.verified : null,
      thinkingControl: declared ? declared.thinking : null,
    };
  });
  const tools = plan.cases.map(item => {
    const profile = (item.toolProfile ?? packages.get(item.id)?.manifest?.toolProfiles?.[0] ?? "workspace-basic") as ToolProfile;
    // Creating tools does not touch the file system, so any root yields the same definitions.
    const definitions = plan.trustedLocalExecution
      ? evaluationTools(tmpdir(), profile, { readOnly: item.readOnly, execute: !item.readOnly, isolation })
        .map(tool => ({ name: tool.name, description: tool.description, parameters: tool.parameters }))
      : [];
    return { caseId: item.id, profile, toolNames: definitions.map(tool => tool.name), definitionsSha256: sha256(definitions) };
  });
  return {
    git: await gitState(),
    runtimes: { node: process.version, python: await pythonVersion() },
    packages: Object.fromEntries(await Promise.all(recordedPackages.map(async name => [name, await packageVersion(name)] as const))),
    models,
    tools,
    isolation: { mode: isolation, launcherSha256: sha256(await readFile(sandboxLauncher)) },
  };
}
