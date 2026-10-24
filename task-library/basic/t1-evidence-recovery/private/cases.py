"""Adjudication ladder for T1 (levels F2, F3, F4 and F5, task 0.6.0). Each question asks how the change behind an
incident must be rolled back under the project's response handbook (docs/RESPONSE.md).

The procedure, its approver and its deadline follow from several facts. Each fact is found by its own chain through
the snapshot and is taken at the incident's start time:

- tier: the service's effective production tier, by the configuration precedence, as the files stood then. Later
  changes in changes/ must be undone, and the value may come from an included file or base.toml.
- class: the class of the change that caused the incident, unless approved amendments effective by then reclassify it.
- freeze (F3 on): whether a change freeze applies. The calendar is in Berlin time and the incident in UTC. Tier 3
  services and services a freeze names are exempt, so this fact depends on the tier.
- reach (F4 on): how many services' effective production upstream is the service, again as the files stood then.

The approver depends on the procedure. It is either a team's primary or secondary on call, or the incident commander:
- weekly team rotations hand over in Berlin time;
- swaps replace people, and ownership transfers change the team (F4 on).

The deadline depends on the procedure and the freeze. F5 also asks what would apply if an earlier change had never been
made, so the facts must be worked out again in that world.

Every question is built with traps. A misreading of one fact makes the procedure, approver or deadline come out
different, and the wrong answer looks just as valid. The misreadings are: a later change not undone, an include
skipped, Berlin time read as UTC, an amendment that was rejected or not yet in effect, a swap, a transfer. A question is
kept only when enough of these misreadings change its conclusion; the generator records which ones do.
"""
import copy
import datetime as dt

SERVICES = ["atlas", "beacon", "cinder", "delta", "ember", "fjord", "garnet", "harbor", "iris", "juniper", "kestrel", "lumen", "mesa", "nectar",
            "orchid", "pylon", "quill", "rowan", "spruce", "tundra", "umbra", "vesper", "willow", "yonder"]
KEYS = ["timeout_ms", "max_retries", "pool_size", "queue_depth"]
SHARED = ["limits-standard", "limits-burst", "limits-floor", "pool-small", "pool-large", "retry-fast", "retry-safe"]
PROFILES = ["profile-core", "profile-edge", "profile-batch"]
ROUTES = ["routes-north", "routes-south", "routes-east"]
TEAMS = {"checkout": ["Ito", "Kim", "Lund", "Okafor"], "identity": ["Petrov", "Quinn", "Reyes", "Sato"],
         "search": ["Tanaka", "Usman", "Vidal", "Weber"], "storage": ["Xu", "Young", "Zaidi", "Abara"],
         "billing": ["Brandt", "Costa", "Dahl", "Eze"], "messaging": ["Fischer", "Gomez", "Hale", "Iqbal"]}
COMMANDERS = ["Moreau", "Novak", "Ortiz", "Park", "Rossi", "Silva", "Toure"]
QUESTIONS = 3
SERVICE_COUNT = 20
POOL = 5  # services reserved for each question's reach traps

LEVELS = {
    "F2": {"freeze": False, "reach": False, "swaps": False, "transfers": False, "what_if": False, "effective": 2},
    "F3": {"freeze": True, "reach": False, "swaps": False, "transfers": False, "what_if": False, "effective": 3},
    "F4": {"freeze": True, "reach": True, "swaps": True, "transfers": True, "what_if": False, "effective": 4},
    "F5": {"freeze": True, "reach": True, "swaps": True, "transfers": True, "what_if": True, "effective": 4},
}
OFFSET = dt.timedelta(hours=2)  # Berlin time is UTC+2 throughout September 2026
MONDAYS = [dt.date(2026, 8, 31) + dt.timedelta(weeks=week) for week in range(5)]
DAYS = [dt.date(2026, 8, 31) + dt.timedelta(days=day) for day in range(32)]
WINDOWS = {"R0": 60, "P1": 720, "P2": 360, "P3": 240, "P4": 120}  # minutes
NOTHING = dt.timedelta(0)

# Misreadings a reader may make, one at a time. The generator keeps a question only when enough of them change its
# conclusion (procedure, approver, deadline, and the what-if answers).
MISTAKES = {
    "current-config": "takes tier and upstream from the files as they are now, not as they stood at the start time",
    "no-includes": "skips included shared files and falls back to base.toml",
    "ignore-amendments": "uses the class in the change record",
    "late-amendments": "applies approved amendments that take effect after the start time",
    "rejected-amendments": "applies rejected amendments",
    "handover-utc": "reads the rotations' Berlin handover times as UTC",
    "freeze-utc": "reads the freeze calendar's Berlin times as UTC",
    "ignore-exemptions": "ignores the services a freeze exempts by name",
    "ignore-tier3": "ignores the exemption of tier 3 services",
    "count-lines": "counts every service whose own files name the service as upstream",
    "ignore-swaps": "ignores swaps",
    "current-owner": "takes the team in OWNERS without its transfer date",
}


def level_mistakes(features):
    names = ["current-config", "no-includes", "ignore-amendments", "late-amendments", "rejected-amendments", "handover-utc"]
    if features["freeze"]:
        names += ["freeze-utc", "ignore-exemptions", "ignore-tier3"]
    if features["reach"]:
        names += ["count-lines", "ignore-swaps", "current-owner"]
    return names


def fields(features):
    facts = ["tier"] + (["freeze"] if features["freeze"] else []) + ["class"] + (["reach"] if features["reach"] else [])
    return facts + ["procedure", "approver", "deadline"] + (["cf_procedure", "cf_deadline"] if features["what_if"] else [])


def procedures(features):
    return ["R0", "P1", "P2"] + (["P3"] if features["reach"] else []) + (["P4"] if features["freeze"] else [])


def stamp(moment):
    return moment.strftime("%Y-%m-%d %H:%M")


def iso(moment):
    return moment.strftime("%Y-%m-%dT%H:%MZ")


def minutes(count):
    return dt.timedelta(minutes=count)


class World:
    """Configuration, change history, amendments, freezes, owners and rotations of one snapshot. Times are naive UTC
    datetimes except freeze times, which are naive Berlin times, as the calendar states them."""

    def __init__(self, rng, features):
        self.features = features
        self.services = rng.sample(SERVICES, SERVICE_COUNT)
        order = list(self.services)
        rng.shuffle(order)
        self.asked = order[:QUESTIONS]
        self.pools = [order[QUESTIONS + POOL * index:QUESTIONS + POOL * (index + 1)] for index in range(QUESTIONS)]
        self.free = order[QUESTIONS + POOL * QUESTIONS:]
        quiet = [service for service in self.services if service not in self.asked]  # upstream targets outside the traps
        self.team_names = rng.sample(sorted(TEAMS), 4)
        owners = list(self.services)
        rng.shuffle(owners)
        self.owner = {service: self.team_names[index % 4] for index, service in enumerate(owners)}
        self.transfer = {}  # service -> (moment, team before it)
        names = rng.sample(SHARED, 6)
        tops, middles, bottoms = names[:2], names[2:4], names[4:]
        self.parent = {}
        for name in middles:
            self.parent[name] = rng.choice(bottoms)
        for name in tops:
            if rng.random() < 0.8:
                self.parent[name] = rng.choice(middles)
        self.shared = {}
        for name in names:
            self.shared[name] = {key: rng.randrange(41, 140) for key in rng.sample(KEYS, rng.randrange(1, 3))}
            if rng.random() < 0.4:
                self.shared[name]["tier"] = rng.randrange(1, 4)
            if rng.random() < 0.3:
                self.shared[name]["upstream"] = rng.choice(quiet)
        self.base, self.prod0, self.include, self.staging, self.retired = {}, {}, {}, {}, {}
        self.staging_include, self.retired_include = {}, {}
        for service in self.services:
            others = [other for other in quiet if other != service]
            self.base[service] = {"tier": rng.randrange(1, 4), "upstream": rng.choice(others), **{key: rng.randrange(2, 40) for key in KEYS}}
            self.include[service] = rng.choice(names) if rng.random() < 0.6 else None
            prod = {key: self.base[service][key] + rng.randrange(1, 9) for key in rng.sample(KEYS, rng.randrange(1, 3))}
            if rng.random() < 0.5:
                prod["tier"] = rng.randrange(1, 4)
            if rng.random() < 0.5:
                prod["upstream"] = rng.choice(others)
            self.prod0[service] = prod
            self.staging[service] = {"tier": rng.randrange(1, 4), "upstream": rng.choice(others),
                                     **{key: self.base[service][key] + rng.randrange(10, 30) for key in rng.sample(KEYS, 2)}}
            self.retired[service] = {"tier": rng.randrange(1, 4), "upstream": rng.choice(others), **{key: rng.randrange(2, 60) for key in rng.sample(KEYS, 1)}}
            self.staging_include[service] = rng.choice(names) if rng.random() < 0.3 else None
            self.retired_include[service] = rng.choice(names) if rng.random() < 0.3 else None
        self.events = []  # in time order: id, time, service, key, to (None: removed), class, reverts
        self.amendments = []
        self.freezes = []  # start and end in Berlin time
        self.swaps = []  # start and end in UTC; team None for the incident commander
        self.rotation = {}
        for team in self.team_names:
            members = list(TEAMS[team])
            rng.shuffle(members)
            self.rotation[team] = {monday: (members[week % 4], members[(week + 1) % 4]) for week, monday in enumerate(MONDAYS)}
        commanders = []
        for _ in DAYS:
            commanders.append(rng.choice([name for name in COMMANDERS if not commanders or name != commanders[-1]]))
        self.commanders = dict(zip(DAYS, commanders))
        self.ids = set()
        self.spare_profiles, self.spare_routes = list(PROFILES), list(ROUTES)

    def fresh(self, rng, prefix, low, high):
        while True:
            value = f"{prefix}-{rng.randrange(low, high)}"
            if value not in self.ids:
                self.ids.add(value)
                return value

    def add_event(self, rng, moment, service, key, to, kind="standard", reverts=None):
        event = {"id": self.fresh(rng, "CHG", 1000, 9999), "time": moment, "service": service, "key": key, "to": to, "class": kind,
                 "reverts": reverts["id"] if reverts else None}
        self.events.append(event)
        self.events.sort(key=lambda item: item["time"])
        return event

    def event(self, change_id):
        return next(event for event in self.events if event["id"] == change_id)

    # Facts, with optional misreadings.

    def prod_at(self, service, moment, skip=None):
        """prod.toml's settings at a moment (None: now), replaying the recorded changes, without the change `skip`."""
        values = dict(self.prod0[service])
        for event in self.events:
            if event["service"] == service and event["id"] != skip and (moment is None or event["time"] <= moment):
                if event["to"] is None:
                    values.pop(event["key"], None)
                else:
                    values[event["key"]] = event["to"]
        return values

    def effective(self, service, key, moment, skip=None, includes=True):
        values = self.prod_at(service, moment, skip)
        if key in values:
            return values[key]
        name = self.include[service] if includes else None
        while name is not None:
            if key in self.shared[name]:
                return self.shared[name][key]
            name = self.parent.get(name)
        return self.base[service][key]

    def upstream_lines(self, service):
        """Services that one of this service's own files names as upstream, whatever the precedence."""
        return {values.get("upstream") for values in (self.prod_at(service, None), self.staging[service], self.retired[service], self.base[service])}

    def class_at(self, question, mistakes):
        cause = self.event(question["cause"])
        if "ignore-amendments" in mistakes:
            return cause["class"]
        found = [amendment for amendment in self.amendments if amendment["amends"] == cause["id"]
                 and (amendment["status"] == "approved" or "rejected-amendments" in mistakes)
                 and (amendment["effective"] <= question["start"] or "late-amendments" in mistakes)]
        return max(found, key=lambda amendment: amendment["effective"])["class"] if found else cause["class"]

    def frozen(self, service, start, tier, mistakes):
        if not self.features["freeze"] or (tier == 3 and "ignore-tier3" not in mistakes):
            return False
        shift = NOTHING if "freeze-utc" in mistakes else OFFSET
        return any(freeze["start"] - shift <= start < freeze["end"] - shift and (service not in freeze["exempt"] or "ignore-exemptions" in mistakes)
                   for freeze in self.freezes)

    def facts(self, question, skip=None, mistakes=()):
        features, service, start = self.features, question["service"], question["start"]
        moment = None if "current-config" in mistakes else start
        includes = "no-includes" not in mistakes
        tier = self.effective(service, "tier", moment, skip, includes)
        freeze = self.frozen(service, start, tier, mistakes)
        kind = self.class_at(question, mistakes)
        reach = None
        if features["reach"]:
            if "count-lines" in mistakes:
                reach = sum(1 for other in self.services if other != service and service in self.upstream_lines(other))
            else:
                reach = sum(1 for other in self.services if other != service and self.effective(other, "upstream", moment, skip, includes) == service)
        if kind == "rollback":
            procedure = "R0"
        elif features["freeze"] and tier == 1 and freeze:
            procedure = "P4"
        elif features["reach"] and reach >= 3:
            procedure = "P3"
        elif kind == "emergency" or tier == 1:
            procedure = "P2"
        else:
            procedure = "P1"
        window = WINDOWS[procedure] // (2 if freeze and procedure in ("P1", "P2") else 1)
        result = {"tier": tier, "freeze": freeze, "class": kind, "reach": reach, "procedure": procedure, "deadline": iso(start + minutes(window))}
        result["approver"], result["role"], result["team"] = self.approver(question, procedure, mistakes)
        return result

    def owner_at(self, service, moment, mistakes=()):
        if service in self.transfer and "current-owner" not in mistakes and moment < self.transfer[service][0]:
            return self.transfer[service][1]
        return self.owner[service]

    def on_call(self, team, role, moment, mistakes=()):
        """(person, team, role) on call at a moment: a team's primary or secondary, or (team None) the incident commander."""
        shift = NOTHING if "handover-utc" in mistakes else OFFSET
        if team is None:
            day = max(day for day in DAYS if dt.datetime.combine(day, dt.time(8)) - shift <= moment)
            person = self.commanders[day]
        else:
            week = max(monday for monday in MONDAYS if dt.datetime.combine(monday, dt.time(9)) - shift <= moment)
            person = self.rotation[team][week][0 if role == "primary" else 1]
        if "ignore-swaps" not in mistakes:
            for swap in self.swaps:
                if swap["team"] == team and swap["role"] == role and swap["for"] == person and swap["start"] <= moment < swap["end"]:
                    person = swap["by"]
        return person

    def approver(self, question, procedure, mistakes=()):
        start = question["start"]
        if procedure in ("P3", "P4"):
            return self.on_call(None, "commander", start, mistakes), "commander", None
        team = self.owner_at(question["service"], start, mistakes)
        role = "secondary" if procedure == "P2" else "primary"
        return self.on_call(team, role, start, mistakes), role, team

    def answer(self, question, mistakes=()):
        result = self.facts(question, None, mistakes)
        if self.features["what_if"]:
            what_if = self.facts(question, question["what_if"], mistakes)
            result["cf_procedure"], result["cf_deadline"] = what_if["procedure"], what_if["deadline"]
        return {field: result[field] for field in fields(self.features)}

    def conclusion(self, answer):
        return tuple(answer[field] for field in ("procedure", "approver", "deadline", "cf_procedure", "cf_deadline") if field in answer)

    def effective_mistakes(self, question):
        truth = self.conclusion(self.answer(question))
        return [mistake for mistake in level_mistakes(self.features) if self.conclusion(self.answer(question, {mistake})) != truth]

    # Questions and their traps.

    def make_question(self, rng, service, pool, used_days):
        features = self.features
        profile = rng.choice(["monday", "daily", "plain", "plain"])
        if profile == "monday":
            days = [day for day in (7, 14, 21) if day not in used_days]
            if not days:
                profile = "plain"
        if profile != "monday":
            days = [day for day in range(3, 27) if day not in used_days and dt.date(2026, 9, day).weekday() != 0]
        day = rng.choice(days)
        midnight = dt.datetime(2026, 9, day)
        if profile == "monday":  # weekly handover at 09:00 Berlin, 07:00 UTC
            start = midnight + dt.timedelta(hours=7) + minutes(rng.randrange(1, 120))
        elif profile == "daily":  # commander handover at 08:00 Berlin, 06:00 UTC
            start = midnight + dt.timedelta(hours=6) + minutes(rng.randrange(1, 120))
        else:
            start = midnight + dt.timedelta(hours=10) + minutes(rng.randrange(1, 720))
        if start.minute == 0:
            start += minutes(7)
        question = {"service": service, "start": start, "day": day, "pool": pool}
        self.cause(rng, question)
        self.tier_traps(rng, question)
        if features["reach"]:
            self.reach_traps(rng, question)
        self.class_traps(rng, question)
        if features["freeze"]:
            self.freeze_traps(rng, question)
        if features["what_if"] and not self.what_if(rng, question):
            return None
        self.approver_traps(rng, question)
        return question

    def cause(self, rng, question):
        service, start = question["service"], question["start"]
        moment = start - minutes(rng.randrange(2, 10))
        key = rng.choice(KEYS)
        kind = rng.choices(["standard", "emergency", "rollback"], [5, 3, 1])[0]
        if kind == "rollback":
            earlier = moment - dt.timedelta(hours=rng.randrange(6, 40), minutes=rng.randrange(60))
            before = self.prod_at(service, earlier).get(key)
            reverted = self.add_event(rng, earlier, service, key, (before or self.base[service][key]) + rng.randrange(3, 9))
            cause = self.add_event(rng, moment, service, key, before, "rollback", reverted)
        else:
            now = self.prod_at(service, moment).get(key)
            cause = self.add_event(rng, moment, service, key, (now or self.base[service][key]) + rng.randrange(3, 12), kind)
        question["cause"] = cause["id"]

    def tier_traps(self, rng, question):
        """The tier at the start time comes from prod.toml, an included profile or base.toml; a later change may set it
        to another value, and an earlier change may have set it."""
        service, start = question["service"], question["start"]
        target = rng.choice([1, 1, 2, 2, 3])
        source = rng.choice(["prod", "prod", "include", "base"])
        question["tierSource"] = source
        prod = self.prod0[service]
        prod.pop("tier", None)
        if source == "prod":
            if rng.random() < 0.6:
                old = rng.choice([value for value in (1, 2, 3) if value != target])
                if rng.random() < 0.7:
                    prod["tier"] = old
                else:
                    self.base[service]["tier"] = old
                    self.include[service] = None
                self.add_event(rng, start - dt.timedelta(days=rng.randrange(1, 5), hours=rng.randrange(24)), service, "tier", target)
            else:
                prod["tier"] = target
        elif source == "include" and self.spare_profiles:
            profile = self.spare_profiles.pop(rng.randrange(len(self.spare_profiles)))
            self.shared[profile] = {"tier": target, **{key: rng.randrange(41, 140) for key in rng.sample(KEYS, 1)}}
            if rng.random() < 0.5:
                self.parent[profile] = rng.choice([name for name in SHARED if name in self.shared])
            self.include[service] = profile
            self.base[service]["tier"] = rng.choice([value for value in (1, 2, 3) if value != target])
        else:
            question["tierSource"] = "base"
            name = self.include[service]
            while name is not None and "tier" not in self.shared[name]:
                name = self.parent.get(name)
            if name is not None:
                self.include[service] = None
            self.base[service]["tier"] = target
        if rng.random() < 0.7:
            later = start + dt.timedelta(hours=rng.randrange(1, 72), minutes=rng.randrange(60))
            self.add_event(rng, later, service, "tier", rng.choice([value for value in (1, 2, 3) if value != target]))

    def reach_traps(self, rng, question):
        """Services of this question's pool send requests to the service, or seem to: some are counted at the start time
        and some are decoys, through prod.toml, an included routes file, base.toml and changes either side of it."""
        service, start, pool = question["service"], question["start"], question["pool"]
        counted = rng.choice([2, 3, 3, 4])
        decoys = min(rng.choice([1, 2]), len(pool) - counted)
        elsewhere = lambda other: rng.choice([name for name in self.services if name not in self.asked and name != other])
        modes = []
        for other in pool[:counted]:
            mode = rng.choice(["prod", "base", "away-later", "earlier-to", "include"])
            if mode == "include" and not self.spare_routes:
                mode = "prod"
            modes.append(mode)
            prod = self.prod0[other]
            if mode == "prod":
                prod["upstream"] = service
            elif mode == "base":
                prod.pop("upstream", None)
                self.include[other] = None
                self.base[other]["upstream"] = service
            elif mode == "away-later":
                prod["upstream"] = service
                self.add_event(rng, start + dt.timedelta(hours=rng.randrange(1, 60)), other, "upstream", elsewhere(other))
            elif mode == "earlier-to":
                prod["upstream"] = elsewhere(other)
                self.add_event(rng, start - dt.timedelta(days=rng.randrange(1, 6), hours=rng.randrange(24)), other, "upstream", service)
            else:
                routes = self.spare_routes.pop(rng.randrange(len(self.spare_routes)))
                self.shared[routes] = {"upstream": service, **{key: rng.randrange(41, 140) for key in rng.sample(KEYS, 1)}}
                prod.pop("upstream", None)
                self.include[other] = routes
        for other in pool[counted:counted + decoys]:
            mode = rng.choice(["to-later", "overridden-base", "staging"])
            modes.append(mode)
            if mode == "to-later":
                self.prod0[other]["upstream"] = elsewhere(other)
                self.add_event(rng, start + dt.timedelta(hours=rng.randrange(1, 60)), other, "upstream", service)
            elif mode == "overridden-base":
                self.base[other]["upstream"] = service
                self.prod0[other]["upstream"] = elsewhere(other)
            else:
                self.staging[other]["upstream"] = service
                self.retired[other]["upstream"] = service
        question["reachModes"] = modes

    def class_traps(self, rng, question):
        start, cause = question["start"], self.event(question["cause"])
        other = lambda kind: rng.choice([value for value in ("standard", "emergency") if value != kind])
        if cause["class"] != "rollback" and rng.random() < 0.5:
            self.amend(rng, cause, "approved", start - minutes(rng.randrange(10, 1800)), other(cause["class"]))
        in_force = self.class_at(question, ())
        if in_force == "rollback":
            return
        if rng.random() < 0.5:
            self.amend(rng, cause, "approved", start + minutes(rng.randrange(30, 2880)), other(in_force))
        if rng.random() < 0.4:
            self.amend(rng, cause, "rejected", start - minutes(rng.randrange(10, 1800)), other(in_force))

    def amend(self, rng, cause, status, effective, kind):
        self.amendments.append({"id": self.fresh(rng, "AMD", 10, 99), "amends": cause["id"], "status": status, "effective": effective, "class": kind})

    def freeze_traps(self, rng, question):
        """A freeze whose Berlin start or end lies between the start time in UTC and in Berlin time, or one that covers
        it but exempts the service by name, or one that covers it plainly (tier 3 services are exempt)."""
        service, start = question["service"], question["start"]
        kind = rng.choice(["start-edge", "end-edge", "inside", "inside-exempt", "none"])
        question["freezeTrap"] = kind
        exempt = rng.sample([name for name in self.services if name not in self.asked], rng.randrange(0, 3))
        hour = start.replace(minute=0)
        edge = hour + dt.timedelta(hours=rng.choice([1, 2]))  # Berlin; edge - 2h < start < edge
        if kind == "start-edge":
            self.freezes.append({"start": edge, "end": edge + dt.timedelta(days=rng.randrange(1, 3), hours=rng.randrange(1, 12)), "exempt": exempt})
        elif kind == "end-edge":
            self.freezes.append({"start": edge - dt.timedelta(days=rng.randrange(1, 3), hours=rng.randrange(1, 12)), "end": edge, "exempt": exempt})
        elif kind in ("inside", "inside-exempt"):
            local = hour + OFFSET
            self.freezes.append({"start": local - dt.timedelta(hours=rng.randrange(4, 40)), "end": local + dt.timedelta(hours=rng.randrange(4, 40)),
                                 "exempt": sorted(exempt + [service]) if kind == "inside-exempt" else exempt})

    def what_if(self, rng, question):
        """Pick an earlier change whose absence changes the procedure, or else the deadline; add one if needed."""
        service, start = question["service"], question["start"]
        candidates = [event for event in self.events if event["time"] < start and event["id"] != question["cause"]
                      and ((event["service"] == service and event["key"] == "tier") or (event["service"] in question["pool"] and event["key"] == "upstream"))]
        if not candidates:
            return False
        truth = self.facts(question)
        scored = []
        for event in candidates:
            changed = self.facts(question, event["id"])
            scored.append((2 if changed["procedure"] != truth["procedure"] else 1 if changed["deadline"] != truth["deadline"] else 0, event["id"]))
        best = max(score for score, _ in scored)
        if best == 0:
            return False
        question["what_if"] = rng.choice(sorted(change for score, change in scored if score == best))
        return True

    def approver_traps(self, rng, question):
        """Once the procedure is known: an ownership transfer after the start time, a swap that covers it, and a decoy
        swap of the other role or of an earlier time."""
        features, service, start = self.features, question["service"], question["start"]
        truth = self.facts(question)
        team, role = truth["team"], truth["role"]
        if features["transfers"] and team is not None and rng.random() < 0.5:
            new_team = rng.choice([name for name in self.team_names if name != team])
            self.transfer[service] = (start + dt.timedelta(hours=rng.randrange(1, 72)), team)
            self.owner[service] = new_team
        elif features["transfers"] and rng.random() < 0.4:
            # A transfer before the start time: OWNERS is current.
            self.transfer[service] = (start - dt.timedelta(days=rng.randrange(1, 10), hours=rng.randrange(24)),
                                      rng.choice([name for name in self.team_names if name != self.owner[service]]))
            team = self.owner[service] if team is not None else None
        if not features["swaps"]:
            return
        person = self.on_call(team, role, start)
        members = TEAMS[team] if team else COMMANDERS
        if rng.random() < 0.6:
            covering = rng.choice([name for name in members if name != person])
            self.swaps.append({"start": start - minutes(rng.randrange(60, 1200)), "end": start + minutes(rng.randrange(60, 1200)),
                               "team": team, "role": role, "by": covering, "for": person})
        if rng.random() < 0.5:
            if team is not None:
                other_role = "secondary" if role == "primary" else "primary"
                other = self.on_call(team, other_role, start)
                self.swaps.append({"start": start - minutes(rng.randrange(60, 1200)), "end": start + minutes(rng.randrange(60, 1200)),
                                   "team": team, "role": other_role, "by": rng.choice([name for name in members if name not in (person, other)]), "for": other})
            else:
                self.swaps.append({"start": start - minutes(rng.randrange(1500, 3000)), "end": start - minutes(rng.randrange(10, 600)),
                                   "team": None, "role": "commander", "by": rng.choice([name for name in members if name != person]), "for": person})

    def noise(self, rng, questions):
        """Unrelated changes, amendments, freezes, swaps and transfers, away from the questions' facts."""
        asked_days = [question["day"] for question in questions]
        reserved = set(self.asked) | {name for pool in self.pools for name in pool}
        quiet = [name for name in self.services if name not in self.asked]
        for _ in range(28):
            moment = dt.datetime(2026, 9, rng.randrange(1, 29), rng.randrange(24), rng.randrange(60))
            service = rng.choice(self.services)
            options = list(KEYS) + (["tier"] if service not in self.asked else []) + (["upstream"] if service not in reserved else [])
            key = rng.choice(options)
            if key == "tier":
                value = rng.randrange(1, 4)
            elif key == "upstream":
                value = rng.choice([name for name in quiet if name != service])
            else:
                value = self.base[service][key] + rng.randrange(1, 20)
            self.add_event(rng, moment, service, key, value, rng.choices(["standard", "emergency"], [4, 1])[0])
        noise_changes = [event for event in self.events if event["service"] not in self.asked and event["class"] != "rollback"]
        for event in rng.sample(noise_changes, min(4, len(noise_changes))):
            self.amend(rng, event, rng.choice(["approved", "rejected"]), event["time"] + minutes(rng.randrange(-600, 600)),
                       "emergency" if event["class"] == "standard" else "standard")
        far = [day for day in range(2, 28) if all(abs(day - asked) > 2 for asked in asked_days)]
        if self.features["freeze"]:
            for day in rng.sample(far, min(2, len(far))):
                begin = dt.datetime(2026, 9, day, rng.randrange(6, 20))
                self.freezes.append({"start": begin, "end": begin + dt.timedelta(hours=rng.randrange(6, 30)),
                                     "exempt": rng.sample(quiet, rng.randrange(0, 3))})
        if self.features["swaps"]:
            for day in rng.sample(far, min(3, len(far))):
                begin = dt.datetime(2026, 9, day, rng.randrange(0, 20))
                if rng.random() < 0.7:
                    team = rng.choice(self.team_names)
                    role = rng.choice(["primary", "secondary"])
                    person = self.on_call(team, role, begin)
                    by = rng.choice([name for name in TEAMS[team] if name != person])
                else:
                    team, role = None, "commander"
                    person = self.on_call(None, role, begin)
                    by = rng.choice([name for name in COMMANDERS if name != person])
                self.swaps.append({"start": begin, "end": begin + dt.timedelta(hours=rng.randrange(4, 20)), "team": team, "role": role, "by": by, "for": person})
        if self.features["transfers"]:
            for service in rng.sample([name for name in self.services if name not in self.asked], 2):
                self.transfer[service] = (dt.datetime(2026, 9, rng.randrange(1, 28), rng.randrange(24)),
                                          rng.choice([name for name in self.team_names if name != self.owner[service]]))
        self.freezes.sort(key=lambda freeze: freeze["start"])
        self.swaps.sort(key=lambda swap: swap["start"])


def build(level_id, rng):
    """One adjudication snapshot: (files as {path: lines}, project, questions with keys)."""
    features = LEVELS[level_id]
    for _ in range(400):
        world = World(rng, features)
        questions, used_days = [], set()
        for service, pool in zip(world.asked, world.pools):
            for _ in range(80):
                saved = copy.deepcopy(world)
                question = world.make_question(rng, service, pool, used_days)
                if question is not None and len(world.effective_mistakes(question)) >= features["effective"]:
                    used_days.add(question["day"])
                    questions.append(question)
                    break
                world = saved
            else:
                break
        if len(questions) < QUESTIONS:
            continue
        world.noise(rng, questions)
        # Later questions' traps and the noise must not undo earlier questions' traps, and the procedures must vary.
        if all(len(world.effective_mistakes(question)) >= features["effective"] for question in questions) and \
                len({world.answer(question)["procedure"] for question in questions}) >= 2:
            break
    else:
        raise RuntimeError(f"no adjudication snapshot for {level_id}")
    project = f"{rng.choice(['north', 'quiet', 'amber', 'lucid', 'brisk'])}-{rng.choice(['relay', 'ledger', 'harvest', 'signal', 'canopy'])}"
    files, cases = render(world, rng, project, questions)
    return files, project, cases


def toml(section, values, include=None):
    order = ["tier", "upstream"] + KEYS
    lines = [f"[{section}]"] + ([f'include = "shared/{include}.toml"'] if include else [])
    return lines + [f'{key} = "{values[key]}"' if key == "upstream" else f"{key} = {values[key]}" for key in order if key in values]


def handbook(features):
    lines = ["# Rolling back a change that caused an incident", "",
             "An incident file gives its start time (Start). Every fact below is taken at that moment.", "", "## Facts", "",
             "- tier: the service's effective production tier, by docs/CONFIG.md, as the files stood at the start time."]
    if features["freeze"]:
        lines += ["- freeze: whether a change freeze applies to the service (calendar/freezes.md). A freeze applies to every service",
                  "  while it runs, except services of tier 3 and the services it exempts by name."]
    lines += ["- class: the class of the change that caused the incident. It is the class in the change record, unless approved",
              "  amendments in changes/amendments/ whose effective time is at or before the start time change it; then the one",
              "  with the latest effective time decides. Rejected amendments change nothing."]
    if features["reach"]:
        lines += ["- reach: the number of other services whose effective production upstream is the service, as the files stood at",
                  "  the start time."]
    lines += ["", "## Procedure", "", "The first rule that matches decides:", "", "1. R0: the class is rollback."]
    number = 2
    if features["freeze"]:
        lines.append(f"{number}. P4: tier 1, and a freeze applies.")
        number += 1
    if features["reach"]:
        lines.append(f"{number}. P3: reach 3 or more.")
        number += 1
    lines += [f"{number}. P2: the class is emergency, or tier 1.", f"{number + 1}. P1: any other case.", "", "## Approver", "",
              "- R0 and P1: the primary on call of the team that owns the service at the start time.",
              "- P2: the secondary on call of that team."]
    if features["freeze"] or features["reach"]:
        lines.append(f"- {' and '.join(name for name, on in (('P3', features['reach']), ('P4', features['freeze'])) if on)}: the incident commander at the start time.")
    lines += ["", "Each service's OWNERS file names its team. The rotations are in oncall/."]
    if features["swaps"]:
        lines.append("A swap in oncall/swaps.md replaces the person it names, in the role it names, for the time it gives.")
    lines += ["", "## Deadline", "",
              "The rollback is due a window after the start time: " + ", ".join(f"{name} {WINDOWS[name] // 60} hour{'s' if WINDOWS[name] > 60 else ''}"
                                                                          for name in ("R0", "P1", "P2", "P3", "P4") if name in procedures(features)) + "."]
    if features["freeze"]:
        lines.append("The P1 and P2 windows are halved while a freeze applies to the service.")
    lines.append("Give deadlines in UTC as YYYY-MM-DDTHH:MMZ.")
    if features["what_if"]:
        lines += ["", "## What if", "",
                  "A question may ask what would apply if one change had never been made. Then the key that change set keeps the",
                  "value it had before the change (its From) until the next recorded change of the same key in the same file.",
                  "Everything else is as recorded."]
    return lines


def render(world, rng, project, questions):
    features = world.features
    files = {}
    quiet = world.free + [name for pool in world.pools for name in pool]
    for question in questions:
        cause = world.event(question["cause"])
        start = question["start"]
        # A decoy change shortly before the cause, approved in a second review and rolled back without effect. It sets a
        # plain key of a service no question asks about, so no answer changes.
        decoy_service = rng.choice(quiet)
        decoy_key = rng.choice(KEYS)
        decoy_time = cause["time"] - minutes(rng.randrange(25, 50))
        before = world.prod_at(decoy_service, decoy_time).get(decoy_key)
        decoy = world.add_event(rng, decoy_time, decoy_service, decoy_key, (before or world.base[decoy_service][decoy_key]) + rng.randrange(2, 9), "emergency")
        undo = world.add_event(rng, decoy_time + minutes(rng.randrange(5, 15)), decoy_service, decoy_key, before, "rollback", decoy)
        review, decoy_review, incident = world.fresh(rng, "REV", 100, 999), world.fresh(rng, "REV", 100, 999), world.fresh(rng, "INC", 100, 999)
        files[f"reviews/{review}.md"] = [f"# {review}", "", f"Outcome: approved as {cause['id']}.", "The reviewers found no blocking issues."]
        files[f"reviews/{decoy_review}.md"] = [f"# {decoy_review}", "", f"Outcome: approved as {decoy['id']}.", "The reviewers found no blocking issues."]
        files[f"incidents/{incident}.md"] = [f"# {incident}", "", f"Start: {stamp(start)} UTC", "Impact: elevated error rates on the checkout path.",
                                             "Timeline (UTC):",
                                             f"- {decoy['time']:%H:%M} the change approved in {decoy_review} reached production; it was rolled back at "
                                             f"{undo['time']:%H:%M} without effect.",
                                             f"- {cause['time']:%H:%M} the change approved in {review} reached production; errors began "
                                             f"{int((start - cause['time']).total_seconds() // 60)} minutes later.",
                                             f"Root cause: the {cause['time']:%H:%M} change."]
        question.update(incident=incident, review=review)
    for _ in range(5):
        incident = world.fresh(rng, "INC", 100, 999)
        moment = dt.datetime(2026, 9, rng.randrange(1, 28), rng.randrange(24), rng.randrange(60))
        files[f"incidents/{incident}.md"] = [f"# {incident}", "", f"Start: {stamp(moment)} UTC", "Impact: none.",
                                             "Root cause: a failed health probe, resolved without a change."]
    for _ in range(3):
        review = world.fresh(rng, "REV", 100, 999)
        files[f"reviews/{review}.md"] = [f"# {review}", "", "Outcome: rejected.", "The proposal was withdrawn by its authors."]
    files.update({"README.md": [f"# {project}", "", f"Services: {', '.join(sorted(world.services))}.", "",
                           "Configuration and its history: docs/CONFIG.md. Incident response: docs/RESPONSE.md.",
                           "Incidents are in incidents/, reviews in reviews/, changes in changes/ and amendments in changes/amendments/.",
                           "Each service's owning team is in its OWNERS file, and the on-call rotations are in oncall/."
                           + (" Change freezes are in calendar/." if features["freeze"] else "")],
             "docs/CONFIG.md": ["# Configuration", "",
                                "Each service has config/base.toml and one file per environment (prod.toml, staging.toml).",
                                'An environment file may include a shared file with a line include = "<path>", and a shared file may include',
                                "another shared file in the same way.",
                                "For an environment, a key set in that environment's file itself wins; otherwise a key set in the file it",
                                "includes, then in the file that one includes, and so on; otherwise the key's value in base.toml.",
                                "The key tier is the service's tier (1, 2 or 3), and upstream names the service that a service sends its",
                                "requests to. Both follow the same rules as every other key.",
                                "Files ending in .bak are retired copies and are never loaded.", "", "## History", "",
                                "Every change to a prod.toml is recorded in changes/ with its time in UTC, the key, and its value before (From)",
                                'and after (To). "(not set)" means that the file did not set the key. Nothing else has changed since',
                                "2026-08-31: not base.toml, staging.toml or the shared files, and no include line.",
                                "To find a value at a past moment, take each prod.toml as it stood then, by undoing every change recorded after",
                                "that moment, and apply the precedence above."],
             "docs/RESPONSE.md": handbook(features)})
    for service in world.services:
        root = f"services/{service}"
        files[f"{root}/config/base.toml"] = toml(service, world.base[service])
        files[f"{root}/config/prod.toml"] = toml(service, world.prod_at(service, None), world.include[service])
        files[f"{root}/config/staging.toml"] = toml(service, world.staging[service], world.staging_include[service])
        files[f"{root}/config/prod.toml.bak"] = toml(service, world.retired[service], world.retired_include[service])
        owners = [f"Team: {world.owner[service]}"]
        if service in world.transfer:
            moment, before = world.transfer[service]
            owners.append(f"Since {stamp(moment)} UTC; before then the service belonged to team {before}.")
        files[f"{root}/OWNERS"] = owners
    for name, values in world.shared.items():
        files[f"shared/{name}.toml"] = toml(name, values, world.parent.get(name))
    state = {service: dict(values) for service, values in world.prod0.items()}
    show = lambda value: "(not set)" if value is None else str(value)
    for event in world.events:
        before = state[event["service"]].get(event["key"])
        if event["to"] is None:
            state[event["service"]].pop(event["key"], None)
        else:
            state[event["service"]][event["key"]] = event["to"]
        files[f"changes/{event['id']}.md"] = [f"# {event['id']}", "", f"Time: {stamp(event['time'])} UTC", f"Service: {event['service']}",
                                              f"File: services/{event['service']}/config/prod.toml", f"Key: {event['key']}",
                                              f"From: {show(before)}", f"To: {show(event['to'])}", f"Class: {event['class']}"] + \
                                             ([f"Reverts: {event['reverts']}"] if event["reverts"] else [])
    for amendment in world.amendments:
        files[f"changes/amendments/{amendment['id']}.md"] = [f"# {amendment['id']}", "", f"Amends: {amendment['amends']}", f"Status: {amendment['status']}",
                                                             f"Effective: {stamp(amendment['effective'])} UTC", f"Class: {amendment['class']}"]
    if features["freeze"]:
        files["calendar/freezes.md"] = ["# Change freezes", "",
                                        "Times are Berlin time, which is UTC+2 throughout September 2026. A freeze runs from its start (included) to",
                                        "its end (excluded).", ""] + [freeze_line(freeze) for freeze in world.freezes]
    for team in world.team_names:
        files[f"oncall/{team}.md"] = [f"# On call: {team}", "",
                                      "Each week runs from Monday 09:00 Berlin time to the next Monday 09:00. Berlin time is UTC+2 throughout",
                                      "September 2026.", "", "| Week from | Primary | Secondary |", "| --- | --- | --- |"] + \
                                     [f"| {monday.isoformat()} | {primary} | {secondary} |" for monday, (primary, secondary) in world.rotation[team].items()]
    if features["freeze"] or features["reach"]:
        files["oncall/platform.md"] = ["# Incident commanders", "",
                                       "Each day's commander serves from 08:00 Berlin time to 08:00 the next day. Berlin time is UTC+2 throughout",
                                       "September 2026.", "", "| Day | Commander |", "| --- | --- |"] + \
                                      [f"| {day.isoformat()} | {name} |" for day, name in world.commanders.items()]
    if features["swaps"]:
        files["oncall/swaps.md"] = ["# Swaps", "", "Times are UTC. A swap runs from its start (included) to its end (excluded).", ""] + \
                                   [swap_line(swap) for swap in world.swaps]
    return files, [case_key(world, question) for question in questions]


def freeze_line(freeze):
    return f"- {stamp(freeze['start'])} to {stamp(freeze['end'])}." + (f" Exempt: {', '.join(sorted(freeze['exempt']))}." if freeze["exempt"] else "")


def swap_line(swap):
    return f"- {stamp(swap['start'])} to {stamp(swap['end'])}: {swap['by']} covers " + \
        (f"the {swap['team']} {swap['role']}" if swap["team"] else "the incident commander") + f" for {swap['for']}."


FORMS = {"tier": "<1, 2 or 3>", "freeze": "<true or false>", "class": '"<standard, emergency or rollback>"', "reach": "<integer>",
         "approver": '"<name>"', "deadline": '"<YYYY-MM-DDTHH:MMZ>"', "cf_deadline": '"<YYYY-MM-DDTHH:MMZ>"'}


def case_key(world, question):
    features, service, start = world.features, question["service"], question["start"]
    answer = world.answer(question)
    truth = world.facts(question)
    names = fields(features)
    choice = '"<' + ", ".join(procedures(features)[:-1]) + " or " + procedures(features)[-1] + '>"'
    form = "{" + ", ".join(f'"{name}": {FORMS.get(name, choice)}' for name in names) + "}"
    text = f"Incident {question['incident']} was caused by a production change. Following docs/RESPONSE.md, how must that change be rolled back?"
    if features["what_if"]:
        text += f" Also give the procedure and deadline that would apply if {question['what_if']} had never been made (cf_procedure, cf_deadline)."
    whole = lambda path, absent=None: {"path": path, "whole": True, **({"absentKey": absent} if absent else {})}
    gate = [whole(f"incidents/{question['incident']}.md"), whole(f"reviews/{question['review']}.md"), whole(f"changes/{question['cause']}.md"),
            whole("docs/RESPONSE.md")]
    in_force = [amendment for amendment in world.amendments if amendment["amends"] == question["cause"] and amendment["status"] == "approved"
                and amendment["effective"] <= start]
    # A deciding line may be shown by a search as well as by a read (grader 1.7.1): every freeze line, the rotation row
    # in force, and the swap that applies.
    line = lambda path, text: {"path": path, "lineText": text}
    freeze_lines = [line("calendar/freezes.md", freeze_line(freeze)) for freeze in world.freezes] if features["freeze"] else []
    proofs = {"tier": [whole(f"services/{service}/config/prod.toml", "tier")],
              "freeze": freeze_lines,
              "class": [whole(f"changes/amendments/{amendment['id']}.md") for amendment in in_force],
              "reach": [whole(f"services/{other}/config/prod.toml", "upstream") for other in world.services
                        if other != service and world.effective(other, "upstream", start) == service],
              "procedure": [], "deadline": []}
    if truth["team"] is None:
        day = max(day for day in DAYS if dt.datetime.combine(day, dt.time(8)) - OFFSET <= start)
        approver = [line("oncall/platform.md", f"| {day.isoformat()} | {world.commanders[day]} |")]
    else:
        week = max(monday for monday in MONDAYS if dt.datetime.combine(monday, dt.time(9)) - OFFSET <= start)
        primary, secondary = world.rotation[truth["team"]][week]
        approver = [whole(f"services/{service}/OWNERS"), line(f"oncall/{truth['team']}.md", f"| {week.isoformat()} | {primary} | {secondary} |")]
    if world.features["swaps"]:
        base_person = world.on_call(truth["team"], truth["role"], start, {"ignore-swaps"})
        for swap in world.swaps:
            if swap["team"] == truth["team"] and swap["role"] == truth["role"] and swap["for"] == base_person and swap["start"] <= start < swap["end"]:
                approver.append(line("oncall/swaps.md", swap_line(swap)))
    proofs["approver"] = approver
    if features["what_if"]:
        proofs["cf_procedure"] = proofs["cf_deadline"] = [whole(f"changes/{question['what_if']}.md")]
    return {"kind": "case", "text": text, "fields": form, "answer": answer, "gate": gate, "proofs": {name: proofs[name] for name in names},
            "incident": question["incident"], "change": question["cause"], "whatIf": question.get("what_if"),
            "traps": {"tierSource": question["tierSource"], "reachModes": question.get("reachModes"), "freeze": question.get("freezeTrap")},
            "effectiveMistakes": world.effective_mistakes(question)}
