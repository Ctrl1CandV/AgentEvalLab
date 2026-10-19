import test from "node:test";
import assert from "node:assert/strict";
import { combineOrders, parseVerdict, vendorOf } from "../src/visual/judge.js";
import { bradleyTerry } from "../src/visual/panel.js";

test("combineOrders counts only results that hold in both orders", () => {
  assert.deepEqual(combineOrders("A", "B"), { outcome: "win", inconsistent: false });
  assert.deepEqual(combineOrders("B", "A"), { outcome: "loss", inconsistent: false });
  assert.deepEqual(combineOrders("A", "A"), { outcome: "tie", inconsistent: true });
  assert.deepEqual(combineOrders("A", "tie"), { outcome: "tie", inconsistent: false });
  assert.deepEqual(combineOrders(null, "B"), { outcome: "missing", inconsistent: false });
});

test("parseVerdict accepts exactly one complete verdict object", () => {
  const verdict = { criteria: { fit: "A", hierarchy: "A", layout: "B", typography: "tie", color: "A", responsive: "A", form: "A", polish: "A" }, overall: "A", confidence: "high", reasons: "x" };
  assert.equal(parseVerdict(`Here it is: ${JSON.stringify(verdict)}`)?.overall, "A");
  assert.equal(parseVerdict(`${JSON.stringify(verdict)} ${JSON.stringify(verdict)}`), null);
  assert.equal(parseVerdict(JSON.stringify({ ...verdict, overall: "C" })), null);
});

test("vendorOf groups models by vendor", () => {
  assert.equal(vendorOf({ provider: "supergpt", id: "gpt-6-luna" }), "openai");
  assert.equal(vendorOf({ provider: "supercn", id: "glm-5.3-flash" }), vendorOf({ provider: "supercn", id: "glm-5.3" }));
});

test("bradleyTerry ranks by results and treats symmetric results as equal", () => {
  const even = bradleyTerry(["a", "b"], [{ a: "a", b: "b", scoreA: 1 }, { a: "a", b: "b", scoreA: 0 }]);
  assert.ok(Math.abs(even.a! - even.b!) < 1e-9);
  const games = [
    ...Array.from({ length: 6 }, () => ({ a: "x", b: "y", scoreA: 1 })), { a: "x", b: "y", scoreA: 0 },
    ...Array.from({ length: 5 }, () => ({ a: "y", b: "z", scoreA: 1 })), { a: "y", b: "z", scoreA: 0.5 },
  ];
  const strength = bradleyTerry(["x", "y", "z"], games);
  assert.ok(strength.x! > strength.y! && strength.y! > strength.z!);
  assert.ok(Math.abs(Math.log(strength.x!) + Math.log(strength.y!) + Math.log(strength.z!)) < 1e-9);
  const sweep = bradleyTerry(["p", "q"], [{ a: "p", b: "q", scoreA: 1 }]);
  assert.ok(Number.isFinite(sweep.p!) && sweep.p! > sweep.q!);
});
