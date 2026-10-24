#!/usr/bin/env python3
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
CAL = os.path.abspath(os.path.join(HERE, "..", "..", "..", "retired", "vis-001-original-landing", "private", "frontend"))
VAR = os.path.join(HERE, "variants")


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def copy_frontend(dst):
    if os.path.exists(dst):
        shutil.rmtree(dst)
    os.makedirs(dst)
    for fn in ("index.html", "style.css", "app.js"):
        with open(os.path.join(dst, fn), "w", encoding="utf-8", newline="\n") as f:
            f.write(read(os.path.join(CAL, fn)))


def build_wrapping_label():
    dst = os.path.join(VAR, "wrapping_label")
    copy_frontend(dst)
    p = os.path.join(dst, "index.html")
    h = read(p)
    # Internal calibration detail.
    h = h.replace('<label for="f-email">Email</label>', "<label>Email")
    h = h.replace('<input id="f-email" name="email" type="email" required />',
                  '<input id="f-email" name="email" type="email" required /></label>')
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(h)
    return dst


def build_palette_ok_low_contrast():
    dst = os.path.join(VAR, "palette_ok_low_contrast")
    copy_frontend(dst)
    p = os.path.join(dst, "style.css")
    css = read(p)
    # Internal calibration detail.
    css += "\n/* Deliberately reduce hero subtitle contrast for the negative case. */\n"
    css += '[data-role="hero-sub"]{ color:#DDDDDD !important; }\n'
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(css)
    return dst


if __name__ == "__main__":
    print("CAL frontend exists:", os.path.isdir(CAL))
    for b in (build_wrapping_label, build_palette_ok_low_contrast):
        print("built:", os.path.relpath(b(), HERE))
