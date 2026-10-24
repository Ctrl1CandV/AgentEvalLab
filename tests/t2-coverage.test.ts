import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";

// The T2 finance desk's self-calibration (grader 1.2.0, PLAN-007 WP0.3): every changing command belongs to one request
// of the day, in order, and the day's books end as a correctly handled day. The negative tests and the alternative
// flows run on every close day; the whole calibration takes about 15 seconds.
test("T2 coverage invariant: unknown, early, reopened and out-of-order changes fail; alternative flows pass", () => {
  const run = spawnSync("python3", ["-B", "task-library/basic/t2-finance-desk/private/grader.py", "--self-calibrate"],
    { encoding: "utf8", timeout: 300_000, env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" } });
  assert.equal(run.status, 0, run.stdout.slice(-2000) + run.stderr);
  const fails = (item: string, scenario: string) => {
    const line = run.stdout.split("\n").find(entry => entry.startsWith(`${item} ${scenario}:`));
    assert.ok(line, `${item} ${scenario} missing`);
    return JSON.parse(line.replace(/^.*fails /, "").replace(/'/g, "\"")) as string[];
  };
  for (const item of ["fn1", "fn2", "fn3", "fn4"]) {
    assert.deepEqual(fails(item, "unknown-request-posts"), ["coverage", "end-state"]);
    assert.deepEqual(fails(item, "change-before-the-first-begin"), ["coverage", "end-state"]);
    assert.deepEqual(fails(item, "reopens-the-plan-request"), ["coverage"]);
    assert.deepEqual(fails(item, "handles-R11-before-R10"), ["coverage"]);
    for (const scenario of ["oracle-through-ledger-py", "oracle-without-begin", "begin-repeated", "unknown-request-without-changes", "plan-revised-within-its-request"]) {
      assert.deepEqual(fails(item, scenario), [], `${item} ${scenario}`);
    }
  }
  assert.match(run.stdout, /RESULT: PASS/);
});
