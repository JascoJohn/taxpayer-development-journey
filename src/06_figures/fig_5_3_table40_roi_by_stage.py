"""Table 40 as a figure: return on programme cost (discounted revenue / cost) by stage, median and 80% interval, over 10 years (signed-off headline) and 20 years (age-earnings path)."""
import _style as S
import matplotlib.pyplot as plt
import numpy as np


def make():
    d = S.load_json(S.paths.STAGE_ECONOMICS)
    stages = ["entry", "active", "enterprise", "legacy"]
    label = {"entry": "Entry", "active": "Active", "enterprise": "Enterprise", "legacy": "Legacy"}
    r10 = [d["stages"][s]["monte_carlo_at_10pct"]["roi"] for s in stages] + [d["portfolio"]["monte_carlo_at_10pct"]["roi"]]
    r20 = [d["stages"][s]["variants"]["horizon_20_aged"]["0.1"]["roi"] for s in stages] + [d["portfolio"]["variants"]["horizon_20_aged"]["0.1"]["roi"]]
    names = [label[s] for s in stages] + ["Portfolio\n(without Asset)"]
    x = np.arange(len(names))
    fig, ax = plt.subplots(figsize=(8.8, 5.0))
    for off, r, colour, lab in ((-0.18, r10, S.NAVY, "10 years (signed-off headline)"), (0.18, r20, S.GOLD, "20 years (age-earnings path)")):
        med = np.array([v["median"] for v in r])
        lo = med - np.array([v["p10"] for v in r])
        hi = np.array([v["p90"] for v in r]) - med
        ax.errorbar(x + off, med, yerr=[lo, hi], fmt="o", color=colour, capsize=4, markersize=6, linewidth=1.4, label=lab)
    ax.axhline(1.0, color=S.RED, linestyle="--", linewidth=1.1)
    ax.text(-0.45, 1.06, "break-even (ROI = 1)", color=S.RED, fontsize=8, va="bottom", ha="left")
    ax.set_xticks(x)
    ax.set_xticklabels(names)
    ax.set_ylabel("Return on programme cost (x): median, 80% interval")
    ax.set_yscale("symlog", linthresh=1.0)
    ax.set_ylim(0, 60)
    ax.set_yticks([0, 0.5, 1, 2, 5, 10, 20, 50])
    ax.set_yticklabels(["0", "0.5", "1", "2", "5", "10", "20", "50"])
    ax.legend(loc="upper center", fontsize=8, ncol=2, bbox_to_anchor=(0.5, 1.10))
    fig.text(0.5, -0.03, "MODELLED: statutory tax on survey earnings x assumed reach and uptake, 10% discount rate", ha="center", fontsize=8, color=S.GREY)
    return S.save(fig, "fig_5_3_table40_roi_by_stage")
