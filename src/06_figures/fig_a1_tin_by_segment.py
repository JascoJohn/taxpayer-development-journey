"""TIN holding by lifecycle segment, FinScope Tanzania 2023, survey-weighted, with 95% confidence intervals (outputs/tables/tin_by_segment.csv)."""
import textwrap

import _style as S
import matplotlib.pyplot as plt


def make():
    rows = [r for r in S.read_csv(S.paths.TIN_BY_SEGMENT_CSV) if r["suppressed"] != "True"]
    x = range(len(rows))
    y = [float(r["tin_rate_pct"]) for r in rows]
    lo = [float(r["tin_rate_pct"]) - float(r["ci95_low_pct"]) for r in rows]
    hi = [float(r["ci95_high_pct"]) - float(r["tin_rate_pct"]) for r in rows]
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    bars = ax.bar(x, y, color=[S.NAVY if r["segment"] == "overall" else S.SLATE for r in rows], width=0.6, yerr=[lo, hi], capsize=4, ecolor=S.GOLD)
    for b, r in zip(bars, rows):
        if r["low_precision"] == "True":
            b.set_hatch("//")
            b.set_edgecolor("white")
    ax.set_xticks(list(x))
    ax.set_xticklabels([textwrap.fill(r["label"].replace(" (", "\n("), 17, replace_whitespace=False) for r in rows], fontsize=8)
    ax.set_ylabel("Adults reporting a TIN (%)")
    ax.set_ylim(0, max(float(r["ci95_high_pct"]) for r in rows) * 1.15)
    ax.text(0.99, 0.97, "bars: estimate; whiskers: 95% CI; hatched: low precision (fewer than 10 survey-reported TIN holders)", transform=ax.transAxes, ha="right", va="top", fontsize=7.5, color=S.GREY)
    return S.save(fig, "fig_a1_tin_by_segment")
