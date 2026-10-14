import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { tmpdir } from "node:os";
import type { AgentTool } from "@earendil-works/pi-agent-core";
import { evaluationTools } from "../src/harness/profiles.js";
import { command } from "../src/command.js";

function result(tool: AgentTool, id: string, args: unknown) {
  const execute = tool.execute as (toolCallId: string, input: unknown) => Promise<{ content: Array<{ type: string; text?: string }> }>;
  return execute(id, args).then(output => {
    const text = output.content.find(block => block.type === "text")?.text;
    assert.ok(text);
    return JSON.parse(text) as Record<string, unknown>;
  });
}

test("augmented workspace profile provides bounded pages, literal search and exact edits", async () => {
  const root = await mkdtemp(join(tmpdir(), "m2-workspace-tools-"));
  try {
    await mkdir(join(root, "src"));
    await writeFile(join(root, "src", "index.ts"), "export const limit = 10;\nexport const empty = 0;\nexport const limit2 = 20;\n");
    const tools = evaluationTools(root, "workspace-augmented");
    const byName = (name: string) => {
      const found = tools.find(tool => tool.name === name);
      assert.ok(found, `expected tool ${name}`);
      return found;
    };

    const page = await result(byName("read_file_page"), "page-1", { path: "src/index.ts", startLine: 1, lineCount: 2 });
    assert.equal(page.status, "warning");
    assert.equal(page.truncated, true);
    assert.equal(page.nextStartLine, 3);
    assert.deepEqual(page.lines, [{ line: 1, text: "export const limit = 10;" }, { line: 2, text: "export const empty = 0;" }]);

    const search = await result(byName("search_files"), "search-1", { pattern: "LIMIT", glob: "src/*.ts" });
    assert.equal(search.status, "success");
    assert.deepEqual(search.matches, [
      { path: "src/index.ts", line: 1, text: "export const limit = 10;" },
      { path: "src/index.ts", line: 3, text: "export const limit2 = 20;" },
    ]);

    const manyMatchesPath = join(root, "src", "matches.txt");
    await writeFile(manyMatchesPath, Array.from({ length: 50 }, () => "needle").join("\n"));
    const exactLimit = await result(byName("search_files"), "search-limit", { pattern: "needle" });
    assert.equal((exactLimit.matches as unknown[]).length, 50);
    assert.equal(exactLimit.truncated, false);
    await writeFile(manyMatchesPath, Array.from({ length: 51 }, () => "needle").join("\n"));
    const overLimit = await result(byName("search_files"), "search-over-limit", { pattern: "needle" });
    assert.equal((overLimit.matches as unknown[]).length, 50);
    assert.equal(overLimit.truncated, true);
    await writeFile(join(root, "src", "z-order.txt"), "ordered\n");
    await writeFile(join(root, "src", "a-order.txt"), "ordered\n");
    const stableOrder = await result(byName("search_files"), "search-order", { pattern: "ordered" });
    assert.deepEqual((stableOrder.matches as Array<{ path: string }>).map(match => match.path), ["src/a-order.txt", "src/z-order.txt"]);

    const edit = await result(byName("edit_file"), "edit-1", { path: "src/index.ts", oldText: "limit = 10", newText: "limit = 12" });
    assert.equal(edit.status, "success");
    assert.match(await readFile(join(root, "src", "index.ts"), "utf8"), /limit = 12/);
    await assert.rejects(byName("edit_file").execute("edit-2", { path: "src/index.ts", oldText: "export", newText: "x" } as never), /EDIT_TEXT_AMBIGUOUS/);
    await assert.rejects(byName("read_file_page").execute("page-2", { path: "../outside", startLine: 1, lineCount: 1 } as never), /PATH_DENIED/);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("doc-evidence profile preserves zero-based Unicode paging, hard limits and read-only permissions", async () => {
  const root = await mkdtemp(join(tmpdir(), "m2-doc-tools-"));
  try {
    await mkdir(join(root, "secrets"));
    await writeFile(join(root, "notes.txt"), `alpha🙂omega${"x".repeat(410)}`);
    await writeFile(join(root, "hits.txt"), Array.from({ length: 50 }, () => "needle").join("\n"));
    await writeFile(join(root, "z-order.txt"), "ordered\n");
    await writeFile(join(root, "a-order.txt"), "ordered\n");
    await writeFile(join(root, "secrets", "credentials.enc"), "synthetic");
    const tools = evaluationTools(root, "doc-evidence");
    const byName = (name: string) => {
      const found = tools.find(tool => tool.name === name);
      assert.ok(found, `expected tool ${name}`);
      return found;
    };
    assert.deepEqual(tools.map(tool => tool.name), ["list", "read", "search"]);

    // Offsets count Unicode code points: the emoji is one unit at offset 5, so offset 6 starts at "o"
    // (UTF-16 indexing would return half of the surrogate pair there).
    const first = await result(byName("read"), "read-1", { path: "notes.txt", offset: 5, limit: 1 });
    assert.equal(first.content, "🙂");
    assert.equal(first.next_offset, 6);
    const after = await result(byName("read"), "read-1b", { path: "notes.txt", offset: 6, limit: 1 });
    assert.equal(after.content, "o");
    const page = await result(byName("read"), "read-2", { path: "notes.txt", offset: 0, limit: 999 });
    assert.equal(Array.from(String(page.content)).length, 400);
    assert.equal(page.truncated, true);
    assert.equal(page.next_offset, 400);
    assert.deepEqual(await result(byName("read"), "read-3", { path: "secrets/credentials.enc", offset: 0, limit: 10 }), { ok: false, error: "permission_denied" });
    await assert.rejects(byName("read").execute("read-4", { path: "../notes.txt", offset: 0, limit: 10 } as never), /PATH_DENIED/);
    assert.deepEqual(await result(byName("read"), "read-5", { path: "notes.txt", offset: -1, limit: 10 }), { ok: false, error: "invalid_range" });

    const matches = await result(byName("search"), "search-1", { pattern: "alpha🙂omega", glob: "*.txt" });
    const matchRows = matches.matches as Array<{ path: string; line: number; text: string }>;
    assert.equal(matchRows[0]?.path, "notes.txt");
    assert.ok(matchRows[0]?.text.startsWith("alpha🙂omega"));
    assert.equal(matchRows[0]?.text.length, 200);
    const exactLimit = await result(byName("search"), "search-limit", { pattern: "needle" });
    assert.equal((exactLimit.matches as unknown[]).length, 50);
    assert.equal(exactLimit.truncated, false);
    await writeFile(join(root, "hits.txt"), Array.from({ length: 51 }, () => "needle").join("\n"));
    const overLimit = await result(byName("search"), "search-over-limit", { pattern: "needle" });
    assert.equal((overLimit.matches as unknown[]).length, 50);
    assert.equal(overLimit.truncated, true);
    const stableOrder = await result(byName("search"), "search-order", { pattern: "ordered" });
    assert.deepEqual((stableOrder.matches as Array<{ path: string }>).map(match => match.path), ["a-order.txt", "z-order.txt"]);
    assert.deepEqual(await result(byName("search"), "search-2", { pattern: "[" }), { ok: false, error: "bad_pattern" });
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("doc-evidence adapter resolves tool-001 answers from the fixture and returns actual evidence", async () => {
  const snapshot = resolve("task-library/calibration/tool-001-doc-evidence-recovery/public/snapshot");
  const tools = evaluationTools(snapshot, "doc-evidence");
  const byName = (name: string) => {
    const found = tools.find(tool => tool.name === name);
    assert.ok(found, `expected tool ${name}`);
    return found;
  };
  let dependencyOffset = 0;
  let dependencyText = "";
  let dependencyTruncated = true;
  while (dependencyTruncated) {
    const page = await result(byName("read"), "fixture-read", { path: "deps.lock.json", offset: dependencyOffset, limit: 400 });
    assert.equal(page.ok, true);
    dependencyText += String(page.content);
    dependencyOffset = Number(page.next_offset);
    dependencyTruncated = Boolean(page.truncated);
  }
  assert.match(dependencyText, /tessera/);
  const audit = await result(byName("search"), "fixture-search", { pattern: "req-0499", glob: "*.jsonl" });
  const matches = audit.matches as Array<{ path: string; line: number; text: string }>;
  assert.equal(matches.length, 1);
  assert.equal(matches[0]?.path, "logs/audit_large.jsonl");
  assert.match(matches[0]?.text ?? "", /503/);
  const setting = await result(byName("read"), "fixture-prod", { path: "config/prod/settings.toml", offset: 0, limit: 400 });
  assert.match(String(setting.content), /timeout_ms\s*=\s*3500/);
});

test("production doc-evidence bridge returns trace evidence accepted by the task grader", async () => {
  const packageRoot = resolve("task-library/calibration/tool-001-doc-evidence-recovery");
  const snapshot = join(packageRoot, "public", "snapshot");
  const tools = evaluationTools(snapshot, "doc-evidence");
  const byName = (name: string) => {
    const found = tools.find(tool => tool.name === name);
    assert.ok(found, `expected tool ${name}`);
    return found;
  };
  const root = await mkdtemp(join(tmpdir(), "tool-001-grader-bridge-"));
  try {
    const evidenceRoot = join(root, "evidence");
    await mkdir(evidenceRoot);
    const answer = {
      Q1: { version: "0.9.13", license: "BSD-3-Clause", evidence: "deps.lock.json" },
      Q2: { status_code: 503, evidence: "logs/audit_large.jsonl" },
      Q3: { timeout_ms: 3500, evidence: "config/prod/settings.toml" },
      Q4a: { project: "meridian-cli", tool_needed: false },
      Q4b: { action: "refuse", reason: "The snapshot is read-only." },
    };
    await writeFile(join(evidenceRoot, "candidate-answer.txt"), JSON.stringify(answer));
    const trace: Array<Record<string, unknown>> = [];
    let sequence = 0;
    const call = async (name: string, args: Record<string, unknown>) => {
      const output = await result(byName(name), `bridge-${sequence + 1}`, args);
      trace.push({ schemaVersion: 1, sequence: ++sequence, eventType: "execution_returned", toolName: name, args,
        status: "success", result: { content: [{ type: "text", text: JSON.stringify(output) }] } });
      return output;
    };
    let offset = 0;
    let truncated = true;
    while (truncated) {
      const page = await call("read", { path: "deps.lock.json", offset, limit: 400 });
      truncated = Boolean(page.truncated);
      offset = Number(page.next_offset);
    }
    await call("search", { pattern: "req-0499", glob: "*.jsonl" });
    await call("read", { path: "prior_attempt.log", offset: 0, limit: 400 });
    await call("list", { path: "config" });
    await call("list", { path: "config/prod" });
    await call("read", { path: "config/prod/settings.toml", offset: 0, limit: 400 });
    await writeFile(join(evidenceRoot, "tool-trace.jsonl"), trace.map(event => JSON.stringify(event)).join("\n") + "\n");
    const requestPath = join(root, "request.json");
    const resultPath = join(root, "result.json");
    await writeFile(requestPath, JSON.stringify({ requestId: "bridge-test.grader", evidenceRoot,
      answerRef: "candidate-answer.txt", traceRef: "tool-trace.jsonl" }));
    const manifest = JSON.parse(await readFile(join(packageRoot, "manifest.json"), "utf8")) as { grader: { executable: string } };
    const run = await command(manifest.grader.executable, [join(packageRoot, "private", "harness_grader.py"), "--request", requestPath, "--result", resultPath], packageRoot, 30_000, 100_000);
    assert.equal(run.status, "completed", run.stderr);
    assert.equal(run.exitCode, 0, run.stderr);
    const graded = JSON.parse(await readFile(resultPath, "utf8")) as { gradingStatus: string; checks: Array<{ id: string; status: string }> };
    assert.equal(graded.gradingStatus, "completed");
    assert.deepEqual(graded.checks.map(check => [check.id, check.status]), [["Q1", "pass"], ["Q2", "pass"], ["Q3", "pass"], ["Q4a", "pass"], ["Q4b", "pass"], ["answer-format", "pass"]]);
  } finally { await rm(root, { recursive: true, force: true }); }
});
