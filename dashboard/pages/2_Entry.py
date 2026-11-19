import base64
import os

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from tdj_lib.names import N

from tdj_lib.stage_card import show_stage_economics
from common import (
    inject_base_style, inject_hero_style, stage_header, callout, evidence_tag,
    stage_nav_footer, GREEN,
    PipelineData, demo_safety_banner, looks_like_nida, looks_like_phone,
)

st.set_page_config(page_title=f"Entry — {N.entry.full}", page_icon="🚪", layout="wide")
inject_base_style()
stage_header("🚪", "Entry", "Join", "Targeting", "2")

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")
_PERSONA_PATH = os.path.join(ASSETS_DIR, "entry_persona_juma.png")
_TEXTURE_PATH = os.path.join(ASSETS_DIR, "network_texture.png")


@st.cache_data(show_spinner=False)
def _b64_file(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


inject_hero_style(_b64_file(_TEXTURE_PATH) if os.path.exists(_TEXTURE_PATH) else "")

pipeline = PipelineData()

# ---------------------------------------------------------------------------
# A3: recognize a handoff from Seed, without requiring one
# ---------------------------------------------------------------------------
came_from_seed = st.session_state.get("seed_handoff_complete", False)
seed_nida = st.session_state.get("seed_handoff_nida", "")

# ---------------------------------------------------------------------------
# About this pilot -- same treatment as Seed and Active
# ---------------------------------------------------------------------------
with st.expander("Why Entry exists"):
    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown("**The problem**")
        st.write(
            "Juma is 19, runs a phone-repair stall in Mwanza, and has used mobile "
            "money since he was 16. He's already participating in the economy — "
            "receiving customer payments, running a small operation — but to the tax authority "
            "he doesn't exist yet: no TIN, no registration. Getting one feels like "
            "an extra task competing against unfamiliar paperwork and time he "
            "doesn't have."
        )
        st.markdown("**The mechanism**")
        st.write(
            f"{N.entry.swahili} addresses this from two directions. **Targeting** "
            "answers *who* the tax authority should reach first when outreach budget is "
            "limited. **Registration on the Ngazi Platform** answers what happens *once someone "
            "is reached* — in the pilot the invitation is an SMS with a link to this "
            "registration channel, which needs no cost-sharing with mobile operators; "
            "USSD becomes the channel for scaling up once an agreement with operators "
            "is in place. The prototype demonstrates the registration step within a session."
        )
    with c2:
        evidence_tag("modelled")
        show_stage_economics(st, pipeline, "entry")

# ---------------------------------------------------------------------------
# Hero
# ---------------------------------------------------------------------------
hc1, hc2 = st.columns([2, 1])
with hc1:
    st.markdown(
        """
        <div class="tdj-hero"><div class="tdj-hero-inner">
            <div class="tdj-hero-title">Two ways in: get found, or come in yourself</div>
            <p class="tdj-hero-sub">Below: the real model that decides who the tax authority should
            reach first, and registration on the Ngazi Platform — a way to join the tax authority's records the
            moment someone is ready, no phone channel required.</p>
        </div></div>
        """,
        unsafe_allow_html=True,
    )
with hc2:
    if os.path.exists(_PERSONA_PATH):
        st.image(_PERSONA_PATH, width="stretch")

if came_from_seed:
    st.markdown(
        '<div class="tdj-note-card"><div class="tdj-note-label">Welcome back</div>'
        "<p>You completed Michezo ya Kodi and confirmed your age. Let's get you "
        "set up — registration on the Ngazi Platform below already has your NIDA number "
        "ready.</p></div>",
        unsafe_allow_html=True,
    )

st.divider()

# ---------------------------------------------------------------------------
# Section 1: Targeting
# ---------------------------------------------------------------------------
st.markdown("## Targeting: who to reach first")

targeting = pipeline.targeting_model()
SUPPRESSED_TEXT = "suppressed (fewer than 10 respondents)"
EDUCATION_LEVELS = ["No formal education", "Some primary", "Primary completed", "Some secondary or O-level", "A-level, university or higher"]

if targeting.available:
    _tm = targeting.value
    _t = _tm["held_out_test"]["logistic_regression"]
    st.caption(
        f"Trained on {_tm['split']['train'] + _tm['split']['test']:,} real adult respondents of FinScope Tanzania 2023 "
        f"(outcome: reports holding a Tax ID Number, a survey-reported measure; survey weights used in fitting and evaluation). Held-out test ROC-AUC "
        f"{_t['roc_auc_weighted']:.2f} (weighted), {_t['roc_auc_unweighted']:.2f} (unweighted). "
        "An observational ranking by how closely a profile matches adults who report a TIN today: it is not a causal "
        "estimate and has not been checked against tax authority registration records."
    )
    _tbf = pipeline.targeting_bootstrap()
    if _tbf.available:
        _tb = _tbf.value
        _lk, _lz = _tb["leakage_adjusted_auc"], _tb["leave_one_zone_out"]
        st.caption(
            f"Without every banking, credit, insurance, pension, vehicle, land-title, securities and formal-employment item the held-out weighted AUC is "
            f"{_lk['without_formal_product_columns']['held_out_auc_weighted']:.3f}, so it is not carried by those items. For the register-only model (age, sex, region, urban/rural) "
            f"the AUC on a zone the model never saw is {_lz['pooled_loZo_auc_weighted']:.3f} pooled ({_lz['range_by_zone'][0]:.2f}–{_lz['range_by_zone'][1]:.2f} by zone; zones with few TIN holders are noisy)."
        )
else:
    st.caption(
        "The real-data targeting model is not connected (targeting_model.json missing); nothing is shown "
        f"on this tab ({targeting.note})."
    )

tab_individual, tab_scale = st.tabs(["🎯 Score an individual", "📊 Targeting at scale"])

with tab_individual:
    if targeting.available:
        card = _tm["scoring_card"]
        evidence_tag("computed")
        st.write(
            "A small, interpretable scoring card fitted on the same real respondents (age, residence, business ownership, "
            "mobile money and education). It returns a predicted probability of reporting a TIN for a profile like this one. "
            f"(The full model uses {_tm['features']['n_encoded_features']:,} survey features; the card is a reduced version "
            "meant for explanation.)"
        )
        c1, c2 = st.columns(2)
        with c1:
            urban = st.radio("Residence", ["Rural", "Urban"], index=1, horizontal=True)
            business = st.radio("Owns a business", ["No", "Yes"], index=1, horizontal=True)
            mobile_money = st.radio("Active mobile money use", ["No", "Yes"], index=1, horizontal=True)
        with c2:
            education = st.select_slider("Education", EDUCATION_LEVELS, value="Primary completed")
            age = st.slider("Age", 16, 90, 26)

        coef, a10 = card["coefficients"], (age - 40) / 10.0
        z = (card["intercept"] + coef["age_per_10_years"] * a10 + coef["age_squared_per_100"] * a10 ** 2
             + coef["urban_residence"] * (urban == "Urban") + coef["business_owner"] * (business == "Yes")
             + coef["mobile_money"] * (mobile_money == "Yes") + coef["education_level_0_to_4"] * EDUCATION_LEVELS.index(education))
        prob = 100.0 / (1.0 + float(np.exp(-z)))

        gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=round(prob, 1),
            number={"suffix": "%"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": GREEN},
                "steps": [
                    {"range": [0, 5], "color": "#EFEFEF"},
                    {"range": [5, 25], "color": "#D8E7D8"},
                    {"range": [25, 100], "color": "#9CC79F"},
                ],
            },
            title={"text": "Predicted probability of reporting a TIN"},
        ))
        gauge.update_layout(height=280, margin=dict(t=40, b=10))
        st.plotly_chart(gauge, width="stretch")
        st.caption(
            f"{card['fit']}; in-sample weighted ROC-AUC {card['in_sample_weighted_roc_auc']:.2f}. About "
            f"{_tm['out_of_fold_all_adults']['base_rate_weighted'] * 100:.1f}% of Tanzanian adults report holding a TIN. "
            "The probability describes how common survey-reported TINs are among adults with this profile; it is an association, not an "
            "effect of any action on the person."
        )
    else:
        st.warning(f"Individual scoring isn't available ({targeting.note}).")

with tab_scale:
    seg_fig = pipeline.targeting_deciles()
    if not targeting.available or not seg_fig.available:
        st.warning(f"Population-level data isn't connected right now ({seg_fig.note or targeting.note}).")
    else:
        seg = seg_fig.value
        deciles = seg["deciles"]
        mult = seg["targeting_multiplier"]
        evidence_tag("modelled")
        st.caption(
            f"The Entry segment ({seg['definition'].split(' (')[0].split(';')[0]}; {seg['n_unweighted']:,} respondents) is ranked by the full "
            "model's out-of-fold predicted propensity and split into ten equal-population groups (decile 1 = highest). "
            "Only group-level aggregates are published, never individual scores. A modelled comparison, not a measured "
            "outcome from an actual campaign."
        )
        usable = [d for d in deciles if not d.get("suppressed")]
        if len(usable) < len(deciles):
            st.warning(f"{len(deciles) - len(usable)} decile(s) {SUPPRESSED_TEXT}; the comparison uses the others only.")
        k = st.slider("Share of the Entry segment you can reach this quarter (top-scoring first)", 10, 100, 10, step=10, format="%d%%") // 10
        top = [d for d in usable if d["decile"] <= k]
        wt_all = sum(d["weighted_population"] for d in usable)
        wt_top = sum(d["weighted_population"] for d in top)
        mean_all = sum(d["weighted_population"] * d["mean_predicted_pct"] for d in usable) / wt_all / 100 if wt_all else 0.0
        mean_top = sum(d["weighted_population"] * d["mean_predicted_pct"] for d in top) / wt_top / 100 if wt_top else 0.0
        reach = 10_000
        expected_targeted, expected_random = reach * mean_top, reach * mean_all
        multiple = (mean_top / mean_all) if mean_all else 0.0

        m1, m2, m3 = st.columns(3)
        m1.metric(f"Targeted (per {reach:,} people reached)", f"~{expected_targeted:,.0f} adults reporting a TIN")
        m2.metric(f"Random selection (per {reach:,} people)", f"~{expected_random:,.0f} adults reporting a TIN")
        m3.metric("Targeting multiplier", f"{multiple:.1f}×",
                  help="Mean predicted propensity of the reached share divided by the mean for the whole Entry segment")

        cmp_fig = go.Figure(go.Bar(
            x=["Random selection", "Targeted (top-scoring)"],
            y=[expected_random, expected_targeted],
            marker_color=["#B9B9B9", GREEN],
            text=[f"~{expected_random:,.0f}", f"~{expected_targeted:,.0f}"],
            textposition="outside",
        ))
        cmp_fig.update_layout(
            height=280, margin=dict(t=20, b=10),
            yaxis_title="Modelled adults reporting a TIN per 10,000 reached", plot_bgcolor="white",
        )
        st.plotly_chart(cmp_fig, width="stretch")

        def _mix(rows, key):
            w = sum(d["weighted_population"] for d in rows)
            return sum(d["weighted_population"] * d[key] for d in rows) / w if w else float("nan")

        st.markdown("#### Who gets contacted first")
        w1, w2, w3 = st.columns(3)
        w1.metric("Urban", f"{_mix(top, 'urban_pct'):.0f}%", help=f"{_mix(usable, 'urban_pct'):.0f}% across the Entry segment")
        w2.metric("Business owners", f"{_mix(top, 'business_owner_pct'):.0f}%", help=f"{_mix(usable, 'business_owner_pct'):.0f}% across the Entry segment")
        w3.metric("Mobile money users", f"{_mix(top, 'mobile_money_pct'):.0f}%", help=f"{_mix(usable, 'mobile_money_pct'):.0f}% across the Entry segment")

        _cal = mult.get("entry_calibration")
        if _cal:
            _raw = _cal.get("uncalibrated_mean_predicted_tin_rate_pct")
            st.caption(
                "Calibration note: the model is fitted on all adults and over-predicts for this age group"
                + (f" (raw mean prediction {_raw:.1f}%)" if _raw is not None else "")
                + f". Predicted levels are recalibrated within the age band so that the mean predicted TIN rate ({_cal['mean_predicted_tin_rate_pct']:.2f}%) "
                f"equals the rate observed in the survey ({_cal['observed_tin_rate_pct']:.2f}%, a low-precision figure resting on very few "
                "respondents reporting a TIN); the ranking is unchanged, so the multiplier is almost unaffected. The counts above are modelled, not observed."
            )

        with st.expander("Decile table (aggregates)"):
            rows = []
            for d in deciles:
                if d.get("suppressed"):
                    rows.append({"Decile": d["decile"], "Respondents": SUPPRESSED_TEXT, "Mean predicted TIN %": "", "Observed TIN %": ""})
                    continue
                mark = " †" if d.get("low_precision") else ""
                rows.append({"Decile": d["decile"], "Respondents": d["n_unweighted"],
                             "Mean predicted TIN %": f"{d['mean_predicted_pct']:.1f}",
                             "Observed TIN %": f"{d['observed_tin_rate_pct']:.1f}{mark}"})
            st.dataframe(rows, hide_index=True, width="stretch")
            _tbs = pipeline.targeting_bootstrap()
            if _tbs.available:
                _sv, _rg = _tbs.value["models"]["survey"], _tbs.value["models"]["register"]
                _pr = _tbs.value["dashboard_pair_per_10000_reached"]["register_only"]
                st.caption("† low precision: fewer than 10 respondents reporting a TIN among the unweighted respondents of that decile. "
                           f"Multiplier at the top 10%, refit in every bootstrap replicate: survey model {_sv['multiplier']['median']:.1f}× "
                           f"(95% interval {_sv['multiplier']['ci95'][0]:.1f}–{_sv['multiplier']['ci95'][1]:.1f}); register data alone (what a tax authority holds) {_rg['multiplier']['median']:.1f}× "
                           f"(95% interval {_rg['multiplier']['ci95'][0]:.1f}–{_rg['multiplier']['ci95'][1]:.1f}), about {_pr['targeted']['median']:.0f} against {_pr['random']:.0f} TIN holders per 10,000 reached. "
                           "The observed top-decile ratio is not shown: too few Entry-age respondents report a TIN for it to be published as a number.")
            else:
                st.caption("† low precision: fewer than 10 respondents reporting a TIN among the unweighted respondents of that decile. The bootstrap intervals are not connected (run `python run_all.py --full-bootstrap`).")

        st.caption(
            "\"TIN likelihood\" here means how closely someone's profile matches people who already report a TIN in the "
            "survey, used as a targeting signal — not a causal claim that contacting a given person will cause them to register."
        )

st.divider()

# ---------------------------------------------------------------------------
# Section 2: Registration on the Ngazi Platform
# ---------------------------------------------------------------------------
st.markdown("## Registration on the Ngazi Platform")
st.caption(
    "Reserve your place in the tax authority's records today — without waiting for a "
    "phone-based channel that doesn't exist yet."
)

_ngazi_reg_defaults = {
    "ngazi_reg_screen": "intro",
    "ngazi_reg_registered": False,
    "ngazi_reg_business_registered": False,
}
for k, v in _ngazi_reg_defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

screen = st.session_state.ngazi_reg_screen

if screen == "intro":
    st.markdown(
        '<div class="tdj-card">Like Juma, you might already be economically active — '
        "The tax authority just hasn't seen you yet. Registration on the Ngazi Platform adds you to its records "
        "and reserves your place in the tax base today. It doesn't replace an "
        "eventual in-person step — it just turns that step into a short visit for "
        "verification and document submission, instead of registration from "
        "scratch.</div>",
        unsafe_allow_html=True,
    )
    if st.button("Get started →", key="ngazi_reg_start", type="primary"):
        st.session_state.ngazi_reg_screen = "form"
        st.rerun()

elif screen == "form":
    demo_safety_banner()
    regions_fig = pipeline.active_benchmark_regions()
    region_options = regions_fig.value if regions_fig.available else [
        "Dar es Salaam", "Mwanza", "Arusha", "Dodoma", "Mbeya", "Morogoro",
    ]

    f1, f2 = st.columns(2)
    with f1:
        name = st.text_input("Full name", key="ngazi_reg_name_field")
        nida = st.text_input(
            "NIDA number", value=seed_nida, key="ngazi_reg_nida_field",
            help="20 digits — format checked only, not verified against NIDA.",
        )
        if nida:
            st.caption("✓ Format accepted (not verified)" if looks_like_nida(nida)
                       else "Doesn't look like a 20-digit NIDA number yet.")
    with f2:
        phone = st.text_input(
            "Phone number", key="ngazi_reg_phone_field",
            help="e.g. 07XXXXXXXX — format checked only, not verified with a telecom.",
        )
        if phone:
            st.caption("✓ Format accepted (not verified)" if looks_like_phone(phone)
                       else "Doesn't look like a Tanzanian phone number yet.")
        region = st.selectbox("Region", region_options, key="ngazi_reg_region_field")

    if st.button("Join the tax authority's records", key="ngazi_reg_submit", type="primary"):
        missing = []
        if not name.strip():
            missing.append("full name")
        if not looks_like_nida(nida):
            missing.append("a 20-digit NIDA number")
        if not looks_like_phone(phone):
            missing.append("a valid-looking phone number")
        if missing:
            st.warning("Still needed: " + ", ".join(missing) + ".")
        else:
            st.session_state.ngazi_reg_name = name.strip()
            st.session_state.ngazi_reg_nida = nida
            st.session_state.ngazi_reg_phone = phone
            st.session_state.ngazi_reg_region = region
            st.session_state.ngazi_reg_registered = True
            st.session_state.ngazi_reg_screen = "confirmation"
            st.rerun()

elif screen == "confirmation":
    name = st.session_state.get("ngazi_reg_name", "")
    st.markdown(
        f'<div class="tdj-card"><b>You\'re now in the tax authority\'s records as a prospective '
        f"taxpayer{', ' + name if name else ''}.</b><br>You are not yet a fully "
        "registered taxpayer, and nothing has been verified — this reserves your "
        "place. The one remaining real-world step is a short tax office visit for "
        "verification and document submission, not a repeat of registration from "
        "scratch.</div>",
        unsafe_allow_html=True,
    )

    st.divider()
    st.markdown("#### Already running a business?")
    st.write(
        "Add your business registration number, license, or permit — completely "
        "optional, and you can finish here without it."
    )
    demo_safety_banner()
    biz = st.text_input("Business registration number, license, or permit", key="ngazi_reg_biz_field")
    if st.button("Add business details", key="ngazi_reg_biz_submit"):
        if biz.strip():
            st.session_state.ngazi_reg_business_number = biz.strip()
            st.session_state.ngazi_reg_business_registered = True
            st.rerun()

    if st.session_state.ngazi_reg_business_registered:
        st.markdown(
            '<div class="tdj-note-card"><div class="tdj-note-label">You\'re already '
            'an active taxpayer</div><p>Here\'s your benchmarking tool — the same '
            "shared reference point Mzani wa Kodi gives every officer and taxpayer "
            "at the Active stage.</p></div>",
            unsafe_allow_html=True,
        )
        st.page_link("pages/3_Active.py", label="Go to Mzani wa Kodi →", icon="⚖️")

    st.write("")
    if st.button("↺ Start a new demo registration", key="ngazi_reg_reset"):
        for k in list(_ngazi_reg_defaults) + [
            "ngazi_reg_name", "ngazi_reg_nida", "ngazi_reg_phone", "ngazi_reg_region",
            "ngazi_reg_business_number",
        ]:
            st.session_state.pop(k, None)
        st.rerun()

st.divider()
callout(
    "STRATEGIC CONTRIBUTION",
    "Seed introduces future taxpayers to the tax authority. Entry converts that familiarity into "
    "the first formal interaction with the tax system — targeting "
    "decides who to reach, and registration on the Ngazi Platform gives them something to do the "
    "moment they're reached, without waiting on a phone channel that was never "
    "built. Someone who registers a business here arrives at Active already known "
    "to the tax authority, not as a stranger.",
)

stage_nav_footer("entry")
