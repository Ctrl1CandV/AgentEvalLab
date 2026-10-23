import test from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdir, mkdtemp, readdir, rm, symlink, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { copyArtifacts, inspectArtifacts } from "../src/evaluation/artifacts.js";

test("snapshots skip links and special files, list them, and copy only regular files", async () => {
  const root = await mkdtemp(join(tmpdir(), "artifacts-"));
  try {
    const source = join(root, "workspace");
    await mkdir(join(source, ".bench", "proj"), { recursive: true });
    await mkdir(join(source, "src"));
    await writeFile(join(source, "src", "cli.ts"), "console.log(1);\n");
    // A scratch benchmark copy that links back to the sources, as a model made in an E3 stage.
    await symlink("../../src", join(source, ".bench", "proj", "src"));
    await symlink(root, join(source, "outside"));
    execFileSync("mkfifo", [join(source, "pipe")]);

    const inspected = await inspectArtifacts(source);
    assert.deepEqual(inspected.files.map(file => file.path), ["src/cli.ts"]);
    assert.deepEqual(inspected.skipped, [{ path: ".bench/proj/src", kind: "link" }, { path: "outside", kind: "link" }, { path: "pipe", kind: "special" }]);

    const copied = await copyArtifacts(source, join(root, "snapshot"));
    assert.equal(copied.sha256, inspected.sha256);
    assert.deepEqual(copied.skipped, inspected.skipped);
    // Only regular files are copied, and directories only as their files need them.
    assert.deepEqual((await readdir(join(root, "snapshot"))).sort(), ["src"]);

    const clean = await inspectArtifacts(join(root, "snapshot", "src"));
    assert.equal("skipped" in clean, false, "a manifest without links has no skipped list");
  } finally { await rm(root, { recursive: true, force: true }); }
});
