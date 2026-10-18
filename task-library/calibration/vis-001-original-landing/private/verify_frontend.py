#!/usr/bin/env python3
"""vis-001 frontend structure and accessibility checks with self-calibration.

Checks that run without a browser: semantic structure, fixed copy, form labels, and WCAG 2.2 contrast.
Responsive layout, long-content rendering, visual quality, and full axe-core scans require a rendering backend and human review (Phase 4), so they remain blocked.
Self-calibration expects the reference frontend to pass and targeted mutations to fail.
Exit code 0 means all calibration expectations pass; 1 means otherwise.
"""
import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
CONTENT = json.load(open(os.path.join(PKG, "public", "content.json"), encoding="utf-8"))
REF = os.path.join(HERE, "frontend")


class Doc(HTMLParser):
    def __init__(self):
        super().__init__()
        self.roles = {}
        self.labels_for = set()
        self.controls = []
        self.has_legend = False
        self.text = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "data-role" in a:
            self.roles[a["data-role"]] = self.roles.get(a["data-role"], 0) + 1
        if tag == "label" and a.get("for"):
            self.labels_for.add(a["for"])
        if tag == "legend":
            self.has_legend = True
        if tag in ("input", "select", "textarea"):
            self.controls.append({"tag": tag, "id": a.get("id"), "name": a.get("name"),
                                   "type": a.get("type"), "required": "required" in a})

    def handle_data(self, data):
        if data.strip():
            self.text.append(data.strip())


def parse_dir(d):
    html = open(os.path.join(d, "index.html"), encoding="utf-8").read()
    doc = Doc()
    doc.feed(html)
    doc.fulltext = "\n".join(doc.text)
    doc.html = html
    css = open(os.path.join(d, "style.css"), encoding="utf-8").read() if os.path.isfile(os.path.join(d, "style.css")) else ""
    js = open(os.path.join(d, "app.js"), encoding="utf-8").read() if os.path.isfile(os.path.join(d, "app.js")) else ""
    return doc, css, js


def palette(css):
    return dict(re.findall(r"(--[a-z\-]+)\s*:\s*(#[0-9A-Fa-f]{6})", css))


def _lin(c):
    c /= 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _lum(hx):
    hx = hx.lstrip("#")
    r, g, b = int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast(h1, h2):
    l1, l2 = sorted([_lum(h1), _lum(h2)], reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def check(d):
    doc, css, js = parse_dir(d)
    pal = palette(css)
    res = {}
    # The markers named in the instruction; "feature" is counted separately below. Version 0.2.0 also required a
    # "feature-list" marker that no public material names, which 0.3.0 removed as a grader defect.
    need_roles = ["nav", "hero", "hero-h1", "cta-primary", "features", "signup-form", "form-state", "footer"]
    miss = [r for r in need_roles if r not in doc.roles]
    res["semantic structure and roles"] = (not miss, f"missing {miss}" if miss else "ok")
    res["at least three features"] = (doc.roles.get("feature", 0) >= 3, f"feature={doc.roles.get('feature',0)}")
    # Fixed copy is checked independently from layout
    required_copy = [CONTENT["brand"], CONTENT["hero"]["h1"], CONTENT["hero"]["sub"],
                     CONTENT["hero"]["cta_primary"], CONTENT["hero"]["cta_secondary"], CONTENT["footer"]]
    for f in CONTENT["features"]:
        required_copy += [f["title"], f["body"]]
    required_copy += [CONTENT["form"]["legend"], CONTENT["form"]["states"]["empty"],
                      CONTENT["form"]["states"]["error"], CONTENT["form"]["states"]["success"]]
    hay = doc.html + "\n" + js + "\n" + doc.fulltext
    miss_copy = [c for c in required_copy if c not in hay]
    res["all fixed copy present"] = (not miss_copy, f"missing {miss_copy[:3]}" if miss_copy else "ok")
    # Form fields and label associations
    by_name = {}
    for c in doc.controls:
        by_name.setdefault(c["name"], []).append(c)
    ok_fields = True
    detail = []
    for fname, ftype in [("title", "text"), ("email", "email")]:
        c = (by_name.get(fname) or [{}])[0]
        if c.get("type") != ftype or not c.get("required") or c.get("id") not in doc.labels_for:
            ok_fields = False; detail.append(fname)
    sel = (by_name.get("district") or [{}])[0]
    if sel.get("tag") != "select" or not sel.get("required") or sel.get("id") not in doc.labels_for:
        ok_fields = False; detail.append("district")
    if not by_name.get("condition") or not doc.has_legend:
        ok_fields = False; detail.append("condition/legend")
    res["form fields and label associations"] = (ok_fields, f"issues {detail}" if detail else "ok")
    # Three visible form states
    res["form states (empty/error/success)"] = (all(s in js for s in ("empty", "error", "success")) and "form-state" in doc.roles,
                                             "app.js must switch all three states and include a form-state element")
    # Contrast
    bad = []
    for req in CONTENT["contrast_requirements"]:
        fa, ba = req["pair"]
        if fa in pal and ba in pal:
            r = contrast(pal[fa], pal[ba])
            if r < req["min"]:
                bad.append(f"{req['role']}:{r:.2f}<{req['min']}")
        else:
            bad.append(f"palette missing {fa}/{ba}")
    res["contrast (WCAG 2.2)"] = (not bad, "; ".join(bad) if bad else "ok")
    return res


def _mutate(src, dst, kind):
    shutil.copytree(src, dst)
    ip = os.path.join(dst, "index.html")
    cp = os.path.join(dst, "style.css")
    html = open(ip, encoding="utf-8").read()
    css = open(cp, encoding="utf-8").read()
    if kind == "missing_features":
        feats = re.findall(r'<li data-role="feature">.*?</li>', html, re.S)
        for f in feats[1:]:
            html = html.replace(f, "", 1)
        open(ip, "w", encoding="utf-8").write(html)
    elif kind == "low_contrast":
        css = css.replace("--muted:#555555", "--muted:#CCCCCC")
        open(cp, "w", encoding="utf-8").write(css)
    elif kind == "unlabeled":
        html = html.replace('<label for="f-email">Email</label>', "<span>Email</span>")
        open(ip, "w", encoding="utf-8").write(html)
    elif kind == "copy_changed":
        html = html.replace(CONTENT["hero"]["cta_primary"], "Sign up now")
        open(ip, "w", encoding="utf-8").write(html)
    return dst


def self_calibrate():
    allok = True
    print("== vis-001 structure and accessibility self-calibration (browser-free checks) ==")
    ref = check(REF)
    npass = sum(1 for ok, _ in ref.values() if ok)
    print(f"-- reference frontend: {npass}/{len(ref)} passed")
    for k, (ok, d) in ref.items():
        print(f"   [{'PASS' if ok else 'FAIL'}] {k}: {d}")
    allok &= (npass == len(ref))
    for kind, expect_fail in [("missing_features", "at least three features"), ("low_contrast", "contrast (WCAG 2.2)"),
                              ("unlabeled", "form fields and label associations"), ("copy_changed", "all fixed copy present")]:
        tmp = tempfile.mkdtemp(prefix="vis001_")
        try:
            d = os.path.join(tmp, "fe")
            _mutate(REF, d, kind)
            r = check(d)
            rejected = not r[expect_fail][0]
            print(f"   [{ 'PASS' if rejected else 'FAIL'}] mutation {kind} → {expect_fail} {'rejected as expected' if rejected else 'not rejected (unexpected)'}")
            allok &= rejected
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    print("RESULT:", "PASS" if allok else "FAIL")
    print("Note: responsive layout, long content, visual quality, and full axe-core checks remain blocked pending a rendering backend and human review (see rubric/calibration).")
    return 0 if allok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frontend")
    ap.add_argument("--self-calibrate", action="store_true")
    a = ap.parse_args()
    if a.self_calibrate:
        sys.exit(self_calibrate())
    if a.frontend:
        r = check(a.frontend)
        for k, (ok, d) in r.items():
            print(f"[{'PASS' if ok else 'FAIL'}] {k}: {d}")
        sys.exit(0 if all(ok for ok, _ in r.values()) else 1)
    ap.error("provide --frontend or --self-calibrate")


if __name__ == "__main__":
    main()



