// PLAN-007 WP2.4: read-only runtime mounts, the answer-only ("none") tool profile and repository workspaces.
import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { AssistantMessageEventStream } from "@earendil-works/pi-ai/utils/event-stream";
import { command } from "../src/command.js";
import { defaultBudget } from "../src/config.js";
import { isolatedCommand, sandboxAvailable } from "../src/sandbox.js";
import { workspaceTools } from "../src/harness/tools.js";
import { evaluationTools } from "../src/harness/profiles.js";
import { createPiRunner } from "../src/harness/pi.js";
import { evaluatedCondition } from "../src/evaluation/condition.js";
import { validatePlan } from "../src/evaluation/validate.js";
import { runEvaluation } from "../src/evaluation/run.js";
import { emptyExecution } from "../src/types.js";
import type { EvaluationPlan } from "../src/evaluation/types.js";

const sha256 = (content: string | Buffer) => createHash("sha256").update(content).digest("hex");
const python = "python3";

test("runtime mount: visible read-only at its fixed path, with its environment, in execute_command", async t => {
  const root = await mkdtemp(join(tmpdir(), "runtime-mount-test-"));
  try {
    if (!await sandboxAvailable(root)) { t.skip("bubblewrap is unavailable"); return; }
    const site = join(root, "site");
    const workspace = join(root, "workspace");
    await mkdir(site);
    await mkdir(workspace);
    await writeFile(join(site, "helperlib.py"), "VALUE = 'from the mount'\n");
    const runtime = { mounts: [{ source: site, target: "/runtime/py" }], env: { PYTHONPATH: "/runtime/py" } };
    const script = "import helperlib, os\nprint(helperlib.VALUE, os.environ['PYTHONPATH'])\ntry:\n  open('/runtime/py/x', 'w')\n  print('writable')\nexcept OSError:\n  print('read-only')\n";
    const sandboxed = isolatedCommand(python, ["-c", script], [workspace], "sandbox", runtime);
    const result = await command(sandboxed.executable, sandboxed.args, workspace, 20_000);
    assert.equal(result.exitCode, 0, result.stderr);
    assert.deepEqual(result.stdout.trim().split("\n"), ["from the mount /runtime/py", "read-only"]);

    const [, , execute] = workspaceTools(workspace, { readOnly: true, execute: true, runtime });
    assert.equal(execute!.name, "execute_command");
    const output = await execute!.execute("call", { executable: python, args: ["-c", "import helperlib; print(helperlib.VALUE)"] });
    const text = JSON.parse((output.content[0] as { text: string }).text) as { stdout: string; exitCode: number };
    assert.equal(text.exitCode, 0);
    assert.equal(text.stdout.trim(), "from the mount");

    // Without a mount the module is not there: nothing of the host's site leaks in.
    const bare = isolatedCommand(python, ["-c", "import helperlib"], [workspace], "sandbox");
    assert.notEqual((await command(bare.executable, bare.args, workspace, 20_000)).exitCode, 0);
    // A mount must sit under /runtime.
    const outside = isolatedCommand(python, ["-c", "pass"], [workspace], "sandbox", { mounts: [{ source: site, target: "/usr/lib/x" }], env: {} });
    assert.notEqual((await command(outside.executable, outside.args, workspace, 20_000)).exitCode, 0);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("answer-only: the none profile gives the model no tools, and the condition records none", async () => {
  assert.deepEqual(evaluationTools(tmpdir(), "none", { execute: true }), []);
  let seen: string[] | null = null;
  const runner = createPiRunner({
    apiKey: "offline-test-key",
    createTools: () => evaluationTools(tmpdir(), "none"),
    stream: (selectedModel, context) => {
      // Tools reach a request through system messages that add them.
      seen = context.messages.flatMap(message => (message as { toolsAdded?: Array<{ name: string }> }).toolsAdded ?? []).map(tool => tool.name);
      const message = {
        role: "assistant" as const, content: [{ type: "text" as const, text: "The answer is 42." }], api: selectedModel.api, provider: selectedModel.provider, model: selectedModel.id,
        usage: { input: 4, output: 4, cacheRead: 0, cacheWrite: 0, totalTokens: 8, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
        stopReason: "stop" as const, timestamp: Date.now(),
      };
      const stream = new AssistantMessageEventStream();
      stream.push({ type: "start", partial: { ...message, content: [], stopReason: "pending" } });
      stream.push({ type: "done", reason: "stop", message });
      return stream;
    },
  });
  const execution = await runner({ prompt: "What is six times seven?" }, { provider: "anthropic", id: "claude-sonnet-4-6" }, { ...defaultBudget }, async () => {});
  assert.equal(execution.status, "done");
  assert.match(execution.output, /42/);
  assert.deepEqual(seen, [], "no tool is offered");
  assert.equal(execution.toolCalls, 0);

  const plan: EvaluationPlan = {
    schemaVersion: 3, name: "answer-only", trustedLocalExecution: false,
    artifactLimits: { maxFiles: 10, maxFileBytes: 100_000, maxTrialBytes: 1_000_000, graderResultMaxBytes: 100_000, toolEvidenceMaxBytes: 100_000 }, models: [{ provider: "anthropic", id: "claude-sonnet-4-6" }], budget: { ...defaultBudget },
    cases: [{ id: "answer", input: { prompt: "Answer." }, toolProfile: "none", evaluator: { kind: "exact-match", expected: "42" } }],
  } as unknown as EvaluationPlan;
  validatePlan(plan);  // answer-only needs no trusted execution
  const condition = await evaluatedCondition(plan, new Map());
  assert.deepEqual(condition.tools.map(entry => [entry.profile, entry.toolNames]), [["none", []]]);
});

/** A small v2 package with one repository item, its runtime, and a grader that works as an ER grader does. */
async function repositoryPackage(root: string, archived = false): Promise<{ path: string; manifestSha256: string }> {
  const pkg = join(root, "package");
  const source = join(root, "source");
  await mkdir(join(source, "tests"), { recursive: true });
  await writeFile(join(source, "calc.py"), "def add(a, b):\n    return a - b\n\n\ndef mul(a, b):\n    return a * b\n");
  await writeFile(join(source, "tests", "__init__.py"), "");
  await writeFile(join(source, "tests", "test_calc.py"), "import unittest\nfrom calc import mul\n\n\nclass Calc(unittest.TestCase):\n    def test_mul(self):\n        self.assertEqual(mul(2, 3), 6)\n");
  await writeFile(join(source, ".gitignore"), "*.log\n");
  await writeFile(join(source, "kept.log"), "tracked although ignored\n");
  await mkdir(join(pkg, "private", "gold"), { recursive: true });
  await mkdir(join(pkg, "items", "calc-1", "public"), { recursive: true });
  await mkdir(join(pkg, "runtime", "py"), { recursive: true });
  const archive = join(pkg, "private", "calc-1.tar");
  const tar = await command("tar", ["-cf", archive, "-C", source, "."], root);
  assert.equal(tar.exitCode, 0, tar.stderr);
  // The gold tests: test_add, which needs the runtime's helper.
  const goldTests = "import unittest\nimport helperlib\nfrom calc import add, mul\n\n\nclass Calc(unittest.TestCase):\n    def test_mul(self):\n        self.assertEqual(mul(2, 3), 6)\n\n    def test_add(self):\n        self.assertEqual(add(2, 3), helperlib.FIVE)\n";
  await writeFile(join(root, "gold_test_calc.py"), goldTests);
  const diff = await command("git", ["diff", "--no-index", "--", "source/tests/test_calc.py", "gold_test_calc.py"], root);
  const testPatch = diff.stdout.replace("a/source/tests/test_calc.py", "a/tests/test_calc.py").replace("b/gold_test_calc.py", "b/tests/test_calc.py")
    .replace("--- a/source/tests/test_calc.py", "--- a/tests/test_calc.py").replace("+++ b/gold_test_calc.py", "+++ b/tests/test_calc.py");
  await writeFile(join(pkg, "private", "gold", "calc-1.test.patch"), testPatch);
  await writeFile(join(pkg, "runtime", "py", "helperlib.py"), "FIVE = 5\n");
  const grader = `import json, os, re, subprocess, sys, tarfile, tempfile
arg = lambda name: sys.argv[sys.argv.index(name) + 1]
request = json.load(open(arg("--request")))
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
manifest = json.load(open(os.path.join(root, "manifest.json")))
item = next(entry for entry in manifest["items"] if entry["id"] == request["context"]["itemId"])
work = tempfile.mkdtemp()
repo = os.path.join(work, "repo")
os.mkdir(repo)
archive = tarfile.open(os.path.join(root, item["repository"]["archive"]))
archive.extractall(repo)
patch = os.path.join(request["evidenceRoot"], request["patchRef"])
applied = os.path.getsize(patch) == 0 or subprocess.run(["git", "apply", "--binary", "--whitespace=nowarn", patch], cwd=repo).returncode == 0
gold = os.path.join(root, "private", "gold", item["id"] + ".test.patch")
# Restore every file the gold tests touch to its base version, then apply the gold tests.
for path in sorted(set(re.findall(r"^diff --git a/(\\S+) b/", open(gold).read(), re.M))):
    target = os.path.join(repo, path)
    try:
        member = archive.getmember("./" + path)
        with archive.extractfile(member) as base, open(target, "wb") as out:
            out.write(base.read())
    except KeyError:
        if os.path.exists(target):
            os.remove(target)
subprocess.run(["git", "apply", gold], cwd=repo, check=True)
with open(os.path.join(request["evidenceRoot"], "tests-after-restore.py"), "w") as out:
    out.write(open(os.path.join(repo, "tests", "test_calc.py")).read())
runtime = request.get("runtime") or {"mounts": [], "env": {}}
command = [sys.executable, "-m", "unittest", "-v", "tests.test_calc"]
env = dict(os.environ)
if request["sandbox"]:
    command = ["python3", request["sandbox"]["launcher"], "--rw", repo] + [part for mount in runtime["mounts"] for part in ("--mount", mount["source"] + ":" + mount["target"])] + [part for name, value in runtime["env"].items() for part in ("--env", name + "=" + value)] + ["--"] + command
else:
    env.update(runtime["env"])
run = subprocess.run(command, cwd=repo, capture_output=True, text=True, env=env, timeout=60)
passed = lambda name: bool(re.search(name + r" \\(.*\\) \\.\\.\\. ok", run.stderr))
checks = [("fail-to-pass", "REQ-FIX", applied and passed("test_add")), ("pass-to-pass", "REQ-KEEP", applied and passed("test_mul"))]
with open(os.path.join(request["evidenceRoot"], "tests.log"), "w") as out:
    out.write(run.stderr)
json.dump({"schemaVersion": 1, "requestId": request["requestId"], "taskId": request["task"]["id"], "taskVersion": request["task"]["version"], "graderVersion": "1.0.0",
    "gradingStatus": "completed", "checks": [{"id": check, "requirementId": requirement, "status": "pass" if ok else "fail", "evidenceRefs": ["tests.log"]} for check, requirement, ok in checks],
    "dimensions": [], "unscoredCheckIds": [], "reason": None, "error": None}, open(arg("--result"), "w"))
`;
  await writeFile(join(pkg, "private", "grader.py"), grader);
  const instruction = "Fix the issue in the repository under repo/.";
  const issue = "add(2, 3) returns -1; it should return 5.";
  const card = "# Card\n";
  await writeFile(join(pkg, "instruction.md"), instruction);
  await writeFile(join(pkg, "card.md"), card);
  await writeFile(join(pkg, "items", "calc-1", "public", "ISSUE.md"), issue);
  const file = async (path: string) => ({ path, sha256: sha256(await readFile(join(pkg, ...path.split("/")))) });
  // Archived: the repository and the runtime as external assets (PLAN-007 WP3.2), the runtime unpacked into a cache.
  const repositoryArchive = archived ? "assets/calc-1.tar" : "private/calc-1.tar";
  if (archived) {
    await mkdir(join(pkg, "assets"));
    await command("mv", [join(pkg, "private", "calc-1.tar"), join(pkg, "assets", "calc-1.tar")], root);
    const packed = await command("tar", ["-cf", join(pkg, "assets", "runtime-py.tar"), "-C", join(pkg, "runtime", "py"), "."], root);
    assert.equal(packed.exitCode, 0, packed.stderr);
    await rm(join(pkg, "runtime"), { recursive: true });
  }
  const manifest = {
    schemaVersion: 2, id: "repository-fixture", version: "0.1.0", familyId: "ER-fixture", capability: "engineering", usage: "development",
    source: { kind: "original-design", references: [] }, license: { taskText: "project", thirdPartyContent: [] },
    entryPoint: { instruction: "instruction.md" },
    files: { public: [await file("instruction.md")], trusted: [await file("card.md"), await file(repositoryArchive), await file("private/gold/calc-1.test.patch"),
      await file("private/grader.py"), await file(archived ? "assets/runtime-py.tar" : "runtime/py/helperlib.py")] },
    requirements: [{ id: "REQ-FIX", critical: true, introducedAt: "0.1.0", checkIds: ["fail-to-pass"] }, { id: "REQ-KEEP", critical: true, introducedAt: "0.1.0", checkIds: ["pass-to-pass"] }],
    items: [{ id: "calc-1", level: "L1", files: [await file("items/calc-1/public/ISSUE.md")], activeRequirementIds: ["REQ-FIX", "REQ-KEEP"],
      split: "dev", structure: "repo:calc", provenance: { source: "fixture", published: "2026-10-24", license: "MIT", exposure: "generated" },
      repository: { archive: repositoryArchive, directory: "repo" }, mounts: ["runtime/py"] }],
    toolProfiles: ["workspace-augmented"],
    grader: { id: "repository-fixture", version: "1.0.0", entryPoint: "private/grader.py", executable: python, args: ["{entryPoint}", "--request", "{request}", "--result", "{result}"] },
    environment: { runtime: "Python 3", dependencies: "none", network: false },
    tier: "core", capabilities: ["engineering"], card: "card.md",
    scoreModel: { primary: { kind: "resolved" }, groups: [{ id: "tests", weight: 1, critical: true, rule: "all", checkIds: ["fail-to-pass", "pass-to-pass"] }] },
    runtime: { mounts: [{ path: "runtime/py", env: { PYTHONPATH: "{mount}" }, ...(archived ? { archive: "assets/runtime-py.tar" } : {}) }] },
  };
  const bytes = JSON.stringify(manifest, null, 1);
  await writeFile(join(pkg, "manifest.json"), bytes);
  return { path: pkg, manifestSha256: sha256(bytes) };
}

test("repository workspace: one commit at a fixed author and date; the change is a patch; the grader restores the test files", async t => {
  const root = await mkdtemp(join(tmpdir(), "repository-workspace-test-"));
  try {
    if (!await sandboxAvailable(root)) { t.skip("bubblewrap is unavailable"); return; }
    const pkg = await repositoryPackage(root);
    const plan = (name: string): EvaluationPlan => ({
      schemaVersion: 3, name, models: [{ provider: "anthropic", id: "claude-sonnet-4-6" }], budget: { ...defaultBudget }, trustedLocalExecution: true,
      artifactLimits: { maxFiles: 10, maxFileBytes: 100_000, maxTrialBytes: 1_000_000, graderResultMaxBytes: 100_000, toolEvidenceMaxBytes: 100_000 },
      cases: [{ id: "calc", packagePath: pkg.path, packageManifestSha256: pkg.manifestSha256, items: ["calc-1"], toolProfile: "workspace-augmented",
        input: { prompt: "Fix it." }, evaluator: { kind: "task-package", timeoutMs: 120_000 } }],
    }) as EvaluationPlan;
    const git = async (cwd: string, args: string[]) => {
      const result = await command("git", args, cwd);
      assert.equal(result.exitCode, 0, result.stderr);
      return result.stdout.trim();
    };

    // A fix, committed by the model itself, plus an attempt to weaken the tests: only the fix counts.
    const fixed = await runEvaluation(plan("repository-fix"), { outputRoot: join(root, "results"), runner: async input => {
      const repo = join(input.workspacePath, "repo");
      assert.equal(await git(repo, ["rev-list", "--count", "HEAD"]), "1", "a fresh single-commit history");
      assert.equal(await git(repo, ["log", "-1", "--format=%an <%ae> %aI"]), "agenteval <agenteval@invalid> 2000-01-01T00:00:00+00:00");
      assert.equal(await git(repo, ["status", "--porcelain"]), "", "every file of the archive is committed, the ignored one too");
      assert.equal(await readFile(join(input.workspacePath, "public", "ISSUE.md"), "utf8"), "add(2, 3) returns -1; it should return 5.");
      await writeFile(join(repo, "calc.py"), "def add(a, b):\n    return a + b\n\n\ndef mul(a, b):\n    return a * b\n");
      await git(repo, ["-c", "user.name=m", "-c", "user.email=m@invalid", "commit", "-qam", "fix add"]);
      await writeFile(join(repo, "tests", "test_calc.py"), "import unittest\n");
      await writeFile(join(repo, "notes.py"), "# a new file\n");
      return { ...emptyExecution() };
    } });
    const fixRecord = fixed.report.records[0]!;
    assert.equal(fixRecord.evaluation.status, "passed", JSON.stringify([fixRecord.evaluation, fixRecord.execution.error]));
    const trial = join(fixed.directory, fixRecord.id);
    const patch = await readFile(join(trial, "submission.patch"), "utf8");
    assert.match(patch, /\+    return a \+ b/);
    assert.match(patch, /notes\.py/);
    const grader = join(trial, "score-runs", fixRecord.scoreRunId!, "grader");
    const request = JSON.parse(await readFile(join(grader, "request.json"), "utf8"));
    assert.equal(request.patchRef, "submission.patch");
    assert.deepEqual(request.runtime.mounts.map((mount: { target: string }) => mount.target), ["/runtime/py"]);
    assert.deepEqual(request.runtime.env, { PYTHONPATH: "/runtime/py" });
    assert.match(await readFile(join(grader, "evidence", "tests-after-restore.py"), "utf8"), /def test_add/, "the weakened test file was restored");
    const artifacts = JSON.parse(await readFile(join(trial, "artifact-manifest.json"), "utf8")) as { files: Array<{ path: string }> };
    assert.deepEqual(artifacts.files.map(entry => entry.path), ["public/ISSUE.md"], "the repository is delivered as the patch, not copied");

    // Only weakening the tests, and destroying the workspace's .git: the change is still read, and it fails.
    const weakened = await runEvaluation(plan("repository-tests-only"), { outputRoot: join(root, "results"), runner: async input => {
      const repo = join(input.workspacePath, "repo");
      await writeFile(join(repo, "tests", "test_calc.py"), "import unittest\n\n\nclass Calc(unittest.TestCase):\n    def test_add(self):\n        pass\n\n    def test_mul(self):\n        pass\n");
      await rm(join(repo, ".git"), { recursive: true, force: true });
      return { ...emptyExecution() };
    } });
    const weakRecord = weakened.report.records[0]!;
    assert.equal(weakRecord.evaluation.status, "failed", JSON.stringify(weakRecord.evaluation));
    assert.deepEqual(weakRecord.evaluation.checks.map(check => [check.id, check.passed]), [["fail-to-pass", false], ["pass-to-pass", true]]);
    assert.match(await readFile(join(weakened.directory, weakRecord.id, "submission.patch"), "utf8"), /tests\/test_calc\.py/);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("external assets: a repository and a runtime archived under assets/, the runtime unpacked once into the cache", async t => {
  const root = await mkdtemp(join(tmpdir(), "repository-assets-test-"));
  const previous = process.env.AGENTEVAL_RUNTIME_CACHE;
  process.env.AGENTEVAL_RUNTIME_CACHE = join(root, "runtime-cache");
  try {
    if (!await sandboxAvailable(root)) { t.skip("bubblewrap is unavailable"); return; }
    const pkg = await repositoryPackage(root, true);
    const plan = {
      schemaVersion: 3, name: "repository-assets", models: [{ provider: "anthropic", id: "claude-sonnet-4-6" }], budget: { ...defaultBudget }, trustedLocalExecution: true,
      artifactLimits: { maxFiles: 10, maxFileBytes: 100_000, maxTrialBytes: 1_000_000, graderResultMaxBytes: 100_000, toolEvidenceMaxBytes: 100_000 },
      cases: [{ id: "calc", packagePath: pkg.path, packageManifestSha256: pkg.manifestSha256, items: ["calc-1"], toolProfile: "workspace-augmented",
        input: { prompt: "Fix it." }, evaluator: { kind: "task-package", timeoutMs: 120_000 } }],
    } as unknown as EvaluationPlan;
    const fixed = await runEvaluation(plan, { outputRoot: join(root, "results"), runner: async input => {
      await writeFile(join(input.workspacePath, "repo", "calc.py"), "def add(a, b):\n    return a + b\n\n\ndef mul(a, b):\n    return a * b\n");
      return { ...emptyExecution() };
    } });
    const record = fixed.report.records[0]!;
    assert.equal(record.evaluation.status, "passed", JSON.stringify([record.evaluation, record.execution.error]));
    const request = JSON.parse(await readFile(join(fixed.directory, record.id, "score-runs", record.scoreRunId!, "grader", "request.json"), "utf8"));
    const source = request.runtime.mounts[0].source as string;
    assert.ok(source.startsWith(join(root, "runtime-cache")), source);
    assert.equal(await readFile(join(source, "helperlib.py"), "utf8"), "FIVE = 5\n");
    // An asset file that is not declared is refused.
    await writeFile(join(pkg.path, "assets", "stray.tar"), "x");
    await assert.rejects(runEvaluation(plan, { outputRoot: join(root, "results-2"), runner: async () => ({ ...emptyExecution() }) }), /PACKAGE_ASSET_FILE_SET_MISMATCH/);
  } finally {
    if (previous === undefined) delete process.env.AGENTEVAL_RUNTIME_CACHE; else process.env.AGENTEVAL_RUNTIME_CACHE = previous;
    await rm(root, { recursive: true, force: true });
  }
});
