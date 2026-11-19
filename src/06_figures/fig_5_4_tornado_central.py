"""Tornado of the portfolio's median 10-year return on programme cost on the CENTRAL case (HBS receipts of owners with receipts): each driver moved to a low and a high setting with everything else at the
central case (outputs/tables/fig5_4_tornado_central.csv). Same size and style as the former persistence figure it replaces (persistence now appears as one driver here and in Table 5.2)."""
import _style as S
import matplotlib.pyplot as plt


def make():
    d = S.load_json(S.paths.STAGE_ECONOMICS)["tornado_central"]
    rows = list(reversed(d["drivers"]))                      # largest swing at the top
    base = d["portfolio_median_roi_10y_central"]
    fig, ax = plt.subplots(figsize=(10.4, 4.8))
    for i, r in enumerate(rows):
        lo, hi = r["median_roi_unfavourable"], r["median_roi_favourable"]
        ax.barh(i, lo - base, left=base, color=S.RED, height=0.62, alpha=0.85)
        ax.barh(i, hi - base, left=base, color=S.NAVY, height=0.62, alpha=0.85)
        ax.text(min(lo, hi) - 0.01, i, "%.2f" % min(lo, hi), ha="right", va="center", fontsize=7.5, color=S.SLATE)
        ax.text(max(lo, hi) + 0.01, i, "%.2f" % max(lo, hi), ha="left", va="center", fontsize=7.5, color=S.SLATE)
    ax.axvline(base, color=S.SLATE, linewidth=1.2)
    ax.axvline(1.0, color=S.RED, linestyle="--", linewidth=1)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(["%s\n(%s)" % (r["driver"], r["setting"]) for r in rows], fontsize=8)
    ax.set_xlabel("Portfolio return on programme cost, 10 years (x, median); central case %.2f; dashed line: break-even" % base)
    ax.set_xlim(0, max(1.15, max(max(r["median_roi_unfavourable"], r["median_roi_favourable"]) for r in rows) + 0.12))
    fig.text(0.5, 1.02, "[MODELLED] red: unfavourable setting, navy: favourable setting; everything else at the central case", ha="center", color=S.GREY, fontsize=9)
    return S.save(fig, "fig_5_4_tornado_central")
