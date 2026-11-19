"""Table 5.1 as a figure: return on programme cost (discounted revenue / cost) by stage over 10 years. Dots and thin whiskers: the CENTRAL case (HBS 2017/18 receipts of owners with receipts), median and 80% interval.
Thick gold bars: the BRACKET of the median between the low case (HBS, all owners, zeros kept) and the high case (ILFS 2024 gross receipts); it only differs for Active, Enterprise and the portfolio, because Entry
and Legacy use the same revenue per registrant in every basis. ILFS is never shown alone."""
import _style as S
import matplotlib.pyplot as plt
import numpy as np


def make():
    d = S.load_json(S.paths.STAGE_ECONOMICS)
    stages = ["entry", "active", "enterprise", "legacy"]
    label = {"entry": "Entry", "active": "Active", "enterprise": "Enterprise", "legacy": "Legacy"}
    bases = d["income_bases"]
    central = [bases["central"]["stages"][s]["roi_10y"] for s in stages] + [bases["central"]["portfolio_excluding_asset"]["roi_10y"]]
    low = [bases["low"]["stages"][s]["roi_10y"]["median"] for s in stages] + [bases["low"]["portfolio_excluding_asset"]["roi_10y"]["median"]]
    high = [bases["high"]["stages"][s]["roi_10y"]["median"] for s in stages] + [bases["high"]["portfolio_excluding_asset"]["roi_10y"]["median"]]
    names = [label[s] for s in stages] + ["Portfolio\n(without Asset)"]
    x = np.arange(len(names))
    fig, ax = plt.subplots(figsize=(8.8, 5.0))
    med = np.array([v["median"] for v in central])
    first = True
    for xi, lo_, hi_ in zip(x, low, high):
        if abs(hi_ - lo_) > 1e-9:
            ax.plot([xi, xi], [lo_, hi_], color=S.GOLD, linewidth=9, alpha=0.55, solid_capstyle="butt", zorder=1,
                    label="bracket of the median: low (HBS, all owners) to high (ILFS gross)" if first else None)
            first = False
    ax.errorbar(x, med, yerr=[med - np.array([v["p10"] for v in central]), np.array([v["p90"] for v in central]) - med], fmt="o", color=S.NAVY, capsize=4, markersize=7, linewidth=1.4, zorder=3,
                label="central case (HBS receipts of owners with receipts): median, 80% interval")
    ax.axhline(1.0, color=S.RED, linestyle="--", linewidth=1.1)
    ax.text(-0.45, 1.06, "break-even (ROI = 1)", color=S.RED, fontsize=8, va="bottom", ha="left")
    ax.set_xticks(x)
    ax.set_xticklabels(names)
    ax.set_ylabel("Return on programme cost, 10 years (x)")
    ax.set_yscale("symlog", linthresh=1.0)
    ax.set_ylim(0, 60)
    ax.set_yticks([0, 0.5, 1, 2, 5, 10, 20, 50])
    ax.set_yticklabels(["0", "0.5", "1", "2", "5", "10", "20", "50"])
    ax.legend(loc="upper center", fontsize=7.5, ncol=1, bbox_to_anchor=(0.5, 1.16))
    fig.text(0.5, -0.03, "[MODELLED] statutory tax on survey receipts x assumed reach and uptake, 10% discount rate; not a forecast", ha="center", fontsize=8, color=S.GREY)
    return S.save(fig, "fig_5_3_table40_roi_by_stage")
