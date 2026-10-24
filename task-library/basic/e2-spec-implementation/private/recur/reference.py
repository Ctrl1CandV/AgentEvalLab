#!/usr/bin/env python3
"""Reference implementation of the E2 recur specification (items/recur/prompt.md). Standard library only."""
import calendar
import datetime
import json
import re
import sys

WEEKDAYS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
FREQUENCIES = {"daily", "weekly", "monthly", "yearly"}
LAST = datetime.date(2099, 12, 31)
MAX_OCCURRENCES = 1000
DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


class Invalid(Exception):
    pass


def date(value):
    if not isinstance(value, str) or not DATE.match(value):
        raise Invalid()
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        raise Invalid() from None


def positive(value):
    if type(value) is not int or value < 1:
        raise Invalid()
    return value


def candidates(rule, start):
    """Occurrences on or after start, in date order, never after LAST."""
    freq, interval = rule["freq"], rule.get("interval", 1)
    if freq == "daily":
        day = start
        while day <= LAST:
            yield day
            day += datetime.timedelta(days=interval)
    elif freq == "weekly":
        days = sorted({WEEKDAYS.index(code) for code in rule.get("days", [WEEKDAYS[start.weekday()]])})
        monday = start - datetime.timedelta(days=start.weekday())
        while monday <= LAST:
            for offset in days:
                day = monday + datetime.timedelta(days=offset)
                if day > LAST:
                    return
                if day >= start:
                    yield day
            monday += datetime.timedelta(weeks=interval)
    elif freq == "monthly":
        index = start.year * 12 + start.month - 1
        while index // 12 <= LAST.year:
            year, month = divmod(index, 12)
            month += 1
            length = calendar.monthrange(year, month)[1]
            day = None
            if "nth" in rule:
                n, code = rule["nth"]
                matches = [number for number in range(1, length + 1) if datetime.date(year, month, number).weekday() == WEEKDAYS.index(code)]
                if n <= len(matches) and -n <= len(matches):
                    day = datetime.date(year, month, matches[n - 1] if n > 0 else matches[n])
            else:
                wanted = rule.get("monthday", start.day)
                if wanted <= length:
                    day = datetime.date(year, month, wanted)
                elif rule.get("overflow", "skip") == "clamp":
                    day = datetime.date(year, month, length)
            if day is not None and day >= start:
                yield day
            index += interval
    else:
        year = start.year
        while year <= LAST.year:
            if start.month == 2 and start.day == 29 and not calendar.isleap(year):
                if rule.get("overflow", "skip") == "clamp":
                    yield datetime.date(year, 2, 28)
            else:
                yield datetime.date(year, start.month, start.day)
            year += interval


def validate(rule):
    start = date(rule.get("start"))
    freq = rule.get("freq")
    if freq not in FREQUENCIES:
        raise Invalid()
    if "interval" in rule:
        positive(rule["interval"])
    if ("count" in rule) == ("until" in rule):
        raise Invalid()
    if "count" in rule:
        positive(rule["count"])
    else:
        date(rule["until"])
    if "days" in rule and freq != "weekly" or ("monthday" in rule or "nth" in rule) and freq != "monthly":
        raise Invalid()
    if "overflow" in rule and freq not in ("monthly", "yearly"):
        raise Invalid()
    if "days" in rule:
        days = rule["days"]
        if not isinstance(days, list) or not days or any(code not in WEEKDAYS for code in days):
            raise Invalid()
    if "monthday" in rule and "nth" in rule:
        raise Invalid()
    if "monthday" in rule and (type(rule["monthday"]) is not int or not 1 <= rule["monthday"] <= 31):
        raise Invalid()
    if "nth" in rule:
        nth = rule["nth"]
        if (not isinstance(nth, list) or len(nth) != 2 or type(nth[0]) is not int or nth[0] == 0 or not -5 <= nth[0] <= 5
                or nth[1] not in WEEKDAYS):
            raise Invalid()
    if "overflow" in rule and rule["overflow"] not in ("skip", "clamp"):
        raise Invalid()
    if "except" in rule:
        if not isinstance(rule["except"], list):
            raise Invalid()
        for value in rule["except"]:
            date(value)
    return start


def expand(rule):
    try:
        start = validate(rule)
    except Invalid:
        return "INVALID"
    until = date(rule["until"]) if "until" in rule else None
    generated = []
    for day in candidates(rule, start):
        if until is not None and day > until:
            break
        generated.append(day)
        if len(generated) > MAX_OCCURRENCES:
            return "INVALID"
        if "count" in rule and len(generated) == rule["count"]:
            break
    excluded = {date(value) for value in rule.get("except", [])}
    return [day.isoformat() for day in generated if day not in excluded]


def main():
    with open(sys.argv[1], encoding="utf-8") as handle:
        data = json.load(handle)
    print(json.dumps({rule["id"]: expand(rule) for rule in data["rules"]}))


if __name__ == "__main__":
    main()
