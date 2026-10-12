#!/usr/bin/env python3
"""Deterministic rsn-002 certificate checks; symbolic equivalence remains human review."""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
ABS_TOL = 0.005
REL_TOL = 0.001
EXPECTED_DIMENSIONS = {
    "g": {"m": 1, "s": -2}, "L": {"m": 1, "s": 0},
    "mu": {"m": 0, "s": 0}, "v": {"m": 1, "s": -1},
}


def load(rel):
    with open(os.path.join(PKG, rel), encoding="utf-8") as handle:
        return json.load(handle)


def finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def close(actual, expected):
    return finite_number(actual) and abs(float(actual) - expected) <= max(ABS_TOL, REL_TOL * abs(expected))


def in_domain(theta_deg, mu):
    return finite_number(theta_deg) and finite_number(mu) and 0 < theta_deg < 90 and mu >= 0 and math.tan(math.radians(theta_deg)) > mu


def correct_speed(theta_deg, mu, length, gravity):
    if not in_domain(theta_deg, mu) or not finite_number(length) or not finite_number(gravity) or length <= 0 or gravity <= 0:
        return None
    angle = math.radians(theta_deg)
    radicand = 2 * gravity * length * (math.sin(angle) - mu * math.cos(angle))
    return math.sqrt(radicand) if radicand > 0 else None


def student_speed(theta_deg, mu, length, gravity):
    if not in_domain(theta_deg, mu) or not finite_number(length) or not finite_number(gravity) or length <= 0 or gravity <= 0:
        return None
    radicand = 2 * gravity * length * (math.sin(math.radians(theta_deg)) - mu)
    return math.sqrt(radicand) if radicand >= 0 else None


def check_sample_values(answer):
    samples = load("public/samples.json")["samples"]
    values = answer.get("v")
    if not isinstance(values, dict):
        return False, {"reasonCode": "SAMPLE_VALUES_MISSING"}
    actuals = {}
    passed = True
    for sample in samples:
        expected = correct_speed(sample["theta_deg"], sample["mu"], sample["L"], sample["g"])
        actual = values.get(sample["id"])
        actuals[sample["id"]] = {"expected": round(expected, 8), "provided": actual if finite_number(actual) else None,
                                  "passed": close(actual, expected)}
        passed &= close(actual, expected)
    return passed, {"samples": actuals, "absoluteTolerance": ABS_TOL, "relativeTolerance": REL_TOL}


def check_step(answer):
    return answer.get("errorStepId") == "S1", {"expectedStepId": "S1", "provided": answer.get("errorStepId")}


def check_dimensions(answer):
    provided = answer.get("dimensionCertificate")
    passed = isinstance(provided, dict) and set(provided) == set(EXPECTED_DIMENSIONS) and all(
        isinstance(provided.get(name), dict) and set(provided[name]) == {"m", "s"} and
        all(type(provided[name].get(unit)) is int for unit in ("m", "s")) and provided[name] == expected
        for name, expected in EXPECTED_DIMENSIONS.items())
    return passed, {"passed": passed, "baseUnits": ["m", "s"]}


def check_counterexample(answer):
    cert = answer.get("counterexampleCertificate")
    if not isinstance(cert, dict):
        return False, {"reasonCode": "CERTIFICATE_MISSING"}
    theta, mu, length, gravity = (cert.get(key) for key in ("thetaDeg", "mu", "L", "g"))
    correct = correct_speed(theta, mu, length, gravity)
    student = student_speed(theta, mu, length, gravity)
    actual_correct, actual_student = cert.get("correctV"), cert.get("studentV")
    passed = correct is not None and student is not None and not close(correct, student) and close(actual_correct, correct) and close(actual_student, student)
    return passed, {"certificateKind": "counterexample", "parametersValid": correct is not None and student is not None,
                    "providedCorrectV": actual_correct if finite_number(actual_correct) else None,
                    "providedStudentV": actual_student if finite_number(actual_student) else None,
                    "recomputedCorrectV": round(correct, 8) if correct is not None else None,
                    "recomputedStudentV": round(student, 8) if student is not None else None,
                    "distinguishes": correct is not None and student is not None and not close(correct, student)}


def check_limit(answer):
    cert = answer.get("limitCertificate")
    if not isinstance(cert, dict):
        return False, {"reasonCode": "CERTIFICATE_MISSING"}
    mu, length, gravity = cert.get("mu"), cert.get("L"), cert.get("g")
    valid = finite_number(mu) and 0 < mu < 1 and finite_number(length) and length > 0 and finite_number(gravity) and gravity > 0
    if not valid:
        return False, {"certificateKind": "limit", "parametersValid": False}
    expected_correct = math.sqrt(2 * gravity * length)
    expected_student = math.sqrt(2 * gravity * length * (1 - mu))
    passed = close(cert.get("correctLimit"), expected_correct) and close(cert.get("studentLimit"), expected_student) and not close(expected_correct, expected_student)
    return passed, {"certificateKind": "limit", "parametersValid": True,
                    "providedCorrectLimit": cert.get("correctLimit") if finite_number(cert.get("correctLimit")) else None,
                    "providedStudentLimit": cert.get("studentLimit") if finite_number(cert.get("studentLimit")) else None,
                    "recomputedCorrectLimit": round(expected_correct, 8), "recomputedStudentLimit": round(expected_student, 8),
                    "distinguishes": not close(expected_correct, expected_student)}


def grade(answer):
    if not isinstance(answer, dict):
        answer = {}
    checks = []
    for check_id, fn in (("sample-values", check_sample_values), ("wrong-step-location", check_step),
                         ("dimension-certificate", check_dimensions), ("counterexample-certificate", check_counterexample),
                         ("limit-certificate", check_limit)):
        passed, evidence = fn(answer)
        checks.append((check_id, passed, evidence))
    return checks


def reference_answer():
    samples = load("public/samples.json")["samples"]
    values = {sample["id"]: correct_speed(sample["theta_deg"], sample["mu"], sample["L"], sample["g"]) for sample in samples}
    theta, mu, length, gravity = 60.0, 0.2, 2.0, 9.8
    counter = {"thetaDeg": theta, "mu": mu, "L": length, "g": gravity,
               "correctV": correct_speed(theta, mu, length, gravity), "studentV": student_speed(theta, mu, length, gravity)}
    mu_limit, length_limit, gravity_limit = 0.2, 2.0, 9.8
    return {"errorStepId": "S1", "correctFormula": "v = sqrt(2*g*L*(sin(theta)-mu*cos(theta)))", "v": values,
            "dimensionCertificate": EXPECTED_DIMENSIONS, "counterexampleCertificate": counter,
            "limitCertificate": {"mu": mu_limit, "L": length_limit, "g": gravity_limit,
                                 "correctLimit": math.sqrt(2 * gravity_limit * length_limit),
                                 "studentLimit": math.sqrt(2 * gravity_limit * length_limit * (1 - mu_limit))},
            "explanation": "The sample values and certificates are computed from the stated model."}


def self_calibrate():
    rows = []
    ref = reference_answer()
    expected_automated = {"sample-values", "wrong-step-location", "dimension-certificate", "counterexample-certificate", "limit-certificate"}

    def record(name, answer, expected):
        got = {check_id for check_id, passed, _ in grade(answer) if passed}
        ok = got == expected
        rows.append((name, ok, sorted(got)))

    record("reference-answer", ref, expected_automated)
    alt = json.loads(json.dumps(ref))
    theta, mu, length, gravity = 50.0, 0.1, 2.5, 10.0
    alt["counterexampleCertificate"] = {"thetaDeg": theta, "mu": mu, "L": length, "g": gravity,
                                         "correctV": correct_speed(theta, mu, length, gravity),
                                         "studentV": student_speed(theta, mu, length, gravity)}
    record("alternative-parameters", alt, expected_automated)
    for name, mutate in (
        ("wrong-step", lambda a: a.update(errorStepId="S4")),
        ("student-numbers", lambda a: a.update(v={s["id"]: student_speed(s["theta_deg"], s["mu"], s["L"], s["g"]) for s in load("public/samples.json")["samples"]})),
        ("invalid-counterexample", lambda a: a.update(counterexampleCertificate={"thetaDeg": 30, "mu": 1, "L": 2, "g": 9.8, "correctV": 1, "studentV": 2})),
        ("bad-limit-certificate", lambda a: a.update(limitCertificate={"mu": 0.2, "L": 2, "g": 9.8, "correctLimit": 1, "studentLimit": 1})),
        ("missing-dimensions", lambda a: a.pop("dimensionCertificate")),
    ):
        negative = json.loads(json.dumps(ref))
        mutate(negative)
        got = {check_id for check_id, passed, _ in grade(negative) if passed}
        target = {"invalid-counterexample": "counterexample-certificate", "bad-limit-certificate": "limit-certificate"}.get(name)
        rows.append((f"reject-{name}", target not in got if target else got != expected_automated, sorted(got)))
    malformed_passes = any(passed for _, passed, _ in grade(None))
    rows.append(("reject-malformed", not malformed_passes, []))
    deterministic = grade(ref) == grade(ref)
    rows.append(("repeatable", deterministic, []))
    for name, ok, detail in rows:
        print(f"{name}: {'PASS' if ok else 'FAIL'} {detail if detail else ''}")
    print("human-review: formula-equivalence and explanation-quality remain unscored by design")
    print(f"RESULT: {'PASS' if all(ok for _, ok, _ in rows) else 'FAIL'} ({sum(ok for _, ok, _ in rows)}/{len(rows)})")
    return 0 if all(ok for _, ok, _ in rows) else 1


if __name__ == "__main__":
    raise SystemExit(self_calibrate())
