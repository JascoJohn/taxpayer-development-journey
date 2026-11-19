import streamlit as st
import plotly.graph_objects as go
from common import (
    STAGES, NAVY, GOLD, SLATE, CREAM, inject_base_style, callout, evidence_tag,
    EVIDENCE_TIER_HELP, PipelineData,
)

st.set_page_config(
    page_title="The Taxpayer Development Journey — A Behavioral Lifecycle Architecture for Tax Compliance: Evidence from Tanzania",
    page_icon="🧭",
    layout="wide",
)
inject_base_style()

st.title("The Taxpayer Development Journey")
st.caption("A Behavioral Lifecycle Architecture for Tax Compliance: Evidence from Tanzania")

_mm = PipelineData().tin_mobile_money()
if _mm.available:                                        # the respondent count is read from the pipeline output, not typed
    _all_adults = next(r for r in _mm.value["descriptives"]["tin_rate_by_group"] if r["group"].startswith("All adults"))
    _n_finscope = f" (n = {int(_all_adults['n_unweighted_base']):,})"
else:
    _n_finscope = ""
callout(
    "AT A GLANCE",
    "Willingness is already high; the barriers are friction and voice. "
    "Six lifecycle stages — Seed, Entry, Active, Enterprise, Asset, Legacy — "
    "anchored by one connective infrastructure that carries a taxpayer's record "
    f"forward across all six. Evidence base: FinScope Tanzania 2023{_n_finscope}, "
    "the Integrated Labour Force Survey 2024, the Census 2022 10% sample, "
    "published TRA, NBS, Bank of Tanzania and TCRA statistics, and an observational analysis of mobile money and TIN "
    "holding on the real FinScope respondents.",
)

st.markdown("### The Journey")
st.write(
    "The tax authority meets a young mobile money user, a small trader, an informal business "
    "owner, an asset owner, and an heir as though each is a stranger — even when, "
    "over the span of one life, they are the same person. Six real, built "
    "artifacts anchor this journey. Click a stage below to open its tool."
)

# ---- Lifecycle strip --------------------------------------------------------
cols = st.columns(6)
for col, stage in zip(cols, STAGES):
    with col:
        st.page_link(stage["page"], label=f"{stage['icon']}  {stage['label']}", icon=None)
        st.caption(f"*{stage['verb']} → {stage['mechanism']}*")
        st.caption(stage["tool"])

st.divider()

# ---- Portfolio impact chart --------------------------------------------------
st.markdown("### Portfolio-Level Impact")
st.write(
    "In the project's model, the six stages together reach more than any single stage, "
    "because each reaches people the others do not. These are scenario results on assumed "
    "effects, not measured outcomes."
)

_morale = PipelineData().tax_morale_model()
if _morale.available:
    _m = _morale.value
    _best = max(_m["intervention_effects"].values(), key=lambda e: e["new_compliance_prob"])["new_compliance_prob"]
    scenarios = ["Today\n(observed adult TIN rate)", "Best single module\n(presumptive tax simplification)", "Full combined system\n(all six stages)"]
    values = [round(_m["baseline_compliance_probability"] * 100, 2), round(_best * 100, 2), round(_m["combined_intervention_probability"] * 100, 2)]
else:
    scenarios, values = ["Model not connected"], [0]
fig = go.Figure(
    data=[go.Bar(x=scenarios, y=values, marker_color=[SLATE, SLATE, NAVY][:len(values)],
                 text=[f"{v}%" for v in values], textposition="outside")]
)
fig.update_layout(
    yaxis_title="Modelled probability that an adult holds a TIN (%)",
    yaxis_range=[0, max(values) * 1.3 + 1],
    height=380,
    margin=dict(t=20, b=20),
    plot_bgcolor="white",
)
st.plotly_chart(fig, width="stretch")
evidence_tag("modelled")
if _morale.available:
    _m = _morale.value
    st.caption(
        "Modelled probability that an adult holds a TIN under the project's tax morale model, recalibrated so that today's value equals the observed adult TIN rate "
        f"({_m['baseline_compliance_probability'] * 100:.2f}%, FinScope 2023). The intervention effects are assumed uplifts expressed as odds ratios (not measured). "
        f"The combined effect ({_m['combined_intervention_probability'] * 100:.1f}%) sits below the naive sum of the solo effects ({_m['naive_sum_of_solo_effects_pct']:.1f}%), "
        "which is not a meaningful probability at a low baseline."
    )
else:
    st.caption("The tax morale model is not connected right now.")

st.divider()

# ---- Mobile money and TIN holding (observational, real respondents) ----------
st.markdown("### Mobile Money and TIN Holding in Tanzania's Own Data")
if _mm.available:
    _v = _mm.value
    _rates = {r["group"]: r for r in _v["descriptives"]["tin_rate_by_group"]}
    _ame = _v["average_marginal_effect_of_mobile_money"]
    _share = _v["descriptives"]["share_of_tin_holders_using_mobile_money"]
    c1, c2, c3 = st.columns(3)
    with c1:
        evidence_tag("computed")
        _u, _n = _rates["Mobile-money users"], _rates["Non-users of mobile money"]
        st.metric("TIN holding: users vs non-users",
                  f"{_u['tin_rate_pct']:.1f}% vs {_n['tin_rate_pct']:.2f}%",
                  help="Share of adults holding a TIN among mobile-money users and non-users (survey-weighted). "
                       "The non-user figure rests on fewer than 10 respondents holding a TIN: low precision.")
    with c2:
        evidence_tag("computed")
        _lo, _hi = _ame["ci95_percentage_points"]
        st.metric("Association, adjusted (average marginal effect)", f"+{_ame['percentage_points']:.1f} pp",
                  delta=f"95% CI {_lo:.1f} to {_hi:.1f}", delta_color="off",
                  help="Difference in the predicted probability of holding a TIN between mobile-money use and non-use, averaged "
                       "over respondents, from a survey-weighted Firth-penalised logistic regression (age, sex, residence, "
                       "education, income source, region). Observational, cross-sectional; not a causal estimate.")
    with c3:
        evidence_tag("computed")
        st.metric("TIN holders who use mobile money", f"{_share['share_of_tin_holders_using_mm_pct']:.1f}%",
                  help="Weighted share of adult TIN holders who use mobile money.")
    st.caption(
        f"Observational, cross-sectional association from FinScope Tanzania 2023{_n_finscope}; not a causal "
        "estimate. Mobile-money users differ from non-users in ways the survey does not fully measure."
    )
else:
    st.info(f"The mobile-money and TIN analysis is not connected right now ({_mm.note}).")

st.divider()

# ---- Targeting: who to reach first, with intervals ---------------------------
st.markdown("### Who to Reach First: Targeting With Intervals")
_tb = PipelineData().targeting_bootstrap()
if _tb.available:
    _b = _tb.value
    _reg, _sur = _b["models"]["register"], _b["models"]["survey"]
    _leak, _lozo = _b["leakage_adjusted_auc"], _b["leave_one_zone_out"]
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        evidence_tag("computed")
        k1.metric("Register data alone (age, sex, region, urban/rural)", f"{_reg['multiplier']['median']:.1f}×",
                  delta=f"95% interval {_reg['multiplier']['ci95'][0]:.1f}–{_reg['multiplier']['ci95'][1]:.1f}", delta_color="off",
                  help="Top-decile Entry-age adults versus the Entry average, modelled TIN holding, respondent bootstrap refitting the model in every replicate. A ratio of model predictions, not a causal effect.")
    with k2:
        evidence_tag("computed")
        k2.metric("Survey model (all questionnaire items)", f"{_sur['multiplier']['median']:.1f}×",
                  delta=f"95% interval {_sur['multiplier']['ci95'][0]:.1f}–{_sur['multiplier']['ci95'][1]:.1f}", delta_color="off",
                  help="Same construction with the full FinScope feature set; it uses items a tax authority does not hold, so it is an upper reference.")
    with k3:
        evidence_tag("computed")
        k3.metric("Survey model AUC without formal-product items", f"{_leak['without_formal_product_columns']['held_out_auc_weighted']:.3f}",
                  help="Held-out weighted ROC-AUC after dropping every banking, credit, insurance, pension, vehicle, land-title, securities and formal-employment column (%d source columns)." % _leak["source_columns_dropped"])
    with k4:
        evidence_tag("computed")
        k4.metric("Register-only AUC on a zone it never saw", f"{_lozo['pooled_loZo_auc_weighted']:.3f}",
                  delta=f"by zone {_lozo['range_by_zone'][0]:.2f}–{_lozo['range_by_zone'][1]:.2f}", delta_color="off",
                  help="Leave-one-zone-out, nine zones; the held-out zone gets no region effect. Zones with few TIN holders are noisy.")
    _pair = _b["dashboard_pair_per_10000_reached"]["register_only"]
    st.caption(
        f"Per 10,000 Entry-age adults reached, register data alone would find about {_pair['targeted']['median']:.0f} TIN holders (interval {_pair['targeted']['ci95'][0]:.0f}–{_pair['targeted']['ci95'][1]:.0f}) "
        f"against about {_pair['random']:.0f} by random selection. The observed top-decile ratio is not shown: too few Entry-age TIN holders for it to be published as a number. "
        "Modelled from FinScope Tanzania 2023; not a measured campaign result."
    )
else:
    st.info(f"The targeting intervals are not connected right now ({_tb.note}).")

st.caption(EVIDENCE_TIER_HELP)

st.divider()
st.markdown(
    f"<p style='color:{SLATE}; font-size:0.85rem;'>Most stage pages (Entry, Active, "
    "Enterprise, Legacy) read live cost/revenue/model figures from this project's own "
    "pipeline (see the README) rather than fixed numbers — each page captions exactly "
    "which of its figures are COMPUTED, MODELLED or CITED and which remain ILLUSTRATIVE, and why.</p>",
    unsafe_allow_html=True,
)
