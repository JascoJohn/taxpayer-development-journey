"""Figure 1.1, macro gap, LIKE FOR LIKE: Tanzania's 2023 tax-to-GDP ratio against the peers' 2023 ratios and their average (World Bank WDI), the gap in percentage points and in TZS, with Tanzania's 2024 value as a
separate marker (the latest year, not comparable with the peers' 2023). The Ministry of Finance medium-term ratio is context only (outputs/stats/macro_inputs.json)."""
import _style as S
import matplotlib.pyplot as plt


def make():
    m = S.load_json(S.paths.MACRO_INPUTS)
    t, b, ctx = m["tanzania"], m["benchmark"], m["context_target"]
    names = ["Tanzania\n(%d)" % b["common_year_all_five"]] + ["%s\n(%d)" % (k, v["year"]) for k, v in sorted(b["peers"].items())] + ["Peer average\n(%d)" % b["year"]]
    vals = [b["tanzania_same_year_pct"]] + [v["tax_to_gdp_pct"] for _, v in sorted(b["peers"].items())] + [b["benchmark_pct"]]
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    bars = ax.bar(range(len(vals)), vals, color=[S.NAVY] + [S.SLATE] * (len(vals) - 2) + [S.GOLD], width=0.6)
    ax.axhline(ctx["tax_to_gdp_pct"], color=S.GREY, linestyle=":", linewidth=1.2, label="Ministry of Finance: %.1f%% in 2026/27 (context, not used in the gap)" % ctx["tax_to_gdp_pct"])
    ax.plot([0.42], [t["tax_to_gdp_pct"]], marker="D", color=S.NAVY, markerfacecolor="white", markersize=8, linestyle="none", zorder=5, label="Tanzania %d: %.2f%% (latest year; peers have no %d value)" % (t["latest_year"], t["tax_to_gdp_pct"], t["latest_year"]))
    ax.set_xticks(range(len(vals)))
    ax.set_xticklabels(names, fontsize=8)
    ax.set_ylabel("Tax revenue (% of GDP)")
    ax.set_ylim(0, max(vals) * 1.3)
    S.label_bars(ax, bars, "{:.2f}", "%")
    ax.legend(loc="upper left", fontsize=8)
    fig.text(0.99, -0.03, "gap to the peer average in %d: %.2f percentage points, about TZS %.2f trillion of %d GDP" % (b["common_year_all_five"], abs(b["gap_pp"]), b["revenue_gap_tzs"] / 1e12, b["common_year_all_five"]), ha="right", fontsize=8, color=S.GREY)
    fig.text(0.01, 1.02, "[COMPUTED from CITED World Bank WDI series]", ha="left", fontsize=9, color=S.GREY)
    return S.save(fig, "fig_a5_macro_gap")
