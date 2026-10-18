import { mkdir, readFile, realpath } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { command } from "../command.js";
import { sandboxLauncher } from "../sandbox.js";

const repositoryRoot = fileURLToPath(new URL("../../", import.meta.url));
const playwrightDirectory = join(repositoryRoot, "node_modules", "playwright-core");
const renderScript = join(repositoryRoot, "scripts", "render_frontend.mjs");

export interface RenderResult {
  screenshots: Record<string, { file: string; width?: number; height?: number; pageHeight?: number }>;
  overflow: Record<string, boolean>;
  rolesPresent: string[];
  formStates: Record<string, boolean>;
  errors: string[];
}

/** The headless shell matching the installed playwright-core; CHROMIUM_PATH overrides it. */
async function chromiumPath(): Promise<string> {
  if (process.env.CHROMIUM_PATH) return process.env.CHROMIUM_PATH;
  const browsers = JSON.parse(await readFile(join(playwrightDirectory, "browsers.json"), "utf8")) as { browsers: Array<{ name: string; revision: string }> };
  const shell = browsers.browsers.find(browser => browser.name === "chromium-headless-shell");
  if (!shell) throw new Error("CHROMIUM_REVISION_UNKNOWN");
  return join(homedir(), ".cache", "ms-playwright", `chromium_headless_shell-${shell.revision}`, "chrome-linux", "headless_shell");
}

/**
 * Render a static frontend in headless Chromium inside the bubblewrap sandbox. Only the output directory is writable;
 * the submission, playwright-core, the browser and the render script are read-only, and there is no network.
 */
export async function renderSubmission(site: string, output: string, states: { error: string; success: string }): Promise<RenderResult> {
  await mkdir(output, { recursive: true });
  const chromium = await chromiumPath();
  // Chromium's shared libraries (nss, nspr, alsa) come from the conda environment that also provides node.
  const runtimeLibraries = join(dirname(dirname(await realpath(process.execPath))), "lib");
  const run = await command("python3", [sandboxLauncher, "--rw", output, "--ro", site, "--ro", playwrightDirectory, "--ro", dirname(dirname(chromium)),
    "--ro", dirname(renderScript), "--", "/usr/bin/env", `CHROMIUM=${chromium}`, `LD_LIBRARY_PATH=${runtimeLibraries}`,
    process.execPath, renderScript, playwrightDirectory, site, output, JSON.stringify(states)], output, 120_000, 200_000);
  if (run.status !== "completed" || run.exitCode !== 0) throw new Error("RENDER_FAILED");
  return JSON.parse(await readFile(join(output, "render.json"), "utf8")) as RenderResult;
}
