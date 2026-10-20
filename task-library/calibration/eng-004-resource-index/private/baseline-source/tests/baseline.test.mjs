import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";

const catalog = {
  resources: [
    { id: "r-02", title: "Beta guide", tags: ["docs"], rank: 3 },
    { id: "r-01", title: "Alpha torch", tags: [], rank: 0, owner: "ops" },
  ],
};

function cli(...args) {
  const run = spawnSync(process.execPath, ["--experimental-strip-types", "--disable-warning=ExperimentalWarning", "src/cli.ts", ...args, "--input", "-"],
    { input: JSON.stringify(catalog), encoding: "utf8" });
  return { code: run.status, stdout: run.stdout, stderr: run.stderr };
}

test("index sorts by id and keeps every field", () => {
  const run = cli("index");
  assert.equal(run.code, 0);
  const value = JSON.parse(run.stdout);
  assert.deepEqual(value.resources.map(resource => resource.id), ["r-01", "r-02"]);
  assert.equal(value.resources[0].rank, 0);
  assert.deepEqual(value.resources[0].tags, []);
  assert.equal(value.resources[0].owner, "ops");
});

test("json export matches the index", () => {
  assert.equal(cli("export", "--format", "json").stdout, cli("index").stdout);
});

test("csv export has a header and one row per resource", () => {
  const lines = cli("export", "--format", "csv").stdout.trim().split(/\r?\n/);
  assert.equal(lines[0], "id,title,tags,rank");
  assert.equal(lines.length, 3);
});

test("an unknown command fails with code 2", () => {
  const run = cli("frobnicate");
  assert.equal(run.code, 2);
  assert.equal(run.stdout, "");
});
