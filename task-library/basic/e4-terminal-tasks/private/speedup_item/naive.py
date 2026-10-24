#!/usr/bin/env python3
"""analyze.py: the nightly traffic report.

    python3 analyze.py events.csv > report.json

Reads the day's request events and prints the report as JSON. The dashboards parse this exact output.
"""
import csv
import json
import sys
from datetime import datetime, timedelta, timezone


def parse_time(text):
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%S.%f%z").astimezone(timezone.utc)


def load(path):
    rows, skipped = [], 0
    with open(path, newline="", encoding="utf-8") as handle:
        for record in csv.DictReader(handle):
            try:
                row = {"time": parse_time(record["ts"]), "user": record["user"].strip().lower(),
                       "path": record["path"].split("?")[0].rstrip("/") or "/", "status": int(record["status"]),
                       "bytes": int(record["bytes"]), "latency": int(record["latency_ms"]), "referrer": record["referrer"] or "-"}
            except (ValueError, KeyError, AttributeError):
                skipped += 1
                continue
            rows.append(row)
    return rows, skipped


def sessions(rows):
    """Sessions per user: a new session starts after more than 30 minutes without a request."""
    result = {}
    for user in sorted(set(row["user"] for row in rows)):
        mine = [row for row in rows if row["user"] == user]
        mine.sort(key=lambda row: row["time"])
        count, last = 0, None
        for row in mine:
            if last is None or row["time"] - last > timedelta(minutes=30):
                count += 1
            last = row["time"]
        result[user] = count
    return result


def percentile(values, share):
    """Nearest rank: the smallest value with at least share% of the values at or below it."""
    ordered = sorted(values)
    rank = -(-share * len(ordered) // 100)
    return ordered[max(rank, 1) - 1]


def latency(rows):
    result = {}
    for path in sorted(set(row["path"] for row in rows)):
        values = [row["latency"] for row in rows if row["path"] == path]
        result[path] = {"count": len(values), "p50": percentile(values, 50), "p95": percentile(values, 95)}
    return result


def transitions(rows):
    """The ten most frequent referrer-to-path pairs, ties in alphabetical order."""
    pairs = [f"{row['referrer']} -> {row['path']}" for row in rows if row["referrer"] != "-"]
    counted = [(pairs.count(pair), pair) for pair in sorted(set(pairs))]
    counted.sort(key=lambda item: (-item[0], item[1]))
    return [{"pair": pair, "count": count} for count, pair in counted[:10]]


def error_rates(rows):
    """Share of 5xx responses per UTC hour."""
    result = {}
    for hour in sorted(set(row["time"].strftime("%Y-%m-%dT%H") for row in rows)):
        mine = [row for row in rows if row["time"].strftime("%Y-%m-%dT%H") == hour]
        errors = len([row for row in mine if row["status"] >= 500])
        result[hour] = round(errors / len(mine), 4)
    return result


def bursts(rows):
    """Users with five or more requests within some ten seconds (both ends included)."""
    found = []
    for user in sorted(set(row["user"] for row in rows)):
        times = sorted(row["time"] for row in rows if row["user"] == user)
        for start in times:
            window = [moment for moment in times if start <= moment <= start + timedelta(seconds=10)]
            if len(window) >= 5:
                found.append(user)
                break
    return found


def daily_bytes(rows):
    days = {}
    for row in rows:
        day = row["time"].date().isoformat()
        days[day] = days.get(day, 0) + row["bytes"]
    return dict(sorted(days.items()))


def main():
    rows, skipped = load(sys.argv[1])
    report = {"rows": len(rows), "skipped": skipped, "sessions": sessions(rows), "latency": latency(rows), "transitions": transitions(rows),
              "error_rates": error_rates(rows), "bursts": bursts(rows), "daily_bytes": daily_bytes(rows)}
    print(json.dumps(report, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
