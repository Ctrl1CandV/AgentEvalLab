#!/usr/bin/env python3
"""Activity report for an events export.

Usage: python3 report.py events.csv > report.txt
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
            if parts[0] == "ts":
                # A header; exports that were concatenated repeat it.
                continue
            if len(parts) != 4:
                continue
            ts, user, action, amount = parts
            try:
                value = float(amount)
            except ValueError:
                continue
            rows.append((ts, user.lower(), action, value))
    return rows


def main():
    rows = load(sys.argv[1])
    users = []
    for row in rows:
        if row[1] not in users:
            users.append(row[1])
    out = ""
    out += "users: %d\n" % len(users)
    totals = []
    for user in users:
        total = 0.0
        for row in rows:
            if row[1] == user:
                total += row[3]
        totals.append((user, total))
    ranked = sorted(totals, key=lambda pair: -pair[1])
    out += "top:\n"
    for user, total in ranked[:10]:
        out += "  %s %.2f\n" % (user, total)
    actions = []
    for row in rows:
        if row[2] not in actions:
            actions.append(row[2])
            actions.sort()
    for action in actions:
        values = sorted(row[3] for row in rows if row[2] == action)
        median = values[(len(values) - 1) // 2]
        out += "%s: n=%d median=%s max=%s\n" % (action, len(values), round(median, 1), max(values))
    first = min(row[0] for row in rows) if rows else "-"
    last = max(row[0] for row in rows) if rows else "-"
    out += "span: %s .. %s\n" % (first, last)
    sys.stdout.write(out)


if __name__ == "__main__":
    main()
