"""Editing Pass 5 (one-off): chapter banners for the new front-matter headings ("Introduction", "About this project", "Disclosures").

Takes the report's own "EXECUTIVE SUMMARY" banner (word/media/image4.png of the Pass 4 report), erases its lettering by interpolating each row between two clean columns and letters the new title in the same typeface (DejaVu Serif Bold,
white, capitals) at the same size, position and colour. Output: report/working/images/banner_<name>.png (4800 x 864, as the originals). Run once; not part of the pipeline.
"""
import io
import os
import zipfile

import matplotlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "_archive", "report_versions", "final_v1.0_pre_pass5.docx")
OUT = os.path.join(ROOT, "report", "working", "images")
FONT = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf", "DejaVuSerif-Bold.ttf")
TITLES = {"introduction": "INTRODUCTION", "about": "ABOUT THIS PROJECT", "disclosures": "DISCLOSURES", "executive_summary": "EXECUTIVE SUMMARY"}
BOX = (175, 380, 1879, 476)          # lettering box of the original "EXECUTIVE SUMMARY" (x0, y0, x1, y1, measured)


def clean_base():
    z = zipfile.ZipFile(SRC)
    im = Image.open(io.BytesIO(z.read("word/media/image4.png"))).convert("RGB")
    a = np.array(im).astype(float)
    x0, x1 = BOX[0] - 40, BOX[2] + 40
    for y in range(BOX[1] - 25, BOX[3] + 25):
        l, r = a[y, x0 - 6:x0], a[y, x1:x1 + 6]
        lv, rv = l.mean(axis=0), r.mean(axis=0)
        t = np.linspace(0, 1, x1 - x0)[:, None]
        a[y, x0:x1] = lv * (1 - t) + rv * t
    return Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8))


def main():
    base = clean_base()
    # size: the original lettering is 1704 px wide for "EXECUTIVE SUMMARY"
    size = 100
    while True:
        f = ImageFont.truetype(FONT, size)
        w = f.getbbox("EXECUTIVE SUMMARY")[2] - f.getbbox("EXECUTIVE SUMMARY")[0]
        if w >= 1704 or size > 400:
            break
        size += 1
    f = ImageFont.truetype(FONT, size)
    print("font size", size)
    for name, text in TITLES.items():
        im = base.copy()
        d = ImageDraw.Draw(im)
        bb = f.getbbox(text)
        y = BOX[1] + ((BOX[3] - BOX[1]) - (bb[3] - bb[1])) // 2 - bb[1]
        d.text((BOX[0] - bb[0], y), text, font=f, fill=(255, 255, 255))
        im.save(os.path.join(OUT, "banner_%s.png" % name), optimize=True)
        print(name, bb[2] - bb[0])


if __name__ == "__main__":
    main()
