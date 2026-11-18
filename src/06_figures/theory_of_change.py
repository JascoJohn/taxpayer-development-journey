"""Theory of Change graphic of Chapter 3 ("Theory of Change: The Behavioral Lifecycle"), redrawn in Editing Pass 1b with the agreed tool names.

Not a data figure: it draws no number. Same structure and content as the submitted graphic (title, sub-title, six stage boxes joined by arrows, the reciprocity arc and its caption);
only the tool names change (read from config.yaml `names:`, Swahili name in bold with the English descriptor under it) and the look follows the journey graphic
(src/06_figures/journey_graphic.py): the six stage colours, the ink colour, DejaVu Sans / DejaVu Serif, flat cards with a thin line.
The stage descriptors are the owner's role-plus-age bands (Seed ages 6-15, Entry 16-24, Active informal business owners 25-64, Enterprise registered business owners 25-64, Asset property owners 45-64, Legacy 65+); Active and Enterprise follow stage mapping B (Pass 6B-1).

Output: outputs/figures/theory_of_change.png and .svg at the original's pixel size (2837 x 1121). Deterministic. run_figures.py runs it; it can also be run alone:
    python src/06_figures/theory_of_change.py
"""
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Polygon, FancyArrowPatch  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # src/
import paths  # noqa: E402
from journey_graphic import COLORS, INK, GREY_TXT, PX  # noqa: E402      (one palette for the document's graphics)

W, H = 2837, 1121
GOLD = "#B8780F"
STAGES = [("seed", "SEED", ["Ages 6–15"], ["(Tax Learning Games)"]),
          ("entry", "ENTRY", ["Ages 16–24"], ["(Taxpayer Targeting", "and Registration Tool)"]),
          ("active", "ACTIVE", ["Informal business owners,", "ages 25–64"], ["(Presumptive Tax", "Estimator)"]),
          ("enterprise", "ENTERPRISE", ["Registered business owners,", "ages 25–64"], ["(Tax Progression", "Dashboard)"]),
          ("asset", "ASSET", ["Property owners,", "ages 45–64"], ["(Tax Asset Score)"]),
          ("legacy", "LEGACY", ["Ages 65+"], ["(Tax Legacy Score)"])]
BOX_X = [28, 501, 974, 1447, 1920, 2393]
BOX_W, BOX_TOP, BOX_BOTTOM = 416, 282, 836
TITLE = "Theory of Change: The Behavioral Lifecycle"
SUB = "Each stage converts existing willingness into a designed, visible exchange — removing friction before enforcement is ever required"
CAPTION = "Reciprocity made visible at each stage compounds into sustained participation and stronger norms for the next generation"


def make(out_dir=None):
    names = paths.CFG["names"]
    for key, _, _, desc in STAGES:
        assert " ".join(desc) == "(%s)" % names[key]["english"], (key, names[key]["english"])      # the line breaks above only wrap the configured name
    out_dir = out_dir or os.path.join(paths.ROOT, "outputs", "figures")
    plt.rcParams.update({"svg.fonttype": "path", "svg.hashsalt": "tdj-toc", "font.family": "DejaVu Sans"})
    fig = plt.figure(figsize=(W / 100.0, H / 100.0), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)
    ax.axis("off")
    ax.text(W / 2, 142, TITLE, ha="center", va="center", color=INK, fontsize=56 * PX, fontweight="bold", family="DejaVu Serif")
    ax.text(W / 2, 230, SUB, ha="center", va="center", color=GREY_TXT, fontsize=34 * PX, style="italic", family="DejaVu Serif")
    mid = (BOX_TOP + BOX_BOTTOM) / 2
    for i, (key, label, descriptor, english) in enumerate(STAGES):
        x, c = BOX_X[i], COLORS[i]
        ax.add_patch(FancyBboxPatch((x, BOX_TOP), BOX_W, BOX_BOTTOM - BOX_TOP, boxstyle="round,pad=0,rounding_size=26", facecolor=c, edgecolor="none", zorder=2))
        cx = x + BOX_W / 2
        ax.text(cx, BOX_TOP + 90, label, ha="center", va="center", color="white", fontsize=44 * PX, fontweight="bold", family="DejaVu Serif", zorder=3)
        ax.plot([x + 70, x + BOX_W - 70], [BOX_TOP + 150, BOX_TOP + 150], color="white", lw=3 * PX, alpha=0.55, zorder=3)
        y = BOX_TOP + 215
        for line in descriptor:
            ax.text(cx, y, line, ha="center", va="center", color="white", fontsize=33 * PX, zorder=3)
            y += 50
        ty = mid + 90
        ax.text(cx, ty, names[key]["swahili"], ha="center", va="center", color="white", fontsize=31 * PX, fontweight="bold", zorder=3)
        for line in english:
            ty += 50
            ax.text(cx, ty, line, ha="center", va="center", color="white", fontsize=28 * PX, zorder=3)
        if i < 5:                                                                           # arrow to the next stage
            x0, x1 = x + BOX_W + 6, BOX_X[i + 1] - 6
            ax.plot([x0, x1 - 18], [mid, mid], color=INK, lw=5 * PX, solid_capstyle="butt", zorder=4)
            ax.add_patch(Polygon([[x1 - 24, mid - 15], [x1 + 2, mid], [x1 - 24, mid + 15]], closed=True, facecolor=INK, edgecolor="none", zorder=4))
    # the reciprocity arc: rises from below the first stage to below the last (drawn under the boxes, not across them)
    arc = FancyArrowPatch((BOX_X[0] + BOX_W / 2, 985), (BOX_X[5] + BOX_W / 2, 985), connectionstyle="arc3,rad=-0.08", arrowstyle="-|>", mutation_scale=34, linewidth=5 * PX,
                          linestyle=(0, (4, 3)), color=GOLD, zorder=1)
    ax.add_patch(arc)
    ax.text(W / 2, 1062, CAPTION, ha="center", va="center", color=GOLD, fontsize=32 * PX, zorder=3)
    os.makedirs(out_dir, exist_ok=True)
    out = []
    for ext, meta in (("png", {"Software": None}), ("svg", {"Date": None, "Creator": None})):
        p = os.path.join(out_dir, "theory_of_change.%s" % ext)
        fig.savefig(p, format=ext, dpi=100, metadata=meta, facecolor="white")
        out.append(p)
    plt.close(fig)
    svg = out[1]
    with open(svg, encoding="utf-8") as f:
        t = f.read()
    t = t.replace('width="%.2fpt" height="%.2fpt"' % (W * PX, H * PX), 'width="%dpx" height="%dpx"' % (W, H), 1)       # the original's pixel size (the viewBox is unchanged)
    with open(svg, "w", encoding="utf-8", newline="\n") as f:
        f.write(t)
    return out


if __name__ == "__main__":
    for p in make():
        print("wrote", p)
