"""Hidden tests for the recur item: each fixture is a rule list and the full expected output, written by hand.

Fixtures are grouped into checks, one per rule area. A check passes when every fixture in it produces exactly the
expected output. Weekday facts were read from a printed calendar; the one long list is plain consecutive days.
"""
import datetime


def rules(*items):
    return {"rules": [dict(item) for item in items]}


def r(identifier, **fields):
    return {"id": identifier, **fields}


THOUSAND_DAYS = [(datetime.date(2026, 1, 1) + datetime.timedelta(days=offset)).isoformat() for offset in range(1000)]

FIXTURES = [
    # check, fixture id, input, expected
    ("validation", "field-values", rules(
        r("v1", start="2026-02-30", freq="daily", count=1),
        r("v2", start="2026-3-02", freq="daily", count=1),
        r("v3", start="2026-01-01", freq="hourly", count=1),
        r("v4", start="2026-01-01", freq="daily", interval=0, count=1),
        r("v5", start="2026-01-01", freq="daily", interval=2.0, count=1),
        r("v6", start="2026-01-01", freq="daily", interval="2", count=1),
        r("v7", start="2026-01-01", freq="daily", interval=True, count=1),
        r("v8", start="2026-01-01", freq="daily", count=0),
        r("v9", start="2026-01-01", freq="daily", until="2026-13-01"),
        r("v10", start="2026-01-01", freq="weekly", days=[], count=1),
        r("v11", start="2026-01-01", freq="weekly", days=["MO", "XX"], count=1),
        r("v12", start="2026-01-01", freq="monthly", monthday=32, count=1),
        r("v13", start="2026-01-01", freq="monthly", nth=[0, "FR"], count=1),
        r("v14", start="2026-01-01", freq="monthly", nth=[6, "FR"], count=1),
        r("v15", start="2026-01-01", freq="monthly", overflow="wrap", count=1),
        r("v16", start="2026-01-01", freq="daily", count=1, **{"except": ["2026-02-30"]}),
        r("v17", start="2026-01-01", freq="daily", count=1, **{"except": "2026-01-01"}),
        r("v18", start="2026-01-01", freq="daily", interval=1, count=2),
        r("v19", freq="daily", count=1)),
     {"v1": "INVALID", "v2": "INVALID", "v3": "INVALID", "v4": "INVALID", "v5": "INVALID", "v6": "INVALID", "v7": "INVALID", "v8": "INVALID",
      "v9": "INVALID", "v10": "INVALID", "v11": "INVALID", "v12": "INVALID", "v13": "INVALID", "v14": "INVALID", "v15": "INVALID",
      "v16": "INVALID", "v17": "INVALID", "v18": ["2026-01-01", "2026-01-02"], "v19": "INVALID"}),
    ("validation", "field-combinations", rules(
        r("c1", start="2026-01-01", freq="daily", count=3, until="2026-02-01"),
        r("c2", start="2026-01-01", freq="daily"),
        r("c3", start="2026-01-01", freq="daily", days=["MO"], count=1),
        r("c4", start="2026-01-01", freq="weekly", monthday=5, count=1),
        r("c5", start="2026-01-01", freq="yearly", nth=[1, "MO"], count=1),
        r("c6", start="2026-01-01", freq="weekly", overflow="skip", count=1),
        r("c7", start="2026-01-01", freq="monthly", monthday=5, nth=[1, "MO"], count=1),
        r("c8", start="2026-05-05", freq="yearly", overflow="clamp", count=1)),
     {"c1": "INVALID", "c2": "INVALID", "c3": "INVALID", "c4": "INVALID", "c5": "INVALID", "c6": "INVALID", "c7": "INVALID", "c8": ["2026-05-05"]}),
    ("daily", "intervals-and-until", rules(
        r("d1", start="2026-01-30", freq="daily", interval=3, count=4),
        r("d2", start="2026-02-26", freq="daily", until="2026-03-02"),
        r("d3", start="2026-03-10", freq="daily", until="2026-03-01")),
     {"d1": ["2026-01-30", "2026-02-02", "2026-02-05", "2026-02-08"],
      "d2": ["2026-02-26", "2026-02-27", "2026-02-28", "2026-03-01", "2026-03-02"], "d3": []}),
    ("weekly", "days-weeks-and-start", rules(
        r("w1", start="2026-03-04", freq="weekly", count=3),
        r("w2", start="2026-03-04", freq="weekly", days=["MO", "FR"], count=4),
        r("w3", start="2026-03-05", freq="weekly", days=["TU", "SU", "TH"], interval=2, until="2026-04-01")),
     {"w1": ["2026-03-04", "2026-03-11", "2026-03-18"],
      "w2": ["2026-03-06", "2026-03-09", "2026-03-13", "2026-03-16"],
      "w3": ["2026-03-05", "2026-03-08", "2026-03-17", "2026-03-19", "2026-03-22", "2026-03-31"]}),
    ("monthly", "monthday-and-skip", rules(
        r("m1", start="2026-01-10", freq="monthly", monthday=5, count=3),
        r("m2", start="2026-01-31", freq="monthly", interval=2, count=3),
        r("m3", start="2026-01-30", freq="monthly", until="2026-04-30")),
     {"m1": ["2026-02-05", "2026-03-05", "2026-04-05"], "m2": ["2026-01-31", "2026-03-31", "2026-05-31"],
      "m3": ["2026-01-30", "2026-03-30", "2026-04-30"]}),
    ("clamp", "month-end-clamp", rules(
        r("k1", start="2026-01-30", freq="monthly", overflow="clamp", until="2026-03-31"),
        r("k2", start="2026-03-31", freq="monthly", overflow="clamp", count=4),
        r("k3", start="2028-01-31", freq="monthly", overflow="clamp", count=2)),
     {"k1": ["2026-01-30", "2026-02-28", "2026-03-30"], "k2": ["2026-03-31", "2026-04-30", "2026-05-31", "2026-06-30"],
      "k3": ["2028-01-31", "2028-02-29"]}),
    ("nth", "nth-weekday", rules(
        r("n1", start="2026-01-01", freq="monthly", nth=[1, "MO"], count=3),
        r("n2", start="2026-01-01", freq="monthly", nth=[5, "FR"], until="2026-06-30"),
        r("n3", start="2026-01-20", freq="monthly", nth=[-2, "TU"], overflow="clamp", count=3),
        r("n4", start="2026-02-01", freq="monthly", nth=[-5, "SU"], until="2026-05-31"),
        r("n5", start="2026-01-01", freq="monthly", nth=[5, "FR"], overflow="clamp", until="2026-03-31")),
     {"n1": ["2026-01-05", "2026-02-02", "2026-03-02"], "n2": ["2026-01-30", "2026-05-29"],
      "n3": ["2026-01-20", "2026-02-17", "2026-03-24"], "n4": ["2026-03-01", "2026-05-03"], "n5": ["2026-01-30"]}),
    ("yearly", "leap-day-and-interval", rules(
        r("y1", start="2028-02-29", freq="yearly", count=3),
        r("y2", start="2028-02-29", freq="yearly", overflow="clamp", count=3),
        r("y3", start="2026-07-15", freq="yearly", interval=3, until="2035-07-15")),
     {"y1": ["2028-02-29", "2032-02-29", "2036-02-29"], "y2": ["2028-02-29", "2029-02-28", "2030-02-28"],
      "y3": ["2026-07-15", "2029-07-15", "2032-07-15", "2035-07-15"]}),
    ("count-except", "count-before-exceptions", rules(
        r("e1", start="2026-03-02", freq="daily", count=5, **{"except": ["2026-03-03", "2026-03-05"]}),
        r("e2", start="2026-01-31", freq="monthly", count=3, **{"except": ["2026-03-31", "2026-02-28"]}),
        r("e3", start="2026-03-02", freq="weekly", until="2026-03-16", **{"except": ["2026-03-09"]})),
     {"e1": ["2026-03-02", "2026-03-04", "2026-03-06"], "e2": ["2026-01-31", "2026-05-31"], "e3": ["2026-03-02", "2026-03-16"]}),
    ("limits", "end-of-range-and-size", rules(
        r("l1", start="2026-01-01", freq="daily", until="2099-12-31"),
        r("l2", start="2099-12-28", freq="daily", count=10),
        r("l3", start="2026-01-01", freq="daily", count=1000),
        r("l4", start="2026-01-01", freq="daily", count=1001),
        r("l5", start="2090-06-01", freq="yearly", count=20),
        r("l6", start="2099-12-30", freq="weekly", days=["TH", "SU"], count=5)),
     {"l1": "INVALID", "l2": ["2099-12-28", "2099-12-29", "2099-12-30", "2099-12-31"], "l3": THOUSAND_DAYS, "l4": "INVALID",
      "l5": [f"{year}-06-01" for year in range(2090, 2100)], "l6": ["2099-12-31"]}),
    ("examples", "specification-examples", rules(
        r("a", start="2026-01-31", freq="monthly", count=4),
        r("b", start="2026-01-31", freq="monthly", count=4, overflow="clamp"),
        r("c", start="2026-03-02", freq="weekly", days=["MO", "TH"], count=4, **{"except": ["2026-03-05"]}),
        r("d", start="2026-01-01", freq="monthly", nth=[-1, "FR"], until="2026-03-31")),
     {"a": ["2026-01-31", "2026-03-31", "2026-05-31", "2026-07-31"], "b": ["2026-01-31", "2026-02-28", "2026-03-31", "2026-04-30"],
      "c": ["2026-03-02", "2026-03-09", "2026-03-12"], "d": ["2026-01-30", "2026-02-27", "2026-03-27"]}),
]
