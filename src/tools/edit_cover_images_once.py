"""One-off image edits for the working copy of the report (Editing Pass 1, 2026-11-13). NOT part of run_all.py; needs the report in report/submission_v1/ and Windows fonts.

Reads the two full-page images of the submitted report (cover poster = media/image1.png, title page = media/image2.png of the docx) and writes edited copies to
report/working/images/ (the originals are never touched):
  * cover poster: paints out the "[competition banner]" banner (top right) and the "SUBMITTED BY ... phone number" block (bottom strip) with the surrounding background,
    and sets the author line in the strip;
  * title page: paints out the two banner lines ("[competition banner lines]") and the phone number with the surrounding gradient, restores the faint network
    line that crosses the banner, and sets "MBA, CPA(T) | email | ORCID" under the (unchanged) author name.
The background is rebuilt row by row by interpolating between the pixels just left and right of each painted box (the gradient is vertical, so rows are what matter).

Run:  python src/tools/edit_cover_images_once.py
"""
import io
import os
import zipfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOCX = os.path.join(ROOT, "report", "submission_v1", "Taxpayer_Development_Journey_submission_v1.docx")
OUT = os.path.join(ROOT, "report", "working", "images")
AUTHOR_LINE = "Jasco John, MBA, CPA(T)  |  jasco.john98@gmail.com  |  ORCID https://orcid.org/0009-0007-3630-7943"
TITLE_LINE = "MBA, CPA(T)  |  jasco.john98@gmail.com  |  ORCID https://orcid.org/0009-0007-3630-7943"
FONT_DIR = os.path.join(os.environ.get("WINDIR", ""), "Fonts")


def fill_rows(a, x0, y0, x1, y1, band=24, gap=6, left_only=False):
    """Paints the box [x0,x1) x [y0,y1) with, per row, a linear blend of the mean colours of the `band` columns just left and just right of the box."""
    for y in range(y0, y1):
        left = a[y, max(0, x0 - gap - band):x0 - gap].mean(axis=0)
        right = left if left_only or x1 + gap >= a.shape[1] else a[y, x1 + gap:min(a.shape[1], x1 + gap + band)].mean(axis=0)
        t = np.linspace(0, 1, x1 - x0)[:, None]
        a[y, x0:x1] = left * (1 - t) + right * t


def centered_text(img, text, cx, cy, font, fill):
    d = ImageDraw.Draw(img)
    w = d.textlength(text, font=font)
    d.text((cx - w / 2, cy), text, font=font, fill=fill, anchor="lm")


def cover(raw):
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    a = np.array(im).astype(float)
    fill_rows(a, 812, 10, 1046, 38, left_only=True)      # (the right neighbour is the poster's border line)                                    # "[competition banner]"
    fill_rows(a, 60, 1450, 640, 1490)                                  # person icon, "SUBMITTED BY Jasco John", separator, phone icon and number
    out = Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8))
    font = ImageFont.truetype(os.path.join(FONT_DIR, "arial.ttf"), 17)
    centered_text(out, AUTHOR_LINE, 527, 1469, font, (34, 34, 34))
    return out


def title(raw):
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    a = np.array(im).astype(float)
    # the faint network line that crosses the banner: find it just above and below the box, redraw it through the box
    def peak_x(y, lo=1750, hi=2350):
        row = a[y, lo:hi].sum(axis=1)
        return lo + int(np.argmax(row)), a[y, lo + int(np.argmax(row))].copy()
    top_x, col_top = peak_x(488)
    bot_x, col_bot = peak_x(676)
    fill_rows(a, 1400, 495, 2680, 668, band=40, gap=10)                 # banner lines
    fill_rows(a, 1670, 3612, 2430, 3712, band=40, gap=10)               # phone number
    out = Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8))
    # redraw the line through the banner box at 4x and blend (anti-aliased)
    S = 4
    layer = Image.new("L", (out.width, 200 * S), 0)
    ImageDraw.Draw(layer).line([(top_x * S, (495 - 480) * S), (bot_x * S, (668 - 480) * S)], fill=255, width=3 * S)
    mask = layer.resize((out.width, 200), Image.LANCZOS)
    box = out.crop((0, 480, out.width, 680))
    colour = Image.new("RGB", box.size, tuple(int(v) for v in (col_top + col_bot) / 2))
    box.paste(colour, (0, 0), mask)
    out.paste(box, (0, 480))
    font = ImageFont.truetype(os.path.join(FONT_DIR, "segoeui.ttf"), 54)
    centered_text(out, TITLE_LINE, 2040, 3662, font, (238, 241, 236))
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    with zipfile.ZipFile(DOCX) as z:
        c = cover(z.read("word/media/image1.png"))
        t = title(z.read("word/media/image2.png"))
    c.save(os.path.join(OUT, "cover_poster_edited.png"), optimize=True)
    t.save(os.path.join(OUT, "title_page_edited.png"), optimize=True)
    print("wrote", os.path.join(OUT, "cover_poster_edited.png"), c.size, "and title_page_edited.png", t.size)


if __name__ == "__main__":
    main()
