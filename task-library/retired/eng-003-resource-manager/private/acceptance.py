#!/usr/bin/env python3
import argparse
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import threading
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
CLOCK = lambda: 1700000000.0  # Internal calibration detail.


def load_store_cls(impl_path):
    path = impl_path if os.path.isabs(impl_path) else os.path.join(PKG, impl_path)
    sys.path.insert(0, os.path.dirname(path))
    spec = importlib.util.spec_from_file_location("impl_" + os.path.basename(path).replace(".", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.ResourceStore  # Internal calibration detail.


def new_store(cls, tmp):
    return cls(os.path.join(tmp, "store.json"), clock=CLOCK)


def has_err(res, field, code):
    return any(e.get("field") == field and e.get("code") == code for e in res.get("errors", []))


# Internal calibration detail.
def sc_add_valid(cls, tmp):
    s = new_store(cls, tmp)
    r = s.add("Python docs", "https://docs.python.org", ["dev", " dev ", "", "py"], "note")
    if not r["ok"]:
        return False, 'add operation failed'
    res = r["resource"]
    if res["id"] != "1" or res["tags"] != ["dev", "py"] or res["notes"] != "note":
        return False, f"created resource does not match the expected id, normalized tags, and notes: {res}"
    return True, "ok"


def sc_add_invalid_title(cls, tmp):
    s = new_store(cls, tmp)
    r = s.add("   ", "https://x.io", None, None)
    if r["ok"] or not has_err(r, "title", "required"):
        return False, 'blank title was accepted'
    if len(s.list()) != 0:
        return False, 'blank title created a resource'
    return True, "ok"


def sc_add_invalid_url(cls, tmp):
    s = new_store(cls, tmp)
    r = s.add("t", "notaurl", None, None)
    if r["ok"] or not has_err(r, "url", "invalid_format"):
        return False, 'malformed URL was accepted'
    return True, "ok"


def sc_edit(cls, tmp):
    s = new_store(cls, tmp)
    s.add("t1", "https://a.io", None, None)
    r = s.edit("1", title="t2")
    if not r["ok"] or r["resource"]["title"] != "t2":
        return False, 'existing resource update failed'
    if s.edit("999", title="x")["ok"]:
        return False, 'unknown resource id was accepted'
    return True, "ok"


def sc_delete(cls, tmp):
    s = new_store(cls, tmp)
    s.add("t1", "https://a.io", None, None)
    if not s.delete("1")["ok"]:
        return False, 'existing resource was not deleted'
    if s.delete("1")["ok"]:
        return False, 'deleting the same resource twice succeeded'
    return True, "ok"


def sc_list_filters(cls, tmp):
    s = new_store(cls, tmp)
    s.add("Alpha", "https://a.io", ["x"], "hello")
    s.add("Beta", "https://b.io", ["y"], "world")
    ids = [r["id"] for r in s.list()]
    if ids != ["1", "2"]:
        return False, f"list returned unexpected resource ids: {ids}"
    if [r["id"] for r in s.list(tag="y")] != ["2"]:
        return False, 'tag filter returned the wrong resource ids'
    if [r["id"] for r in s.list(text="hello")] != ["1"]:
        return False, 'text filter returned the wrong resource ids'
    return True, "ok"


def sc_export_roundtrip(cls, tmp):
    s = new_store(cls, tmp)
    s.add("A", "https://a.io", ["t1"], "n1")
    s.add("B", "https://b.io", ["t2"], "n2")
    ej = s.export("json")
    parsed = json.loads(ej)
    if len(parsed["resources"]) != 2:
        return False, 'JSON export returned the wrong resource count'
    csvtext = s.export("csv")
    if "id,title,url,tags,notes,created_at,updated_at" not in csvtext.splitlines()[0]:
        return False, 'CSV export is missing the required header'
    s2 = new_store(cls, os.path.join(tmp, "rt"))
    os.makedirs(os.path.join(tmp, "rt"), exist_ok=True)
    s2 = new_store(cls, os.path.join(tmp, "rt"))
    imp = s2.import_data(ej, "json", "replace")
    if not imp["ok"]:
        return False, f"JSON round-trip import failed: {imp}"
    if [r["title"] for r in s2.list()] != ["A", "B"]:
        return False, 'JSON round-trip import failed'
    return True, "ok"


def sc_import_merge(cls, tmp):
    s = new_store(cls, tmp)
    s.add("A", "https://a.io", None, None)  # id=1
    payload = json.dumps({"resources": [
        {"id": "1", "title": "A2", "url": "https://a2.io"},
        {"title": "C", "url": "https://c.io"}]})
    r = s.import_data(payload, "json", "merge")
    if not r["ok"] or r.get("updated") != 1 or r.get("added") != 1:
        return False, f"merge returned incorrect added/updated counts: {r}"
    titles = {x["id"]: x["title"] for x in s.list()}
    if titles.get("1") != "A2":
        return False, 'merge returned incorrect added/updated counts'
    return True, "ok"


def sc_import_all_or_nothing(cls, tmp):
    s = new_store(cls, tmp)
    s.add("keep", "https://k.io", None, None)
    before = json.dumps(s.list(), sort_keys=True)
    payload = json.dumps({"resources": [
        {"title": "good", "url": "https://g.io"},
        {"title": "", "url": "bad-url"}]})  # Internal calibration detail.
    r = s.import_data(payload, "json", "merge")
    if r["ok"]:
        return False, 'invalid import was accepted'
    if json.dumps(s.list(), sort_keys=True) != before:
        return False, 'failed import changed the stored data'
    return True, "ok"


def sc_import_dup_ids(cls, tmp):
    s = new_store(cls, tmp)
    payload = json.dumps({"resources": [
        {"id": "5", "title": "a", "url": "https://a.io"},
        {"id": "5", "title": "b", "url": "https://b.io"}]})
    r = s.import_data(payload, "json", "merge")
    if r["ok"] or not any(e.get("code") == "duplicate_in_payload" for e in r.get("errors", [])):
        return False, 'duplicate ids in the import payload were accepted'
    if len(s.list()) != 0:
        return False, 'invalid duplicate-id payload changed the store'
    return True, "ok"


def sc_import_corrupt(cls, tmp):
    s = new_store(cls, tmp)
    r = s.import_data("{ not json", "json", "merge")
    if r["ok"] or not has_err(r, "payload", "parse_error"):
        return False, 'malformed JSON payload was accepted'
    return True, "ok"


def sc_import_csv(cls, tmp):
    s = new_store(cls, tmp)
    csvp = "id,title,url,tags,notes\n7,From CSV,https://c.io,a;b,hi\n"
    r = s.import_data(csvp, "csv", "merge")
    if not r["ok"]:
        return False, f"CSV import failed: {r}"
    got = s.get("7")
    if not got["ok"] or got["resource"]["tags"] != ["a", "b"]:
        return False, 'CSV import failed'
    return True, "ok"


def sc_persistence_reload(cls, tmp):
    p = os.path.join(tmp, "store.json")
    s = cls(p, clock=CLOCK)
    s.add("P", "https://p.io", ["z"], None)
    s2 = cls(p, clock=CLOCK)
    if [r["title"] for r in s2.list()] != ["P"]:
        return False, 'saved resource was not restored after reload'
    return True, "ok"


def sc_corrupt_store_recovery(cls, tmp):
    p = os.path.join(tmp, "store.json")
    os.makedirs(tmp, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write("{ this is not valid json ")
    s = cls(p, clock=CLOCK)
    if not getattr(s, "recovered_from_corrupt", False):
        return False, 'corrupt store was not reported as recovered'
    if len(s.list()) != 0:
        return False, 'recovery did not return an empty resource list'
    if not os.path.isfile(p + ".corrupt"):
        return False, 'corrupt store backup file was not created'
    return True, "ok"


SCENARIOS = [
    ("add_valid", sc_add_valid), ("add_invalid_title", sc_add_invalid_title),
    ("add_invalid_url", sc_add_invalid_url), ("edit", sc_edit), ("delete", sc_delete),
    ("list_filters", sc_list_filters), ("export_roundtrip", sc_export_roundtrip),
    ("import_merge", sc_import_merge), ("import_all_or_nothing", sc_import_all_or_nothing),
    ("import_dup_ids", sc_import_dup_ids), ("import_corrupt", sc_import_corrupt),
    ("import_csv", sc_import_csv), ("persistence_reload", sc_persistence_reload),
    ("corrupt_store_recovery", sc_corrupt_store_recovery),
]


def run_scenarios(impl):
    try:
        cls = load_store_cls(impl)
    except Exception as e:  # Internal calibration detail.
        return {name: (False, f"could not load ResourceStore ({type(e).__name__})") for name, _ in SCENARIOS}
    res = {}
    for name, fn in SCENARIOS:
        tmp = tempfile.mkdtemp(prefix="eng003_")
        try:
            res[name] = fn(cls, tmp)
        except Exception as e:
            res[name] = (False, f"scenario raised {type(e).__name__}: {e}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return res


def http_smoke():
    sys.path.insert(0, HERE)
    import ref_server
    tmp = tempfile.mkdtemp(prefix="eng003_http_")
    try:
        store = ref_server.ResourceStore(os.path.join(tmp, "s.json"), clock=CLOCK)
        srv = ref_server.build_server(store, 0, os.path.join(HERE, "frontend"))
        th = threading.Thread(target=srv.serve_forever, daemon=True)
        th.start()
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        try:
            req = urllib.request.Request(base + "/resources", data=json.dumps({"title": "T", "url": "https://t.io", "tags": ["a"]}).encode(),
                                         headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=5) as resp:
                add = json.loads(resp.read().decode())
                code1 = resp.status
            with urllib.request.urlopen(base + "/resources", timeout=5) as resp:
                lst = json.loads(resp.read().decode())
            with urllib.request.urlopen(base + "/", timeout=5) as resp:
                index = resp.read().decode()
            ok = code1 == 201 and add.get("ok") and len(lst.get("resources", [])) == 1 and "<html" in index.lower()
            return ok, f"POST={code1} list={len(lst.get('resources', []))} index_html={'<' in index}"
        finally:
            srv.shutdown()
            srv.server_close()
    except Exception as e:
        return False, f"HTTP smoke scenario raised {type(e).__name__}: {e}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _print(impl, res):
    npass = sum(1 for ok, _ in res.values() if ok)
    print(f"-- {os.path.basename(impl)}: {npass}/{len(res)} scenarios passed")
    for cid, (ok, d) in res.items():
        print(f"   [{'PASS' if ok else 'FAIL'}] {cid}: {d}")


def self_calibrate():
    allok = True
    print("Resource-manager self-calibration")
    ref = "private/ref_store.py"
    r = run_scenarios(ref)
    _print(ref, r)
    ref_all = all(ok for ok, _ in r.values())
    print("Reference scenarios passed:", ref_all)
    allok &= ref_all

    ok, d = http_smoke()
    print(f"[HTTP reference smoke] {'PASS' if ok else 'FAIL'}: {d}")
    allok &= ok

    for b in ["private/bad_store_novalidation.py", "private/bad_store_import_partial.py", "private/bad_store_empty.py"]:
        res = run_scenarios(b)
        npass = sum(1 for ok2, _ in res.values() if ok2)
        rejected = npass < len(res)
        print(f"{os.path.basename(b)}: {npass}/{len(res)} scenarios; {'REJECTED' if rejected else 'NOT REJECTED'}")
        allok &= rejected

    r2 = run_scenarios(ref)
    rep = {k: v[0] for k, v in r.items()} == {k: v[0] for k, v in r2.items()}
    print("Reference results are repeatable:", rep)
    allok &= rep
    print("RESULT:", "PASS" if allok else "FAIL")
    return 0 if allok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--impl")
    ap.add_argument("--self-calibrate", action="store_true")
    a = ap.parse_args()
    if a.self_calibrate:
        sys.exit(self_calibrate())
    if a.impl:
        res = run_scenarios(a.impl)
        _print(a.impl, res)
        sys.exit(0 if all(ok for ok, _ in res.values()) else 1)
    ap.error("Provide --impl or --self-calibrate.")


if __name__ == "__main__":
    main()
