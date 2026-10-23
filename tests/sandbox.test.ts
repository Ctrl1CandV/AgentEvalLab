import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { workspaceTools } from "../src/harness/tools.js";
import { sandboxAvailable } from "../src/sandbox.js";
import { validatePlan } from "../src/evaluation/validate.js";
import { defaultBudget } from "../src/config.js";

async function run(root: string, isolation: "sandbox" | "host", executable: string, args: string[]) {
  const tool = workspaceTools(root, { execute: true, isolation }).find(candidate => candidate.name === "execute_command")!;
  const output = await tool.execute("call", { executable, args } as never);
  return JSON.parse((output.content[0] as { text: string }).text) as { status: string; exitCode: number | null; stdout: string; stderr: string };
}

test("execute_command cannot reach files outside the workspace, the network, or the host home", async t => {
  if (!(await sandboxAvailable(tmpdir()))) {
    t.skip("bubblewrap is unavailable on this host");
    return;
  }
  const workspace = await mkdtemp(join(tmpdir(), "sandbox-workspace-"));
  const outside = await mkdtemp(join(tmpdir(), "sandbox-outside-"));
  try {
    await writeFile(join(outside, "oracle.json"), "{\"answer\":42}");
    const secret = join(outside, "oracle.json");

    const blocked = await run(workspace, "sandbox", "cat", [secret]);
    assert.notEqual(blocked.exitCode, 0);
    assert.doesNotMatch(blocked.stdout, /answer/);

    const written = await run(workspace, "sandbox", "sh", ["-c", "echo created > result.txt"]);
    assert.equal(written.exitCode, 0);
    assert.equal(await readFile(join(workspace, "result.txt"), "utf8"), "created\n");

    const network = await run(workspace, "sandbox", "python3", ["-c",
      "import socket\ntry:\n    socket.create_connection(('1.1.1.1', 443), timeout=3)\n    print('connected')\nexcept OSError:\n    print('offline')"]);
    assert.equal(network.stdout.trim(), "offline");

    const home = await run(workspace, "sandbox", "sh", ["-c", "test -e \"$0\" && echo visible || echo hidden", process.cwd()]);
    assert.equal(home.stdout.trim(), "hidden", "the repository with private task material must not be visible");

    const host = await run(workspace, "host", "cat", [secret]);
    assert.match(host.stdout, /answer/, "explicit host isolation runs unconfined");
  } finally {
    await rm(workspace, { recursive: true, force: true });
    await rm(outside, { recursive: true, force: true });
  }
});

test("plans accept only sandbox or host isolation", () => {
  const plan = {
    name: "isolation", models: [{ provider: "anthropic", id: "claude-sonnet-4-6" }], budget: { ...defaultBudget },
    trustedLocalExecution: false, cases: [{ id: "case", input: { prompt: "text" }, evaluator: { kind: "human", dimensions: ["clarity"] } }],
  };
  validatePlan({ ...plan, isolation: "sandbox" });
  validatePlan({ ...plan, isolation: "host" });
  assert.throws(() => validatePlan({ ...plan, isolation: "none" }), /INVALID_ISOLATION/);
});

test("execute_command states and enforces the plan's command limits", async () => {
  const workspace = await mkdtemp(join(tmpdir(), "command-limits-"));
  try {
    const standard = workspaceTools(workspace, { execute: true, isolation: "host" }).find(candidate => candidate.name === "execute_command")!;
    assert.match(standard.description, /10 seconds and return 16000 bytes/);
    const long = workspaceTools(workspace, { execute: true, isolation: "host", commandLimits: { timeoutMs: 1_500, maxOutputBytes: 2_000 } })
      .find(candidate => candidate.name === "execute_command")!;
    assert.match(long.description, /1.5 seconds and return 2000 bytes/);
    const call = async (args: string[]) => JSON.parse(((await long.execute("call", { executable: "sh", args } as never)).content[0] as { text: string }).text) as { status: string };
    assert.equal((await call(["-c", "sleep 1; echo done"])).status, "completed", "a command within the limit completes");
    assert.equal((await call(["-c", "sleep 3"])).status, "timeout");
    assert.equal((await call(["-c", "head -c 5000 /dev/zero"])).status, "output_limit");
  } finally {
    await rm(workspace, { recursive: true, force: true });
  }
});

test("plans accept command limits within bounds only", () => {
  const plan = {
    name: "limits", models: [{ provider: "anthropic", id: "claude-sonnet-4-6" }], budget: { ...defaultBudget },
    trustedLocalExecution: false, cases: [{ id: "case", input: { prompt: "text" }, evaluator: { kind: "human", dimensions: ["clarity"] } }],
  };
  validatePlan({ ...plan, commandLimits: { timeoutMs: 600_000, maxOutputBytes: 64_000 } });
  for (const commandLimits of [{ timeoutMs: 500, maxOutputBytes: 16_000 }, { timeoutMs: 600_000 }, { timeoutMs: 600_000, maxOutputBytes: 64_000, extra: 1 },
    { timeoutMs: 7_200_000, maxOutputBytes: 16_000 }]) {
    assert.throws(() => validatePlan({ ...plan, commandLimits }), /INVALID_COMMAND_LIMITS/);
  }
});
