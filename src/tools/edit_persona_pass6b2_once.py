"""One-off edit of two persona pictures (Pass 6B-2, Figures 4.10 and 4.14): only the NUMBER changes, in the style the cards already use (Pass 2/3 script edit_persona_pass2_once.py).
NOT part of run_all.py. Active card: 12.1M -> 2.92M (claim C072); Enterprise card: 3.49M -> 0.57M (claim C073), the Active and Enterprise populations of stage mapping B.
Reads report/working/images/persona_active_pass2.jpg and persona_enterprise_pass2.jpg (kept untouched; copies of the originals are in _archive/report_versions/personas_before_6b2/),
writes report/working/images/persona_active_6b2.jpg and persona_enterprise_6b2.jpg and a before | after comparison. The number is read from outputs/tables/tin_by_segment.csv.
Run:  python src/tools/edit_persona_pass6b2_once.py
"""
import csv
import os
import shutil

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IMG = os.path.join(ROOT, "report", "working", "images")
BEFORE = os.path.join(ROOT, "_archive", "report_versions", "personas_before_6b2")
import matplotlib  # noqa: E402
DEJAVU_B = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf", "DejaVuSerif-Bold.ttf")
GREEN = (46, 125, 50)


def population_m(segment):
    with open(os.path.join(ROOT, "outputs", "tables", "tin_by_segment.csv"), encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["segment"] == segment:
                return float(r["population_weighted"]) / 1e6
    raise KeyError(segment)


def repaint(src, dst, text):
    a = np.array(Image.open(src).convert("RGB"), dtype=float)
    a[1190:1275, 400:800] = 255                                          # the number band of the card (white background)
    im = Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8)).convert("RGBA")
    font = ImageFont.truetype(DEJAVU_B, 88)
    d = ImageDraw.Draw(im)
    d.text((600, 1232), text, font=font, fill=GREEN, anchor="mm")
    im.convert("RGB").save(dst, quality=95)


def main():
    os.makedirs(BEFORE, exist_ok=True)
    for stage, seg, fmt in (("active", "active", "%.2fM"), ("enterprise", "enterprise", "%.2fM")):
        src = os.path.join(IMG, "persona_%s_pass2.jpg" % stage)
        keep = os.path.join(BEFORE, "persona_%s_pass2.jpg" % stage)
        if not os.path.exists(keep):
            shutil.copy2(src, keep)
        dst = os.path.join(IMG, "persona_%s_6b2.jpg" % stage)
        repaint(keep, dst, fmt % population_m(seg))
        b, a2 = Image.open(keep).convert("RGB"), Image.open(dst).convert("RGB")
        cmp_ = Image.new("RGB", (b.width * 2 + 20, b.height), "white")
        cmp_.paste(b, (0, 0))
        cmp_.paste(a2, (b.width + 20, 0))
        cmp_.save(os.path.join(IMG, "persona_%s_6b2_comparison.png" % stage))
        print(stage, fmt % population_m(seg), "->", dst)


if __name__ == "__main__":
    main()
