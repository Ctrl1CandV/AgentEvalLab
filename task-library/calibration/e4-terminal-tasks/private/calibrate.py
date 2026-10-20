"""Self-calibration of the E4 graders: oracle solutions pass every check, the untouched workspace passes none, and
known partial or wrong solutions pass exactly the checks they should. No model is involved."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

import grader

HERE = os.path.dirname(os.path.abspath(__file__))
ITEMS = os.path.join(grader.PACKAGE, "items")


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def submission(item_id, files, prepare=None):
    """The item's starting workspace with files ({path: text}) written over it."""
    workspace = tempfile.mkdtemp(prefix="e4-calibration-")
    directory = os.path.join(workspace, "public")
    shutil.copytree(os.path.join(ITEMS, item_id, "public"), directory)
    for path, text in files.items():
        os.makedirs(os.path.dirname(os.path.join(directory, path)) or directory, exist_ok=True)
        with open(os.path.join(directory, path), "w", encoding="utf-8") as handle:
            handle.write(text)
    if prepare:
        prepare(directory)
    return workspace


def migrate_shop(directory):
    """Run the submission's own migrate.py on shop.db, as the model would."""
    subprocess.run([sys.executable, "migrate.py", "shop.db"], cwd=directory, capture_output=True, timeout=60)


def scenarios():
    from bisect_item import history
    perf_oracle = read(os.path.join(HERE, "perf", "oracle.py"))
    migrate_oracle = read(os.path.join(HERE, "migrate", "oracle.py"))
    culprit = read(os.path.join(HERE, "bisect_item", "culprit.txt"))
    fixed = history.HEAD_PRICING.replace("quantity > BULK_THRESHOLD", "quantity >= BULK_THRESHOLD")
    solution = os.path.join(HERE, "build", "solution")
    build_fix = {path: read(os.path.join(solution, path)) for path in ("Makefile", "src/main.c", "src/words.c", "src/table.c")}
    everything = set
    fixes = {name: read(os.path.join(HERE, "stockroom_item", "solution", "stockroom", name)) for name in
             ("config.py", "db.py", "importer.py", "inventory.py", "reports.py", "cli.py")}
    shipped = {name: read(os.path.join(ITEMS, "stockroom", "public", "stockroom", name)) for name in fixes}
    def only(*names):
        return {f"stockroom/{name}": fixes[name] for name in names}
    stockroom = [
        ("stockroom", "oracle", {f"stockroom/{name}": text for name, text in fixes.items()}, None, everything(grader.CHECKS["stockroom"])),
        ("stockroom", "untouched", {}, None, everything()),
        ("stockroom", "config-only", only("config.py"), None, {"strict-env", "regression"}),
        ("stockroom", "reports-only", only("reports.py"), None, {"timezone", "money", "regression"}),
        ("stockroom", "index-only", only("db.py"), None, {"export-speed", "regression"}),
        # Deduplication without the cache invalidation, which needs the importer's new parameter and the CLI change.
        ("stockroom", "dedupe-without-cache", {"stockroom/importer.py": fixes["importer.py"].replace("from . import cache\n", "").replace(
            "    if cache_dir is not None:\n        cache.invalidate(cache_dir, \"low-stock\")\n", "")}, None, {"duplicates", "regression"}),
        ("stockroom", "cache-on-restock-only", only("inventory.py"), None, everything()),
        ("stockroom", "floats-rounded", only("config.py", "db.py", "importer.py", "inventory.py", "cli.py") | {"stockroom/reports.py": fixes["reports.py"].replace(
            "        revenue += Decimal(price) * qty", "        revenue += Decimal(float(price) * qty)")}, None, everything(grader.CHECKS["stockroom"]) - {"money"}),
    ]
    assert shipped
    solution = os.path.join(HERE, "pipeline_item", "solution")
    piped = {path: read(os.path.join(solution, path)) for path in ("Makefile", "scripts/normalize.sh", "scripts/join.py")}
    pipeline = [
        ("pipeline", "oracle", piped, None, everything(grader.CHECKS["pipeline"])),
        ("pipeline", "untouched", {}, None, everything()),
        ("pipeline", "makefile-only", {"Makefile": piped["Makefile"]}, None, {"rebuild", "regression"}),
        ("pipeline", "normalize-only", {"scripts/normalize.sh": piped["scripts/normalize.sh"]}, None, {"line-ends", "eu-format", "regression"}),
        ("pipeline", "join-only", {"scripts/join.py": piped["scripts/join.py"]}, None, {"store-ids", "regression"}),
        ("pipeline", "no-eu-handling", {**piped, "scripts/normalize.sh": piped["scripts/normalize.sh"].replace("*/sales-eu*)", "*/no-such-export*)")}, None,
         everything(grader.CHECKS["pipeline"]) - {"eu-format", "combined"}),
    ]
    with open(os.path.join(HERE, "recover_item", "answers.json"), encoding="utf-8") as handle:
        lost = json.load(handle)
    from recover_item import history as lost_history
    tree = {f"recovered/search/{path}": text for path, text in lost["files"].items()}
    old_tree = dict(tree, **{"recovered/search/src/notes.py": lost_history.NOTES_V1})
    recover = [
        ("recover", "oracle", {**tree, "recovered/search.txt": lost["search"] + "\n", "recovered/stash.txt": lost["stash"] + "\n",
                               "recovered/RELEASE.md": lost["release"]}, None, everything(grader.CHECKS["recover"])),
        ("recover", "untouched", {}, None, everything()),
        ("recover", "pre-rebase-branch", {**old_tree, "recovered/search.txt": lost["decoys"]["search"], "recovered/stash.txt": lost["stash"],
                                          "recovered/RELEASE.md": lost["release"]}, None, {"stash-commit", "stash-file"}),
        ("recover", "first-stash", {**tree, "recovered/search.txt": lost["search"], "recovered/stash.txt": lost["decoys"]["stash"],
                                    "recovered/RELEASE.md": lost_history.RELEASE_OLD_STASH}, None, {"search-commit", "search-tree"}),
    ]
    return stockroom + pipeline + recover + [
        ("perf", "oracle", {"report.py": perf_oracle}, None, everything(grader.CHECKS["perf"])),
        ("perf", "untouched", {}, None, everything()),
        ("perf", "fast-but-case-sensitive-users", {"report.py": perf_oracle.replace("user.lower()", "user")}, None, {"speed", "empty"}),
        ("migrate", "oracle", {"migrate.py": migrate_oracle}, migrate_shop, everything(grader.CHECKS["migrate"])),
        ("migrate", "untouched", {}, None, everything()),
        ("migrate", "oracle-without-running-it", {"migrate.py": migrate_oracle}, None, everything(grader.CHECKS["migrate"]) - {"workspace-db"}),
        ("migrate", "comma-names-ignored", {"migrate.py": migrate_oracle.replace('    if "," in name:', '    if False:')}, migrate_shop,
         everything(grader.CHECKS["migrate"]) - {"names", "workspace-db"}),
        ("migrate", "emails-not-lowered", {"migrate.py": migrate_oracle.replace("value = value.strip().lower()", "value = value.strip()")}, migrate_shop,
         everything(grader.CHECKS["migrate"]) - {"emails", "workspace-db"}),
        ("migrate", "float-cents", {"migrate.py": migrate_oracle.replace('''    whole = int(match.group(1).replace(",", ""))
    fraction = (match.group(2) or "").ljust(2, "0")
    return whole * 100 + int(fraction or 0), CURRENCIES[value[0]]''', '''    return int(float(value[1:].replace(",", "")) * 100), CURRENCIES[value[0]]''')}, migrate_shop,
         everything(grader.CHECKS["migrate"]) - {"totals", "workspace-db"}),
        ("migrate", "no-version-check", {"migrate.py": migrate_oracle.replace('''        if "schema_version" in tables:
            return
''', "")}, migrate_shop, everything(grader.CHECKS["migrate"]) - {"idempotent"}),
        ("migrate", "orphans-not-logged", {"migrate.py": migrate_oracle.replace('                log.append((identifier, "orphan"))', "                pass")}, migrate_shop,
         everything(grader.CHECKS["migrate"]) - {"orphans", "workspace-db"}),
        ("bisect", "oracle", {"culprit.txt": culprit, "fixed/pricing.py": fixed}, None, everything(grader.CHECKS["bisect"])),
        ("bisect", "untouched", {}, None, everything()),
        ("bisect", "current-file-copied", {"culprit.txt": culprit, "fixed/pricing.py": history.HEAD_PRICING}, None, {"culprit"}),
        ("bisect", "whole-commit-reverted", {"fixed/pricing.py": fixed.replace("ROUND_HALF_EVEN", "ROUND_HALF_UP")}, None,
         {"regression-fixed", "later-features", "coupons"}),
        ("bisect", "file-before-culprit", {"culprit.txt": culprit, "fixed/pricing.py": history.V9.replace("quantity >= 100", "quantity >= 100")}, None, {"culprit"}),
        ("build", "oracle", build_fix, None, everything(grader.CHECKS["build"])),
        ("build", "untouched", {}, None, everything()),
        ("build", "makefile-only", {"Makefile": build_fix["Makefile"]}, None, everything()),
        ("build", "no-eof-fix", {path: text for path, text in build_fix.items() if path != "src/words.c"}, None,
         everything(grader.CHECKS["build"]) - {"tests", "eof-word"}),
        ("build", "no-tie-fix", {path: text for path, text in build_fix.items() if path != "src/table.c"}, None,
         everything(grader.CHECKS["build"]) - {"tests", "ties"}),
        ("build", "flags-dropped", {**build_fix, "Makefile": build_fix["Makefile"].replace(" -Werror", "")}, None, everything(grader.CHECKS["build"]) - {"flags"}),
    ]


def self_calibrate(launcher):
    rows = []
    for item_id, name, files, prepare, expected in scenarios():
        directory = submission(item_id, files, prepare)
        try:
            results = grader.grade(item_id, directory, launcher)
        finally:
            shutil.rmtree(directory, ignore_errors=True)
        passed = {check for check, ok in results.items() if ok}
        ok = passed == set(expected)
        print(f"{item_id} {name}: passes {sorted(passed)}" + ("" if ok else f"  EXPECTED {sorted(expected)}"))
        rows.append(ok)
    print(f"RESULT: {'PASS' if all(rows) else 'FAIL'} ({sum(rows)}/{len(rows)})")
    return 0 if all(rows) else 1
