"""Fig 5.1 data: modelled probability that an adult reports a TIN, if every adult were reached: today (the observed rate), each intervention alone, all combined (tax-morale model, outputs/stats/economic_model.json)."""
import textwrap

import _style as S
import matplotlib.pyplot as plt

NAMES = {"USSD_registration_nudge": "USSD TIN nudge", "civic_tax_education": "Civic tax education", "mobile_money_TIN_bridge": "Mobile-money TIN bridge",
         "community_compliance_norms": "Community compliance norms", "visible_tax_returns": "Visible tax returns", "presumptive_tax_simplification": "Presumptive tax simplification"}


def make():
    m = S.load_json(S.paths.ECONOMIC_MODEL)["tax_morale_model"]
    base = m["baseline_compliance_probability"] * 100
    solo = sorted(((NAMES[k], v["new_compliance_prob"] * 100) for k, v in m["intervention_effects"].items()), key=lambda x: x[1])
    labels = [n for n, _ in solo] + ["All six combined"]
    vals = [v for _, v in solo] + [m["combined_intervention_probability"] * 100]
    fig, ax = plt.subplots(figsize=(8.6, 4.8))
    bars = ax.bar(range(len(vals)), vals, color=[S.SLATE] * len(solo) + [S.NAVY], width=0.62)
    ax.axhline(base, color=S.GOLD, linestyle="--", linewidth=1.3, label="Today: survey-reported adult TIN rate (%.2f%%)" % base)
    ax.axhline(m["naive_sum_of_solo_effects_pct"], color=S.GREY, linestyle=":", linewidth=1.1, label="Today's rate plus the six separate gains (%.2f%%)" % m["naive_sum_of_solo_effects_pct"])
    ax.set_xticks(range(len(vals)))
    ax.set_xticklabels(["\n".join(textwrap.wrap(l, 13, break_long_words=False)) for l in labels], fontsize=8)
    ax.set_ylabel("Modelled probability that an adult reports a TIN (%),\nif every adult were reached")
    ax.set_ylim(0, max(max(vals), m["naive_sum_of_solo_effects_pct"]) * 1.25)
    S.label_bars(ax, bars, "{:.1f}", "%")
    ax.legend(loc="upper left", fontsize=8)
    fig.text(0.99, -0.03, "MODELLED: assumed uplifts expressed as odds ratios", ha="right", fontsize=8, color=S.GREY)
    return S.save(fig, "fig_5_1_modelled_compliance")
