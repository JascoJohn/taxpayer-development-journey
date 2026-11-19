"""Pass 6B-2 (one-off): chapter banners for the retitled Section 4.5, the retitled Chapter 5 and the new Chapter 7.

The report's banners are baked pictures (4800 x 864): a large gold chapter number and a white serif title. Each new banner starts from the existing banner of the same chapter, erases the old title (and, for Chapter 7, the old digit) by interpolating each row
between two clean columns, and letters the new title in the same typeface (DejaVu Serif Bold) at the size that reproduces the original lettering. Output: report/working/images/banner_<name>.png. Run once; not part of the pipeline.
"""
import io
import os
import sys
import zipfile

import matplotlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "report", "working", "Taxpayer_Development_Journey_working_v6.docx")
OUT = os.path.join(ROOT, "report", "working", "images")
FONT = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf", "DejaVuSerif-Bold.ttf")


def load(name):
    z = zipfile.ZipFile(SRC)
    return Image.open(io.BytesIO(z.read("word/media/%s.png" % name))).convert("RGB")


def masks(a, gold_xmax):
    white = (a.min(axis=2) > 225)
    gold = (a[:, :, 0] > 190) & (a[:, :, 1] > 130) & (a[:, :, 2] < 100)
    gold[780:, :] = False                       # the gold rule along the bottom edge
    gold[:, gold_xmax:] = False                 # the chapter number only (anti-aliased lettering edges look gold-ish)
    white[:, :40] = False
    return white, gold


def bbox(m, x0=0, x1=None):
    x1 = x1 or m.shape[1]
    sub = m[:, x0:x1]
    ys, xs = np.where(sub)
    return xs.min() + x0, ys.min(), xs.max() + x0, ys.max()


def erase(a, box, pad=30):
    x0, y0, x1, y1 = box
    x0, x1 = max(x0 - pad, 8), min(x1 + pad, a.shape[1] - 8)
    for y in range(max(y0 - pad, 0), min(y1 + pad, a.shape[0] - 12)):
        lv, rv = a[y, x0 - 6:x0].mean(axis=0), a[y, x1:x1 + 6].mean(axis=0)
        t = np.linspace(0, 1, x1 - x0)[:, None]
        a[y, x0:x1] = lv * (1 - t) + rv * t
    return a


def font_for(width, text):
    size = 60
    while True:
        f = ImageFont.truetype(FONT, size)
        bb = f.getbbox(text)
        if bb[2] - bb[0] >= width or size > 400:
            return f, size
        size += 1


def main():
    os.makedirs(OUT, exist_ok=True)
    # ---- Chapter 5 (one-line title) and Chapter 7 (same base, digit replaced)
    base = load("image38")
    a = np.array(base).astype(float)
    white, gold = masks(a, 500)
    gx0, gy0, gx1, gy1 = bbox(gold)
    wx0, wy0, wx1, wy1 = bbox(white, gx1 + 20)
    print("ch5 digit", (gx0, gy0, gx1, gy1), "title", (wx0, wy0, wx1, wy1))
    f, size = font_for(wx1 - wx0, "Portfolio-Level Impact")
    gold_rgb = tuple(int(v) for v in a[gold].mean(axis=0))
    print("font size", size, "gold", gold_rgb)
    erased = erase(a.copy(), (wx0, wy0, wx1, wy1))
    img5 = Image.fromarray(np.clip(erased + .5, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img5)
    ref = f.getbbox("Portfolio-Level Impact")
    title_cap_top = wy0   # keep the original baseline: the top of the original lettering
    for name, text, img in (("ch5", "Evidence and Portfolio Impact", img5),):
        d = ImageDraw.Draw(img)
        bb = f.getbbox(text)
        d.text((wx0 - bb[0], wy0 - ref[1]), text, font=f, fill=(255, 255, 255))
        img.save(os.path.join(OUT, "banner_%s_6b2.png" % name), optimize=True)
        print(name, "width", bb[2] - bb[0])
    # chapter 7: erase digit too, letter a gold 7 of the same height
    erased7 = erase(erase(a.copy(), (wx0, wy0, wx1, wy1)), (gx0, gy0, gx1, gy1), pad=16)
    img7 = Image.fromarray(np.clip(erased7 + .5, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img7)
    digit_h = gy1 - gy0
    fd, dsize = font_for(0, "5")
    s = 100
    while True:
        fd = ImageFont.truetype(FONT, s)
        bb = fd.getbbox("7")
        if bb[3] - bb[1] >= digit_h or s > 800:
            break
        s += 1
    bb = fd.getbbox("7")
    d.text((gx0 - bb[0], gy0 - bb[1]), "7", font=fd, fill=gold_rgb)
    bt = f.getbbox("From Prototype to Pilot")
    d.text((wx0 - bt[0], wy0 - ref[1]), "From Prototype to Pilot", font=f, fill=(255, 255, 255))
    img7.save(os.path.join(OUT, "banner_ch7_6b2.png"), optimize=True)
    # ---- Section 4.5 (two-line title)
    base = load("image32")
    a = np.array(base).astype(float)
    white, gold = masks(a, 860)
    gx0, gy0, gx1, gy1 = bbox(gold)
    wx0, wy0, wx1, wy1 = bbox(white, gx1 + 20)
    print("4.5 digit", (gx0, gy0, gx1, gy1), "title", (wx0, wy0, wx1, wy1))
    f45, size45 = font_for(wx1 - wx0 if False else 0, "x")
    # calibrate on the original first line "Asset Stage: Owners the State"
    rows = white[:, wx0:wx1].any(axis=1)
    ys = np.where(rows)[0]
    gaps = np.where(np.diff(ys) > 10)[0]
    line1_end = ys[gaps[0]] if len(gaps) else ys.max()
    l1 = white[wy0:line1_end + 1, wx0:wx1]
    xs = np.where(l1.any(axis=0))[0]
    w1 = xs.max() - xs.min()
    f45, size45 = font_for(w1, "Asset Stage: Owners the State")
    print("4.5 font", size45, "line1 w", w1, "line 2 starts after", line1_end)
    erased = erase(a.copy(), (wx0, wy0, wx1, wy1))
    img = Image.fromarray(np.clip(erased + .5, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    ref = f45.getbbox("Asset Stage: Owners the State")
    # second line top: top of the original second line
    rows2 = np.where(white[line1_end + 1:, wx0:wx1].any(axis=1))[0]
    y2 = line1_end + 1 + rows2.min()
    ref2 = f45.getbbox("Cannot See")
    d.text((wx0 - ref[0], wy0 - ref[1]), "Asset Stage: Making Ownership", font=f45, fill=(255, 255, 255))
    d.text((wx0 - ref2[0], y2 - ref2[1]), "Visible and Valuable", font=f45, fill=(255, 255, 255))
    img.save(os.path.join(OUT, "banner_4_5_6b2.png"), optimize=True)
    print("done")


if __name__ == "__main__":
    main()
