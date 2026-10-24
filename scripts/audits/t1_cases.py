#!/usr/bin/env python3
"""Success audit of T1 adjudication questions (levels F2-F5), written from the snapshot's own public contract
(docs/CONFIG.md and docs/RESPONSE.md) and nothing of the package's private code. For each question it derives every
answer field independently from the snapshot files, then compares the package's answer key and each audited trial's
answer with it.

Usage: python3 -I scripts/audits/t1_cases.py <request.json> <result.json>
The request names the package directory and the trials: {"package": ..., "trials": [{"directory", "itemId", "label"}]}.
"""
import datetime as dt
import glob
import json
import os
import re
import sys

UTC = dt.timezone.utc
BERLIN = dt.timedelta(hours=2)  # the snapshots state UTC+2 throughout September 2026
WINDOWS = {"R0": 60, "P1": 720, "P2": 360, "P3": 240, "P4": 120}  # minutes, docs/RESPONSE.md "Deadline"


def stamp(text):
    return dt.datetime.strptime(text.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=UTC)


def field(text, name):
    found = re.search(rf"^{name}:\s*(.+?)\s*$", text, re.M)
    return found.group(1) if found else None


def read(root, path):
    with open(os.path.join(root, path), encoding="utf-8") as handle:
        return handle.read()


def toml(text):
    """The keys a configuration file sets, and its include line (CONFIG.md: one key per line, sections by name)."""
    keys, include = {}, None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("[") or line.startswith("#"):
            continue
        name, _, value = line.partition("=")
        name, value = name.strip(), value.strip()
        parsed = value[1:-1] if value.startswith('"') else int(value) if re.fullmatch(r"-?\d+", value) else value
        if name == "include":
            include = parsed
        else:
            keys[name] = parsed
    return keys, include


class Snapshot:
    def __init__(self, root):
        self.root = root
        self.services = sorted(os.path.basename(path) for path in glob.glob(os.path.join(root, "services", "*")))
        self.prod, self.includes, self.base = {}, {}, {}
        for service in self.services:
            keys, include = toml(read(root, f"services/{service}/config/prod.toml"))
            self.prod[service], self.includes[f"services/{service}/config/prod.toml"] = keys, include
            self.base[service] = toml(read(root, f"services/{service}/config/base.toml"))[0]
        self.shared = {}
        for path in glob.glob(os.path.join(root, "shared", "*.toml")):
            relative = os.path.relpath(path, root)
            keys, include = toml(read(root, relative))
            self.shared[relative], self.includes[relative] = keys, include
        self.changes = {}
        for path in glob.glob(os.path.join(root, "changes", "CHG-*.md")):
            text = read(root, os.path.relpath(path, root))
            self.changes[os.path.basename(path)[:-3]] = {"time": stamp(field(text, "Time")[:-4]), "service": field(text, "Service"),
                                                         "file": field(text, "File"), "key": field(text, "Key"), "from": field(text, "From"),
                                                         "to": field(text, "To"), "class": field(text, "Class")}
        self.amendments = []
        for path in glob.glob(os.path.join(root, "changes", "amendments", "*.md")):
            text = read(root, os.path.relpath(path, root))
            self.amendments.append({"amends": field(text, "Amends"), "status": field(text, "Status"), "effective": stamp(field(text, "Effective")[:-4]),
                                    "class": field(text, "Class")})
        self.freezes = []
        calendar = os.path.join(root, "calendar", "freezes.md")  # from F3 on
        for line in (read(root, "calendar/freezes.md") if os.path.exists(calendar) else "").splitlines():
            found = re.match(r"- (\S+ \S+) to (\S+ \S+)\.(?: Exempt: (.+)\.)?$", line.strip())
            if found:
                self.freezes.append((stamp(found.group(1)) - BERLIN, stamp(found.group(2)) - BERLIN,
                                     {name.strip() for name in (found.group(3) or "").split(",") if name.strip()}))
        self.rotations, self.commanders, self.swaps = {}, [], []
        for path in glob.glob(os.path.join(root, "oncall", "*.md")):
            text = read(root, os.path.relpath(path, root))
            name = os.path.basename(path)[:-3]
            if name == "swaps":
                for line in text.splitlines():
                    found = re.match(r"- (\S+ \S+) to (\S+ \S+): (\S+) covers the (.+) for (\S+)\.$", line.strip())
                    if found:
                        self.swaps.append((stamp(found.group(1)), stamp(found.group(2)), found.group(3), found.group(4), found.group(5)))
            elif text.startswith("# Incident commanders"):
                for day, person in re.findall(r"^\| (\d{4}-\d\d-\d\d) \| (\S+) \|$", text, re.M):
                    start = stamp(day + " 08:00") - BERLIN
                    self.commanders.append((start, start + dt.timedelta(days=1), person))
            else:
                weeks = re.findall(r"^\| (\d{4}-\d\d-\d\d) \| (\S+) \| (\S+) \|$", text, re.M)
                self.rotations[name] = [(stamp(day + " 09:00") - BERLIN, stamp(day + " 09:00") - BERLIN + dt.timedelta(days=7), primary, secondary)
                                        for day, primary, secondary in weeks]

    def prod_at(self, moment, skip=None):
        """Each prod.toml as it stood at `moment`: undo every change recorded after it (CONFIG.md "History"). Without
        `skip`, the key it set keeps its From until the next change of the same key in the same file (RESPONSE.md)."""
        state = {service: dict(keys) for service, keys in self.prod.items()}
        def put(change, value):
            keys = state[change["file"].split("/")[1]]
            if value == "(not set)":
                keys.pop(change["key"], None)
            else:
                keys[change["key"]] = int(value) if re.fullmatch(r"-?\d+", value) else value
        for change in sorted(self.changes.values(), key=lambda item: item["time"], reverse=True):
            if change["time"] > moment:
                put(change, change["from"])
        if skip and self.changes[skip]["time"] <= moment:
            change = self.changes[skip]
            later = [other for other in self.changes.values() if other["file"] == change["file"] and other["key"] == change["key"]
                     and change["time"] < other["time"] <= moment]
            if not later:
                put(change, change["from"])
        return state

    def effective(self, prod, service, key):
        if key in prod[service]:
            return prod[service][key]
        include, seen = self.includes[f"services/{service}/config/prod.toml"], set()
        while include and include not in seen:
            seen.add(include)
            if key in self.shared[include]:
                return self.shared[include][key]
            include = self.includes.get(include)
        return self.base[service].get(key)

    def team(self, service, moment):
        text = read(self.root, f"services/{service}/OWNERS")
        team = field(text, "Team")
        found = re.search(r"Since (\S+ \S+) UTC; before then the service belonged to team (\S+)\.", text)
        return found.group(2) if found and moment < stamp(found.group(1)) else team

    def covered(self, role, person, moment):
        for start, end, cover, swap_role, replaced in self.swaps:
            if swap_role == role and replaced == person and start <= moment < end:
                return cover
        return person

    def on_call(self, team, position, moment):
        for start, end, primary, secondary in self.rotations[team]:
            if start <= moment < end:
                return self.covered(f"{team} {position}", primary if position == "primary" else secondary, moment)
        raise ValueError(f"no {team} rotation at {moment}")

    def commander(self, moment):
        for start, end, person in self.commanders:
            if start <= moment < end:
                return self.covered("incident commander", person, moment)
        raise ValueError(f"no commander at {moment}")

    def causing_change(self, incident):
        text = read(self.root, f"incidents/{incident}.md")
        start = stamp(field(text, "Start")[:-4])
        cause = re.search(r"Root cause: the (\d\d:\d\d) change", text).group(1)
        review = re.search(rf"^- {cause} the change approved in (REV-\d+)", text, re.M).group(1)
        change = re.search(r"approved as (CHG-\d+)", read(self.root, f"reviews/{review}.md")).group(1)
        return start, change

    def facts(self, incident, skip=None):
        start, change = self.causing_change(incident)
        record = self.changes[change]
        service = record["service"]
        prod = self.prod_at(start, skip)
        tier = int(self.effective(prod, service, "tier"))
        freeze = tier != 3 and any(begin <= start < end and service not in exempt for begin, end, exempt in self.freezes)
        amendments = sorted((item for item in self.amendments if item["amends"] == change and item["status"] == "approved" and item["effective"] <= start),
                            key=lambda item: item["effective"])
        klass = amendments[-1]["class"] if amendments else record["class"]
        reach = sum(1 for other in self.services if other != service and self.effective(prod, other, "upstream") == service)
        if klass == "rollback":
            procedure = "R0"
        elif tier == 1 and freeze:
            procedure = "P4"
        elif reach >= 3:
            procedure = "P3"
        elif klass == "emergency" or tier == 1:
            procedure = "P2"
        else:
            procedure = "P1"
        window = WINDOWS[procedure] // (2 if procedure in ("P1", "P2") and freeze else 1)
        deadline = (start + dt.timedelta(minutes=window)).strftime("%Y-%m-%dT%H:%MZ")
        return {"start": start, "service": service, "change": change, "tier": tier, "freeze": freeze, "class": klass, "reach": reach,
                "procedure": procedure, "deadline": deadline}

    def answer(self, incident, what_if=None):
        facts = self.facts(incident)
        team = self.team(facts["service"], facts["start"])
        procedure = facts["procedure"]
        approver = (self.on_call(team, "primary", facts["start"]) if procedure in ("R0", "P1") else
                    self.on_call(team, "secondary", facts["start"]) if procedure == "P2" else self.commander(facts["start"]))
        result = {key: facts[key] for key in ("tier", "freeze", "class", "reach", "procedure")} | {"approver": approver, "deadline": facts["deadline"]}
        if what_if:
            other = self.facts(incident, what_if)
            result |= {"cf_procedure": other["procedure"], "cf_deadline": other["deadline"]}
        return result


def question_target(text):
    incident = re.search(r"Incident (INC-\d+)", text).group(1)
    what_if = re.search(r"if (CHG-\d+) had never been made", text)
    return incident, what_if.group(1) if what_if else None


def last_object(text):
    """The JSON object a reply ends with, or the only object in it (the instruction asks for one object)."""
    if not isinstance(text, str):
        return None
    decoder = json.JSONDecoder()
    found = []
    for start in [index for index, char in enumerate(text) if char == "{"]:
        try:
            value, end = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and any(key.startswith("Q") for key in value):
            found.append((end, value))
    return max(found)[1] if found else None


def same(field_name, expected, given):
    if field_name == "freeze" and isinstance(given, str):
        given = {"true": True, "false": False}.get(given.strip().lower(), given)
    if field_name in ("tier", "reach") and isinstance(given, str) and re.fullmatch(r"\d+", given.strip()):
        given = int(given)
    if field_name.endswith("deadline") and isinstance(given, str):
        return given.strip().replace(":00Z", "Z") == expected or given.strip() == expected
    return given == expected


def main():
    request = json.load(open(sys.argv[1]))
    package = request["package"]
    keys = json.load(open(os.path.join(package, "private", "keys.json")))
    oracle, findings = [], []
    derived = {}
    for item_id, entry in sorted(keys.items()):
        if not item_id.startswith("F"):
            continue
        snapshot = Snapshot(os.path.join(package, "items", item_id, "public", "snapshot"))
        for index, question in enumerate(entry["questions"], 1):
            if question["kind"] != "case":
                continue
            incident, what_if = question_target(question["text"])
            mine = snapshot.answer(incident, what_if)
            derived[(item_id, index)] = mine
            differences = {name: {"key": value, "audit": mine.get(name)} for name, value in question["answer"].items() if mine.get(name) != value}
            oracle.append({"item": item_id, "question": f"Q{index}", "incident": incident, "whatIf": what_if, "agrees": not differences, "differences": differences})
    for trial in request["trials"]:
        record = json.load(open(os.path.join(trial["directory"], "result.json")))
        runs = sorted(glob.glob(os.path.join(trial["directory"], "score-runs", "*", "score.json")), key=lambda path: json.load(open(path))["createdAt"])
        checks = json.load(open(os.path.join(os.path.dirname(runs[-1]), "grader", "evidence", "checks.json")))["results"]
        reply = last_object(record["execution"].get("output"))
        for (item_id, index), mine in sorted(derived.items()):
            if item_id != trial["itemId"]:
                continue
            given = (reply or {}).get(f"Q{index}") or {}
            for name, value in mine.items():
                passed = checks.get(f"q{index}-{name}")
                right = same(name, value, given.get(name)) if isinstance(given, dict) else False
                key = keys[item_id]["questions"][index - 1]["answer"].get(name)
                # A right value can still fail by the contract's evidence rule (the trace must show the files).
                verdict = ("true pass" if right else "false pass") if passed else \
                    ("true fail" if not right else "fail by the evidence rule" if value == key else "false fail")
                findings.append({"trial": trial["directory"], "label": trial["label"], "item": item_id, "unit": f"Q{index}.{name}",
                                 "grader": "pass" if passed else "fail", "verdict": verdict,
                                 "detail": f"given {json.dumps(given.get(name) if isinstance(given, dict) else None)}, derived {json.dumps(value)}"})
    agreeing = sum(1 for entry in oracle if entry["agrees"])
    notes = [f"Answer key: the independent solver derives every field of all {len(oracle)} adjudication questions of the package (levels F2 to F5, "
             f"{len({entry['item'] for entry in oracle})} items) and agrees with the key on {agreeing} of them"
             + ("." if agreeing == len(oracle) else "; differences: " + json.dumps([entry for entry in oracle if not entry["agrees"]])),
             "The evidence rule (the trace must show the files a field needs) is the grader's own check and is not re-derived here; a field "
             "with the right value that the grader failed is reported as failing by the evidence rule."]
    json.dump({"oracle": oracle, "findings": findings, "notes": notes}, open(sys.argv[2], "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
