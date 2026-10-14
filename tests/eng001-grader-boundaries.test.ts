import test from "node:test";
import assert from "node:assert/strict";
import { access, mkdtemp, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { command } from "../src/command.js";
import { inspectPackage } from "../src/evaluation/manifest.js";
import type { PackageDescriptor } from "../src/evaluation/manifest.js";

test("eng-001 classifies missing, malformed, timed out and oversized candidates safely", async t => {
  const packagePath = join(process.cwd(), "task-library", "calibration", "eng-001-import-validator");
  try { await access(join(packagePath, "manifest.json")); }
  catch {
    t.skip("eng-001 task package is not available in this checkout");
    return;
  }
  const descriptor: PackageDescriptor = await inspectPackage(packagePath, undefined, true);
  const python = descriptor.manifest?.environment.runtimeCheck?.executable;
  assert.ok(python);
  const version = await command(python, ["--version"], packagePath, 5_000, 2_000);
  if (version.status !== "completed" || version.exitCode !== 0 ||
      !(version.stdout + version.stderr).includes("Python 3.13.")) {
    t.skip("Python 3.13 task runtime is unavailable");
    return;
  }

  const root = await mkdtemp(join(tmpdir(), "eng001-fault-matrix-"));
  try {
    const acceptance = join(packagePath, "private", "acceptance.py");
    const driver = [
      "import json, runpy, sys, tempfile",
      "ns = runpy.run_path(sys.argv[1], run_name='acceptance_probe')",
      "mode, candidate = sys.argv[2], sys.argv[3]",
      "case_id = next(iter(ns['ORACLE']['cases']))",
      "case = ns['ORACLE']['cases'][case_id]",
      "if mode == 'visibility':",
      "    with tempfile.TemporaryDirectory(prefix='eng001_visibility_') as root:",
      "        result = ns['run_impl'](candidate, case, root)",
      "        print(result['stdout'].decode('utf-8', errors='replace'))",
      "else:",
      "    passed, reason = ns['check_case'](candidate, case_id, case)",
      "    print(json.dumps({'passed': passed, 'reason': reason}))",
    ].join("\n");
    const probe = async (mode: string, candidate: string): Promise<string> => {
      const result = await command(python, ["-c", driver, acceptance, mode, candidate], root, 15_000, 8_000);
      assert.equal(result.status, "completed", `probe process status: ${result.status}`);
      assert.equal(result.exitCode, 0, result.stderr);
      return result.stdout.trim();
    };

    const missing = await probe("case", join(root, "does-not-exist.py"));
    assert.deepEqual(JSON.parse(missing), { passed: false, reason: "candidate_missing" });

    const malformed = join(root, "malformed.py");
    await writeFile(malformed, "print('not-json')\n");
    assert.deepEqual(JSON.parse(await probe("case", malformed)), { passed: false, reason: "output_protocol_invalid" });

    const timeout = join(root, "timeout.py");
    await writeFile(timeout, "while True:\n    pass\n");
    assert.deepEqual(JSON.parse(await probe("case", timeout)), { passed: false, reason: "candidate_timeout" });

    const oversized = join(root, "oversized.py");
    await writeFile(oversized, "print('x' * 300000)\n");
    assert.deepEqual(JSON.parse(await probe("case", oversized)), { passed: false, reason: "candidate_output_limit" });

    const visibility = join(root, "visibility.py");
    await writeFile(visibility, [
      "import json, os, sys",
      "from pathlib import Path",
      "args = sys.argv[1:]",
      "named = {args[index + 1] for index, value in enumerate(args[:-1]) if value in ('--schema', '--input')}",
      "print(json.dumps({",
      "  'cwdIsCandidate': Path.cwd().name == 'candidate',",
      "  'onlyGenericFiles': set(os.listdir()) == {'import_validator.py', 'schema.json', 'input.csv'},",
      "  'genericInputsPresent': len(named) == 2 and all(Path(path).is_file() for path in named),",
      "  'noPrivatePathArguments': all('private' not in value.lower() and 'oracle' not in value.lower() for value in args),",
      "}))",
    ].join("\n"));
    const inspected = JSON.parse(await probe("visibility", visibility)) as Record<string, boolean>;
    assert.deepEqual(inspected, {
      cwdIsCandidate: true,
      onlyGenericFiles: true,
      genericInputsPresent: true,
      noPrivatePathArguments: true,
    });
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
