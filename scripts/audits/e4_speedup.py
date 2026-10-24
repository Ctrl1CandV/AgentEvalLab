#!/usr/bin/env python3
"""Success audit of the E4 speedup item, from its public contract: the delivered analyze.py must print exactly what the
original prints, byte for byte, for every input. The audit writes days of its own, independent of the hidden checks'
generator: normal days, days full of malformed and unusual rows (offsets, fractions, whitespace, case, Unicode digits,
underscores, query strings, slashes, quoted commas and line breaks, short and long rows, CRLF), exact session and burst
boundaries, and edge files (empty, header only, a byte-order mark). It runs the original and the delivery in the
sandbox and compares their output and exit status. A fresh large day gives the delivery's time beside the package's
reference, as a note.

Usage: python3 -I scripts/audits/e4_speedup.py <request.json> <result.json>
"""
import csv
import datetime as dt
import io
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LAUNCHER = os.path.join(ROOT, "scripts", "sandbox_exec.py")
HEADER = ["ts", "user", "path", "status", "bytes", "latency_ms", "referrer"]
PATHS = ["/", "/login", "/logout", "/api/v2/import", "/api/v2/export", "/account/settings", "/search", "/cart", "/checkout", "/help/faq"]
REFERRERS = ["", "", "ads", "newsletter", "https://news.example", "search", "-"]


def stamp(moment, offset_minutes=0, digits=3):
    local = moment + dt.timedelta(minutes=offset_minutes)
    fraction = f"{local.microsecond:06d}"[:digits]
    zone = "Z" if offset_minutes == 0 else f"{'+' if offset_minutes > 0 else '-'}{abs(offset_minutes) // 60:02d}:{abs(offset_minutes) % 60:02d}"
    return local.strftime("%Y-%m-%dT%H:%M:%S") + (f".{fraction}" if digits else "") + zone


def normal_row(rng, base, users):
    moment = base + dt.timedelta(seconds=rng.uniform(0, 86_400))
    path = rng.choice(PATHS) + rng.choice(["", "", "/", "?page=2", "?q=a"])
    return [stamp(moment, rng.choice([0, 0, 0, 120, -300]), rng.choice([3, 3, 6])), f"user{rng.randrange(users):04d}", path,
            str(rng.choice([200, 200, 200, 201, 304, 404, 500, 503])), str(rng.randrange(100, 200_000)), str(rng.randrange(5, 3_000)), rng.choice(REFERRERS)]


QUIRK_KINDS = ["offset +14:00", "no fraction", "no such day", "user with spaces and capitals", "Unicode or empty user", "odd path",
               "odd status", "odd bytes", "odd latency", "odd referrer", "two fields", "no referrer column", "extra fields", "all fields empty",
               "space instead of T", "lowercase z", "normal", "normal"]


def quirky_row(rng, base, users, kind=None):
    row = normal_row(rng, base, users)
    kind = rng.randrange(18) if kind is None else kind
    if kind == 0:
        row[0] = row[0].replace("Z", "+14:00") if row[0].endswith("Z") else row[0]
    elif kind == 1:
        row[0] = row[0].split(".")[0] + "Z"  # no fraction: the original skips it
    elif kind == 2:
        row[0] = "2026-09-31T10:00:00.000Z"  # no such day
    elif kind == 3:
        row[1] = f"  USER{rng.randrange(users):04d} "
    elif kind == 4:
        row[1] = rng.choice(["Ölaf", "ǅemal", "ẞtraße", "", "İstanbul"])
    elif kind == 5:
        row[2] = rng.choice(["//", "", "/?x=1", "/search?q=a?b", "/cart///", "/über/", "/a b/"])
    elif kind == 6:
        row[3] = rng.choice([" 500", "503 ", "+502", "５０３", "1_000", "abc", "", "5e2", "-500"])
    elif kind == 7:
        row[4] = rng.choice(["1_234", "-5", "007", " 12 ", "１２", "", "nan", "0x10"])
    elif kind == 8:
        row[5] = rng.choice(["0", "٣٤", "12_0", "", "1.5", " 9"])
    elif kind == 9:
        row[6] = rng.choice(["https://x.example/?a=1,b=2", "line one\nline two", 'say "hi"', "-", " ads "])
    elif kind == 10:
        row = row[:2]  # too short: the original skips it
    elif kind == 11:
        row = row[:6]  # no referrer: it becomes "-"
    elif kind == 12:
        row = row + ["extra", "fields"]
    elif kind == 13:
        row = [""] * 7
    elif kind == 14:
        row[0] = row[0].replace("T", " ")
    elif kind == 15:
        row[0] = row[0][:-1] + "z"
    return row


def write_day(rows, crlf=False, bom=False):
    handle = io.StringIO()
    writer = csv.writer(handle, lineterminator="\r\n" if crlf else "\n")
    writer.writerow(HEADER)
    for row in rows:
        writer.writerow(row)
    return ("\ufeff" if bom else "") + handle.getvalue()


def boundary_rows(base):
    """Sessions split after more than 30 minutes and bursts of five within ten seconds, both ends included."""
    rows = []
    for user, gaps in (("edge0001", [0, 1800, 1800.001]), ("edge0002", [0, 2.5, 2.5, 2.5, 2.5]), ("edge0003", [0, 2.5, 2.5, 2.5, 2.501])):
        moment = base
        for gap in gaps:
            moment += dt.timedelta(seconds=gap)
            rows.append([stamp(moment), user, "/", "200", "1", "1", ""])
    return rows


def cases(seed):
    rng = random.Random(seed)
    base = dt.datetime(2026, 9, 14, tzinfo=dt.timezone.utc)
    found = []
    for index in range(4):
        found.append((f"normal-{index}", write_day([normal_row(rng, base, 400) for _ in range(3_000)], crlf=index == 3)))
    for index in range(5):
        found.append((f"quirks-{index}", write_day([quirky_row(rng, base, 250) if rng.random() < 0.35 else normal_row(rng, base, 250) for _ in range(2_000)] + boundary_rows(base))))
    found += [("empty", ""), ("header-only", write_day([])), ("bom", write_day([normal_row(rng, base, 50) for _ in range(50)], bom=True)),
              ("blank-lines", write_day([]) + "\n\n,,,,,,\n"), ("boundaries", write_day(boundary_rows(base))),
              ("one-row", write_day([normal_row(rng, base, 1)]))]
    return found


def run(directory, program, data_path, timeout=600):
    command = [sys.executable, LAUNCHER, "--rw", directory, "--", "python3", program, data_path]
    started = time.perf_counter()
    try:
        done = subprocess.run(command, cwd=directory, capture_output=True, timeout=timeout)
        return done.returncode, done.stdout, time.perf_counter() - started
    except subprocess.TimeoutExpired:
        return 124, b"", timeout


def main():
    request = json.load(open(sys.argv[1]))
    package = request["package"]
    original = os.path.join(package, "items", "speedup", "public", "analyze.py")
    reference = os.path.join(package, "private", "speedup_item", "reference.py")
    findings, notes = [], []
    work = tempfile.mkdtemp(prefix="audit-e4-")
    try:
        inputs = cases("e4-speedup-audit")
        expected = {}
        oracle_dir = os.path.join(work, "original")
        os.makedirs(oracle_dir)
        shutil.copy(original, os.path.join(oracle_dir, "analyze.py"))
        for name, text in inputs:
            path = os.path.join(oracle_dir, f"{name}.csv")
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write(text)
            code, stdout, _ = run(oracle_dir, "analyze.py", path)
            expected[name] = (code, stdout)
        crashing = [name for name, (code, _) in expected.items() if code != 0]
        notes.append(f"{len(inputs)} audit inputs; the original exits non-zero on {crashing or 'none'} (such inputs are compared too: same status, same output).")
        large_rng = random.Random("e4-speedup-audit-large")
        large = write_day([normal_row(large_rng, dt.datetime(2026, 9, 15, tzinfo=dt.timezone.utc), 2_000) for _ in range(200_000)])
        for trial in request["trials"]:
            if trial.get("itemId") != "speedup":
                continue
            candidate = os.path.join(work, os.path.basename(trial["directory"]))
            shutil.copytree(os.path.join(trial["directory"], "artifacts", "public"), candidate)
            grade = json.load(open(sorted((os.path.join(trial["directory"], "score-runs", name, "score.json") for name in os.listdir(os.path.join(trial["directory"], "score-runs"))),
                                          key=lambda path: json.load(open(path))["createdAt"])[-1]))["evaluation"]
            checks = {check["id"].split("-", 1)[-1] if check["id"].startswith("speedup-") else check["id"]: check["passed"] for check in grade["checks"]}
            outputs_pass = all(checks.get(name) for name in ("small", "large", "quirks"))
            mismatches = []
            for name, text in inputs:
                path = os.path.join(candidate, f"audit-{name}.csv")
                with open(path, "w", encoding="utf-8", newline="") as handle:
                    handle.write(text)
                code, stdout, _ = run(candidate, "analyze.py", path)
                if (code, stdout) != expected[name]:
                    mismatches.append(f"{name} (exit {code} vs {expected[name][0]}, {len(stdout)} vs {len(expected[name][1])} bytes)")
            verdict = ("true pass" if not mismatches else "false pass") if outputs_pass else ("note" if not mismatches else "true fail")
            findings.append({"trial": trial["directory"], "label": trial["label"], "item": "speedup", "unit": "output identical to the original on audit inputs",
                             "grader": "pass" if outputs_pass else "fail", "verdict": verdict, "detail": "; ".join(mismatches[:5])})
            path = os.path.join(candidate, "audit-large.csv")
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write(large)
            shutil.copy(reference, os.path.join(candidate, "audit_reference.py"))
            times = {"delivery": [], "reference": []}
            outputs = {}
            for _ in range(2):
                for label, program in (("delivery", "analyze.py"), ("reference", "audit_reference.py")):
                    code, stdout, seconds = run(candidate, program, path)
                    times[label].append(seconds)
                    outputs[label] = (code, stdout)
            same = outputs["delivery"] == outputs["reference"]
            findings.append({"trial": trial["directory"], "label": trial["label"], "item": "speedup", "unit": "fresh 200,000-event day",
                             "grader": "pass" if checks.get("large") else "fail",
                             "verdict": ("true pass" if same else "false pass") if checks.get("large") else ("note" if same else "true fail"),
                             "detail": f"output {'identical to' if same else 'different from'} the reference; best time {min(times['delivery']):.2f} s vs reference {min(times['reference']):.2f} s "
                                       f"(ratio {min(times['delivery']) / min(times['reference']):.2f}, wall time on a shared machine, a note only)"})
    finally:
        shutil.rmtree(work, ignore_errors=True)
    json.dump({"findings": findings, "notes": notes}, open(sys.argv[2], "w"), indent=1)


if __name__ == "__main__":
    main()
