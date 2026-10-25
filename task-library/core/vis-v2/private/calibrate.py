"""Self-calibration of the VIS v2 functional checks (VALIDATION §1): per brief, the reference and the plain anchor
pass every check; each mutant (one broken behaviour, written into a copy of the reference) fails exactly the checks it
targets and no other; a submission without index.html fails everything. The mutants include vis-001's false passes:
an address without a dot in the domain reaching the success message, and an extra option in the interest select."""
import os
import shutil
import tempfile

import grader
from briefs import CHECKS, COMMON_CHECKS

ANCHORS = os.path.join(grader.HERE, "anchors")

# brief -> [(name, {file: [(old, new)]}, failing checks)]; every `old` must occur in the file, so no mutant is a no-op.
COMMON_MUTANTS = [
    ("script-error", {"app.js": [("const C = window.CONTENT;", "const C = window.CONTENT; undefinedFunction();")]}, None),
    ("phone-overflow", {"style.css": [("* { box-sizing: border-box; }", "* { box-sizing: border-box; } body { min-width: 1500px; }")]}, {"no-overflow"}),
]
MUTANTS = {
    "dashboard": [
        ("filter-ignores-kpis", {"app.js": [("$('[data-role=\"kpi-total\"]').textContent = rows.length;", "$('[data-role=\"kpi-total\"]').textContent = C.shipments.length;")]}, {"filter"}),
        ("tiny-chart", {"style.css": [(".chart { display: block; width: 100%; min-width: 220px; height: 170px;", ".chart { display: block; width: 150px; height: 80px;")]}, {"chart"}),
        ("unlabelled-filter", {"index.html": [('<label for="region">Region</label>', '<span>Region</span>')]}, {"labels"}),
    ],
    "editor": [
        ("no-unsaved-state", {"app.js": [('for (const field of ["#title", "#body"]) $(field).addEventListener("input", () => setStatus(true));', "")]}, {"unsaved"}),
        ("save-keeps-old-title", {"app.js": [("notes[current] = { title: $(\"#title\").value, body: $(\"#body\").value };", "notes[current] = { ...notes[current], body: $(\"#body\").value };")]}, {"save"}),
        ("opens-first-note", {"app.js": [('button.addEventListener("click", () => open(index));', 'button.addEventListener("click", () => open(0));')]}, {"open-note", "save"}),
    ],
    "multistep": [
        ("accepts-any-email", {"app.js": [("const EMAIL = /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/;", "const EMAIL = /.*/;")]}, {"validation", "review", "navigation", "submit"}),
        ("back-resets-plan", {"app.js": [('$("#back").addEventListener("click", () => show(step - 1));',
                                          '$("#back").addEventListener("click", () => { document.querySelector(\'input[name="plan"]\').checked = true; show(step - 1); });')]}, {"navigation"}),
        ("no-success-message", {"app.js": [("success.hidden = false;", "")]}, {"submit"}),
    ],
    "landing-fernwood": [
        # vis-001's false pass: "hiker@example" reached the success message.
        ("accepts-address-without-dot", {"app.js": [("const EMAIL = /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/;", "const EMAIL = /^[^\\s@]+@[^\\s@]+$/;")]}, {"form-invalid"}),
        # vis-001's false pass: an extra option in the interest select.
        ("extra-interest", {"app.js": [("$(\"#interest\").append(...N.interests.map(name => new Option(name, name.toLowerCase())));",
                                        "$(\"#interest\").append(...[...N.interests, \"Skiing\"].map(name => new Option(name, name.toLowerCase())));")]}, {"options"}),
        ("missing-product", {"app.js": [("$(\"#product-grid\").replaceChildren(...C.products.map(", "$(\"#product-grid\").replaceChildren(...C.products.slice(1).map(")]}, {"copy"}),
    ],
    "landing-quanta": [
        ("yearly-times-twelve", {"app.js": [("C.plans[index].monthly * (yearly ? C.yearlyMultiple : 1)", "C.plans[index].monthly * (yearly ? 12 : 1)")]}, {"prices-yearly"}),
        ("one-way-toggle", {"app.js": [("yearly = !yearly; render();", "yearly = true; render();")]}, {"toggle-back"}),
    ],
    "mobile-schedule": [
        ("no-aria-pressed", {"app.js": [('button.setAttribute("aria-pressed", String(saved.has(key)));', "")]}, {"favourite"}),
        ("small-targets", {"style.css": [(".fav { display: grid; place-items: center; width: 48px; height: 48px;", ".fav { display: grid; place-items: center; width: 18px; height: 18px; padding: 0;")]}, {"touch-targets"}),
        ("all-days-shown", {"app.js": [("panel.hidden = position !== day;", "panel.hidden = false;")]}, {"tabs"}),
    ],
    "catalogue": [
        ("case-sensitive-search", {"app.js": [("book.title.toLowerCase().includes(query)", "book.title.includes($(\"#search\").value.trim())")]}, {"search", "combined"}),
        ("genre-ignores-search", {"app.js": [("book.title.toLowerCase().includes(query) && (!genre || book.genre === genre)", "(genre ? book.genre === genre : book.title.toLowerCase().includes(query))")]}, {"combined"}),
        ("sort-descending", {"app.js": [("left.year - right.year", "right.year - left.year")]}, {"sort"}),
    ],
    "states": [
        ("retry-never-loads", {"app.js": [("history.replaceState(null, \"\", \"#loaded\");\n    fromHash();", "$(\"#loading\").hidden = true;")]}, {"retry"}),
        ("all-states-shown", {"app.js": [("$(`[data-role=\"state-${state}\"]`).hidden = state !== name;", "$(`[data-role=\"state-${state}\"]`).hidden = false;")]},
         {"empty", "error", "loaded", "retry"}),
    ],
}


def anchor_site(brief, kind, destination):
    """The reference page, or the plain anchor (the same files with the shared plain stylesheet), copied to `destination`."""
    shutil.copytree(os.path.join(ANCHORS, brief), destination)
    if kind == "plain":
        shutil.copyfile(os.path.join(ANCHORS, "plain.css"), os.path.join(destination, "style.css"))
    return destination


def mutate(site, edits):
    for name, replacements in edits.items():
        path = os.path.join(site, name)
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        for old, new in replacements:
            if old not in text:
                raise ValueError(f"mutant edit not found in {name}: {old[:60]}")
            text = text.replace(old, new, 1)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)


def self_calibrate(launcher, only=None):
    rows = []
    for brief in only or list(CHECKS):
        expected = COMMON_CHECKS + CHECKS[brief]
        with tempfile.TemporaryDirectory(prefix=f"vis-{brief}-") as work:
            for kind in ("reference", "plain"):
                results = grader.run_scenario(anchor_site(brief, kind, os.path.join(work, kind)), brief, os.path.join(work, f"{kind}-out"), launcher)
                failed = sorted(check for check, (ok, _) in results.items() if not ok)
                rows.append((f"{brief} {kind} passes every check", not failed, failed))
            for name, edits, targets in COMMON_MUTANTS + MUTANTS[brief]:
                site = anchor_site(brief, "reference", os.path.join(work, name))
                mutate(site, edits)
                results = grader.run_scenario(site, brief, os.path.join(work, f"{name}-out"), launcher)
                failed = {check for check, (ok, _) in results.items() if not ok}
                # A script error stops the page's behaviour: every behaviour check fails, and `renders` with them.
                wanted = set(expected) - {"labels", "no-overflow"} if targets is None else targets
                rows.append((f"{brief} mutant {name} fails exactly {sorted(wanted)}", failed == wanted, sorted(failed)))
            empty = os.path.join(work, "empty")
            os.makedirs(empty)
            results = grader.run_scenario(empty, brief, os.path.join(work, "empty-out"), launcher)
            rows.append((f"{brief} missing index.html fails every check", not any(ok for ok, _ in results.values()), []))
        for name, ok, failed in rows[-(len(COMMON_MUTANTS) + len(MUTANTS[brief]) + 3):]:
            print(f"{'PASS' if ok else 'FAIL'}: {name}{'' if ok else f' (failed: {failed})'}", flush=True)
    bad = [name for name, ok, _ in rows if not ok]
    print(f"RESULT: {'PASS' if not bad else 'FAIL'} ({len(rows) - len(bad)}/{len(rows)})")
    return 0 if not bad else 1
