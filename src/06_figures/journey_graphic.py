"""The six-stage journey graphic of Chapter 4 (Learn -> Join -> Understand -> Progress -> Reveal -> Preserve), redrawn in Editing Pass 1 with the agreed tool names.

Not a data figure: it draws no number. It recreates, as closely as the bundled fonts allow, the graphic of the first version of the report (PDF p. 14): the six stage
colours, the timeline with its arrows and dotted connectors, six cards (coloured header, stage name, divider, tool name, tagline), the taglines unchanged. Only the tool names change:
they are read from config.yaml `names:` (Swahili name in bold, the English descriptor in brackets underneath).

Output: outputs/figures/journey_graphic.png and .svg at the original's pixel size (5200 x 2028). Deterministic (DejaVu fonts from matplotlib, fixed SVG hash salt, no metadata).
run_figures.py runs it with the other figures; it can also be run alone:  python src/06_figures/journey_graphic.py
"""
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Polygon, Circle  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # src/
import paths  # noqa: E402

W, H = 5200, 2028
PX = 72.0 / 100.0                                     # points per pixel at dpi 100 (the figure is 52 x 20.28 inches)
COLORS = ["#2E7D32", "#00695C", "#0D47A1", "#003366", "#B8780F", "#37474F"]       # sampled from the original graphic
STAGES = [("seed", "LEARN", "Seed", ["Early familiarity", "before economic", "participation"]),
          ("entry", "JOIN", "Entry", ["Creates the lifelong", "digital taxpayer", "identity"]),
          ("active", "UNDERSTAND", "Active", ["Fair, evidence-based", "presumptive", "assessment"]),
          ("enterprise", "PROGRESS", "Enterprise", ["Makes compliance", "progression visible", "and recognised"]),
          ("asset", "REVEAL", "Asset", ["Rewards transparent", "asset declaration"]),
          ("legacy", "PRESERVE", "Legacy", ["Preserves taxpayer", "history through", "succession"])]
DESCRIPTOR_LINES = {"seed": ["(Tax Learning Games)"], "entry": ["(Taxpayer Targeting", "and Registration Tool)"], "active": ["(Presumptive Tax", "Estimator)"],
                    "enterprise": ["(Tax Progression", "Dashboard)"], "asset": ["(Tax Asset Score)"], "legacy": ["(Tax Legacy Score)"]}      # line breaks of config names[*].english
CARD_X = [192, 1006, 1820, 2636, 3450, 4264]
CARD_W, CARD_TOP, CARD_BOTTOM, HEAD_H = 744, 491, 1742, 148
CIRCLE_X = [x + CARD_W / 2 for x in CARD_X]
TL_Y, R = 234, 42
INK, GREY_TXT, DIVIDER = "#2B3A42", "#78909C", "#D9DDE0"


def _names():
    n = paths.CFG["names"]
    for s, _, _, _ in STAGES:
        assert " ".join(DESCRIPTOR_LINES[s]) == "(%s)" % n[s]["english"], (s, n[s]["english"])        # the line breaks above only wrap the configured name
    return n


def make(out_dir=None):
    names = _names()
    out_dir = out_dir or os.path.join(paths.ROOT, "outputs", "figures")
    plt.rcParams.update({"svg.fonttype": "path", "svg.hashsalt": "tdj-journey", "font.family": "DejaVu Sans"})
    fig = plt.figure(figsize=(W / 100.0, H / 100.0), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)
    ax.axis("off")
    # timeline: coloured segments with arrow heads, then the circles
    for i in range(5):
        x0, x1 = CIRCLE_X[i] + R - 6, CIRCLE_X[i + 1] - R - 6
        ax.plot([x0, x1 - 70], [TL_Y, TL_Y], color=COLORS[i], lw=15 * PX, solid_capstyle="butt", zorder=2)
        ax.add_patch(Polygon([[x1 - 105, TL_Y - 52], [x1 + 10, TL_Y], [x1 - 105, TL_Y + 52]], closed=True, facecolor=COLORS[i], edgecolor="none", zorder=2))
    for i, x in enumerate(CIRCLE_X):
        ax.add_patch(Circle((x, TL_Y), R - 6, facecolor=COLORS[i], edgecolor="none", zorder=3))
        ax.plot([x, x], [TL_Y + R + 8, CARD_TOP - 8], color=COLORS[i], lw=5 * PX, linestyle=(0, (1, 2.6)), zorder=1)
    for i, (key, verb, label, tagline) in enumerate(STAGES):
        x, c = CARD_X[i], COLORS[i]
        card = FancyBboxPatch((x, CARD_TOP), CARD_W, CARD_BOTTOM - CARD_TOP, boxstyle="round,pad=0,rounding_size=26", facecolor="white", edgecolor="none", zorder=2)
        ax.add_patch(card)
        head = plt.Rectangle((x, CARD_TOP), CARD_W, HEAD_H, facecolor=c, edgecolor="none", zorder=3)
        ax.add_patch(head)
        head.set_clip_path(card)                                                       # the head takes the card's rounded top corners
        ax.add_patch(FancyBboxPatch((x, CARD_TOP), CARD_W, CARD_BOTTOM - CARD_TOP, boxstyle="round,pad=0,rounding_size=26", facecolor="none", edgecolor=c, linewidth=7 * PX, zorder=4))
        cx = x + CARD_W / 2
        ax.text(cx, CARD_TOP + HEAD_H / 2 + 2, " ".join(verb), ha="center", va="center", color="white", fontsize=34 * PX, zorder=5)         # letter-spaced capitals
        ax.text(cx, 718, label, ha="center", va="center", color=c, fontsize=76 * PX, fontweight="bold", family="DejaVu Serif", zorder=5)
        ax.plot([x + 70, x + CARD_W - 70], [798, 798], color=DIVIDER, lw=4 * PX, zorder=4)
        y = 888
        ax.text(cx, y, names[key]["swahili"], ha="center", va="center", color=INK, fontsize=42 * PX, fontweight="bold", zorder=5)
        for line in DESCRIPTOR_LINES[key]:
            y += 66
            ax.text(cx, y, line, ha="center", va="center", color=INK, fontsize=38 * PX, zorder=5)
        y += 118
        for line in tagline:
            ax.text(cx, y, line, ha="center", va="center", color=GREY_TXT, fontsize=39 * PX, style="italic", family="DejaVu Serif", zorder=5)
            y += 64
    os.makedirs(out_dir, exist_ok=True)
    out = []
    for ext, meta in (("png", {"Software": None}), ("svg", {"Date": None, "Creator": None})):
        p = os.path.join(out_dir, "journey_graphic.%s" % ext)
        fig.savefig(p, format=ext, dpi=100, metadata=meta, facecolor="white")
        out.append(p)
    plt.close(fig)
    svg = out[1]
    with open(svg, encoding="utf-8") as f:
        t = f.read()
    t = t.replace('width="3744pt" height="1460.16pt"', 'width="%dpx" height="%dpx"' % (W, H), 1)             # the original's pixel size (the viewBox is unchanged)
    with open(svg, "w", encoding="utf-8", newline="\n") as f:
        f.write(t)
    return out


if __name__ == "__main__":
    for p in make():
        print("wrote", p)
