"""Judging and ranking for AtCoder Heuristic Contest problems, as ALE-Bench judges them.

The problem data (statements, official tools, seeds, standings, performance tables) come from ALE-Bench
(SakanaAI/ALE-Bench on Hugging Face, CC BY-ND 4.0, officially provided by AtCoder Inc.). The judging and ranking rules
follow the ALE-Bench code (github.com/SakanaAI/ALE-Bench, Apache-2.0): `ale_bench/result.py` (overall score),
`ale_bench/data.py` (rank and performance) and `ale_bench/constants.py` (which contests score cases that are not
accepted). Execution differs: ALE-Bench runs Docker; this module runs bubblewrap through the harness's sandbox launcher.

Used by the grader (private test cases, the sandbox launcher from the request) and by the public helper `run.py`,
which carries its own copy of the run and judge steps.
"""
import concurrent.futures
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import time

# Contests whose private (system) test scores count accepted cases even when others fail. All are long contests; in
# every short contest one failed case makes the whole submission score 0. From ale_bench/constants.py.
ALLOW_SCORE_NON_AC_PRIVATE = {
    "ahc001", "ahc003", "ahc008", "ahc011", "ahc013", "ahc014", "ahc016", "ahc017", "ahc018", "ahc019", "ahc022", "ahc023",
    "ahc025", "ahc027", "ahc029", "ahc030", "ahc031", "ahc033", "ahc036", "ahc038", "ahc040", "ahc043", "ahc045", "ahc048",
    "ahc051", "awtf2025heuristic", "future-contest-2022-qual",
}
# The judge measures CPU time and allows 10% over the problem's time limit plus 0.1 s (see calibration.md).
TIME_GRACE_FACTOR = 1.1
TIME_GRACE_SECONDS = 0.1
GRADING_PARALLELISM = 4
COMPILE_SECONDS = 120
CPP_COMMAND = ["g++", "-O2", "-std=gnu++20", "-o", "main", "main.cpp"]
SCORE_LINE = re.compile(r"^Score = (\d+)\s*$")


# Runs inside the sandbox, from a read-only directory: starts the solution, waits for it, and writes its CPU time to a
# descriptor the judge passed in and the solution never sees. (The sandbox's own init does not pass the solution's
# CPU time on to the process the judge waits for.)
CPU_WRAPPER = """import os, sys, time
fd = int(sys.argv[1])
pid = os.fork()
if pid == 0:
    os.close(fd)
    try:
        os.execvp(sys.argv[2], sys.argv[2:])
    finally:
        os._exit(127)
tick = os.sysconf("SC_CLK_TCK")
def report(seconds):
    try:
        os.write(fd, ("%.6f\\n" % seconds).encode())
    except OSError:
        pass
# Sample the solution's CPU time every 10 ms, so that a solution its tester kills at the end of the interaction is still
# measured; the exact figure follows when it exits.
while True:
    done, status, usage = os.wait4(pid, os.WNOHANG)
    if done:
        break
    try:
        with open("/proc/%d/stat" % pid) as handle:
            fields = handle.read().rsplit(")", 1)[1].split()
        report((int(fields[11]) + int(fields[12])) / tick)
    except (OSError, IndexError, ValueError):
        pass
    time.sleep(0.01)
report(usage.ru_utime + usage.ru_stime)
os.close(fd)
code = os.waitstatus_to_exitcode(status)
sys.exit(code if code >= 0 else 128 - code)
"""


def sandboxed(launcher, directory, command, read_only=()):
    if not launcher:
        return command
    return [sys.executable, launcher, "--rw", directory, *[argument for path in read_only for argument in ("--ro", path)], "--", *command]


def install_wrapper(judge_directory):
    """The CPU-time wrapper, in a directory the sandbox mounts read-only."""
    directory = os.path.join(judge_directory, "bin")
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, "cputime.py")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(CPU_WRAPPER)
    return path


def compile_solution(launcher, directory):
    """Compile main.cpp, or accept main.py. Returns (command to run, None) or (None, compiler message)."""
    if os.path.exists(os.path.join(directory, "main.cpp")):
        try:
            result = subprocess.run(sandboxed(launcher, directory, CPP_COMMAND), cwd=directory, capture_output=True, text=True,
                                    timeout=COMPILE_SECONDS)
        except subprocess.TimeoutExpired:
            return None, "compilation took longer than 120 seconds"
        if result.returncode != 0 or not os.path.exists(os.path.join(directory, "main")):
            return None, (result.stderr or result.stdout)[-4000:]
        return ["./main"], None
    if os.path.exists(os.path.join(directory, "main.py")):
        return ["python3", "main.py"], None
    return None, "neither main.cpp nor main.py exists"


def timed_run(command, cwd, stdin, stdout, stderr, wall_cap):
    """Run a command; returns (exit status, CPU seconds reported by the wrapper or None, killed at the wall-clock cap)."""
    report_read, report_write = os.pipe()
    command = [part if part != "{cpu-fd}" else str(report_write) for part in command]
    try:
        process = subprocess.Popen(command, cwd=cwd, stdin=stdin, stdout=stdout, stderr=stderr, pass_fds=(report_write,))
    finally:
        os.close(report_write)
    try:
        killed = False
        try:
            process.wait(timeout=wall_cap)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            killed = True
        report = b""
        while chunk := os.read(report_read, 64):
            report += chunk
    finally:
        os.close(report_read)
    try:
        seconds = float(report.decode().split()[-1])
    except (ValueError, IndexError):
        seconds = None
    return process.returncode, seconds, killed


def run_case(launcher, run_directory, judge_directory, problem, run_command, input_path, output_path):
    """Run one case and judge it with the official tester. Returns (verdict, score, CPU seconds, message).

    The solution runs in the sandbox, which can write only `run_directory` (the solution itself). The tester, the
    inputs and the outputs stay in `judge_directory`, out of the solution's reach: the tester runs outside the sandbox
    and, for a reactive problem, starts the sandboxed solution itself. The time limit applies to the solution's CPU
    time, measured by the wrapper; a wall-clock cap of three times the limit only stops a program that blocks."""
    limit = problem["time_limit"]
    allowed = limit * TIME_GRACE_FACTOR + TIME_GRACE_SECONDS
    wrapper = os.path.join(judge_directory, "bin", "cputime.py")
    guarded = sandboxed(launcher, run_directory,
                        [sys.executable, wrapper, "{cpu-fd}", "prlimit", f"--as={problem['memory_limit']}", f"--cpu={int(allowed) + 2}", "--",
                         *run_command], read_only=[os.path.dirname(wrapper)])
    tester = os.path.join(judge_directory, "tester")
    with open(input_path, "rb") as source, open(output_path, "wb") as sink, open(output_path + ".err", "w+b") as errors:
        if problem["problem_type"] == "reactive":
            status, seconds, killed = timed_run([tester, *guarded], run_directory, source, sink, errors, limit * 3 + 2)
            errors.seek(0)
            stderr = errors.read().decode("utf-8", "replace")
        else:
            status, seconds, killed = timed_run(guarded, run_directory, source, sink, subprocess.DEVNULL, limit * 3 + 2)
            stderr = ""
    os.remove(output_path + ".err")
    if killed:
        return "TLE", 0, limit * 3 + 2, "stopped at the wall-clock cap"
    if seconds is None:
        return "RE", 0, 0.0, f"the solution did not run (exit status {status})"
    if seconds > allowed:
        return "TLE", 0, seconds, f"used {seconds:.2f} s of CPU time; the limit is {limit} s"
    if problem["problem_type"] != "reactive":
        if status != 0:
            return "RE", 0, seconds, f"exit status {status}"
        stderr = subprocess.run([tester, input_path, output_path], cwd=judge_directory, capture_output=True, text=True, timeout=120).stderr
    lines = [line for line in stderr.strip().splitlines() if line.strip()]
    if "wrong answer: " in stderr:
        return "WA", 0, seconds, stderr.split("wrong answer: ", 1)[1].strip()[:300]
    match = SCORE_LINE.match(lines[-1]) if lines else None
    if problem["problem_type"] == "reactive" and status != 0 and not match:
        return "RE", 0, seconds, f"exit status {status}"
    if not match:
        return "WA", 0, seconds, (stderr.strip()[-300:] or "no score")
    return "AC", int(match.group(1)), seconds, ""


def judge(launcher, run_directory, judge_directory, problem, inputs, parallelism=GRADING_PARALLELISM):
    """Compile the solution in `run_directory` and judge every input: ([(name, verdict, score, seconds, message)],
    None), or (None, compiler message)."""
    run_command, error = compile_solution(launcher, run_directory)
    if run_command is None:
        return None, error
    install_wrapper(judge_directory)
    out_directory = os.path.join(judge_directory, "out")
    os.makedirs(out_directory, exist_ok=True)

    def one(path):
        name = os.path.basename(path)
        verdict, score, seconds, message = run_case(launcher, run_directory, judge_directory, problem, run_command, path,
                                                    os.path.join(out_directory, name))
        return name, verdict, score, seconds, message
    with concurrent.futures.ThreadPoolExecutor(parallelism) as pool:
        return list(pool.map(one, inputs)), None


def overall_score(problem_id, cases):
    """The submission's total as AtCoder counted it (ale_bench/result.py, overall_absolute_score)."""
    if cases is None:
        return 0
    accepted = all(case[1] == "AC" for case in cases)
    if not accepted and problem_id not in ALLOW_SCORE_NON_AC_PRIVATE:
        return 0
    return sum(case[2] for case in cases if case[1] == "AC")


def load_table(path, value):
    with open(path, encoding="utf-8") as handle:
        return [(int(row["rank"]), int(row[value])) for row in csv.DictReader(handle)]


def score_rank_list(standings):
    """[(score, first rank, last rank)] of the standings, the last entry being the score-0 entry (data.py, Standings)."""
    groups, rank_start = [], standings[0][0]
    for index in range(1, len(standings)):
        score = standings[index - 1][1]
        next_rank, next_score = standings[index]
        if score == next_score:
            continue  # in early contests, the same score may have different ranks
        groups.append((score, rank_start, next_rank - 1))
        rank_start = next_rank
    groups.append((standings[-1][1], standings[-1][0], standings[-1][0]))
    return groups


def rank_of(standings, total):
    """(standings rank, rank for the performance) of an absolute total (data.py, Standings.get_new_rank): above every
    lower score; on a tie, the average of the tied ranks for the performance; a total of 0 takes the last entry."""
    groups = score_rank_list(standings)
    if total == 0:
        return groups[-1][1], float(groups[-1][1])
    for score, first, last in groups:
        if total > score:
            return first, float(first)
        if total == score:
            return first, (first + last) / 2
    raise RuntimeError("the standings end with a score-0 entry, so a positive total always ranks")


def performance_of(table, rank):
    """AtCoder performance at a rank (data.py, RankPerformanceMap): entries sharing a rank stand at the middle of their
    rank range, the last (score-0) entry at its own rank, and other ranks are interpolated linearly."""
    points = {}
    for index in range(len(table) - 1):
        rank_here, perf = table[index]
        next_rank = table[index + 1][0]
        if rank_here == next_rank:
            continue
        points[(rank_here + next_rank - 1) / 2] = perf
    points[float(table[-1][0])] = table[-1][1]
    rank = float(rank)
    if rank in points:
        return points[rank]
    keys = sorted(points)
    lose, win = -1, len(keys)
    while win - lose > 1:
        middle = (lose + win) // 2
        if rank < keys[middle]:
            win = middle
        else:
            lose = middle
    if win == len(keys):
        raise RuntimeError("the rank lies beyond the last entry")
    win = max(win, 1)
    high, low = keys[win - 1], keys[win]
    return round(points[high] - (points[high] - points[low]) * (rank - high) / (low - high))


def load_problem(directory):
    """The judging facts of a problem directory (data.json from ALE-Bench)."""
    with open(os.path.join(directory, "data.json"), encoding="utf-8") as handle:
        data = json.load(handle)
    metadata, constraints = data["metadata"], data["constraints"]
    return {"id": metadata["problem_id"], "title": metadata["title"], "problem_type": metadata["problem_type"],
            "score_type": metadata["score_type"], "time_limit": float(constraints["time_limit"]),
            "memory_limit": int(constraints["memory_limit"]), "start_at": metadata["start_at"], "end_at": metadata["end_at"]}


def copy_tools(source, destination):
    for name in ("gen", "tester"):
        shutil.copy2(os.path.join(source, name), os.path.join(destination, name))
