"""One-off image edits for the working copy of the report (Editing Pass 2, 2026-11-14). NOT part of run_all.py; needs Windows fonts and the Pass 1 images.

Title page (report/working/images/title_page_edited.png, from Pass 1) -> title_page_pass2.png:
  * the subtitle is re-lettered "A Behavioral Lifecycle Architecture for Tax Compliance: Evidence from Tanzania" (two lines, same centre, line pitch and colour; Lora Italic, the title page's own font);
  * the note at the foot is re-lettered "Every number is labelled COMPUTED, MODELLED or CITED; sources and scripts: see the repository." (same position, colour, width).
The background is rebuilt row by row from the pixels just left and right of each painted box (the gradient is vertical). The originals are never touched.

Persona pictures (the six cards of the report, each placed twice): the media of report/submission_v1 (image15/17/19/21/24/27.jpg) -> report/working/images/persona_<stage>_pass2.jpg
and persona_<stage>_comparison.png (before | after). Edits (see PERSONA_OPS): every TRA emblem, certificate seal, cap badge and plaque is painted out and replaced by a plain equivalent;
"TRA" in panels and bubbles is re-lettered ("the tax office" in the text panels; "Kodi" in the bubbles, where "the tax office" does not fit); the Seed number ~15M becomes ~16.4M (claims map C070)
and the Entry label (16-25) becomes (16-24). Lora / Lato are not installed: Cambria stands in for the panel text, DejaVu Serif Bold (the card's own number font) for the number,
Calibri for the small caps label, Comic Sans Bold / Arial Narrow Bold for the bubbles.

Run:  python src/tools/edit_pass2_images_once.py
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "report", "working", "images")
FONT_DIR = os.path.join(os.environ.get("WINDIR", ""), "Fonts")
LORA_IT = os.path.join(ROOT, "src", "06_figures", "assets", "fonts", "Lora-Italic[wght].ttf")      # Editing Pass 3: the title page's own fonts
LATO = os.path.join(ROOT, "src", "06_figures", "assets", "fonts", "Lato-Regular.ttf")
SUBTITLE = ["A Behavioral Lifecycle Architecture", "for Tax Compliance: Evidence from Tanzania"]
NOTE = "Every number is labelled COMPUTED, MODELLED or CITED; sources and scripts: see the repository."
GOLD = (249, 168, 37)
NOTE_COLOUR = (153, 185, 155)


def fill_rows(a, x0, y0, x1, y1, band=40, gap=10):
    for y in range(y0, y1):
        left = a[y, max(0, x0 - gap - band):x0 - gap].mean(axis=0)
        right = a[y, x1 + gap:min(a.shape[1], x1 + gap + band)].mean(axis=0)
        t = np.linspace(0, 1, x1 - x0)[:, None]
        a[y, x0:x1] = left * (1 - t) + right * t


def fit_font(path, text, target_w, lo=20, hi=200):
    best = lo
    for s in range(lo, hi):
        f = ImageFont.truetype(path, s)
        if f.getlength(text) <= target_w:
            best = s
        else:
            break
    return ImageFont.truetype(path, best)


def title_page():
    im = Image.open(os.path.join(OUT, "title_page_edited.png")).convert("RGB")
    a = np.array(im).astype(float)
    fill_rows(a, 1380, 1300, 2720, 1500)                      # the old two-line subtitle
    fill_rows(a, 1250, 5140, 2830, 5206)                      # the old note
    out = Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(out)
    # Lora Italic at the size at which "A Behavioral Lifecycle Architecture for" measures 1260 px (the width of that line in the submitted title page)
    size = 60
    for s in range(40, 140):
        f0 = ImageFont.truetype(LORA_IT, s)
        f0.set_variation_by_axes([400])
        if f0.getlength("A Behavioral Lifecycle Architecture for") <= 1260:
            size = s
    f = ImageFont.truetype(LORA_IT, size)
    f.set_variation_by_axes([400])
    cx = 2040
    for i, line in enumerate(SUBTITLE):
        d.text((cx, 1355 + 90 * i), line, font=f, fill=GOLD, anchor="mm")
    fn = fit_font(LATO, NOTE, 1453)
    d.text((cx, 5174), NOTE, font=fn, fill=NOTE_COLOUR, anchor="mm")
    return out


def dashboard_crops():
    """Figures 4.16, 4.21 and 4.26 of the report: crops of the regenerated dashboard screenshots (outputs/figures/dashboard_*.png, made by run_all.py --screenshots)."""
    boxes = {"enterprise": ("fig_4_16_dashboard_enterprise.png", (360, 700, 1340, 1190)), "asset": ("fig_4_21_dashboard_asset.png", (360, 1190, 1340, 1650)),
             "legacy": ("fig_4_26_dashboard_legacy.png", (360, 1180, 1340, 1660))}
    for page, (name, box) in boxes.items():
        Image.open(os.path.join(ROOT, "outputs", "figures", "dashboard_%s.png" % page)).convert("RGB").crop(box).save(os.path.join(OUT, name), optimize=True)
        print("wrote", name)


def main():
    os.makedirs(OUT, exist_ok=True)
    dashboard_crops()
    t = title_page()
    t.save(os.path.join(OUT, "title_page_pass2.png"), optimize=True)
    print("wrote title_page_pass2.png", t.size)


if __name__ == "__main__":
    main()
