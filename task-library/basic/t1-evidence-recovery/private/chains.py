"""Depth-ladder snapshots for T1 (levels D2, D4, D6 and D8, task 0.5.0): every question follows a chain of references.

A chain starts at an incident and runs through its review and the approved change to the service whose configuration
the change set; from there it follows that service's production upstream some number of times and ends at a key's
effective production value. Each file that must be read to take the next step is one reference, so a question's depth
is the number of files it needs after the incident: the review, the change, and every configuration file that decides
an upstream or the final value. Errors compound with depth, as grid size does for R3.

Every step has a plausible distractor: the incident names a second, unrelated review; the review names a superseded
change of another service; a later change of the same key exists; staging, base and retired (.bak) files set the same
keys, upstream included; and upstream itself follows the precedence rules, so it may come from an included file.
"""
import random

SERVICES = ["atlas", "beacon", "cinder", "delta", "ember", "fjord", "garnet", "harbor", "iris", "juniper", "kestrel", "lumen", "mesa", "nectar",
            "orchid", "pylon", "quill", "rowan", "spruce", "tundra", "umbra", "vesper", "willow", "yonder"]
KEYS = ["timeout_ms", "max_retries", "pool_size", "queue_depth", "batch_size", "cache_ttl_s"]
SHARED = ["limits-standard", "limits-burst", "limits-batch", "limits-floor", "pool-small", "pool-large", "retry-fast", "retry-safe"]
QUESTIONS = 5
LEVELS = {"D2": 2, "D4": 4, "D6": 6, "D8": 8}
TIMES = {1: "once", 2: "twice", 3: "three times"}


class World:
    """Configuration of every service: base, prod, staging and retired prod values, prod's include, and shared files."""

    def __init__(self, rng):
        self.services = rng.sample(SERVICES, 18)
        self.shared = {}
        self.parent = {}
        names = rng.sample(SHARED, 7)
        # Shared files form short include chains: a top file may include a middle one, which may include a bottom one.
        tops, middles, bottoms = names[:3], names[3:5], names[5:]
        for name in bottoms:
            self.shared[name] = {}
        for name in middles:
            self.shared[name] = {}
            self.parent[name] = rng.choice(bottoms)
        for name in tops:
            self.shared[name] = {}
            if rng.random() < 0.85:
                self.parent[name] = rng.choice(middles)
        for name, values in self.shared.items():
            for key in rng.sample(KEYS, rng.randrange(2, 5)):
                values[key] = rng.randrange(41, 140)
            if rng.random() < 0.35:
                values["upstream"] = None  # filled in below, once services are known
        order = list(self.services)
        rng.shuffle(order)
        self.rank = {service: index for index, service in enumerate(order)}
        later = lambda service: [other for other in order if self.rank[other] > self.rank[service]]
        for name, values in self.shared.items():
            if "upstream" in values:
                values["upstream"] = rng.choice(order[len(order) // 2:])
        self.config = {}
        for service in self.services:
            base = {key: rng.choice([100, 250, 500, 750, 1000, 1500, 2000, 3000]) if key == "timeout_ms" else rng.randrange(2, 40) for key in KEYS}
            candidates = later(service) or [other for other in order if other != service]
            base["upstream"] = rng.choice(candidates)
            prod = {key: base[key] + rng.randrange(1, 9) if key != "timeout_ms" else base[key] * 2 for key in rng.sample(KEYS, rng.randrange(1, 4))}
            if rng.random() < 0.6 and later(service):
                prod["upstream"] = rng.choice(later(service))
            include = rng.choice(sorted(self.shared)) if rng.random() < 0.6 else None
            staging = {key: base[key] + rng.randrange(10, 30) if key != "timeout_ms" else base[key] * 3 for key in rng.sample(KEYS, 3)}
            staging["upstream"] = rng.choice([other for other in order if other != service])
            retired = {key: value + 7 for key, value in prod.items() if key != "upstream"} | {key: base[key] + 11 for key in rng.sample(KEYS, 2)}
            retired["upstream"] = rng.choice([other for other in order if other != service])
            staging_include = rng.choice(sorted(self.shared)) if rng.random() < 0.4 else None
            retired_include = rng.choice([name for name in sorted(self.shared) if name != include])
            self.config[service] = {"base": base, "prod": prod, "include": include, "staging": staging, "staging_include": staging_include,
                                    "retired": retired, "retired_include": retired_include}

    def separate_upstreams(self, rng):
        """Staging, retired and (where it is not the source) base upstreams name another service than the effective one."""
        for service in self.services:
            effective, source = self.resolve(service, "upstream")[1], self.resolve(service, "upstream")[0]
            config = self.config[service]
            others = [other for other in self.services if other not in (service, effective)]
            for values in (config["staging"], config["retired"]) + ((config["base"],) if not source.endswith("base.toml") else ()):
                if values.get("upstream") == effective:
                    values["upstream"] = rng.choice(others)

    def chain(self, service):
        """The shared files a service's production configuration reaches, nearest first."""
        links, name = [], self.config[service]["include"]
        while name is not None:
            links.append(name)
            name = self.parent.get(name)
        return links

    def resolve(self, service, key):
        """(source path, value, files needed, proofs) of a key's effective production value."""
        prod_path = f"services/{service}/config/prod.toml"
        config = self.config[service]
        if key in config["prod"]:
            return prod_path, config["prod"][key], [prod_path], [("line", prod_path, line(key, config["prod"][key]))]
        proofs = [("whole", prod_path, key)]
        files, previous = [prod_path], prod_path
        for name in self.chain(service):
            path = f"shared/{name}.toml"
            proofs.append(("line", previous, f'include = "{path}"'))
            files.append(path)
            if key in self.shared[name]:
                return path, self.shared[name][key], files, proofs + [("line", path, line(key, self.shared[name][key]))]
            proofs.append(("whole", path, key))
            previous = path
        path = f"services/{service}/config/base.toml"
        return path, config["base"][key], files + [path], proofs + [("line", path, line(key, config["base"][key]))]


def line(key, value):
    return f'{key} = "{value}"' if key == "upstream" else f"{key} = {value}"


def toml(section, values, include=None):
    lines = [f"[{section}]"] + ([f'include = "shared/{include}.toml"'] if include else [])
    return lines + [line(key, value) for key, value in values.items()]


def walk(world, start, hops):
    """The services reached by following the effective production upstream `hops` times, with the files and proofs each
    step needs, or None when the walk revisits a service."""
    services, files, proofs = [start], [], []
    for _ in range(hops):
        _, upstream, needed, shown = world.resolve(services[-1], "upstream")
        if upstream in services:
            return None
        services.append(upstream)
        files += needed
        proofs += shown
    return services, files, proofs


def build(level_id, rng):
    """One depth-ladder snapshot: (snapshot files as {path: lines}, project, questions)."""
    depth = LEVELS[level_id]
    for _ in range(500):
        world = World(rng)
        world.separate_upstreams(rng)
        picked = pick(world, depth, rng)
        if picked:
            break
    else:
        raise RuntimeError(f"no chains of depth {depth}")
    project = f"{rng.choice(['north', 'quiet', 'amber', 'lucid', 'brisk'])}-{rng.choice(['relay', 'ledger', 'harvest', 'signal', 'canopy'])}"
    files = {"README.md": [f"# {project}", "", f"Services: {', '.join(sorted(world.services))}.", "",
                           "Configuration precedence is described in docs/CONFIG.md. Incidents live in incidents/, reviews in reviews/,",
                           "changes in changes/."],
             "docs/CONFIG.md": ["# Configuration", "",
                                "Each service has config/base.toml and one file per environment (prod.toml, staging.toml).",
                                'An environment file may include a shared file with a line include = "<path>", and a shared file may include',
                                "another shared file in the same way.",
                                "For an environment, a key set in that environment's file itself wins; otherwise a key set in the file it",
                                "includes, then in the file that one includes, and so on; otherwise the key's value in base.toml.",
                                'The key upstream names the service that a service sends its requests to; it follows the same rules.',
                                "Files ending in .bak are retired copies and are never loaded.",
                                "",
                                "Every production change is recorded in changes/ with its date, the key, and its value before and after.",
                                "A change is released after a review in reviews/ approves it; incidents/ records what caused an incident."]}
    for service in world.services:
        config = world.config[service]
        files[f"services/{service}/config/base.toml"] = toml(service, config["base"])
        files[f"services/{service}/config/prod.toml"] = toml(service, config["prod"], config["include"])
        files[f"services/{service}/config/staging.toml"] = toml(service, config["staging"], config["staging_include"])
        files[f"services/{service}/config/prod.toml.bak"] = toml(service, config["retired"], config["retired_include"])
    for name, values in world.shared.items():
        files[f"shared/{name}.toml"] = toml(name, values, world.parent.get(name))
    ids = set()

    def fresh(prefix, low, high):
        while True:
            value = f"{prefix}-{rng.randrange(low, high)}"
            if value not in ids:
                ids.add(value)
                return value

    def change_file(change, service, key, day, before, after):
        files[f"changes/{change}.md"] = [f"# {change}", "", f"Date: 2026-09-{day:02d}", f"Service: {service}", f"File: services/{service}/config/prod.toml",
                                         f"Key: {key}", f"From: {before}", f"To: {after}", "Released after review."]

    questions = []
    for start, hops, key, walked, chain_proofs in picked:
        # The change behind the incident set one of the start service's production keys; a later change set it again.
        changed = rng.choice(sorted(k for k in world.config[start]["prod"] if k != "upstream") or ["timeout_ms"])
        current = world.config[start]["prod"].get(changed, world.config[start]["base"][changed])
        values = [current + 9 + rng.randrange(1, 5), current + 4 + rng.randrange(1, 4), current]
        days = sorted(rng.sample(range(2, 27), 2))
        change, later_change = fresh("CHG", 1000, 9999), fresh("CHG", 1000, 9999)
        change_file(change, start, changed, days[0], values[0], values[1])
        change_file(later_change, start, changed, days[1], values[1], values[2])
        # The review names a superseded change of another service; the incident names an unrelated review as well. Both
        # lead, by the same steps, to another answer.
        outcome = outcome_of(world, start, hops, key)
        diverging = [service for service in world.services if service != start and outcome_of(world, service, hops, key) not in (None, outcome)]
        other, decoy_service = rng.sample(diverging, 2)
        other_key = rng.choice(KEYS)
        superseded, decoy_change = fresh("CHG", 1000, 9999), fresh("CHG", 1000, 9999)
        base_other = world.config[other]["base"][other_key]
        change_file(superseded, other, other_key, days[0] - 1, base_other, base_other + rng.randrange(1, 9))
        base_decoy = world.config[decoy_service]["base"]["max_retries"]
        change_file(decoy_change, decoy_service, "max_retries", max(1, days[0] - 1), base_decoy + 2, base_decoy + 5)
        review, decoy_review = fresh("REV", 100, 999), fresh("REV", 100, 999)
        files[f"reviews/{review}.md"] = [f"# {review}", "", f"Proposal: {superseded}, superseded during the review.", f"Outcome: approved as {change}.",
                                         "The reviewers found no blocking issues."]
        files[f"reviews/{decoy_review}.md"] = [f"# {decoy_review}", "", f"Outcome: approved as {decoy_change}.", "The reviewers found no blocking issues."]
        incident = fresh("INC", 100, 999)
        files[f"incidents/{incident}.md"] = [f"# {incident}", "", "Impact: elevated error rates on the checkout path.", "Timeline:",
                                             f"- 09:05 the change approved in {decoy_review} reached production; it was rolled back at 09:20 without effect.",
                                             f"- 09:40 the change approved in {review} reached production; errors began two minutes later.",
                                             "Root cause: the 09:40 change."]
        head = [("whole", f"incidents/{incident}.md", None), ("whole", f"reviews/{review}.md", None), ("whole", f"changes/{change}.md", None)]
        intro = f"Incident {incident} was caused by a configuration change."
        if hops == 0:
            question = {"text": f"{intro} To what value did that change set its key?", "fields": '{"value": <integer>, "evidence": "<change file path>"}',
                        "answer": {"value": values[1], "evidence": f"changes/{change}.md"}, "key": changed, "proofs": head}
        else:
            source, value, _, final_proofs = world.resolve(walked[-1], key)
            question = {"text": f"{intro} Start from the service whose configuration that change set and follow its production upstream "
                                f"{TIMES[hops]}. What is the effective production {key} of the service you reach?",
                        "fields": '{"value": <integer>, "evidence": "<file path where the effective value is set>"}',
                        "answer": {"value": value, "evidence": source}, "key": key, "proofs": head + chain_proofs + final_proofs}
        question.update(kind="chain", depth=depth, hops=hops)
        questions.append(question)
    # Unrelated incidents and reviews, as a real project has.
    for _ in range(6):
        incident = fresh("INC", 100, 999)
        files[f"incidents/{incident}.md"] = [f"# {incident}", "", "Impact: none.", "Root cause: a failed health probe, resolved without a change."]
    for _ in range(4):
        review = fresh("REV", 100, 999)
        files[f"reviews/{review}.md"] = [f"# {review}", "", "Outcome: rejected.", "The proposal was withdrawn by its authors."]
    return files, project, questions


def outcome_of(world, start, hops, key):
    """Where a chain from `start` ends: the final (source, value), or None when the walk loops. Depth-2 chains end at
    their own change, so any other service is another outcome."""
    if hops == 0:
        return start
    walked = walk(world, start, hops)
    if walked is None:
        return None
    source, value, _, _ = world.resolve(walked[0][-1], key)
    return source, value


def pick(world, depth, rng):
    """QUESTIONS chains of exactly this depth, from different start services where possible:
    (start service, upstream hops, key, services walked, proofs of the walk)."""
    options = []
    for start in world.services:
        if depth == 2:
            if any(key != "upstream" for key in world.config[start]["prod"]):
                options.append((start, 0, None, [start], []))
            continue
        for hops in (1, 2, 3):
            walked = walk(world, start, hops)
            if walked is None:
                continue
            services, files, proofs = walked
            if not any(key != "upstream" for key in world.config[start]["prod"]):
                continue
            for key in KEYS:
                _, _, needed, _ = world.resolve(services[-1], key)
                # References: the review, the change, then every configuration file the walk and the final value need.
                if 2 + len(set(files) | set(needed)) == depth:
                    options.append((start, hops, key, services, proofs))
    rng.shuffle(options)
    chosen, starts = [], set()
    for option in options:
        # The two decoy changes need services whose chains end elsewhere.
        outcome = outcome_of(world, option[0], option[1], option[2])
        if sum(1 for service in world.services if service != option[0] and outcome_of(world, service, option[1], option[2]) not in (None, outcome)) < 2:
            continue
        if option[0] not in starts:
            chosen.append(option)
            starts.add(option[0])
        if len(chosen) == QUESTIONS:
            break
    if len(chosen) < QUESTIONS or (depth > 4 and len({option[1] for option in chosen}) < 2):
        return None
    return [(start, hops, key, services, proofs) for start, hops, key, services, proofs in chosen]


def seeded(seed):
    return random.Random(seed)
