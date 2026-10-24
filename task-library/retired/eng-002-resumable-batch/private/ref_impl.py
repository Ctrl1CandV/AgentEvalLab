#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import sys

TMP_SUFFIX = ".part"


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_output(rel, data):
    text = data.decode("utf-8", errors="replace")
    obj = {
        "rel_path": rel,
        "input_sha256": sha256_bytes(data),
        "bytes": len(data),
        "lines": text.count("\n"),
        "words": len(text.split()),
    }
    return (json.dumps(obj, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def out_rel_for(rel):
    return rel.replace("\\", "/") + ".json"


def load_journal(path):
    entries = {}
    if not os.path.isfile(path):
        return entries
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue  
            if isinstance(e, dict) and e.get("status") == "done" and "rel_path" in e:
                entries[e["rel_path"]] = e
    return entries


def append_journal(path, entry):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    
    
    need_nl = False
    if os.path.isfile(path) and os.path.getsize(path) > 0:
        with open(path, "rb") as f:
            f.seek(-1, os.SEEK_END)
            need_nl = f.read(1) != b"\n"
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        if need_nl:
            f.write("\n")
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def needs_processing(rel, out_path, input_sha, journal):
    e = journal.get(rel)
    if not e:
        return True
    if e.get("input_sha256") != input_sha:
        return True
    if not os.path.isfile(out_path):
        return True
    if sha256_file(out_path) != e.get("output_sha256"):
        return True
    return False


def publish(out_path, data):
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    tmp = out_path + TMP_SUFFIX
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, out_path)
    return sha256_bytes(data)


def list_inputs(input_dir):
    rels = []
    for root, _dirs, files in os.walk(input_dir):
        for name in files:
            full = os.path.join(root, name)
            if os.path.islink(full):
                continue  
            rels.append(os.path.relpath(full, input_dir).replace("\\", "/"))
    return sorted(rels)


def _crash_point(spec, ctx):
    ee = os.environ.get("EE_CRASH")
    if not ee or spec != ee.split(":", 1)[0]:
        return
    arg = ee.split(":", 1)[1] if ":" in ee else ""
    if spec == "before_journal" and arg == ctx["rel"]:
        raise RuntimeError(f"EE_CRASH before_journal:{arg}")
    if spec == "stale_temp" and arg == ctx["rel"]:
        raise RuntimeError(f"EE_CRASH stale_temp:{arg}")


def run(input_dir, output_dir, journal_path):
    if not os.path.isdir(input_dir):
        print(json.dumps({"error": {"code": "usage", "message": "input-dir not found"}}))
        return 2
    os.makedirs(output_dir, exist_ok=True)
    journal = load_journal(journal_path)
    rels = list_inputs(input_dir)
    processed = skipped = errors = 0
    n = 0
    for rel in rels:
        in_path = os.path.join(input_dir, rel.replace("/", os.sep))
        out_rel = out_rel_for(rel)
        out_path = os.path.join(output_dir, out_rel.replace("/", os.sep))
        try:
            with open(in_path, "rb") as f:
                data = f.read()
        except OSError as e:
            print(json.dumps({"action": "error", "rel_path": rel, "error": str(e)}, ensure_ascii=False))
            errors += 1
            continue
        input_sha = sha256_bytes(data)
        if not needs_processing(rel, out_path, input_sha, journal):
            print(json.dumps({"action": "skipped", "rel_path": rel}, ensure_ascii=False))
            skipped += 1
            continue
        
        out_data = compute_output(rel, data)
        ee = os.environ.get("EE_CRASH", "")
        if ee.startswith("after_n:") and n >= int(ee.split(":", 1)[1]):
            raise RuntimeError(f"EE_CRASH {ee}")
        if ee == f"stale_temp:{rel}":
            tmp = out_path + TMP_SUFFIX
            os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
            with open(tmp, "wb") as f:
                f.write(out_data)
            raise RuntimeError(f"EE_CRASH stale_temp:{rel}")  
        out_sha = publish(out_path, out_data)
        _crash_point("before_journal", {"rel": rel})  
        append_journal(journal_path, {"rel_path": rel, "input_sha256": input_sha,
                                      "output_sha256": out_sha, "status": "done"})
        journal[rel] = {"rel_path": rel, "input_sha256": input_sha, "output_sha256": out_sha, "status": "done"}
        print(json.dumps({"action": "processed", "rel_path": rel}, ensure_ascii=False))
        processed += 1
        n += 1
    print(json.dumps({"summary": {"processed": processed, "skipped": skipped, "errors": errors, "total": len(rels)}}, ensure_ascii=False))
    return 1 if errors else 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-dir", required=True)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--journal", required=True)
    a = ap.parse_args(argv)
    return run(a.input_dir, a.output_dir, a.journal)


if __name__ == "__main__":
    sys.exit(main())
