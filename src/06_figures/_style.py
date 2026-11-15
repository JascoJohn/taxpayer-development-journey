"""Shared style and helpers of the figure scripts (Block F4).

Every figure script in this folder (fig_<id>_<name>.py) defines make() and reads only the pipeline outputs (outputs/stats, outputs/tables, data/processed); it writes
outputs/figures/fig_<id>_<name>.png and .svg. No figure number or title is drawn into an image (the report numbers and captions its figures). The files are deterministic
(fixed fonts, no timestamps, fixed SVG hash salt), so run_all.py leaves identical bytes on a re-run.
"""

import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # src/
import paths  # noqa: E402

NAVY, GOLD, SLATE, CREAM = "#1B3A5C", "#96591A", "#44546A", "#F7F1E5"
LIGHT = "#9FB1C7"
GREY = "#8A8F98"
RED = "#A23B3B"
FIG_DIR = os.path.join(paths.ROOT, "outputs", "figures")

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": SLATE, "axes.labelcolor": SLATE,
    "xtick.color": SLATE, "ytick.color": SLATE, "axes.titlesize": 11, "figure.dpi": 100, "savefig.dpi": 200, "axes.grid": True, "grid.color": "#E5E7EB", "grid.linewidth": 0.6,
    "axes.axisbelow": True, "svg.fonttype": "path", "svg.hashsalt": "tdj-figures", "legend.frameon": False,
})


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def read_csv(path):
    import csv
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def save(fig, name):
    """Writes outputs/figures/<name>.png and .svg (deterministic) and closes the figure; returns the two paths."""
    os.makedirs(FIG_DIR, exist_ok=True)
    out = []
    for ext, meta in (("png", {"Software": None}), ("svg", {"Date": None, "Creator": None})):
        p = os.path.join(FIG_DIR, "%s.%s" % (name, ext))
        fig.savefig(p, format=ext, bbox_inches="tight", metadata=meta, facecolor="white")
        out.append(p)
    plt.close(fig)
    return out


def label_bars(ax, bars, fmt="{:.1f}", suffix="", dy=0.01):
    top = ax.get_ylim()[1]
    for b in bars:
        h = b.get_height()
        ax.text(b.get_x() + b.get_width() / 2, h + dy * top, (fmt + suffix).format(h), ha="center", va="bottom", color=SLATE, fontsize=9)
