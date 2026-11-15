"""Macro gap: Tanzania's tax-to-GDP ratio against the peer countries (World Bank WDI) and the Ministry of Finance medium-term ratio (outputs/stats/macro_inputs.json)."""
import _style as S
import matplotlib.pyplot as plt


def make():
    m = S.load_json(S.paths.MACRO_INPUTS)
    t, b, ctx = m["tanzania"], m["benchmark"], m["context_target"]
    names = ["Tanzania\n(%d)" % t["latest_year"]] + ["%s\n(%d)" % (k, v["year"]) for k, v in sorted(b["peers"].items())] + ["Peer average\n(%d)" % b["year"]]
    vals = [t["tax_to_gdp_pct"]] + [v["tax_to_gdp_pct"] for _, v in sorted(b["peers"].items())] + [b["benchmark_pct"]]
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    bars = ax.bar(range(len(vals)), vals, color=[S.NAVY] + [S.SLATE] * (len(vals) - 2) + [S.GOLD], width=0.6)
    ax.axhline(ctx["tax_to_gdp_pct"], color=S.GREY, linestyle=":", linewidth=1.2, label="Ministry of Finance: %.1f%% in 2026/27 (context, not used in the gap)" % ctx["tax_to_gdp_pct"])
    ax.set_xticks(range(len(vals)))
    ax.set_xticklabels(names, fontsize=8)
    ax.set_ylabel("Tax revenue (% of GDP)")
    ax.set_ylim(0, max(vals) * 1.3)
    S.label_bars(ax, bars, "{:.1f}", "%")
    ax.legend(loc="upper left", fontsize=8)
    fig.text(0.99, -0.03, "gap to the peer average: %.1f percentage points (World Bank WDI)" % abs(b["gap_pp"]), ha="right", fontsize=8, color=S.GREY)
    return S.save(fig, "fig_a5_macro_gap")
