import { mkdtemp, readFile, rm, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { ManifestItem, PackageDescriptor } from "./manifest.js";
import type { SimulatorToolOptions } from "../harness/tools.js";

/**
 * A simulator session (PLAN-007 WP3.3, AP): a package's trusted simulator, run by the harness outside the sandbox for
 * one trial, with its state in a private directory the model's tools cannot reach. The model talks to it only through
 * the `simulator` tool; the simulator appends every accepted command to `log.jsonl` in its state directory, which the
 * grader receives (`simulatorRef`) to replay the run.
 */
export interface SimulatorSession {
  tool: SimulatorToolOptions;
  /** The simulator's command log, or "" when it never ran. */
  log(): Promise<string>;
  cleanup(): Promise<void>;
}

export const MAX_SIMULATOR_LOG_BYTES = 10 * 1024 * 1024;

export async function simulatorSession(descriptor: PackageDescriptor, item: ManifestItem | null): Promise<SimulatorSession> {
  const simulator = descriptor.manifest?.simulator;
  if (!simulator) throw new Error("PACKAGE_SIMULATOR_REQUIRED");
  const state = await mkdtemp(join(tmpdir(), "agenteval-simulator-"));
  const entryPoint = join(descriptor.root, ...simulator.entryPoint.split("/"));
  return {
    tool: { executable: simulator.executable, args: [entryPoint, "--item", item?.id ?? "", "--state", state], stateDirectory: state,
      description: simulator.description, timeoutMs: simulator.timeoutMs },
    async log() {
      const path = join(state, "log.jsonl");
      const info = await stat(path).catch(() => null);
      if (!info) return "";
      if (info.size > MAX_SIMULATOR_LOG_BYTES) throw new Error("SIMULATOR_LOG_SIZE_LIMIT");
      return readFile(path, "utf8");
    },
    cleanup: () => rm(state, { recursive: true, force: true }),
  };
}
