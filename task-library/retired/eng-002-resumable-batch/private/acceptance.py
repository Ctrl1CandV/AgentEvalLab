#!/usr/bin/env python3
"""Private acceptance checker for resumable batch processing."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
STATES = os.path.join(HERE, "states")
PY = shutil.which("python") or sys.executable
REF = os.path.join(HERE, "ref_impl.py")


def _abs(p):
    return p if os.path.isabs(p) else os.path.join(PKG, p)


def expected_output(rel, data):
    text = data.decode("utf-8", errors="replace")
    obj = {"rel_path": rel, "input_sha256": hashlib.sha256(data).hexdigest(),
           "bytes": len(data), "lines": text.count("\n"), "words": len(text.split())}
    return (json.dumps(obj, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def sha_file(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def list_inputs(input_dir):
    rels = []
    for root, _d, files in os.walk(input_dir):
        for n in files:
            full = os.path.join(root, n)
            if os.path.islink(full):
                continue
            rels.append(os.path.relpath(full, input_dir).replace("\\", "/"))
    return sorted(rels)


def out_for(output_dir, rel):
    return os.path.join(output_dir, (rel + ".json").replace("/", os.sep))


def copy_state(name):
    src = os.path.join(STATES, name)
    tmp = tempfile.mkdtemp(prefix="eng002_")
    work = os.path.join(tmp, "work")
    shutil.copytree(src, work)
    return tmp, work


def run_tool(impl, work, env=None):
    cmd = [PY, _abs(impl), "--input-dir", os.path.join(work, "input"),
           "--output-dir", os.path.join(work, "output"), "--journal", os.path.join(work, "journal.jsonl")]
    e = dict(os.environ)
    e.pop("EE_CRASH", None)
    if env:
        e.update(env)
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=e)
    actions, summary = [], None
    for ln in p.stdout.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            o = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if "action" in o:
            actions.append(o)
        elif "summary" in o:
            summary = o["summary"]
    return p.returncode, actions, summary, p.stderr


def final_problems(work):
    ind, outd = os.path.join(work, "input"), os.path.join(work, "output")
    rels = list_inputs(ind)
    probs = []
    for rel in rels:
        data = open(os.path.join(ind, rel.replace("/", os.sep)), "rb").read()
        op = out_for(outd, rel)
        if not os.path.isfile(op):
            probs.append(f"{rel}: expected output is missing")
        elif open(op, "rb").read() != expected_output(rel, data):
            probs.append(f"{rel}: output does not match the expected content")
    jload = {}
    jp = os.path.join(work, "journal.jsonl")
    if os.path.isfile(jp):
        for line in open(jp, encoding="utf-8", errors="replace"):
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(e, dict) and e.get("status") == "done":
                jload[e["rel_path"]] = e
    for rel in rels:
        e = jload.get(rel)
        if not e:
            probs.append(f"{rel}: journal has no completed entry")
            continue
        op = out_for(outd, rel)
        if os.path.isfile(op) and e.get("output_sha256") != sha_file(op):
            probs.append(f"{rel}: journal output hash does not match the output")
    if os.path.isdir(outd):
        for root, _d, files in os.walk(outd):
            for fn in files:
                if fn.endswith(".part"):
                    probs.append(f"output does not match the expected content {fn}")
    return probs


STATIC = {
    "empty": {"processed": {"a.txt", "b.txt", "sub/c.txt", "empty.txt"}, "skipped": set()},
    "complete": {"processed": set(), "skipped": {"a.txt", "b.txt", "sub/c.txt", "empty.txt"}, "mtime": True},
    "missing_output": {"processed": {"a.txt"}, "skipped": {"b.txt", "sub/c.txt", "empty.txt"}},
    "corrupt_output": {"processed": {"b.txt"}, "skipped": {"a.txt", "sub/c.txt", "empty.txt"}},
    "bad_journal": {"processed": {"sub/c.txt", "empty.txt"}, "skipped": {"a.txt", "b.txt"}},
    "input_changed": {"processed": {"b.txt"}, "skipped": {"a.txt", "sub/c.txt", "empty.txt"}},
    "stale_tmp": {"processed": {"a.txt", "b.txt", "sub/c.txt", "empty.txt"}, "skipped": set()},
}


def static_case(impl, name):
    exp = STATIC[name]
    tmp, work = copy_state(name)
    try:
        outd = os.path.join(work, "output")
        old = time.time() - 10000
        if exp.get("mtime") and os.path.isdir(outd):
            for root, _d, files in os.walk(outd):
                for fn in files:
                    os.utime(os.path.join(root, fn), (old, old))
        rc, actions, summary, stderr = run_tool(impl, work)
        if rc != 0:
            return False, f"exit {rc}!=0 ({stderr.strip()[:100]})"
        got_proc = {a["rel_path"] for a in actions if a["action"] == "processed"}
        got_skip = {a["rel_path"] for a in actions if a["action"] == "skipped"}
        if got_proc != exp["processed"]:
            return False, f"processed {sorted(got_proc)} != {sorted(exp['processed'])}"
        if got_skip != exp["skipped"]:
            return False, f"skipped {sorted(got_skip)} != {sorted(exp['skipped'])}"
        probs = final_problems(work)
        if probs:
            return False, "Output validation failed: " + "; ".join(probs[:4])
        if exp.get("mtime"):
            for root, _d, files in os.walk(outd):
                for fn in files:
                    if abs(os.path.getmtime(os.path.join(root, fn)) - old) > 5:
                        return False, f"completed output was rewritten (mtime changed): {fn}"
        return True, "ok"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def interrupt_case(crash_env, label):
    """Private acceptance checker for resumable batch processing."""
    tmp, work = copy_state("empty")
    try:
        rc1, _a1, _s1, _e1 = run_tool(REF, work, env={"EE_CRASH": crash_env})
        if rc1 == 0:
            return False, f"{label}: expected the interrupted process to exit nonzero, got 0"
        rc2, _a2, _s2, e2 = run_tool(REF, work, env=None)
        if rc2 != 0:
            return False, f"{label}: resume exited {rc2} ({e2.strip()[:100]})"
        probs = final_problems(work)
        if probs:
            return False, f"{label}: resumed output validation failed: " + "; ".join(probs[:4])
        return True, "Recovered successfully after interruption"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_static_suite(impl):
    return {name: static_case(impl, name) for name in STATIC}


def _print(impl, res):
    npass = sum(1 for ok, _ in res.values() if ok)
    print(f"-- {os.path.basename(impl)}: {npass}/{len(res)} cases passed")
    for cid, (ok, d) in res.items():
        print(f"   [{'PASS' if ok else 'FAIL'}] {cid}: {d}")


def self_calibrate():
    allok = True
    print('Resumable-batch self-calibration')
    print('Reference implementation checks')
    ref = run_static_suite(REF)
    _print(REF, ref)
    ref_all = all(ok for ok, _ in ref.values())
    print("Reference scenarios passed:", ref_all)
    allok &= ref_all

    print('Interruption recovery checks')
    interrupts = {
        "before_journal:a.txt": interrupt_case("before_journal:a.txt", "before_journal"),
        "stale_temp:a.txt": interrupt_case("stale_temp:a.txt", "stale_temp"),
        "after_n:2": interrupt_case("after_n:2", "after_n"),
    }
    for k, (ok, d) in interrupts.items():
        print(f"   [{'PASS' if ok else 'FAIL'}] {k}: {d}")
    int_all = all(ok for ok, _ in interrupts.values())
    print("Interruption scenarios passed:", int_all)
    allok &= int_all

    print('Mutant rejection checks')
    for b in ["private/bad_trusts_journal.py", "private/bad_input_hash_ignored.py", "private/bad_empty.py"]:
        res = run_static_suite(b)
        npass = sum(1 for ok, _ in res.values() if ok)
        rejected = npass < len(res)
        print(f"   {os.path.basename(b)}: {npass}/{len(res)} cases; {'REJECTED' if rejected else 'NOT REJECTED'}")
        allok &= rejected

    print('Repeatability check')
    ref2 = run_static_suite(REF)
    rep = {k: v[0] for k, v in ref.items()} == {k: v[0] for k, v in ref2.items()}
    print("Reference results are repeatable:", rep)
    allok &= rep

    print("RESULT:", "PASS" if allok else "FAIL")
    return 0 if allok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--impl")
    ap.add_argument("--self-calibrate", action="store_true")
    a = ap.parse_args()
    if a.self_calibrate:
        sys.exit(self_calibrate())
    if a.impl:
        res = run_static_suite(a.impl)
        _print(a.impl, res)
        sys.exit(0 if all(ok for ok, _ in res.values()) else 1)
    ap.error("Provide --impl or --self-calibrate.")


if __name__ == "__main__":
    main()
