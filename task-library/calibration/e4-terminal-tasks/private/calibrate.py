"""Self-calibration of the E4 graders: oracle solutions pass every check, the untouched workspace passes none, and
known partial or wrong solutions pass exactly the checks they should. No model is involved."""
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
    return [
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
