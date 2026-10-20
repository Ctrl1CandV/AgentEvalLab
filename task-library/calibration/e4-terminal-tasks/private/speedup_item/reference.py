#!/usr/bin/env python3
"""The speedup item's reference: the same report as analyze.py, byte for byte, in one pass and O(n log n).

Canonical timestamps take a fast path; anything else goes to strptime exactly as the original does, so its lenient
and strict cases come out the same. Times are kept as integer microseconds since 1970 in UTC.
"""
import bisect
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone

UTC = timezone.utc
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
CANONICAL = re.compile(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})\.(\d{3})(Z|[+-]\d{2}:\d{2})\Z")
MICRO = timedelta(microseconds=1)
HOUR, DAY, GAP, BURST = 3_600_000_000, 86_400_000_000, 1_800_000_000, 10_000_000


def strict(text):
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return (datetime.strptime(text, "%Y-%m-%dT%H:%M:%S.%f%z") - EPOCH) // MICRO


def micros(text, cache={}):
    match = CANONICAL.match(text)
    if match is None:
        return strict(text)
    year, month, day, hour, minute, second, milli, zone = match.groups()
    key = (year, month, day, hour)
    base = cache.get(key)
    if base is None:
        base = cache[key] = (datetime(int(year), int(month), int(day), int(hour), tzinfo=UTC) - EPOCH) // MICRO
    offset = 0 if zone == "Z" else (1 if zone[0] == "+" else -1) * (int(zone[1:3]) * 3_600_000_000 + int(zone[4:6]) * 60_000_000)
    return base + int(minute) * 60_000_000 + int(second) * 1_000_000 + int(milli) * 1_000 - offset


def percentile(ordered, share):
    rank = -(-share * len(ordered) // 100)
    return ordered[max(rank, 1) - 1]


def main():
    times, latencies, hours, pairs, days = defaultdict(list), defaultdict(list), defaultdict(lambda: [0, 0]), Counter(), defaultdict(int)
    rows = skipped = 0
    with open(sys.argv[1], newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader, [])
        columns = [header.index(name) for name in ("ts", "user", "path", "status", "bytes", "latency_ms", "referrer")]
        for record in reader:
            if not record:
                continue  # DictReader skips empty rows without a word
            stamp, user, path, status, size, latency, referrer = (record[position] if position < len(record) else None for position in columns)
            try:
                if user is None:
                    micros(stamp)
                    raise ValueError  # the original fails on the missing user only after reading the time
                moment = micros(stamp)
                user = user.strip().lower()
                path = path.split("?")[0].rstrip("/") or "/"
                status, size, latency = int(status), int(size), int(latency)
            except ValueError:
                skipped += 1
                continue
            referrer = referrer or "-"
            rows += 1
            times[user].append(moment)
            latencies[path].append(latency)
            hour = hours[moment // HOUR]
            hour[0] += 1
            hour[1] += status >= 500
            if referrer != "-":
                pairs[f"{referrer} -> {path}"] += 1
            days[moment // DAY] += size
    sessions, bursts = {}, []
    for user in sorted(times):
        moments = sorted(times[user])
        sessions[user] = 1 + sum(1 for earlier, later in zip(moments, moments[1:]) if later - earlier > GAP)
        if any(bisect.bisect_right(moments, start + BURST) - position >= 5 for position, start in enumerate(moments)):
            bursts.append(user)
    latency = {}
    for path in sorted(latencies):
        ordered = sorted(latencies[path])
        latency[path] = {"count": len(ordered), "p50": percentile(ordered, 50), "p95": percentile(ordered, 95)}
    top = sorted(pairs.items(), key=lambda item: (-item[1], item[0]))[:10]
    error_rates = {(EPOCH + timedelta(hours=hour)).strftime("%Y-%m-%dT%H"): round(errors / total, 4)
                   for hour, (total, errors) in sorted(hours.items())}
    daily = {(date(1970, 1, 1) + timedelta(days=day)).isoformat(): total for day, total in sorted(days.items())}
    report = {"rows": rows, "skipped": skipped, "sessions": sessions, "latency": latency,
              "transitions": [{"pair": pair, "count": count} for pair, count in top], "error_rates": error_rates, "bursts": bursts,
              "daily_bytes": daily}
    print(json.dumps(report, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
