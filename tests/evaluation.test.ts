import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, writeFile, readFile, rm, access } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { runEvaluation } from "../src/evaluation/run.js";
import { defaultBudget } from "../src/config.js";
import { emptyExecution } from "../src/types.js";
import { git } from "../src/command.js";
import { workspaceTools } from "../src/harness/tools.js";
import type { EvaluationPlan } from "../src/evaluation/types.js";

const base: EvaluationPlan = {
  name: "integration", models: [{ provider: "anthropic", id: "claude-sonnet-4-6" }],
  budget: { ...defaultBudget }, trustedLocalExecution: false,
  cases: [{ id: "output", input: { prompt: "input" }, evaluator: { kind: "exact-match", expected: "token=public" } }],
};

test("evaluation completes all phases and scores before redaction", async () => {
  const root = await mkdtemp(join(tmpdir(), "eval-test-"));
  const paths: string[] = [];
  try {
    const result = await runEvaluation(base, { outputRoot: root, runner: async input => {
      paths.push(input.workspacePath);
      return { ...emptyExecution(), output: "token=public", modelCalls: 1 };
    } });
    assert.equal(result.report.summary.passed, 1);
    assert.equal(result.report.summary.reportedTokens, null);
    assert.match(result.report.records[0].execution.output, /REDACTED/);
    await assert.rejects(access(paths[0]));
    const events = await readFile(join(result.directory, "events.jsonl"), "utf8");
    for (const phase of ["workspace_started", "execution_started", "evaluation_completed", "cleanup_completed"]) assert.ok(events.includes(phase));
    assert.match(await readFile(join(result.directory, "report.md"), "utf8"), /passed/);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("runner failures do not prevent subsequent cases", async () => {
  const root = await mkdtemp(join(tmpdir(), "eval-failure-"));
  let calls = 0;
  try {
    const plan = { ...base, cases: [...base.cases, { ...base.cases[0], id: "second" }] };
    const result = await runEvaluation(plan, { outputRoot: root, runner: async () => {
      if (++calls === 1) throw new Error("private failure");
      return { ...emptyExecution(), output: "token=public" };
    } });
    assert.equal(result.report.summary.total, 2);
    assert.equal(result.report.summary.passed, 1);
    assert.equal(result.report.summary.executionFailures, 1);
    assert.ok(!JSON.stringify(result.report).includes("private failure"));
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("repository execution exports changes to independent evaluator and cleans the workspace", async () => {
  const root = await mkdtemp(join(tmpdir(), "eval-repo-"));
  const repository = join(root, "source");
  const { mkdir } = await import("node:fs/promises");
  await mkdir(repository);
  let solver = "";
  try {
    await git(repository, ["init"]);
    await writeFile(join(repository, "base.txt"), "unchanged");
    await git(repository, ["add", "."]);
    await git(repository, ["-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-m", "base"]);
    const plan: EvaluationPlan = { ...base, trustedLocalExecution: true, cases: [{
      id: "repository", input: { prompt: "write artifact" }, repository: { path: repository, commit: "HEAD" },
      evaluator: { kind: "commands", checks: [{ id: "artifact", executable: process.execPath, args: ["-e", "if(require('fs').readFileSync('artifact.txt','utf8')!=='ok')process.exit(1)"] }] },
    }] };
    const result = await runEvaluation(plan, { outputRoot: join(root, "results"), runner: async input => {
      solver = input.workspacePath;
      await writeFile(join(solver, "artifact.txt"), "ok");
      return emptyExecution();
    } });
    assert.equal(result.report.summary.passed, 1);
    assert.equal(result.report.records[0].cleanup, "cleaned");
    await assert.rejects(access(solver));
    assert.equal((await git(repository, ["status", "--porcelain"])).trim(), "");
    assert.match(await readFile(join(result.directory, result.report.records[0].id, "submission.patch"), "utf8"), /artifact.txt/);
    await assert.rejects(runEvaluation({ ...plan, trustedLocalExecution: false }, { outputRoot: root }), /TRUST/);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("workspace tools reject traversal and git metadata", async () => {
  const root = await mkdtemp(join(tmpdir(), "eval-tools-"));
  try {
    const tools = workspaceTools(root);
    const write = tools.find(tool => tool.name === "write_file")!;
    await assert.rejects(write.execute("id", { path: "../outside", content: "x" }), /PATH_DENIED/);
    await assert.rejects(write.execute("id", { path: ".git/config", content: "x" }), /PATH_DENIED/);
    await write.execute("id", { path: "nested/file.txt", content: "ok" });
    assert.equal(await readFile(join(root, "nested/file.txt"), "utf8"), "ok");
  } finally { await rm(root, { recursive: true, force: true }); }
});
