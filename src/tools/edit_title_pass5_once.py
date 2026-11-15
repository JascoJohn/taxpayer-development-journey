"""Editing Pass 5 (one-off): the cover (green title page) of the report, report/working/images/title_page_pass2.png -> title_page_pass5.png (and a before / after sheet).

Re-letters two lines of the author block, in the title page's own sans-serif (Lato Regular, src/06_figures/assets/fonts), same centre, size and colour:
  * the credentials line becomes "MBA, CPA(T) | jasco.john98@gmail.com | +255 759 003 950 | ORCID 0009-0007-3630-7943" (the telephone is added, the ORCID is given as the bare identifier);
  * the year line "2026" becomes "November 2026" (the report date).
The background is rebuilt row by row from the pixels just left and right of each painted box (as in edit_pass2_images_once.py). Run once; not part of the pipeline.
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "report", "working", "images")
LATO = os.path.join(ROOT, "src", "06_figures", "assets", "fonts", "Lato-Regular.ttf")
OLD_LINE = "MBA, CPA(T)  |  jasco.john98@gmail.com  |  ORCID https://orcid.org/0009-0007-3630-7943"
NEW_LINE = "MBA, CPA(T)  |  jasco.john98@gmail.com  |  +255 759 003 950  |  ORCID 0009-0007-3630-7943"


def fill_rows(a, x0, y0, x1, y1, band=40, gap=10):
    for y in range(y0, y1):
        left = a[y, max(0, x0 - gap - band):x0 - gap].mean(axis=0)
        right = a[y, x1 + gap:min(a.shape[1], x1 + gap + band)].mean(axis=0)
        t = np.linspace(0, 1, x1 - x0)[:, None]
        a[y, x0:x1] = left * (1 - t) + right * t


def font_for_width(text, width):
    best = 20
    for s in range(20, 200):
        if ImageFont.truetype(LATO, s).getlength(text) <= width:
            best = s
        else:
            break
    return ImageFont.truetype(LATO, best)


def main():
    src = Image.open(os.path.join(OUT, "title_page_pass2.png")).convert("RGB")
    a = np.array(src).astype(float)
    colour = tuple(int(v) for v in np.array(src)[3644:3698, 966:3115].reshape(-1, 3)[np.array(src)[3644:3698, 966:3115].reshape(-1, 3).sum(axis=1).argmax()])
    fill_rows(a, 900, 3630, 3200, 3712)                       # the old credentials line (x 966-3114, y 3644-3697)
    fill_rows(a, 1900, 3722, 2200, 3810)                      # the old year (x 1958-2141, y 3736-3795)
    out = Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(out)
    f_line = font_for_width(OLD_LINE, 2148)                   # the old line was 2148 px wide
    d.text((2040, 3670), NEW_LINE, font=f_line, fill=colour, anchor="mm")
    f_year = font_for_width("2026", 183)
    d.text((2040, 3765), "November 2026", font=f_year, fill=colour, anchor="mm")
    out.save(os.path.join(OUT, "title_page_pass5.png"), optimize=True)
    crop_box = (700, 3420, 3380, 3860)
    sheet = Image.new("RGB", (crop_box[2] - crop_box[0], 2 * (crop_box[3] - crop_box[1]) + 20), "white")
    sheet.paste(src.crop(crop_box), (0, 0))
    sheet.paste(out.crop(crop_box), (0, crop_box[3] - crop_box[1] + 20))
    sheet.save(os.path.join(OUT, "title_page_pass5_comparison.png"))
    print("wrote title_page_pass5.png", out.size, "line font", f_line.size, "year font", f_year.size, "colour", colour)


if __name__ == "__main__":
    main()
