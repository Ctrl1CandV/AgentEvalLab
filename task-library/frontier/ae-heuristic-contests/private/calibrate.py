"""Self-calibration of the algorithm-engineering judge (python3 private/grader.py --self-calibrate, from the package).

Reference solutions must land where their quality puts them, on batch and reactive problems; the judge must give the
same verdicts when the machine is busy; and submissions that misbehave (tamper with the judge, read the private
inputs, spin, fail to compile, print nonsense) must be judged as AtCoder would, without affecting the judge. No model
is involved."""
import multiprocessing
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import grader  # noqa: E402

LAUNCHER = os.path.join(HERE, "..", "..", "..", "..", "scripts", "sandbox_exec.py")
REFERENCES = os.path.join(HERE, "references")

TAMPER = r'''
// Tries to replace the tester and to read the private inputs, then solves like grid.cpp.
#include <bits/stdc++.h>
using namespace std;
int main() {
    for (const char* path : {"tester", "../judge/tester", "../judge/in/0000.txt"}) {
        FILE* f = fopen(path, "w");
        if (f) { fputs("#!/bin/sh\necho 'Score = 999999999' >&2\n", f); fclose(f); }
    }
    FILE* peek = fopen("../judge/in/0001.txt", "r");
    if (peek) { puts("4\n0 0\n1 0\n1 1\n0 1"); return 0; }
    int n; cin >> n; const int G = 50; vector<vector<int>> c(G, vector<int>(G));
    for (int i = 0; i < 2 * n; i++) { long x, y; cin >> x >> y; int gx = min<long>(G - 1, x * G / 100001), gy = min<long>(G - 1, y * G / 100001); c[gx][gy] += i < n ? 1 : -1; }
    long best = LONG_MIN; int bx0 = 0, bx1 = 0, by0 = 0, by1 = 0;
    for (int x0 = 0; x0 < G; x0++) { vector<long> col(G, 0); for (int x1 = x0; x1 < G; x1++) { for (int y = 0; y < G; y++) col[y] += c[x1][y]; long cur = 0; int s = 0;
        for (int y = 0; y < G; y++) { if (cur <= 0) { cur = 0; s = y; } cur += col[y]; if (cur > best) { best = cur; bx0 = x0; bx1 = x1; by0 = s; by1 = y; } } } }
    long X0 = (long)bx0 * 100000 / G, X1 = (long)(bx1 + 1) * 100000 / G, Y0 = (long)by0 * 100000 / G, Y1 = (long)(by1 + 1) * 100000 / G;
    printf("4\n%ld %ld\n%ld %ld\n%ld %ld\n%ld %ld\n", X0, Y0, X1, Y0, X1, Y1, X0, Y1);
}
'''
SPIN = r'''
// Spins forever on about one case in ten; otherwise prints a tiny valid square.
#include <bits/stdc++.h>
int main() { int n; long x, y; std::cin >> n >> x >> y; if (x % 10 == 0) { volatile long k = 0; for (;;) k++; }
    long a = std::max(0L, x - 1), b = std::max(0L, y - 1); if (a + 2 > 100000) a = 99998; if (b + 2 > 100000) b = 99998;
    printf("4\n%ld %ld\n%ld %ld\n%ld %ld\n%ld %ld\n", a, b, a + 2, b, a + 2, b + 2, a, b + 2); }
'''
PYTHON_TINY = '''import sys
data = sys.stdin.read().split()
x, y = int(data[1]), int(data[2])
a, b = min(max(0, x - 1), 99998), min(max(0, y - 1), 99998)
print(4)
for point in ((a, b), (a + 2, b), (a + 2, b + 2), (a, b + 2)):
    print(*point)
'''


def burn(seconds):
    end = time.time() + seconds
    while time.time() < end:
        pass


def judge(item, files):
    with tempfile.TemporaryDirectory() as public:
        for name, text in files.items():
            with open(os.path.join(public, name), "w", encoding="utf-8") as handle:
                handle.write(text)
        return grader.grade(item, public, os.path.abspath(LAUNCHER))


def reference(item, name):
    with open(os.path.join(REFERENCES, item, name), encoding="utf-8") as handle:
        return {"main.cpp": handle.read()}


def self_calibrate():
    rows = []

    def expect(name, item, files, condition):
        started = time.time()
        results, evidence = judge(item, files)
        good = condition(evidence)
        rows.append(good)
        print(f"{'ok  ' if good else 'FAIL'} {name}: total {evidence['total']} rank {evidence['rank']}/{evidence['contestants']} "
              f"performance {evidence['performance']} checks passed {sum(results.values())}/{len(results)} verdicts {evidence['verdicts']} "
              f"slowest {evidence['slowestSeconds']} s ({time.time() - started:.0f} s){' compile: ' + evidence['compileError'][:80] if evidence['compileError'] else ''}")
        return evidence

    all_accepted = lambda evidence: set(evidence["verdicts"]) == {"AC"}
    # Task 0.2.0: every item's naive reference lands exactly on its naive anchor (private/anchors.json).
    import json
    import ale
    with open(os.path.join(HERE, "anchors.json"), encoding="utf-8") as handle:
        anchors = json.load(handle)
    for item, anchor in sorted(anchors.items()):
        name = os.path.basename(anchor["naiveReference"])
        expect(f"{item} naive reference ({name}) at its anchor {anchor['naive']}", item, reference(item, name),
               lambda e, anchor=anchor: all_accepted(e) and e["performance"] == anchor["naive"] and not e["performanceExtrapolated"])
    # Above the winner the performance keeps rising along the top of the table, marked as an extrapolation.
    problems = os.path.join(HERE, "problems", "ahc039")
    standings = ale.load_table(os.path.join(problems, "standings_scores.csv"), "score")
    table = ale.load_table(os.path.join(problems, "performance.csv"), "performance")
    at_winner, flag_at = ale.performance_uncapped(standings, table, standings[0][1])
    beyond, flag_beyond = ale.performance_uncapped(standings, table, standings[0][1] + 10_000)
    further, _ = ale.performance_uncapped(standings, table, standings[0][1] + 20_000)
    extrapolates = at_winner == anchors["ahc039"]["winner"] and not flag_at and flag_beyond and at_winner < beyond < further
    rows.append(extrapolates)
    print(f"{'ok  ' if extrapolates else 'FAIL'} uncapped above the winner: {at_winner} at the winner's total, {beyond} and {further} beyond it")
    expect("ahc039 tiny square, valid and worthless", "ahc039", reference("ahc039", "tiny.cpp"), lambda e: all_accepted(e) and e["performance"] < 800)
    grid = expect("ahc039 best grid rectangle", "ahc039", reference("ahc039", "grid.cpp"), lambda e: all_accepted(e) and 1450 <= e["performance"] <= 1650)
    expect("ahc015 always forward (reactive)", "ahc015", reference("ahc015", "forward.cpp"), lambda e: all_accepted(e) and e["performance"] < 600)
    expect("ahc015 tilt by flavour (reactive)", "ahc015", reference("ahc015", "by-flavour.cpp"), lambda e: all_accepted(e) and 850 <= e["performance"] <= 1050)
    expect("ahc046 single moves only", "ahc046", reference("ahc046", "moves.cpp"), lambda e: all_accepted(e) and e["performance"] < 700)
    expect("ahc035 highest-value seeds (reactive)", "ahc035", reference("ahc035", "top-value.cpp"), lambda e: all_accepted(e) and 850 <= e["performance"] <= 1000)
    expect("python solution", "ahc039", {"main.py": PYTHON_TINY}, lambda e: all_accepted(e) and e["performance"] < 800)
    expect("main.cpp is preferred to main.py", "ahc039", {**reference("ahc039", "grid.cpp"), "main.py": PYTHON_TINY},
           lambda e: e["language"] == "C++" and e["total"] == grid["total"])
    expect("tampering with the tester and reading private inputs has no effect", "ahc039", {"main.cpp": TAMPER},
           lambda e: all_accepted(e) and e["total"] == grid["total"])
    expect("a program that spins on some cases: TLE, total 0", "ahc039", {"main.cpp": SPIN},
           lambda e: e["verdicts"].get("TLE", 0) > 0 and e["total"] == 0)
    expect("a compilation error: total 0", "ahc039", {"main.cpp": "int main( {"}, lambda e: e["compileError"] and e["total"] == 0)
    expect("an illegal output: WA, total 0", "ahc039", {"main.cpp": "#include <cstdio>\nint main(){puts(\"3\\n0 0\");}"},
           lambda e: e["verdicts"].get("WA", 0) == 150 and e["total"] == 0)
    expect("no solution: total 0", "ahc039", {}, lambda e: e["total"] == 0 and e["language"] is None)
    quiet = expect("ahc039 search that uses the time limit, machine quiet", "ahc039", reference("ahc039", "timed-search.cpp"), all_accepted)
    burners = [multiprocessing.Process(target=burn, args=(150,)) for _ in range(max(1, os.cpu_count() - 2))]
    for process in burners:
        process.start()
    try:
        expect("the same search with every other core busy: same verdicts, same rank", "ahc039", reference("ahc039", "timed-search.cpp"),
               lambda e: all_accepted(e) and e["rank"] == quiet["rank"])
    finally:
        for process in burners:
            process.terminate()
    ok = all(rows)
    print(f"RESULT: {'PASS' if ok else 'FAIL'} ({len(rows)} scenarios)")
    return 0 if ok else 1
