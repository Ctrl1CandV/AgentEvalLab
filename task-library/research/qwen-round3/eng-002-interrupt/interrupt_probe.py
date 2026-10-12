#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PY = shutil.which("python") or sys.executable
N_ITEMS = 5000
KILL_AFTER = 50


class _Tee:
    def __init__(self, path, orig):
        self.fh = open(path, "w", encoding="utf-8"); self.orig = orig
    def write(self, s):
        self.fh.write(s)
        try: self.orig.write(s)
        except Exception: self.orig.write(s.encode("ascii", "replace").decode("ascii"))
        return len(s)
    def flush(self):
        self.fh.flush()
        try: self.orig.flush()
        except Exception: pass


def expected_output(rel, data):
    text = data.decode("utf-8", errors="replace")
    obj = {"rel_path": rel, "input_sha256": hashlib.sha256(data).hexdigest(),
           "bytes": len(data), "lines": text.count("\n"), "words": len(text.split())}
    return (json.dumps(obj, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def gen_input(ind, n):
    os.makedirs(ind, exist_ok=True)
    for i in range(n):
        sub = os.path.join(ind, f"d{i % 5}")
        os.makedirs(sub, exist_ok=True)
        with open(os.path.join(sub, f"f{i:04d}.txt"), "wb") as f:
            f.write((f"record {i}\n" * (1 + i % 7)).encode())


def list_inputs(ind):
    rels = []
    for r, _d, fs in os.walk(ind):
        for fn in fs:
            rels.append(os.path.relpath(os.path.join(r, fn), ind).replace("\\", "/"))
    return sorted(rels)


def out_path(outd, rel):
    return os.path.join(outd, (rel + ".json").replace("/", os.sep))


def run_until_k(impl, ind, outd, journal, k):
    proc = subprocess.Popen([PY, impl, "--input-dir", ind, "--output-dir", outd, "--journal", journal],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            encoding="utf-8", errors="replace")
    count = 0
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if o.get("action") == "processed":
            count += 1
            if count >= k:
                proc.kill()  # Internal calibration detail.
                break
    proc.wait(timeout=10)
    return count, proc.returncode


def run_full(impl, ind, outd, journal):
    p = subprocess.run([PY, impl, "--input-dir", ind, "--output-dir", outd, "--journal", journal],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, p.stderr


def load_journal(journal):
    ents = {}
    if os.path.isfile(journal):
        for line in open(journal, encoding="utf-8", errors="replace"):
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(e, dict) and e.get("status") == "done":
                ents[e["rel_path"]] = e
    return ents


def check_partial(ind, outd, journal):
    problems = []
    j = load_journal(journal)
    for rel, e in j.items():
        op = out_path(outd, rel)
        if not os.path.isfile(op):
            problems.append(f"journal marks a missing output as complete: {rel}")
            continue
        h = hashlib.sha256(open(op, "rb").read()).hexdigest()
        if h != e.get("output_sha256"):
            problems.append(f"journal output hash does not match the file: {rel}")
    # Internal calibration detail.
    for rel in list_inputs(ind):
        op = out_path(outd, rel)
        if os.path.isfile(op):
            data = open(os.path.join(ind, rel.replace("/", os.sep)), "rb").read()
            if open(op, "rb").read() != expected_output(rel, data):
                problems.append(f"output does not match the expected content: {rel}")
    # Internal calibration detail.
    for r, _d, fs in os.walk(outd):
        for fn in fs:
            if fn.endswith(".part"):
                problems.append(f"incomplete temporary output remains: {fn}")
    return problems, len(j)


def check_final(ind, outd, journal):
    problems = []
    j = load_journal(journal)
    rels = list_inputs(ind)
    for rel in rels:
        data = open(os.path.join(ind, rel.replace("/", os.sep)), "rb").read()
        op = out_path(outd, rel)
        if not os.path.isfile(op):
            problems.append(f"missing expected output: {rel}"); continue
        if open(op, "rb").read() != expected_output(rel, data):
            problems.append(f"missing expected output: {rel}")
        if rel not in j:
            problems.append(f"journal has no completed entry: {rel}")
    for r, _d, fs in os.walk(outd):
        for fn in fs:
            if fn.endswith(".part"):
                problems.append(f"incomplete temporary output remains: {fn}")
    return problems, len(rels)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--impl", default=os.path.join(HERE, "ref_impl.py"))
    a = ap.parse_args()
    logp = os.path.join(HERE, "logs", "interrupt-probe.log")
    os.makedirs(os.path.dirname(logp), exist_ok=True)
    _o = sys.stdout; sys.stdout = _Tee(logp, _o)
    impl = a.impl if os.path.isabs(a.impl) else os.path.join(HERE, a.impl)
    tmp = tempfile.mkdtemp(prefix="qwen_eng002_")
    ind = os.path.join(tmp, "input"); outd = os.path.join(tmp, "output"); journal = os.path.join(tmp, "j.jsonl")
    allok = True
    try:
        gen_input(ind, N_ITEMS)
        print(f"== eng-002 interruption and resume probe == impl={os.path.basename(impl)} N={N_ITEMS} kill_after={KILL_AFTER}")
        killed, rc1 = run_until_k(impl, ind, outd, journal, KILL_AFTER)
        print(f"Interrupted after {killed} processed records; exit_code={rc1}")
        pp, jn = check_partial(ind, outd, journal)
        interrupted_mid = 0 < jn < N_ITEMS
        print(f"Partial journal has {jn} of {N_ITEMS} completed records: {interrupted_mid}")
        allok &= interrupted_mid
        print(f"Partial-state problems: {len(pp)} {pp[:3]}")
        allok &= (not pp)
        rc2, err2 = run_full(impl, ind, outd, journal)
        print(f"Resume exit_code={rc2}")
        allok &= (rc2 == 0)
        fp, total = check_final(ind, outd, journal)
        print(f"Final state: records={total}, problems={len(fp)} {fp[:3]}")
        allok &= (not fp)
        print("All interrupted-state checks passed." if allok else "Interrupted-state checks failed.")
        print(f"Probe configuration: N={N_ITEMS}; kill_after={KILL_AFTER}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        sys.stdout = _o; sys.stdout.flush()
    print("RESULT:", "PASS" if allok else "FAIL")
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
