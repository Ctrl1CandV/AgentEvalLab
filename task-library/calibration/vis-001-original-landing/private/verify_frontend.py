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


# Block-level elements separate text; inline elements (span, em, a, strong, ...) do not, as in a rendered page.
BLOCK_TAGS = {"address", "article", "aside", "blockquote", "br", "dd", "div", "dl", "dt", "fieldset", "figcaption", "figure", "footer",
              "form", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "legend", "li", "main", "nav", "ol", "p", "section", "table",
              "td", "th", "tr", "ul", "option", "label", "button", "select", "textarea", "title", "script", "style"}


class Doc(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.roles = {}
        self.labels_for = set()
        self.controls = []
        self.has_legend = False
        self.text = []
        self.flow = []
        self.label_depth = 0
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "data-role" in a:
            self.roles[a["data-role"]] = self.roles.get(a["data-role"], 0) + 1
        if tag == "label":
            self.label_depth += 1
            if a.get("for"):
                self.labels_for.add(a["for"])
        if tag == "legend":
            self.has_legend = True
        if tag in ("script", "style"):
            self.skip += 1
        if tag in BLOCK_TAGS:
            self.flow.append(" | ")
        if tag in ("input", "select", "textarea"):
            # A control inside a <label> is associated with it, as the instruction allows ("or a wrapping label").
            self.controls.append({"tag": tag, "id": a.get("id"), "name": a.get("name"), "type": a.get("type"),
                                   "wrapped": self.label_depth > 0})

    def handle_endtag(self, tag):
        if tag == "label" and self.label_depth:
            self.label_depth -= 1
        if tag in ("script", "style") and self.skip:
            self.skip -= 1
        if tag in BLOCK_TAGS:
            self.flow.append(" | ")

    def handle_data(self, data):
        if data.strip():
            self.text.append(data.strip())
        if not self.skip:
            self.flow.append(data)

    def rendered_text(self):
        """Text as a page shows it: inline pieces joined, entities decoded, whitespace collapsed; blocks separated."""
        return re.sub(r"\s+", " ", "".join(self.flow))


def parse_dir(d):
    html = open(os.path.join(d, "index.html"), encoding="utf-8").read()
    doc = Doc()
    doc.feed(html)
    doc.fulltext = "\n".join(doc.text)
    doc.rendered = doc.rendered_text()
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
    # Copy counts when it appears as rendered text (inline markup and character entities allowed), anywhere in the raw
    # HTML (for example a data-* attribute that a script displays), or in app.js; 0.3.0 required it contiguous in the
    # raw HTML or in newline-joined text fragments.
    hay = doc.rendered + "\n" + doc.html + "\n" + js
    miss_copy = [c for c in required_copy if c not in hay]
    res["all fixed copy present"] = (not miss_copy, f"missing {miss_copy[:3]}" if miss_copy else "ok")
    # Form fields and label associations
    by_name = {}
    for c in doc.controls:
        by_name.setdefault(c["name"], []).append(c)
    ok_fields = True
    detail = []
    labelled = lambda control: control.get("wrapped") or (control.get("id") is not None and control.get("id") in doc.labels_for)
    # Names and types come from content.json. "Required" is behaviour, checked through the error state; the HTML
    # required attribute is one way to implement it, not a stated requirement, so 0.3.1 no longer demands it.
    for fname, ftype in [("title", "text"), ("email", "email")]:
        c = (by_name.get(fname) or [{}])[0]
        if (c.get("type") or "text") != ftype or not labelled(c):
            ok_fields = False; detail.append(fname)
    sel = (by_name.get("district") or [{}])[0]
    if sel.get("tag") != "select" or not labelled(sel):
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
    elif kind == "low_contrast":
        css = css.replace("--muted:#555555", "--muted:#CCCCCC")
    elif kind == "unlabeled":
        html = html.replace('<label for="f-email">Email</label>', "<span>Email</span>")
    elif kind == "copy_changed":
        html = html.replace(CONTENT["hero"]["cta_primary"], "Sign up now")
    elif kind == "inline_heading":
        html = html.replace("meet its next reader.</h1>", 'meet its <span class="mark">next\n   reader</span>.</h1>')
    elif kind == "linked_footer":
        html = re.sub(r"(<footer[^>]*>).*?(</footer>)", lambda m: m.group(1) + '<p>&#169; 2026 BookLoop &#183; <a href="#r">Rules</a> &middot; '
                      '<a href="#p">Privacy</a> · <a href="#c">Contact</a></p>' + m.group(2), html, flags=re.S)
    elif kind == "wrapping_label":
        html = html.replace('<label for="f-email">Email</label>', "").replace('<input id="f-email" name="email" type="email" required />',
                                                                            '<label>Email <input name="email" type="email" required /></label>')
    elif kind == "no_required_attribute":
        html = html.replace(" required", "")
    # Write both files once, whatever the kind, so no branch can skip its write.
    open(ip, "w", encoding="utf-8").write(html)
    open(cp, "w", encoding="utf-8").write(css)
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
    # Legitimate ways of writing the page that must pass (0.3.1): inline markup inside fixed copy, a footer split into
    # links with character entities, a wrapping label without for/id, and required fields without the HTML attribute.
    for kind in ("inline_heading", "linked_footer", "wrapping_label", "no_required_attribute"):
        tmp = tempfile.mkdtemp(prefix="vis001_")
        try:
            d = os.path.join(tmp, "fe")
            _mutate(REF, d, kind)
            r = check(d)
            accepted = all(ok for ok, _ in r.values())
            print(f"   [{'PASS' if accepted else 'FAIL'}] variant {kind} accepted" + ("" if accepted else f": {[k for k, (ok, _) in r.items() if not ok]}"))
            allok &= accepted
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    print("RESULT:", "PASS" if allok else "FAIL")
    print("Note: rendered checks and visual quality belong to the judging step (scripts/judge-visual.ts), not to these browser-free checks.")
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



