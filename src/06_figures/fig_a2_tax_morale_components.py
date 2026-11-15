"""Tax-morale components, Afrobarometer Round 8 Tanzania, all adults 18+, survey-weighted with 95% confidence intervals (outputs/tables/tax_morale_components.csv)."""
import _style as S
import matplotlib.pyplot as plt


def make():
    rows = [r for r in S.read_csv(S.paths.TAX_MORALE_COMPONENTS_CSV) if r["level"] == "All adults 18+" and r["pct"] not in ("", None) and r["suppressed"] != "True"]
    rows = sorted(rows, key=lambda r: float(r["pct"]))
    y = range(len(rows))
    v = [float(r["pct"]) for r in rows]
    lo = [float(r["pct"]) - float(r["ci95_low_pct"]) for r in rows]
    hi = [float(r["ci95_high_pct"]) - float(r["pct"]) for r in rows]
    fig, ax = plt.subplots(figsize=(8.4, 0.34 * len(rows) + 1.4))
    ax.barh(list(y), v, color=S.SLATE, height=0.6, xerr=[lo, hi], capsize=3, ecolor=S.GOLD)
    ax.set_yticks(list(y))
    ax.set_yticklabels([r["indicator"].replace("_", " ") for r in rows], fontsize=8)
    ax.set_xlabel("Share of all adults 18+ (%)   estimate and 95% CI")
    ax.set_xlim(0, 100)
    return S.save(fig, "fig_a2_tax_morale_components")
