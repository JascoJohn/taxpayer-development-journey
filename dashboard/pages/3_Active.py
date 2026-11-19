import base64
import os

import plotly.graph_objects as go
import streamlit as st

from tdj_lib.names import N

from tdj_lib.stage_card import show_stage_economics
from tdj_lib.benchmark_adapters import presumptive_caption
from common import (
    inject_base_style, inject_hero_style, stage_header, callout, evidence_tag,
    stage_nav_footer, GREEN, GREEN_DARK, AMBER,
    PipelineData, mzani_adapter,
)

st.set_page_config(page_title=f"Active — {N.active.full}", page_icon="⚖️", layout="wide")
inject_base_style()
stage_header("⚖️", "Active", "Understand", "Calculation", "3")

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")
_PERSONA_PATH = os.path.join(ASSETS_DIR, "active_persona_neema.png")
_TEXTURE_PATH = os.path.join(ASSETS_DIR, "network_texture.png")


@st.cache_data(show_spinner=False)
def _b64_file(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


inject_hero_style(_b64_file(_TEXTURE_PATH) if os.path.exists(_TEXTURE_PATH) else "")

pipeline = PipelineData()

# ---------------------------------------------------------------------------
# Part C: acknowledge a registration handoff from Entry (Ngazi Platform), if present.
# Strictly additive -- nothing below this block changes for a session with
# no incoming flag, and this block touches nothing else on the page (not
# the calculator, the adapter, or the evidence-tier logic).
# ---------------------------------------------------------------------------
if st.session_state.get("ngazi_reg_business_registered"):
    st.markdown(
        '<div class="tdj-note-card"><div class="tdj-note-label">Welcome</div>'
        "<p>You're already in the tax authority's records as an active taxpayer via the Ngazi "
        "Platform. Here's your shared benchmarking reference point.</p></div>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# About this pilot -- same treatment as Seed's "Why this exists" expander
# ---------------------------------------------------------------------------
with st.expander("Why Mzani wa Kodi exists"):
    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown("**The problem**")
        st.write(
            "Neema runs a small tailoring business in Morogoro. Her business "
            "generates regular income, but she's never registered for a TIN. "
            "When a business like hers is assessed, its turnover has to be "
            "estimated — and because she keeps no formal records, that estimate "
            "can look like it depends entirely on the individual officer's "
            "judgement rather than any shared standard. She accepts that tax is "
            "part of doing business; what erodes trust is not knowing how the "
            "number was arrived at."
        )
        st.markdown("**The mechanism**")
        st.write(
            "Perceived procedural fairness drives voluntary compliance — people "
            "accept an obligation more readily when they believe it was reached "
            "transparently and consistently. Mzani wa Kodi doesn't remove officer "
            "discretion or change the tax rules. It gives the officer and the "
            "taxpayer the same evidence-based reference point, so the "
            "conversation shifts from *how much should this person pay* to "
            "*how does this compare to similar businesses.* A trusted assessment "
            "here is also what a taxpayer keeps building a record against — the "
            "same record Enterprise's Ngazi Status is built on next."
        )
    with c2:
        evidence_tag("modelled")
        show_stage_economics(st, pipeline, "active")

# ---------------------------------------------------------------------------
# Hero
# ---------------------------------------------------------------------------
hc1, hc2 = st.columns([2, 1])
with hc1:
    st.markdown(
        """
        <div class="tdj-hero"><div class="tdj-hero-inner">
            <div class="tdj-hero-title">A shared reference point, not a verdict</div>
            <p class="tdj-hero-sub">Mzani wa Kodi doesn't tell anyone what they owe.
            It shows where a business sits next to real, comparable businesses —
            so an assessment can be discussed, not just handed down.</p>
        </div></div>
        """,
        unsafe_allow_html=True,
    )
with hc2:
    if os.path.exists(_PERSONA_PATH):
        st.image(_PERSONA_PATH, width="stretch")

st.markdown(
    '<span class="tdj-demo-note">This tool does not estimate any one business\'s turnover or tax. '
    "The bands below are survey figures for businesses like it: Household Budget Survey 2017/18, "
    "CPI-uprated to 2024, last-month receipts annualised by months operated, owners with receipts. "
    "Farmers and fishers are not covered, and Zanzibar is not covered.</span>",
    unsafe_allow_html=True,
)

st.divider()

# ---------------------------------------------------------------------------
# Framing toggle -- same computation, different audience copy
# ---------------------------------------------------------------------------
viewer = st.radio(
    "Viewing as",
    options=["taxpayer", "officer"],
    format_func=lambda k: {
        "taxpayer": "👤 I'm the taxpayer — how does my business compare?",
        "officer": "🧑‍💼 I'm the officer — reference benchmark for this assessment",
    }[k],
    horizontal=True,
    label_visibility="collapsed",
)

# ---------------------------------------------------------------------------
# Inputs -- real FinScope categories only
# ---------------------------------------------------------------------------
regions_fig = pipeline.active_benchmark_regions()
activities_fig = pipeline.mzani_activities()

if not (regions_fig.available and activities_fig.available):
    st.warning(
        "Benchmark data isn't connected right now "
        f"({regions_fig.note or activities_fig.note}). This page needs "
        "outputs/stats/mzani_turnover.json and data/processed/finscope_active_benchmark.json to be present."
    )
else:
    ic1, ic2 = st.columns(2)
    with ic1:
        region = st.selectbox(
            "Region", regions_fig.value,
            index=regions_fig.value.index("Morogoro") if "Morogoro" in regions_fig.value else 0,
        )
    with ic2:
        activity = st.selectbox(
            "Business activity", activities_fig.value,
            index=activities_fig.value.index("Service providers")
            if "Service providers" in activities_fig.value else 0,
            help="The three activity groups of the Household Budget Survey 2017/18 (traders in "
                 "agricultural products, non-agricultural traders, service providers).",
        )

    result = mzani_adapter(region, activity, pipeline=pipeline)

    st.write("")

    # ---- Insufficient data: a correct, visible output, not a hidden failure --
    if not result.available:
        st.markdown(
            f"""<div class="tdj-insufficient-card">
            <div class="tdj-insufficient-label">Insufficient data for this combination</div>
            <p>{result.note}</p>
            </div>""",
            unsafe_allow_html=True,
        )
        st.caption(
            "This is the honest outcome for a thin cell — not a bug. The officer "
            "should rely on other evidence (records, comparable local knowledge) "
            "for this specific region/sector pairing rather than a guessed figure."
        )

    else:
        # Part C (Legacy build): a minimal, additive completion signal for the
        # journey recap -- set only when a real (non-refused) benchmark
        # result is shown, distinct from just visiting this page.
        st.session_state.active_benchmark_completed = True

        # ---- The turnover band (HBS 2017/18) --------------------------------
        _where = result.geography or region
        headline = (
            f"Businesses like yours in {_where}" if viewer == "taxpayer"
            else f"Comparable businesses: {activity.lower()} in {_where}"
        )
        st.markdown(f"#### {headline}")
        if result.level_label:
            st.info(result.level_label)
        evidence_tag(result.evidence_tier)
        st.caption(result.source_label)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Businesses with receipts in this cell (survey)", result.sample_size)
        m2.metric("Lower quartile, yearly turnover", f"TZS {result.p25_tzs:,.0f}")
        m3.metric("Median yearly turnover", f"TZS {result.median_tzs:,.0f}")
        m4.metric("Upper quartile, yearly turnover", f"TZS {result.p75_tzs:,.0f}")
        if result.low_precision:
            st.caption("⚠ " + result.low_precision_note)

        st.markdown("#### Presumptive tax at these turnovers")
        evidence_tag("computed")

        def _tax(v):
            return "above the presumptive ceiling" if v is None else f"TZS {v:,.0f}"
        t1, t2, t3 = st.columns(3)
        t1.metric("At the lower quartile", _tax(result.tax_p25_tzs))
        t2.metric("At the median", _tax(result.tax_median_tzs))
        t3.metric("At the upper quartile", _tax(result.tax_p75_tzs))
        st.caption(presumptive_caption())
        fig = go.Figure(go.Bar(
            y=["Above TZS 11M", "TZS 4M – 11M", "Up to TZS 4M"],
            x=[result.share_above_11m_pct, result.share_4m_to_11m_pct, result.share_below_4m_pct], orientation="h",
            marker_color=[GREEN_DARK, GREEN, "#9CC79F"],
            text=[f"{v:.1f}%" for v in (result.share_above_11m_pct, result.share_4m_to_11m_pct, result.share_below_4m_pct)], textposition="outside",
        ))
        fig.update_layout(height=200, margin=dict(t=10, b=10, l=10, r=40), xaxis_title="% of businesses like this, by yearly turnover", plot_bgcolor="white")
        st.plotly_chart(fig, width="stretch")

        with st.expander("How is this estimated?"):
            st.write(
                "The turnover of each business is its receipts last month (sales of products, resale goods, construction and services) "
                "times the months it operated in the last 12, raised to 2024 prices with the consumer price index. The band is the "
                "25th, 50th and 75th percentile of the businesses with receipts in this cell, weighted to the survey population. "
                "The presumptive tax is the schedule in force applied to each of those turnovers; it is a reference, not an assessment. "
                "A region is shown only when at least 30 businesses with receipts were surveyed there; otherwise the zone, then the whole Mainland."
            )
            st.markdown("**Not covered:** " + "; ".join(c.rstrip(".") for c in (result.coverage or [])[:2]) + ".")
        if result.formality_label:
            st.caption(result.formality_label)

        st.markdown(
            f'<div class="tdj-note-card">'
            f'<div class="tdj-note-label">What this is — and isn\'t</div>'
            f"<p>{result.taxpayer_note if viewer == 'taxpayer' else result.officer_note} "
            "It is not a calculated income figure, a legal assessment, or a "
            "replacement for the officer's judgement — it's a shared starting "
            "point for a conversation about a fair number.</p></div>",
            unsafe_allow_html=True,
        )
        st.caption(result.note)

        # -------------------------------------------------------------------
        # Part B (Enterprise build): a small, secondary, optional link onward.
        # Strictly additive -- placed only after the benchmark result renders,
        # never in place of it, and touches nothing above (the calculator,
        # the adapter, or the evidence-tier logic are all unchanged).
        # -------------------------------------------------------------------
        st.write("")
        already_active = bool(st.session_state.get("ngazi_reg_business_registered"))
        st.markdown(
            '<div class="tdj-card" style="font-size:0.92rem;">'
            + ("You're already registered as an active taxpayer via the Ngazi "
               "Platform — " if already_active else "")
            + "Already filing and building compliance? See where you stand on "
              "Ngazi.</div>",
            unsafe_allow_html=True,
        )
        st.page_link("pages/4_Enterprise.py", label="See my Ngazi progression →", icon="📈")

st.divider()

# ---------------------------------------------------------------------------
# The fuller picture -- the original real prevalence chart, kept as-is
# ---------------------------------------------------------------------------
with st.expander("See the full region × activity picture"):
    prevalence_regions_fig = pipeline.available_regions()
    if prevalence_regions_fig.available:
        st.caption(
            "Weighted from FinScope Tanzania 2023 microdata. "
            "This is a **prevalence** table — what share of a region's business "
            "owners are in each activity — not a turnover or income table."
        )
        p_region = st.selectbox(
            "Region", prevalence_regions_fig.value,
            index=prevalence_regions_fig.value.index("Dar es Salaam")
            if "Dar es Salaam" in prevalence_regions_fig.value else 0,
            key="prevalence_region",
        )
        prevalence = pipeline.region_activity_prevalence(p_region)
        shown = [a for a in prevalence.value if not prevalence.value[a]["suppressed"]]
        hidden = [a for a in prevalence.value if prevalence.value[a]["suppressed"]]
        activities_sorted = sorted(shown, key=lambda a: -prevalence.value[a]["pct"])
        fig2 = go.Figure(go.Bar(
            y=activities_sorted,
            x=[prevalence.value[a]["pct"] for a in activities_sorted],
            orientation="h", marker_color=GREEN,
            text=[f"{prevalence.value[a]['pct']:.1f}%" for a in activities_sorted],
            textposition="outside",
        ))
        fig2.update_layout(height=240, margin=dict(t=10, b=10), xaxis_title="% of region's business-activity population")
        st.plotly_chart(fig2, width="stretch")
        for a in hidden:
            st.caption(f"{a}: suppressed (fewer than 10 respondents)")
        if activities_sorted:
            smallest_n = min(prevalence.value[a]["respondent_count"] for a in activities_sorted)
            if smallest_n < 15:
                st.caption(
                    f"Small-sample note: the least-represented category shown in {p_region} has "
                    f"only {smallest_n} survey respondents — treat its percentage as "
                    "indicative, not precise."
                )
    else:
        st.caption(f"Not connected: {prevalence_regions_fig.note}")

st.divider()
callout(
    "STRATEGIC CONTRIBUTION",
    "Seed creates familiarity with the tax authority. Entry encourages registration. "
    "<b>Active removes uncertainty at the point where many informal businesses first "
    "experience taxation</b>, ensuring entry into the tax system is guided by "
    "transparent, evidence-based reference points rather than perceived guesswork. "
    "Each benchmarked conversation adds to a defensible, multi-year assessment "
    "history for that taxpayer — the record Enterprise is built on next.",
)

stage_nav_footer("active")
