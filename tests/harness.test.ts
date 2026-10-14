import test from "node:test";
import assert from "node:assert/strict";
import { access, mkdtemp, readFile, rename, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { defaultBudget, parseModel, validateBudget } from "../src/config.js";
import { EventSinkError, guardEventSink } from "../src/events.js";
import { emptyExecution } from "../src/types.js";
import { persistedExecution, registerSecrets } from "../src/privacy.js";
import { runHarness } from "../src/run.js";
import { createPiRunner } from "../src/harness/pi.js";
import { git } from "../src/command.js";
import { createWorkspace, collectPatch, cleanupWorkspace } from "../src/workspace.js";

const model = parseModel("anthropic:claude-sonnet-4-6");

test("configuration has no task dependency and accepts zero tools", () => {
  validateBudget({ ...defaultBudget, maxToolCalls: 0 });
  assert.throws(() => validateBudget({ ...defaultBudget, maxTurns: 0 }));
  assert.throws(() => parseModel("mock:stock-v1"));
  // A bare ID selects the primary endpoint; a protocol suffix selects the fallback.
  assert.deepEqual(parseModel("supercn:glm-5.3"), { provider: "supercn", id: "glm-5.3" });
  assert.deepEqual(parseModel("supercn-openai:glm-5.3"), { provider: "supercn-openai", id: "glm-5.3" });
});

test("event failures remain visible after listener errors are caught", async () => {
  const events = guardEventSink(async () => { throw new Error("synthetic"); });
  await assert.rejects(events.emit("test"), EventSinkError);
  assert.throws(events.check, EventSinkError);
});

test("persistence redacts without modifying in-memory output", () => {
  const execution = { ...emptyExecution(), output: '{"password":"synthetic"} private-value' };
  registerSecrets(execution, ["private-value"]);
  const saved = persistedExecution(execution, 1000);
  assert.ok(!saved.output.includes("synthetic"));
  assert.ok(!saved.output.includes("private-value"));
  assert.ok(execution.output.includes("private-value"));
});

test("single execution records ordered events without scoring", async () => {
  const root = await mkdtemp(join(tmpdir(), "harness-log-test-"));
  try {
    const result = await runHarness({
      input: { prompt: "not persisted" }, model, outputRoot: root,
      runner: async (_input, _model, _budget, emit) => {
        await Promise.all([emit("first"), emit("second")]);
        return { ...emptyExecution(), output: "text", modelCalls: 1 };
      },
    });
    const entries = (await readFile(join(result.directory, "events.jsonl"), "utf8")).trim().split("\n").map(line => JSON.parse(line));
    assert.deepEqual(entries.map(entry => entry.sequence), [1, 2, 3, 4]);
    assert.equal(result.execution.reportedTokens, null);
    assert.equal("score" in result, false);
    assert.ok(!(await readFile(join(result.directory, "config.json"), "utf8")).includes("not persisted"));
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("Pi validates inputs before attempting a request", async () => {
  const runner = createPiRunner({ apiKey: "synthetic" });
  await assert.rejects(runner({ prompt: " " }, model, { ...defaultBudget }, async () => {}), /EMPTY_PROMPT/);
  await assert.rejects(runner({ prompt: "test" }, model, { ...defaultBudget, timeoutMs: -1 }, async () => {}), /INVALID_BUDGET/);
});

async function baseRepository(prefix: string): Promise<string> {
  const repository = await mkdtemp(join(tmpdir(), prefix));
  await git(repository, ["init", "-q"]);
  await writeFile(join(repository, "base.txt"), "base");
  await git(repository, ["add", "."]);
  await git(repository, ["-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "base"]);
  return repository;
}

test("workspace clone preserves source and only cleans owned workspaces", async () => {
  const repository = await baseRepository("harness-git-test-");
  try {
    const workspace = await createWorkspace(repository, "HEAD");
    try {
      await writeFile(join(workspace.path, "new.txt"), "new");
      assert.match(await collectPatch(workspace), /new.txt/);
      assert.equal((await git(repository, ["status", "--porcelain"])).trim(), "");
      assert.equal((await git(workspace.path, ["remote"])).trim(), "", "the clone must not point back to the source");
      await assert.rejects(cleanupWorkspace({ ...workspace }), /UNOWNED_WORKSPACE/);
    } finally { await cleanupWorkspace(workspace); }
    await assert.rejects(access(workspace.path));
  } finally { await rm(repository, { recursive: true, force: true }); }
});

test("candidate commits are collected from the pinned commit without touching the source", async () => {
  const repository = await baseRepository("harness-git-commit-test-");
  try {
    const sourceRefs = await git(repository, ["for-each-ref", "--format=%(refname) %(objectname)"]);
    const sourceObjects = await git(repository, ["count-objects", "-v"]);
    const workspace = await createWorkspace(repository, "HEAD");
    try {
      const identity = ["-c", "user.name=Candidate", "-c", "user.email=candidate@example.invalid"];
      await writeFile(join(workspace.path, "committed.txt"), "committed");
      await git(workspace.path, ["add", "committed.txt"]);
      await git(workspace.path, [...identity, "commit", "-qm", "candidate work"]);
      await git(workspace.path, [...identity, "checkout", "-qb", "candidate-branch"]);
      await writeFile(join(workspace.path, "uncommitted.txt"), "uncommitted");
      const patch = await collectPatch(workspace);
      assert.match(patch, /committed.txt/);
      assert.match(patch, /uncommitted.txt/);
      assert.doesNotMatch(patch, /base.txt/);
    } finally { await cleanupWorkspace(workspace); }
    assert.equal(await git(repository, ["for-each-ref", "--format=%(refname) %(objectname)"]), sourceRefs);
    assert.equal(await git(repository, ["count-objects", "-v"]), sourceObjects);
  } finally { await rm(repository, { recursive: true, force: true }); }
});

test("a workspace whose Git metadata points elsewhere is rejected", async () => {
  const repository = await baseRepository("harness-git-replaced-test-");
  try {
    const workspace = await createWorkspace(repository, "HEAD");
    const gitDir = join(workspace.path, ".git");
    await rename(gitDir, `${gitDir}-moved`);
    await writeFile(gitDir, `gitdir: ${join(repository, ".git")}\n`);
    await assert.rejects(collectPatch(workspace), /WORKSPACE_REPLACED/);
    await assert.rejects(cleanupWorkspace(workspace), /WORKSPACE_REPLACED/);
    await rm(dirname(workspace.path), { recursive: true, force: true });
  } finally { await rm(repository, { recursive: true, force: true }); }
});
