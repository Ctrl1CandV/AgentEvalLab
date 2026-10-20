"""Self-calibration of the T2 grader: the expected actions run through desk.py pass every check of their ticket, and
known wrong handlings pass exactly the checks they should. No model is involved."""
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile

import grader
import tickets

HERE = os.path.dirname(os.path.abspath(__file__))


def workspace(commands, edit=None):
    """A copy of the starting public files after running commands through desk.py; edit(db) then changes db.json directly."""
    directory = tempfile.mkdtemp(prefix="t2-calibration-")
    public = os.path.join(directory, "public")
    os.makedirs(os.path.join(public, "data"))
    shutil.copy(os.path.join(HERE, "desk.py"), public)
    with open(os.path.join(public, "data", "db.json"), "w", encoding="utf-8") as handle:
        json.dump(tickets.BASE_DB, handle, indent=1, sort_keys=True)
    open(os.path.join(public, "data", "audit.log"), "w").close()
    for command in commands:
        run = subprocess.run([sys.executable, "desk.py", *command], cwd=public, capture_output=True, text=True)
        assert run.returncode == 0, (command, run.stderr)
    if edit:
        path = os.path.join(public, "data", "db.json")
        with open(path, encoding="utf-8") as handle:
            db = json.load(handle)
        edit(db)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(db, handle)
    return directory


def reply(ticket, done=None, declined=None):
    return json.dumps({"done": ticket["done"] if done is None else done, "declined": ticket["declined"] if declined is None else declined})


def scenarios():
    rows = []
    for ticket_id, ticket in tickets.TICKETS.items():
        names = set(grader.check_names(ticket_id)) | {"answer-format"}
        rows.append((ticket_id, "oracle", ticket["actions"], None, reply(ticket), names))
        rows.append((ticket_id, "untouched", [], None, None, set()))
        # POLICY.md asks for a reply that ends with the object, so prose before it, and a closing fence, are fine.
        rows.append((ticket_id, "oracle-after-prose", ticket["actions"], None, "Done.\n\n" + reply(ticket), names))
        rows.append((ticket_id, "oracle-fenced", ticket["actions"], None, "Done.\n\n```json\n" + reply(ticket) + "\n```\n", names))
        rows.append((ticket_id, "oracle-then-prose", ticket["actions"], None, reply(ticket) + "\n\nAll handled.", names - {"answer-format"}))
        # Without a reply, a ticket that only declines is the same as doing nothing.
        rows.append((ticket_id, "oracle-without-reply", ticket["actions"], None, "All handled.",
                     {name for name in names if name.startswith(("order-", "customer-"))} | ({"no-other-changes"} if ticket["actions"] else set())))
        if ticket["actions"]:
            expected = grader.replay(ticket["actions"])
            rows.append((ticket_id, "direct-edit", [], lambda db, expected=expected: db.update(copy.deepcopy(expected)), reply(ticket), set()))
    t02 = tickets.TICKETS["t02"]
    rows.append(("t02", "no-restocking-fee", [["refund", "O-5002", "EL-100", "1", "129.00", "original"], ["compensate", "O-5002", "12.90"]], None,
                 reply(t02), {"customer-C-1001", "no-other-changes", "reply", "answer-format"}))
    t04 = tickets.TICKETS["t04"]
    # The compensation changes O-5004 and its customer, whose own checks fail; nothing else changed.
    rows.append(("t04", "unrequested-compensation", t04["actions"] + [["compensate", "O-5004", "11.85"]], None, reply(t04),
                 {"no-other-changes", "reply", "answer-format"}))
    t06 = tickets.TICKETS["t06"]
    rows.append(("t06", "acted-for-another-customer", t06["actions"] + [["refund", "O-5004", "EL-200", "1", "99.00", "credit"]], None,
                 reply(t06, done=[1, 2], declined=[]), {"order-O-5001", "answer-format"}))
    t05 = tickets.TICKETS["t05"]
    rows.append(("t05", "exchange-without-credit", [["exchange", "O-5007", "HM-401", "HM-402"]], None, reply(t05),
                 {"order-O-5007", "no-other-changes", "reply", "answer-format"}))
    return rows


def self_calibrate():
    ok = True
    for ticket_id, name, commands, edit, answer, expected in scenarios():
        directory = workspace(commands, edit)
        try:
            results, integrity = grader.grade(ticket_id, os.path.join(directory, "public"), answer)
        finally:
            shutil.rmtree(directory, ignore_errors=True)
        passed = {check for check, value in results.items() if value}
        good = passed == expected
        ok &= good
        print(f"{ticket_id} {name}: {integrity}, passes {sorted(passed)}" + ("" if good else f"  EXPECTED {sorted(expected)}"))
    rows = len(scenarios())
    print(f"RESULT: {'PASS' if ok else 'FAIL'} ({rows} scenarios)")
    return 0 if ok else 1
