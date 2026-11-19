"""The "Ngazi Platform" executive-summary poster (the report's page-1 cover), rebuilt in Editing Pass 1b.

Same layout and sections as the submitted poster (title and tagline, banner, six-stage journey, "key evidence at a glance", problem / platform / solution, evidence base,
demonstrated and live, modelled impact, implications for tax administration, closing quote and author line) with: the agreed tool names (config.yaml `names:`), no tax-authority
logo, no challenge text, a neutral QR placeholder, and every number taken from the CURRENT values of docs/claims_map.csv (POSTER_NUMBERS below lists each one with its claim_id;
the WVS 61.8 % is gone). Pass 6B-2: Tanzania's tax-to-GDP tile is 2023 against the peers' 2023 (2024 in brackets); the "MODELLED IMPACT (PORTFOLIO)" panel is replaced by "THREE PRINCIPLES"
(progression, reciprocity, continuity), so the poster carries no modelled compliance probability (10.17 %, 5.56 %, 12.0 %); the evidence base lists the Household Budget Survey 2017/18 and the
TRA collection statistics FY2024/25. The look follows the journey graphic
(src/06_figures/journey_graphic.py): stage colours, ink, DejaVu Sans / Serif, flat cards.

The two portrait/emblem crops in src/06_figures/assets are taken from the submitted poster (illustrations without text). The laptop picture is assets/poster_dashboard_home.png
(a copy of the dashboard home screenshot). Output: outputs/figures/cover_poster.png and .svg at the original's pixel size (1054 x 1492). Deterministic. Run alone:
    python src/06_figures/cover_poster.py
"""
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.image as mpimg  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Polygon, Circle, Rectangle, Wedge, Ellipse  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # src/
import paths  # noqa: E402
from journey_graphic import COLORS, INK, GREY_TXT, DIVIDER  # noqa: E402
import qrcode  # noqa: E402                                  # pip install qrcode (environment/requirements.txt)

W, H = 1054, 1492
PXPT = 72.0 / 100.0
GREEN, GOLD, CREAM = "#1B5E20", "#B8780F", "#FAFAF7"
RED, REDBG, GREENBG = "#B23A3A", "#FBF1EF", "#F0F5EF"
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

# every number on the poster, with the claim of docs/claims_map.csv it comes from (current value) and its label
POSTER_NUMBERS = [
    ("34.1M", "adults, weighted population base (FinScope Tanzania 2023)", "C001 (C016)", "COMPUTED"),
    ("3.83%", "adults reporting a TIN (survey-reported; key-evidence tile and problem panel)", "C002 (C011)", "COMPUTED"),
    ("23.1M", "mobile-money adults with no TIN", "C015", "COMPUTED"),
    ("65.7%", "civic duty: good citizens should always pay the taxes they owe (Afrobarometer R8, 2021; replaces the removed 61.8% WVS / 59.8%)", "C068 (C004, C013)", "COMPUTED"),
    ("11.68%", "Tanzania tax-to-GDP, 2023 (12.26% in 2024), like for like with the peers", "C003 (C005, C010)", "COMPUTED from CITED series"),
    ("13.12%", "peer-average benchmark, 2023 (GHA, KEN, RWA, UGA)", "C003 (C005, C010)", "COMPUTED from CITED series"),
    ("TZS 2.72T", "estimated annual gap to the peer-average benchmark (1.45 pp, 2023)", "C003 (C005, C010)", "COMPUTED from CITED series"),
    ("n = 9,915", "FinScope Tanzania 2023 respondents (evidence base box)", "C006", "COMPUTED"),
]

STAGES = [("seed", "LEARN", ["Play. Learn. Build", "identity early."], ["(Tax Learning Games)"]),
          ("entry", "JOIN", ["Be found. Be invited.", "Be welcomed."], ["(Taxpayer Targeting", "and Registration Tool)"]),
          ("active", "UNDERSTAND", ["See the impact.", "Make informed choices."], ["(Presumptive Tax", "Estimator)"]),
          ("enterprise", "PROGRESS", ["Build trust. Earn status.", "Unlock more."], ["(Tax Progression", "Dashboard)"]),
          ("asset", "REVEAL", ["Your history. Your score.", "Your opportunities."], ["(Tax Asset Score)"]),
          ("legacy", "PRESERVE", ["Your legacy.", "Carried forward."], ["(Tax Legacy Score)"])]
TITLE = "The Taxpayer Development Journey"
SUBTITLE = "A Behavioral Lifecycle Architecture for Tax Compliance: Evidence from Tanzania"
AUTHOR = "Jasco John, MBA, CPA(T)  |  jasco.john98@gmail.com  |  +255 759 003 950  |  ORCID https://orcid.org/0009-0007-3630-7943"
DASHBOARD_URL = "https://taxpayer-development-journey.streamlit.app"
DARK = "#263238"                       # Editing Pass 5: small text is dark and at least 9 px


class Canvas:
    def __init__(self):
        self.fig = plt.figure(figsize=(W / 100.0, H / 100.0), dpi=100)
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, W)
        self.ax.set_ylim(H, 0)
        self.ax.axis("off")
        self.z = 1

    def t(self, x, y, s, px, color=INK, weight="normal", ha="center", va="center", family=None, style="normal", z=6):
        kw = {"family": family} if family else {}
        return self.ax.text(x, y, s, ha=ha, va=va, color=color, fontsize=px * PXPT, fontweight=weight, style=style, zorder=z, **kw)

    def box(self, x, y, w, h, fc="white", ec="none", lw=1.0, r=10, z=2):
        self.ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=%g" % r, facecolor=fc, edgecolor=ec, linewidth=lw * PXPT, zorder=z))

    def circ(self, x, y, r, fc="white", ec="none", lw=1.0, z=3):
        self.ax.add_patch(Circle((x, y), r, facecolor=fc, edgecolor=ec, linewidth=lw * PXPT, zorder=z))

    def poly(self, pts, fc, ec="none", lw=1.0, z=3):
        self.ax.add_patch(Polygon(pts, closed=True, facecolor=fc, edgecolor=ec, linewidth=lw * PXPT, zorder=z))

    def line(self, xs, ys, color=INK, lw=1.0, z=3, **kw):
        self.ax.plot(xs, ys, color=color, lw=lw * PXPT, zorder=z, **kw)


# ---- icons (flat, one colour; drawn on a (cx, cy) with scale s ~ half-size in px)
def head_body(c, cx, cy, s, color, z=5):
    c.circ(cx, cy - 0.45 * s, 0.32 * s, fc=color, z=z)
    c.ax.add_patch(Wedge((cx, cy + 0.9 * s), 0.78 * s, 180, 360, facecolor=color, edgecolor="none", zorder=z))


def icon(c, kind, cx, cy, s, color, bg="white"):
    if kind == "game":
        c.box(cx - s, cy - 0.55 * s, 2 * s, 1.1 * s, fc=color, r=0.3 * s, z=5)
        c.line([cx - 0.62 * s, cx - 0.28 * s], [cy, cy], color=bg, lw=0.2 * s, z=6)
        c.line([cx - 0.45 * s, cx - 0.45 * s], [cy - 0.17 * s, cy + 0.17 * s], color=bg, lw=0.2 * s, z=6)
        c.circ(cx + 0.38 * s, cy + 0.1 * s, 0.12 * s, fc=bg, z=6)
        c.circ(cx + 0.65 * s, cy - 0.1 * s, 0.12 * s, fc=bg, z=6)
    elif kind == "person_check":
        head_body(c, cx - 0.1 * s, cy, s * 0.95, color)
        c.circ(cx + 0.62 * s, cy + 0.45 * s, 0.34 * s, fc=bg, z=6)
        c.circ(cx + 0.62 * s, cy + 0.45 * s, 0.28 * s, fc=color, z=7)
        c.line([cx + 0.5 * s, cx + 0.6 * s, cx + 0.76 * s], [cy + 0.45 * s, cy + 0.56 * s, cy + 0.34 * s], color=bg, lw=0.1 * s, z=8)
    elif kind == "book":
        c.poly([[cx - s, cy - 0.55 * s], [cx - 0.05 * s, cy - 0.4 * s], [cx - 0.05 * s, cy + 0.6 * s], [cx - s, cy + 0.45 * s]], color, z=5)
        c.poly([[cx + s, cy - 0.55 * s], [cx + 0.05 * s, cy - 0.4 * s], [cx + 0.05 * s, cy + 0.6 * s], [cx + s, cy + 0.45 * s]], color, z=5)
        for k in range(3):
            c.line([cx - 0.8 * s, cx - 0.25 * s], [cy - 0.2 * s + k * 0.22 * s, cy - 0.1 * s + k * 0.22 * s], color=bg, lw=0.07 * s, z=6)
            c.line([cx + 0.8 * s, cx + 0.25 * s], [cy - 0.2 * s + k * 0.22 * s, cy - 0.1 * s + k * 0.22 * s], color=bg, lw=0.07 * s, z=6)
    elif kind == "steps":
        for k in range(3):
            c.ax.add_patch(Rectangle((cx - s + k * 0.68 * s, cy + 0.65 * s - (k + 1) * 0.42 * s), 0.68 * s, (k + 1) * 0.42 * s, facecolor=color, edgecolor="none", zorder=5))
        c.poly([[cx + 0.55 * s, cy - 0.9 * s], [cx + 0.66 * s, cy - 0.66 * s], [cx + 0.92 * s, cy - 0.64 * s], [cx + 0.72 * s, cy - 0.48 * s],
                [cx + 0.78 * s, cy - 0.22 * s], [cx + 0.55 * s, cy - 0.36 * s], [cx + 0.32 * s, cy - 0.22 * s], [cx + 0.38 * s, cy - 0.48 * s],
                [cx + 0.18 * s, cy - 0.64 * s], [cx + 0.44 * s, cy - 0.66 * s]], color, z=5)
    elif kind == "shield":
        c.poly([[cx - 0.8 * s, cy - 0.8 * s], [cx, cy - 1.0 * s], [cx + 0.8 * s, cy - 0.8 * s], [cx + 0.8 * s, cy + 0.1 * s], [cx, cy + 1.0 * s], [cx - 0.8 * s, cy + 0.1 * s]], color, z=5)
        c.line([cx - 0.38 * s, cx - 0.08 * s, cx + 0.42 * s], [cy - 0.02 * s, cy + 0.3 * s, cy - 0.42 * s], color=bg, lw=0.2 * s, z=6)
    elif kind == "group":
        for dx, sc in ((-0.7, 0.62), (0.7, 0.62), (0.0, 0.8)):
            head_body(c, cx + dx * s, cy + (0.1 if dx else 0.0) * s, s * sc, color)
    elif kind == "idcard":
        c.box(cx - s, cy - 0.65 * s, 2 * s, 1.3 * s, fc=color, r=0.15 * s, z=5)
        c.circ(cx - 0.5 * s, cy - 0.12 * s, 0.22 * s, fc=bg, z=6)
        for k in range(3):
            c.line([cx - 0.05 * s, cx + 0.8 * s], [cy - 0.3 * s + k * 0.3 * s] * 2, color=bg, lw=0.1 * s, z=6)
    elif kind == "phone":
        c.box(cx - 0.5 * s, cy - s, s, 2 * s, fc=color, r=0.18 * s, z=5)
        c.box(cx - 0.38 * s, cy - 0.78 * s, 0.76 * s, 1.4 * s, fc=bg, r=0.05 * s, z=6)
        c.circ(cx, cy - 0.1 * s, 0.2 * s, fc=color, z=7)
    elif kind == "bars":
        for k, hh in enumerate((0.5, 0.9, 1.4, 1.9)):
            c.ax.add_patch(Rectangle((cx - s + k * 0.52 * s, cy + s - hh * s), 0.4 * s, hh * s, facecolor=color, edgecolor="none", zorder=5))
    elif kind == "bars2":
        for k, hh in enumerate((1.0, 1.6, 1.3)):
            c.ax.add_patch(Rectangle((cx - 0.9 * s + k * 0.66 * s, cy + s - hh * s), 0.5 * s, hh * s, facecolor=color, edgecolor="none", zorder=5))
    elif kind == "target":
        c.circ(cx, cy, s, fc=color, z=5)
        c.circ(cx, cy, 0.68 * s, fc=bg, z=6)
        c.circ(cx, cy, 0.42 * s, fc=color, z=7)
        c.circ(cx, cy, 0.16 * s, fc=bg, z=8)
    elif kind == "coins":
        for k in range(3):
            c.ax.add_patch(Ellipse((cx, cy + 0.5 * s - k * 0.42 * s), 1.8 * s, 0.6 * s, facecolor=color, edgecolor=bg, linewidth=1.2 * PXPT, zorder=5 + k))
    elif kind == "bank":
        c.poly([[cx - s, cy - 0.3 * s], [cx, cy - s], [cx + s, cy - 0.3 * s]], color, z=5)
        for k in range(4):
            c.ax.add_patch(Rectangle((cx - 0.8 * s + k * 0.5 * s, cy - 0.2 * s), 0.28 * s, 0.9 * s, facecolor=color, edgecolor="none", zorder=5))
        c.ax.add_patch(Rectangle((cx - s, cy + 0.8 * s), 2 * s, 0.22 * s, facecolor=color, edgecolor="none", zorder=5))
    elif kind == "puzzle":
        c.ax.add_patch(Rectangle((cx - 0.8 * s, cy - 0.7 * s), 1.6 * s, 1.5 * s, facecolor=color, edgecolor="none", zorder=5))
        c.circ(cx, cy - 0.78 * s, 0.3 * s, fc=color, z=5)
        c.circ(cx + 0.82 * s, cy, 0.3 * s, fc=color, z=5)
        c.circ(cx - 0.8 * s, cy, 0.27 * s, fc=bg, z=6)
    elif kind == "diamond":
        c.poly([[cx - s, cy - 0.35 * s], [cx - 0.55 * s, cy - 0.9 * s], [cx + 0.55 * s, cy - 0.9 * s], [cx + s, cy - 0.35 * s], [cx, cy + 0.95 * s]], color, z=5)
        c.line([cx - s, cx + s], [cy - 0.35 * s] * 2, color=bg, lw=0.07 * s, z=6)
        c.line([cx - 0.35 * s, cx, cx + 0.35 * s], [cy - 0.35 * s, cy - 0.9 * s, cy - 0.35 * s], color=bg, lw=0.07 * s, z=6)
    elif kind == "gear":
        c.circ(cx, cy, 0.82 * s, fc=color, z=5)
        c.circ(cx, cy, 0.36 * s, fc=bg, z=6)
        for k in range(8):
            import math
            a = k * math.pi / 4
            c.circ(cx + 0.9 * s * math.cos(a), cy + 0.9 * s * math.sin(a), 0.18 * s, fc=color, z=5)
    elif kind == "cycle":
        c.ax.add_patch(Wedge((cx, cy), s, 40, 330, width=0.28 * s, facecolor=color, edgecolor="none", zorder=5))
        c.poly([[cx + 0.55 * s, cy - 0.95 * s], [cx + 1.1 * s, cy - 0.7 * s], [cx + 0.5 * s, cy - 0.4 * s]], color, z=5)
    elif kind == "chart_down":
        c.line([cx - s, cx - 0.3 * s, cx + 0.2 * s, cx + s], [cy - 0.6 * s, cy - 0.1 * s, cy - 0.35 * s, cy + 0.6 * s], color=color, lw=0.22 * s, z=5)
        c.poly([[cx + 0.55 * s, cy + 0.75 * s], [cx + 1.05 * s, cy + 0.75 * s], [cx + 1.05 * s, cy + 0.25 * s]], color, z=5)
    elif kind == "link":
        c.box(cx - 0.95 * s, cy - 0.3 * s, 1.0 * s, 0.6 * s, fc="none", ec=color, lw=0.18 * s, r=0.3 * s, z=5)
        c.box(cx - 0.05 * s, cy - 0.3 * s, 1.0 * s, 0.6 * s, fc="none", ec=color, lw=0.18 * s, r=0.3 * s, z=5)
    elif kind == "check":
        c.circ(cx, cy, s, fc=color, z=5)
        c.line([cx - 0.5 * s, cx - 0.1 * s, cx + 0.55 * s], [cy, cy + 0.4 * s, cy - 0.4 * s], color=bg, lw=0.22 * s, z=6)
    elif kind == "share":
        for (dx, dy) in ((-0.7, 0.4), (0.6, -0.5), (0.6, 0.6)):
            c.circ(cx + dx * s, cy + dy * s, 0.25 * s, fc=color, z=5)
        c.line([cx - 0.7 * s, cx + 0.6 * s], [cy + 0.4 * s, cy - 0.5 * s], color=color, lw=0.1 * s, z=5)
        c.line([cx - 0.7 * s, cx + 0.6 * s], [cy + 0.4 * s, cy + 0.6 * s], color=color, lw=0.1 * s, z=5)
    elif kind == "gauge":
        c.ax.add_patch(Wedge((cx, cy + 0.3 * s), s, 180, 360, width=0.28 * s, facecolor=color, edgecolor="none", zorder=5))
        c.line([cx, cx + 0.5 * s], [cy + 0.3 * s, cy - 0.3 * s], color=color, lw=0.14 * s, z=5)
    elif kind == "heart":
        c.circ(cx - 0.35 * s, cy - 0.2 * s, 0.42 * s, fc=color, z=5)
        c.circ(cx + 0.35 * s, cy - 0.2 * s, 0.42 * s, fc=color, z=5)
        c.poly([[cx - 0.74 * s, cy - 0.02 * s], [cx + 0.74 * s, cy - 0.02 * s], [cx, cy + 0.85 * s]], color, z=5)


def make(out_dir=None):
    names = paths.CFG["names"]
    for key, _, _, eng in STAGES:
        assert " ".join(eng) == "(%s)" % names[key]["english"], (key, names[key]["english"])        # the line breaks above only wrap the configured name
    out_dir = out_dir or os.path.join(paths.ROOT, "outputs", "figures")
    plt.rcParams.update({"svg.fonttype": "path", "svg.hashsalt": "tdj-poster", "font.family": "DejaVu Sans"})
    c = Canvas()
    ax = c.ax
    ax.add_patch(Rectangle((0, 0), W, H, facecolor=CREAM, edgecolor="none", zorder=0))
    # ---- title block
    c.poly([[366, 0], [688, 0], [668, 36], [386, 36]], GREEN, z=3)
    c.t(527, 18, "PICTORIAL SUMMARY", 15, "white", "bold")
    c.t(527, 88, "THE NGAZI PLATFORM", 62, GREEN, "bold", family="DejaVu Sans")
    c.t(527, 140, "ONE TAXPAYER. ONE RELATIONSHIP. A LIFETIME OF VALUE.", 21, GOLD, "bold")
    # ---- banner
    c.poly([[160, 154], [895, 154], [922, 199], [895, 244], [160, 244], [133, 199]], GREEN, z=3)
    c.circ(202, 199, 34, fc="none", ec="white", lw=2.0, z=4)
    icon(c, "group", 202, 197, 15, "white", GREEN)
    for k, ln in enumerate(["The Ngazi Platform transforms six disconnected taxpayer interactions", "into one lifelong taxpayer relationship, enabling trust, compliance and",
                            "continuity to build over time rather than reset at every encounter."]):
        c.t(563, 176 + k * 23, ln, 15.5, "white", "bold" if k == 1 else "normal")
    # ---- journey
    c.t(527, 270, "THE TAXPAYER DEVELOPMENT JOURNEY", 19, GREEN, "bold")
    c.t(527, 292, "Six stages. One continuous relationship.", 13.5, INK)
    cx = [110 + 160 * i for i in range(6)]
    c.line([34, 1004], [378, 378], color=COLORS[0], lw=3, z=1)
    for i in range(1, 6):
        c.line([cx[i - 1] + 52, cx[i] - 52], [378, 378], color=COLORS[i - 1], lw=3, z=1)
    c.poly([[1000, 366], [1026, 378], [1000, 390]], COLORS[5], z=1)
    icons = ["game", "person_check", "book", "steps", "shield", "group"]
    for i, (key, verb, tag, eng) in enumerate(STAGES):
        col, x = COLORS[i], cx[i]
        c.circ(x, 312, 13, fc=col, z=4)
        c.t(x, 312, str(i + 1), 14, "white", "bold")
        c.line([x, x], [325, 338], color=col, lw=1.5, z=2, linestyle=(0, (1, 2)))
        c.circ(x, 378, 51, fc="white", ec=col, lw=3.0, z=3)
        icon(c, icons[i], x, 378, 22, col)
        c.t(x, 447, verb, 17, col, "bold")
        c.t(x, 467, names[key]["swahili"], 11.6, INK, "bold")
        y = 483
        for ln in eng:
            c.t(x, y, ln, 10.8, INK)
            y += 15
        y = 483 + 15 * max(len(eng), 2) + 9
        for ln in tag:
            c.t(x, y, ln, 11.4, DARK, style="italic", family="DejaVu Serif")
            y += 16
    c.box(124, 553, 806, 34, fc="#EAEFEA", r=17, z=2)
    icon(c, "link", 162, 570, 11, GREEN)
    c.t(548, 570, "Every interaction strengthens a persistent taxpayer relationship rather than operating as an isolated programme.", 12.4, INK)
    # ---- key evidence
    c.t(527, 612, "KEY EVIDENCE AT A GLANCE", 17, GREEN, "bold")
    c.line([14, 380], [612, 612], color=DIVIDER, lw=1.5)
    c.line([674, 1040], [612, 612], color=DIVIDER, lw=1.5)
    c.box(14, 626, 1026, 166, fc="white", ec="#CFD8DC", lw=1.2, r=12, z=2)
    tiles = [("people", "34.1M", ["Adults in Tanzania", "(weighted population", "base)"], "FinScope Tanzania 2023", GREEN),
             ("idcard", "3.83%", ["Adults reporting a TIN", "(survey-reported)"], "FinScope Tanzania 2023", GREEN),
             ("phone", "23.1M", ["Mobile-money adults", "with no TIN"], "FinScope Tanzania 2023", GREEN),
             ("heart", "65.7%", ["Say good citizens", "should always pay the", "taxes they owe"], "Afrobarometer R8, 2021", GREEN),
             ("bars", "11.68%", ["Tanzania tax-to-GDP,", "2023", "(12.26% in 2024)"], "World Bank WDI", GREEN),
             ("target", "13.12%", ["Peer average,", "2023"], "World Bank WDI (peers)", GREEN),
             ("coins", "TZS 2.72T", ["Annual gap to the", "peer average, 2023"], "Computed from WDI", GOLD)]
    for k, (ic, num, lab, src, colr) in enumerate(tiles):
        x = 14 + 1026 / 14.0 * (2 * k + 1)
        if k:
            c.line([14 + 1026 / 7.0 * k] * 2, [640, 778], color=DIVIDER, lw=1.2)
        if ic == "people":
            icon(c, "group", x, 660, 17, colr)
        else:
            icon(c, ic, x, 660, 17, colr)
        c.t(x, 701, num, 24 if len(num) < 8 else 20.5, colr, "bold")
        for j, ln in enumerate(lab):
            c.t(x, 723 + 13.5 * j, ln, 10.2, INK)
        c.t(x, 778, src, 9.6, DARK, style="italic")
    # ---- problem / platform / solution
    c.box(14, 808, 392, 290, fc=REDBG, ec="#F0D5D0", lw=1.0, r=14, z=2)
    c.t(210, 830, "THE PROBLEM: WHY REFORMS PLATEAU", 14.5, RED, "bold")
    c.box(648, 808, 392, 290, fc=GREENBG, ec="#D3E2D0", lw=1.0, r=14, z=2)
    c.t(844, 830, "THE SOLUTION: WHY NGAZI IS DIFFERENT", 14.5, GREEN, "bold")
    prob = [["Current reforms improve transactions", "— registration, filing, enforcement —", "not relationships."],
            ["Each life-stage interaction", "resets to zero — we treat the same", "citizen as a stranger."],
            ["High civic duty (65.7% say", "taxes should always be paid)", "but very low formal participation", "(3.83% report a TIN) — a relationship gap:", "positive attitudes, low participation."]]
    sol = [["Relationship architecture,", "not standalone products."], ["Persistent taxpayer identity", "across the entire life journey."],
           ["Trust, history, and compliance", "compound over time — never", "reset at every encounter."]]
    prow = [(892, "gear"), (975, "cycle"), (1057, "chart_down")]
    for k, (yy, ic) in enumerate(prow):
        ax.imshow(mpimg.imread(os.path.join(ASSETS, "poster_avatar_child%d.png" % (k + 1))), extent=(24, 94, yy + 35, yy - 35), zorder=4, interpolation="bicubic")
        c.circ(94, yy, 4, fc="white", z=1)
        c.circ(128, yy, 20, fc=RED, z=4)
        icon(c, ic, 128, yy, 10, "white", RED)
        for j, ln in enumerate(prob[k]):
            c.t(158, yy + (j - (len(prob[k]) - 1) / 2.0) * 15, ln, 10.6, INK, ha="left")
        ax.imshow(mpimg.imread(os.path.join(ASSETS, "poster_avatar_adult%d.png" % (k + 1))), extent=(660, 730, yy + 35, yy - 35), zorder=4, interpolation="bicubic")
        c.circ(762, yy, 20, fc=GREEN, z=4)
        icon(c, ["share", "idcard", "bars2"][k], 762, yy, 10, "white", GREEN)
        for j, ln in enumerate(sol[k]):
            c.t(792, yy + (j - (len(sol[k]) - 1) / 2.0) * 16, ln, 11.8, INK, ha="left")
        if k < 2:
            c.line([24, 395], [yy + 41] * 2, color="#E7CFCB", lw=1.0)
            c.line([660, 1030], [yy + 41] * 2, color="#CFE0CC", lw=1.0)
    c.poly([[404, 956], [428, 943], [404, 930]], RED, z=4)
    c.poly([[618, 956], [644, 943], [618, 930]], GREEN, z=4)
    # centre emblem
    c.circ(527, 943, 138, fc="white", ec=GREEN, lw=5, z=4)
    c.circ(527, 943, 127, fc="none", ec=GOLD, lw=2, z=4)
    ax.imshow(mpimg.imread(os.path.join(ASSETS, "poster_tree.png")), extent=(493, 561, 886, 820), zorder=5, interpolation="bicubic")
    c.t(527, 913, "NGAZI", 40, GREEN, "bold")
    c.t(527, 951, "PLATFORM", 33, GOLD, "bold")
    for j, ln in enumerate(["A PERSISTENT TAXPAYER", "RELATIONSHIP ARCHITECTURE"]):
        c.t(527, 995 + 16 * j, ln, 11.4, INK, "bold")
    # ---- bottom boxes
    top, hbox = 1110, 258
    c.box(14, top, 238, hbox, fc="white", ec="#CFD8DC", lw=1.0, r=10, z=2)
    c.t(133, top + 20, "EVIDENCE BASE", 13.5, INK, "bold")
    ev = [("FinScope Tanzania 2023 (n = 9,915)", "& ILFS 2024"), ("Household Budget Survey 2017/18",), ("TRA collection statistics,", "FY2024/25"), ("World Bank & International", "Benchmarks"),
          ("Behavioural Economics &", "Tax Morale Studies"), ("Monte Carlo & Agent-Based Models",), ("Survey-weighted Firth logit",), ("Held-out targeting model (ROC-AUC)",)]
    yy = 42
    for item in ev:
        icon(c, "check", 30, top + yy, 6.5, GREEN)
        for j, ln in enumerate(item):
            c.t(48, top + yy + 12 * j, ln, 9.6, INK, ha="left")
        yy += 12 * len(item) + 5
    c.t(133, top + 238, "Every number is labelled by evidence type:", 9.2, DARK, style="italic")
    c.t(133, top + 251, "COMPUTED · MODELLED · CITED · ILLUSTRATIVE", 9.2, DARK, style="italic")
    c.box(266, top, 250, hbox, fc="white", ec="#CFD8DC", lw=1.0, r=10, z=2)
    c.t(391, top + 20, "DEMONSTRATED & LIVE", 13.5, INK, "bold")
    shot = os.path.join(ASSETS, "poster_dashboard_home.png")      # a copy of the dashboard home screenshot (a static asset, so the poster does not depend on the order of the pipeline steps)
    if os.path.exists(shot):
        im = mpimg.imread(shot)
        hh = min(100 * im.shape[1] / im.shape[1], 120.0 * im.shape[0] / im.shape[1])
        ax.imshow(im, extent=(341, 441, top + 36 + 67, top + 36), zorder=4, interpolation="bicubic")
        c.box(336, top + 31, 110, 77, fc="none", ec=INK, lw=3, r=4, z=5)
    else:
        c.box(336, top + 31, 110, 77, fc="#EEF1F2", ec=INK, lw=3, r=4, z=3)
    for j, ln in enumerate(["All six stages are prototyped", "and linked in a live demonstration."]):
        c.t(391, top + 116 + 13 * j, ln, 9.7, INK)
    # a real QR code for the dashboard (vector squares; qrcode only supplies the module matrix)
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=1, border=0)
    qr.add_data(DASHBOARD_URL)
    qr.make(fit=True)
    mat = qr.get_matrix()
    qs, qx, qy = 82.0, 276.0, top + 168.0
    c.box(qx - 5, qy - 5, qs + 10, qs + 10, fc="white", ec="#90A4AE", lw=1.0, r=3, z=3)
    cell = qs / len(mat)
    for r, row in enumerate(mat):
        k = 0
        while k < len(row):
            if row[k]:
                k2 = k
                while k2 < len(row) and row[k2]:
                    k2 += 1
                ax.add_patch(Rectangle((qx + k * cell, qy + r * cell), (k2 - k) * cell, cell, facecolor="black", edgecolor="none", linewidth=0, zorder=4))
                k = k2
            else:
                k += 1
    c.t(372, top + 196, "Live demonstration:", 9.8, INK, "bold", ha="left")
    c.t(372, top + 213, "taxpayer-development-", 8.9, INK, ha="left")
    c.t(372, top + 226, "journey.streamlit.app", 8.9, INK, ha="left")
    c.box(530, top, 238, hbox, fc="white", ec="#CFD8DC", lw=1.0, r=10, z=2)
    c.t(649, top + 20, "THREE PRINCIPLES", 12, INK, "bold")
    principles = [("PROGRESSION", GREEN, ["Citizens understand their obligations", "and can see the next step as their", "economic circumstances change."]),
                  ("RECIPROCITY", GOLD, ["Citizens who engage receive fair,", "transparent and useful treatment."]),
                  ("CONTINUITY", GREEN, ["Taxpayer identity and verified history", "stay meaningful as people move", "between activities and stages of life."])]
    yy = top + 46
    for head, colr, body in principles:
        c.t(550, yy, head, 14, colr, "bold", ha="left")
        for j, ln in enumerate(body):
            c.t(550, yy + 17 + 12 * j, ln, 9.6, INK, ha="left")
        yy += 17 + 12 * len(body) + 13
    c.t(649, top + 243, "Chapter 7: the behavioural change sought,", 9.0, DARK, style="italic")
    c.t(649, top + 254, "judged by pilots, not assumed", 9.0, DARK, style="italic")
    c.box(782, top, 258, hbox, fc="white", ec="#CFD8DC", lw=1.0, r=10, z=2)
    c.t(911, top + 20, "IMPLICATIONS FOR", 12.8, INK, "bold")
    c.t(911, top + 37, "TAX ADMINISTRATION", 12.8, INK, "bold")
    imp = [("bank", "Scalable Relationship Infrastructure", ["A reusable platform every future", "intervention can plug into."]),
           ("puzzle", "Institutional Capability That Endures", ["Builds long-term taxpayer trust,", "compliance, and data intelligence."]),
           ("diamond", "Active Taxpayers, Not Just Numbers", ["Turning registrations already under", "way into filing, paying taxpayers."])]
    yy = top + 90
    for ic, head, body in imp:
        icon(c, ic, 812, yy + 10, 14, GREEN)
        c.t(836, yy - 4, head, 9.4, INK, "bold", ha="left")
        for j, ln in enumerate(body):
            c.t(836, yy + 11 + 12.5 * j, ln, 9.4, INK, ha="left")
        yy += 56 + (12 if len(body) > 2 else 0)
    # ---- closing band and author line
    c.ax.add_patch(Rectangle((0, 1372), W, 56, facecolor=GREEN, edgecolor="none", zorder=2))
    c.t(34, 1392, "“", 46, GOLD, "bold", family="DejaVu Serif")
    for j, ln in enumerate(["NGAZI IS NOT SIX INNOVATIONS.", "IT IS ONE TAXPAYER RELATIONSHIP ARCHITECTURE", "DEMONSTRATED THROUGH SIX CONNECTED INTERVENTIONS."]):
        c.t(74, 1385 + 16 * j, ln, 12, "white" if j else GOLD, "bold", ha="left")
    for k, (ic, lab) in enumerate([("steps", "Progression"), ("share", "Reciprocity"), ("cycle", "Continuity")]):
        x = 592 + 130 * k
        icon(c, ic, x, 1390, 10, "white", GREEN)
        for j, ln in enumerate(lab.split("\n")):
            c.t(x, 1409 + 11 * j, ln, 9.4, "white")
        if k:
            c.line([x - 65, x - 65], [1382, 1422], color="#5C8F60", lw=1.0, linestyle=(0, (2, 2)))
    for r in range(3):
        for q in range(3):
            c.poly([[994 + 20 * q + 10, 1374 + 18 * r], [994 + 20 * q + 20, 1383 + 18 * r], [994 + 20 * q + 10, 1392 + 18 * r], [994 + 20 * q, 1383 + 18 * r]], GOLD, z=3)
    ax.add_patch(Rectangle((0, 1428), W, 64, facecolor="white", edgecolor="none", zorder=2))
    c.t(527, 1445, TITLE, 14, "#1B5E20", "bold", family="DejaVu Serif")
    c.t(527, 1462, SUBTITLE, 10.8, "#37474F", style="italic", family="DejaVu Serif")
    c.t(527, 1480, AUTHOR, 13.2, "#37474F")
    os.makedirs(out_dir, exist_ok=True)
    out = []
    for ext, meta in (("png", {"Software": None}), ("svg", {"Date": None, "Creator": None})):
        p = os.path.join(out_dir, "cover_poster.%s" % ext)
        c.fig.savefig(p, format=ext, dpi=100, metadata=meta, facecolor=CREAM)
        out.append(p)
    plt.close(c.fig)
    svg = out[1]
    with open(svg, encoding="utf-8") as f:
        t = f.read()
    t = t.replace('width="%.2fpt" height="%.2fpt"' % (W * PXPT, H * PXPT), 'width="%dpx" height="%dpx"' % (W, H), 1)       # the original's pixel size (the viewBox is unchanged)
    with open(svg, "w", encoding="utf-8", newline="\n") as f:
        f.write(t)
    return out


if __name__ == "__main__":
    for p in make():
        print("wrote", p)
