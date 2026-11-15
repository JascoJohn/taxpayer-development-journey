"""Fig 5.2 data: ten-year digital twin, tax-to-GDP with no new policy and with the policy scenario (MODELLED scenario; outputs/stats/economic_model.json)."""
import _style as S
import matplotlib.pyplot as plt


def make():
    m = S.load_json(S.paths.ECONOMIC_MODEL)
    start = m["base_parameters"]["tax_to_gdp_current"] * 100
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    for key, label, colour, style in (("digital_twin_baseline", "No new policy", S.SLATE, "-"), ("digital_twin_policy", "Policy scenario (Entry + Active)", S.NAVY, "-")):
        ys = m[key]["yearly_states"]
        ax.plot([0] + [y["year"] for y in ys], [start] + [y["tax_to_gdp_pct"] for y in ys], color=colour, linestyle=style, linewidth=2, marker="o", markersize=4, label=label)
    ax.set_xlabel("Year")
    ax.set_ylabel("Tax revenue (% of GDP)")
    ax.set_xticks(range(0, 11))
    ax.legend(loc="upper left")
    ax.text(0.99, 0.03, "MODELLED scenario: not a forecast", transform=ax.transAxes, ha="right", fontsize=8, color=S.GREY)
    return S.save(fig, "fig_5_2_digital_twin")
