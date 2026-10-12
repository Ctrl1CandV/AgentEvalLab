#!/usr/bin/env python3
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ref_impl as R  # noqa: E402

PKG = os.path.dirname(HERE)
STATES = os.path.join(HERE, "states")

INPUTS = {
    "a.txt": b"alpha\nbeta\n",
    "b.txt": b"one two three\n",
    "sub/c.txt": b"hello world\nfoo\n",
    "empty.txt": b"",
}
CHANGED_B = b"CHANGED content here\n"


def write_input(base, inputs):
    for rel, data in inputs.items():
        p = os.path.join(base, "input", rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(data)


def correct_out(rel, data):
    return R.compute_output(rel, data)


def put_output(base, rel, data_bytes):
    p = os.path.join(base, "output", R.out_rel_for(rel).replace("/", os.sep))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(data_bytes)


def put_journal(base, entries, trailing_raw=None):
    p = os.path.join(base, "journal.jsonl")
    os.makedirs(base, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
        if trailing_raw is not None:
            f.write(trailing_raw)  


def done_entry(rel, data, out_bytes):
    return {"rel_path": rel, "input_sha256": R.sha256_bytes(data),
            "output_sha256": R.sha256_bytes(out_bytes), "status": "done"}


def fresh(name):
    base = os.path.join(STATES, name)
    if os.path.exists(base):
        shutil.rmtree(base)
    os.makedirs(base)
    return base


def build_all():
    
    b = fresh("empty")
    write_input(b, INPUTS)

    
    b = fresh("complete")
    write_input(b, INPUTS)
    entries = []
    for rel, data in sorted(INPUTS.items()):
        ob = correct_out(rel, data)
        put_output(b, rel, ob)
        entries.append(done_entry(rel, data, ob))
    put_journal(b, entries)

    
    b = fresh("missing_output")
    write_input(b, INPUTS)
    entries = []
    for rel, data in sorted(INPUTS.items()):
        ob = correct_out(rel, data)
        if rel != "a.txt":
            put_output(b, rel, ob)
        entries.append(done_entry(rel, data, ob))
    put_journal(b, entries)

    
    b = fresh("corrupt_output")
    write_input(b, INPUTS)
    entries = []
    for rel, data in sorted(INPUTS.items()):
        ob = correct_out(rel, data)
        put_output(b, rel, ob if rel != "b.txt" else b"{\"corrupted\": true}\n")
        entries.append(done_entry(rel, data, ob))
    put_journal(b, entries)

    
    b = fresh("bad_journal")
    write_input(b, INPUTS)
    a = done_entry("a.txt", INPUTS["a.txt"], correct_out("a.txt", INPUTS["a.txt"]))
    bb = done_entry("b.txt", INPUTS["b.txt"], correct_out("b.txt", INPUTS["b.txt"]))
    for rel in ("a.txt", "b.txt", "sub/c.txt"):
        put_output(b, rel, correct_out(rel, INPUTS[rel]))
    truncated = '{"rel_path": "sub/c.txt", "input_sha256": "'  
    put_journal(b, [a, bb], trailing_raw=truncated)

    
    b = fresh("input_changed")
    write_input(b, dict(INPUTS, **{"b.txt": CHANGED_B}))
    entries = []
    for rel, data in sorted(INPUTS.items()):  
        ob = correct_out(rel, data)
        put_output(b, rel, ob)
        entries.append(done_entry(rel, data, ob))
    put_journal(b, entries)

    
    b = fresh("stale_tmp")
    write_input(b, INPUTS)
    tmpdir = os.path.join(b, "output")
    os.makedirs(tmpdir, exist_ok=True)
    with open(os.path.join(tmpdir, "a.txt.json.part"), "wb") as f:
        f.write(b"STALE PARTIAL")  
    put_journal(b, [])

    print("states built:", sorted(os.listdir(STATES)))


if __name__ == "__main__":
    build_all()
