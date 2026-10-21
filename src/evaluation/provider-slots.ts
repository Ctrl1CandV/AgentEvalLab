import { mkdir, open, readFile, unlink } from "node:fs/promises";
import { join } from "node:path";
import { lookupProviderConfig } from "../providers.js";

/**
 * A cap on concurrent trials per provider endpoint, shared by every harness process of one suite launch (PLAN-006).
 * A trial sends one request at a time, so concurrent trials bound concurrent requests. Slots are lock files under a
 * directory the suite creates afresh for each launch; a lock whose process has exited is taken over.
 *
 * Enabled by two environment variables: AGENTEVAL_PROVIDER_SLOTS (the directory) and AGENTEVAL_PROVIDER_LIMITS (JSON,
 * endpoint host to slots, with "*" as the default). Without them every acquire returns at once.
 */
export interface ProviderSlots {
  acquire(provider: string): Promise<() => Promise<void>>;
}

const noSlots: ProviderSlots = { acquire: async () => async () => {} };

/** The endpoint a provider's requests go to: relays that serve several providers share one host and one cap. */
export function providerHost(provider: string): string {
  const baseUrl = lookupProviderConfig(provider)?.baseUrl;
  if (!baseUrl) return provider;
  try { return new URL(baseUrl).host; } catch { return provider; }
}

function alive(pid: number): boolean {
  try { process.kill(pid, 0); return true; }
  catch (error) { return (error as NodeJS.ErrnoException).code === "EPERM"; }
}

export function fileProviderSlots(directory: string, limits: Record<string, number>, pollMs = 2_000): ProviderSlots {
  return {
    async acquire(provider) {
      const host = providerHost(provider);
      const limit = limits[host] ?? limits["*"];
      if (!limit) return async () => {};
      const root = join(directory, host.replace(/[^A-Za-z0-9._-]/g, "_"));
      await mkdir(root, { recursive: true });
      for (;;) {
        for (let index = 0; index < limit; index++) {
          const path = join(root, `${index}.lock`);
          try {
            const handle = await open(path, "wx");
            await handle.writeFile(String(process.pid));
            await handle.close();
            let released = false;
            return async () => {
              if (released) return;
              released = true;
              await unlink(path).catch(() => {});
            };
          } catch (error) {
            if ((error as NodeJS.ErrnoException).code !== "EEXIST") throw error;
            const owner = Number.parseInt(await readFile(path, "utf8").catch(() => ""), 10);
            // A lock that is still empty is being written; only a lock whose owner has exited is taken over.
            if (Number.isSafeInteger(owner) && owner > 0 && !alive(owner)) await unlink(path).catch(() => {});
          }
        }
        await new Promise(resolve => setTimeout(resolve, pollMs + Math.floor(Math.random() * pollMs)));
      }
    },
  };
}

export function providerSlotsFromEnvironment(environment: NodeJS.ProcessEnv = process.env): ProviderSlots {
  const directory = environment.AGENTEVAL_PROVIDER_SLOTS;
  if (!directory) return noSlots;
  let limits: Record<string, number>;
  try { limits = JSON.parse(environment.AGENTEVAL_PROVIDER_LIMITS ?? "{}") as Record<string, number>; }
  catch { throw new Error("PROVIDER_LIMITS_INVALID"); }
  if (!limits || typeof limits !== "object" || Object.values(limits).some(value => !Number.isSafeInteger(value) || value < 1)) {
    throw new Error("PROVIDER_LIMITS_INVALID");
  }
  return fileProviderSlots(directory, limits);
}
