"""Figure 5.2: reach scenarios of the four stage tools (Entry, Active, Enterprise, Legacy), replacing the retired digital twin. Two panels: incremental revenue (TZS) and active payers owing tax, years 1-10,
at Table 5.1's reach and at 10, 25 and 50% reach; lines are medians, bands the 80% interval. The TRA registration trend is its OWN dashed line (it happens whatever the tools do; it is not added to the tools).
Both axes are logarithmic because the trend is far larger than the tools' effect. No tax-to-GDP chart. Source: outputs/stats/reach_scenarios.json (central income basis, stage mapping B)."""
import _style as S
import matplotlib.pyplot as plt
import numpy as np

SCEN = [("table5_1_reach", "Table 5.1 reach", S.GREY), ("reach_10pct", "10% reach", S.GOLD), ("reach_25pct", "25% reach", S.SLATE), ("reach_50pct", "50% reach", S.NAVY)]


def make():
    d = S.load_json(S.paths.REACH_SCENARIOS)
    rows = [r for r in d["by_year"] if r["set"] == "four_levers"]
    years = np.arange(1, 11)
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 4.8))
    floor = {"incremental_revenue_tzs": 1e6, "active_payers_owing_tax": 1.0}
    for ax, key, ylabel, trend_key, unit in ((axes[0], "incremental_revenue_tzs", "Incremental revenue (TZS a year)", "trend_revenue_tzs", "TZS"),
                                             (axes[1], "active_payers_owing_tax", "Active payers owing tax (persons)", "trend_active_payers_owing_tax", "persons")):
        for name, lab, col in SCEN:
            r = sorted((x for x in rows if x["scenario"] == name), key=lambda x: x["year"])
            med = np.maximum([x[key + "_median"] for x in r], floor[key])
            lo = np.maximum([x[key + "_p10"] for x in r], floor[key])
            hi = np.maximum([x[key + "_p90"] for x in r], floor[key])
            ax.fill_between(years, lo, hi, color=col, alpha=0.15, linewidth=0)
            ax.plot(years, med, color=col, linewidth=2.0, label=lab)
        r = sorted((x for x in rows if x["scenario"] == "table5_1_reach"), key=lambda x: x["year"])
        ax.plot(years, [x[trend_key + "_median"] for x in r], color=S.RED, linestyle="--", linewidth=1.8, label="TRA registration trend (its own line)")
        ax.set_yscale("log")
        ax.set_xticks(years)
        ax.set_xlabel("Year")
        ax.set_ylabel(ylabel)
        ax.grid(True, which="major", alpha=0.3)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=5, fontsize=8, bbox_to_anchor=(0.5, -0.06))
    fig.text(0.5, 1.02, "[MODELLED] four stage tools, central income basis (HBS 2017/18), median and 80% band; constant 2024 TZS; not a forecast", ha="center", color=S.GREY, fontsize=9)
    fig.tight_layout()
    return S.save(fig, "fig_5_2_reach_scenarios")
