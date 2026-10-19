#!/usr/bin/env python3
"""Fast report.py with byte-identical output: the oracle solution of the perf item and the source of expected outputs.

Per-user totals add values in file order, as the original does, so floating-point sums match exactly.
"""
import sys


def load(path):
    rows = []
    with open(path, encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = [part.strip() for part in line.split(",")]
            if parts[0] == "ts" or len(parts) != 4:
                continue
            ts, user, action, amount = parts
            try:
                value = float(amount)
            except ValueError:
                continue
            rows.append((ts, user.lower(), action, value))
    return rows


def report(rows):
    totals = {}
    for _, user, _, value in rows:
        totals[user] = totals.get(user, 0.0) + value
    lines = [f"users: {len(totals)}", "top:"]
    ranked = sorted(totals.items(), key=lambda pair: -pair[1])
    lines += ["  %s %.2f" % (user, total) for user, total in ranked[:10]]
    by_action = {}
    for _, _, action, value in rows:
        by_action.setdefault(action, []).append(value)
    for action in sorted(by_action):
        values = sorted(by_action[action])
        median = values[(len(values) - 1) // 2]
        lines.append("%s: n=%d median=%s max=%s" % (action, len(values), round(median, 1), max(values)))
    first = min(row[0] for row in rows) if rows else "-"
    last = max(row[0] for row in rows) if rows else "-"
    lines.append("span: %s .. %s" % (first, last))
    return "\n".join(lines) + "\n"


def main():
    sys.stdout.write(report(load(sys.argv[1])))


if __name__ == "__main__":
    main()
