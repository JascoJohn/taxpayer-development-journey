"""One-off edits of the six persona pictures of the report (Editing Pass 2, S1.4). NOT part of run_all.py; needs report/submission_v1 and Windows fonts.

Reads image15/17/19/21/24/27.jpg (Amina, Juma, Neema, Asha, Joseph, Mzee) from the submitted docx (never modified), writes report/working/images/persona_<stage>_pass2.jpg and
persona_<stage>_comparison.png (before | after). Every TRA emblem, seal, cap badge and plaque is painted out and replaced by a plain equivalent; "TRA" in the text panels becomes "the tax office"
(the panel is re-set in full, wrapped to the panel width: the original wrapped at half the panel and its last line left the panel); "TRA" in speech bubbles and on the tiny wall / book / clipboard
labels is re-lettered where the background is plain enough ("Kodi" in the bubbles: "the tax office" does not fit; "TAX" on the labels); the Seed number ~15M becomes ~16.4M (claims map C070) and the
Entry label (16-25) becomes (16-24). Fonts (Pass 3): Lora (panel text) and Lato (small caps label), the cards' own fonts; DejaVu Serif Bold for the number (the card's own number font); Comic Sans Bold
and Arial Narrow Bold only where the original lettering is not Lora / Lato (bubbles, certificates).

Run:  python src/tools/edit_persona_pass2_once.py
"""
import io
import math
import os
import zipfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOCX = os.path.join(ROOT, "report", "submission_v1", "Taxpayer_Development_Journey_submission_v1.docx")
OUT = os.path.join(ROOT, "report", "working", "images")
FD = os.path.join(os.environ.get("WINDIR", ""), "Fonts")
import matplotlib  # noqa: E402
DEJAVU_B = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf", "DejaVuSerif-Bold.ttf")
FONTS = os.path.join(ROOT, "src", "06_figures", "assets", "fonts")
LORA = os.path.join(FONTS, "Lora[wght].ttf")                 # Editing Pass 3: the cards' own fonts
LATO = os.path.join(FONTS, "Lato-Regular.ttf")
INK = (52, 63, 74)
PANEL = (244, 246, 250)
SOURCES = {"seed": "image15.jpg", "entry": "image17.jpg", "active": "image19.jpg", "enterprise": "image21.jpg", "asset": "image24.jpg", "legacy": "image27.jpg"}
PANEL_TEXT = {
    "seed": "May complete her entire childhood without one meaningful interaction with the tax office. Her first encounter is likely a legal obligation, not a relationship.",
    "entry": "Uses mobile money daily to run his business, yet has never interacted with the tax office. Not avoiding it \u2014 to the tax office he simply doesn't exist yet: no TIN, no record.",
    "active": "Accepts tax is part of doing business, but her turnover is estimated by an officer's judgement \u2014 leaving her unsure if the assessment is fair.",
    "enterprise": "Already registered and licensed, but her relationship with the tax office still feels transactional \u2014 filing returns is a chore, not a milestone that recognizes her progress.",
    "asset": "Owns a rental property and a commercial vehicle generating real income, but declaring them seems to benefit only the tax office \u2014 the advantage to him is unclear.",
    "legacy": "A lifetime of tax compliance ends at retirement or death, with nothing carried forward \u2014 his successor starts from zero, and decades of trust with the tax office vanish.",
}


# ---------------------------------------------------------------- pixel helpers
def paint_rows(a, x0, y0, x1, y1, band=8, gap=2):
    """Per row, a linear blend of the mean colours just left and right of the box (plain backgrounds: paper, bubbles, plaques)."""
    for y in range(y0, y1):
        left = a[y, max(0, x0 - gap - band):x0 - gap].mean(axis=0)
        right = a[y, x1 + gap:x1 + gap + band].mean(axis=0)
        t = np.linspace(0, 1, x1 - x0)[:, None]
        a[y, x0:x1] = left * (1 - t) + right * t


def erase_dark(a, x0, y0, x1, y1, thr=200, grow=3, iters=250, max_area=30000):
    """Removes the dark lettering inside the box [x0,x1) x [y0,y1) of a plain bubble. The dark pixels of a larger window are labelled; a component is lettering only if it lies
    entirely inside the box (the bubble outline is one big component reaching outside it and is left alone). Lettering, grown by `grow` pixels, is filled by
    diffusing the surrounding bubble colour into it."""
    from scipy import ndimage
    wy0, wy1, wx0, wx1 = max(0, y0 - 80), min(a.shape[0], y1 + 100), max(0, x0 - 120), min(a.shape[1], x1 + 120)
    dark = a[wy0:wy1, wx0:wx1].mean(axis=2) < thr
    lab, n = ndimage.label(dark)
    m = np.zeros(a.shape[:2], bool)
    for k, sl in enumerate(ndimage.find_objects(lab), 1):
        ys, xs = sl
        if ys.start + wy0 >= y0 and ys.stop + wy0 <= y1 and xs.start + wx0 >= x0 and xs.stop + wx0 <= x1:
            comp = lab[sl] == k
            if 100 <= comp.sum() < max_area:          # tiny fragments are the shaded rim of the bubble, not lettering
                m[sl[0].start + wy0:sl[0].stop + wy0, sl[1].start + wx0:sl[1].stop + wx0] |= comp
    for _ in range(grow):
        p = np.pad(m, 1)
        m = m | p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]
    return diffuse(a, m, iters)


def diffuse(a, mask, iters=400):
    """Fills the masked pixels from their surroundings (iterated 4-neighbour averaging): textured backgrounds (leather, wood)."""
    a = a.copy()
    m = mask.astype(bool)
    ys, xs = np.where(m)
    y0, y1, x0, x1 = max(ys.min() - 2, 0), ys.max() + 3, max(xs.min() - 2, 0), xs.max() + 3
    sub = a[y0:y1, x0:x1]
    mm = m[y0:y1, x0:x1]
    bright = sub[~mm][sub[~mm].mean(axis=1) > 180]
    sub[mm] = np.median(bright, axis=0) if len(bright) > 20 else sub[~mm].mean(axis=0)
    for _ in range(iters):
        p = np.pad(sub, ((1, 1), (1, 1), (0, 0)), mode="edge")
        avg = (p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:]) / 4.0
        sub[mm] = avg[mm]
    a[y0:y1, x0:x1] = sub
    return a


def text_layer(size, text, font, fill, angle=0.0, spacing=0):
    d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    w = int(d.textlength(text, font=font)) + 40
    h = int(font.size * 1.6) + 20
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((w // 2, h // 2), text, font=font, fill=fill, anchor="mm")
    if angle:
        layer = layer.rotate(angle, resample=Image.BICUBIC, expand=True)
    return layer


def put(img, layer, cx, cy):
    img.alpha_composite(layer, (int(cx - layer.width / 2), int(cy - layer.height / 2)))


def draw_text(img, text, cx, cy, font_path, size, fill, angle=0.0, index=0):
    font = ImageFont.truetype(font_path, size, index=index) if font_path.endswith(".ttc") else ImageFont.truetype(font_path, size)
    put(img, text_layer(None, text, font, fill, angle), cx, cy)


def disc(img, cx, cy, r, fill, ring=None):
    s = 4
    layer = Image.new("RGBA", (int(2 * r * s) + 8 * s, int(2 * r * s) + 8 * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    c = layer.width / 2
    if ring:
        d.ellipse((c - r * s, c - r * s, c + r * s, c + r * s), fill=ring)
        r2 = r - 1.6
        d.ellipse((c - r2 * s, c - r2 * s, c + r2 * s, c + r2 * s), fill=fill)
    else:
        d.ellipse((c - r * s, c - r * s, c + r * s, c + r * s), fill=fill)
    layer = layer.resize((layer.width // s, layer.height // s), Image.LANCZOS)
    put(img, layer, cx, cy)


# ---------------------------------------------------------------- panel and number
def panel(img, a, text):
    """Re-sets the body of the 'THE CHALLENGE' panel (the heading above stays)."""
    a[1432:1642, 64:1136] = PANEL                       # inside the panel
    a[1642:1668, 64:1136] = 255                         # the old last line ran out below the panel
    im = Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8)).convert("RGBA")
    # keep the panel's lower edge: redraw the rounded bottom by pasting back the original rows 1640-1646 is not needed (flat colours), but restore corners
    font = ImageFont.truetype(LORA, 29)
    font.set_variation_by_axes([400])
    d = ImageDraw.Draw(im)
    words, lines, cur = text.split(" "), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if d.textlength(trial, font=font) <= 925:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    y = 1470
    for ln in lines:
        d.text((102, y), ln, font=font, fill=INK, anchor="lm")
        y += 43
    return im


def number_seed(img, a):
    a[1190:1275, 440:760] = 255
    im = Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8)).convert("RGBA")
    draw_text(im, "~16.4M", 600, 1232, DEJAVU_B, 88, (46, 125, 50))
    return im


def label_entry(img, a):
    a[1282:1318, 395:810] = 255
    im = Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8)).convert("RGBA")
    f = ImageFont.truetype(LATO, 25)
    txt = "YOUNG PEOPLE (16\u201324) LIKE JUMA"
    track = 1.9
    total = sum(f.getlength(c) + track for c in txt) - track
    x = 600 - total / 2
    d = ImageDraw.Draw(im)
    for c in txt:
        d.text((x, 1300), c, font=f, fill=(48, 56, 64), anchor="lm")
        x += f.getlength(c) + track
    return im


# ---------------------------------------------------------------- illustration edits
def edit_illustration(stage, im):
    a = np.array(im.convert("RGB")).astype(float)
    if stage == "entry":                                   # bubble "TRA ya nini?" -> "Kodi ya nini?"
        a = erase_dark(a, 905, 176, 1090, 266, iters=600)
        im = Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8)).convert("RGBA")
        draw_text(im, "Kodi", 994, 226, os.path.join(FD, "comicbd.ttf"), 70, (14, 14, 14), angle=3)
    elif stage == "asset":                                 # thought bubble "TRA?" -> "Kodi?"
        a = erase_dark(a, 694, 136, 862, 240, iters=900)
        im = Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8)).convert("RGBA")
        draw_text(im, "Kodi?", 782, 188, os.path.join(FD, "comicbd.ttf"), 58, (14, 14, 14), angle=8)
    elif stage == "enterprise":                            # TIN certificate: emblem -> plain seal
        paper = a[168, 240].copy()
        paint_rows(a, 255, 130, 282, 160, band=6, gap=2)
        im = Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8)).convert("RGBA")
        disc(im, 268, 145, 10, tuple(int(v) for v in paper), ring=(170, 140, 90))
    elif stage == "active":                                # certificate heading and emblem; cap badge and band lettering
        paper = a[200, 330].copy()
        paint_rows(a, 340, 158, 462, 192, band=4, gap=1)
        # cap band: remove "TRA" lettering and the crown badge, keep the braid
        paint_rows(a, 683, 214, 736, 233, band=4, gap=1)
        mask2 = np.zeros(a.shape[:2], bool)
        mask2[168:213, 686:735] = True
        a = diffuse(a, mask2, 600)
        im = Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8)).convert("RGBA")
        disc(im, 358, 170, 11, tuple(int(v) for v in paper), ring=(150, 120, 70))
        draw_text(im, "TAX OFFICE", 417, 176, os.path.join(FD, "ARIALNB.TTF"), 14, (40, 36, 30))
        disc(im, 710, 192, 10, (222, 176, 58), ring=(150, 110, 20))
    elif stage == "legacy":
        # wall plaque: blank
        paint_rows(a, 850, 330, 908, 410, band=6, gap=2)
        # certificate: emblem -> plain seal, heading -> TAX OFFICE
        paper = a[775, 545].copy()
        paint_rows(a, 562, 754, 594, 786, band=5, gap=1)
        mk = np.zeros(a.shape[:2], bool)
        for x in range(514, 644):
            ylim = int(802 - 0.14 * (x - 514))              # the heading slopes up to the right; the next line starts just below this limit
            mk[776:ylim, x] = a[776:ylim, x].mean(axis=1) < 150
        for _ in range(2):
            pp = np.pad(mk, 1)
            mk = mk | pp[:-2, 1:-1] | pp[2:, 1:-1] | pp[1:-1, :-2] | pp[1:-1, 2:]
        a = diffuse(a, mk, 150)
        im = Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8)).convert("RGBA")
        disc(im, 577, 769, 9, tuple(int(v) for v in paper), ring=(150, 110, 40))
        draw_text(im, "TAX OFFICE", 578, 787, os.path.join(FD, "ARIALNB.TTF"), 12, (45, 35, 20), angle=4)

    else:
        im = Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8)).convert("RGBA")
    return im


def build(stage, raw):
    src = Image.open(io.BytesIO(raw)).convert("RGB")
    im = edit_illustration(stage, src)
    a = np.array(im.convert("RGB")).astype(float)
    im = panel(im, a, PANEL_TEXT[stage])
    if stage == "seed":
        a = np.array(im.convert("RGB")).astype(float)
        im = number_seed(im, a)
    if stage == "entry":
        a = np.array(im.convert("RGB")).astype(float)
        im = label_entry(im, a)
    return src, im.convert("RGB")


def main():
    os.makedirs(OUT, exist_ok=True)
    with zipfile.ZipFile(DOCX) as z:
        for stage, name in SOURCES.items():
            before, after = build(stage, z.read("word/media/" + name))
            after.save(os.path.join(OUT, "persona_%s_pass2.jpg" % stage), quality=95, subsampling=0)
            sheet = Image.new("RGB", (before.width * 2 + 30, before.height), "white")
            sheet.paste(before, (0, 0))
            sheet.paste(after, (before.width + 30, 0))
            sheet.save(os.path.join(OUT, "persona_%s_comparison.png" % stage))
            print("wrote persona_%s_pass2.jpg" % stage, after.size)


if __name__ == "__main__":
    main()
