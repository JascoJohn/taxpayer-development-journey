import json

import plotly.graph_objects as go
import streamlit as st

from tdj_lib import scenario_lab as sl
from tdj_lib.charts import themed
from tdj_lib.names import N
from tdj_lib.stage_card import _tzs
from tdj_lib.styling import CHART_GREEN, CHART_NAVY
from common import inject_base_style, evidence_tag, callout, PipelineData

st.set_page_config(page_title="Scenario lab — The Taxpayer Development Journey", page_icon="🧪", layout="wide")
inject_base_style()
st.markdown("<style>[data-testid=stMetricValue] { font-size: 1.7rem; }</style>", unsafe_allow_html=True)

st.title("Scenario lab")
st.caption("Change the assumptions behind Table 5.1 and see the discounted revenue and return on cost move.")
evidence_tag("modelled")
st.caption("A scenario calculation from stated assumptions, not a forecast: statutory tax on survey earnings (revenue per registrant, COMPUTED) × assumed reach and uptake (MODELLED).")


@st.cache_resource(show_spinner=False)
def _inputs():
    return sl.load_inputs()


@st.cache_resource(show_spinner=False)
def _lab(n_draws: int):
    return sl.Lab(_inputs(), n_draws)


@st.cache_data(show_spinner=False, max_entries=512)
def _run(n_draws: int, controls_json: str):
    return _lab(n_draws).run(json.loads(controls_json))


try:
    inputs = _inputs()
except FileNotFoundError:
    st.warning("The Scenario lab's inputs are not connected right now (outputs/stats/scenario_lab_inputs.json is missing). Run `python run_all.py` to write them.")
    st.stop()

sh = inputs["shared"]
STAGE_ORDER = sh["stage_order"]
LIVE_DRAWS = 1000
REPORT_DRAWS = int(sh["n_draws"])
DEFAULT = sl.default_controls(inputs)
RATES = sorted([sh["discount_rate"]] + sh["discount_sensitivities"])
BASIS_NAME = {"central": "Central", "low": "Low", "high": "High"}
STAGE_LABEL = {"seed": "Seed", "entry": "Entry", "active": "Active", "enterprise": "Enterprise", "asset": "Asset", "legacy": "Legacy"}
PERSIST_LO, PERSIST_HI = 0.50, 0.95
PERSIST_FIXED_DEFAULT = float(sh["persistence_triangle"][1])

# ---- widget defaults (session state, so "Reset to report defaults" can restore them) -----------------------------------------------------------------------------------------
WIDGET_DEFAULTS = {f"lab_on_{s}": True for s in STAGE_ORDER}
WIDGET_DEFAULTS.update({"lab_reach": 1.0, "lab_uptake": 1.0, "lab_pers_mode": "Draws as assumed", "lab_pers_value": PERSIST_FIXED_DEFAULT,
                        "lab_horizon": f"{sh['horizon_years']} years", "lab_rate": float(sh["discount_rate"]), "lab_basis": sh["central_income_basis"]})
for k, v in WIDGET_DEFAULTS.items():
    st.session_state.setdefault(k, v)


def _reset():
    for k, v in WIDGET_DEFAULTS.items():
        st.session_state[k] = v


HORIZONS = {f"{sh['horizon_years']} years": int(sh["horizon_years"]), f"{sh['long_horizon_years']} years, with ageing": int(sh["long_horizon_years"])}

ctrl, out = st.columns([1.3, 2.4], gap="large")

with ctrl:
    with st.container(border=True):
        st.markdown("#### Settings")
        st.markdown("**Stages**")
        tcols = st.columns(2)
        for i, s in enumerate(STAGE_ORDER):
            with tcols[i % 2]:
                help_ = {"seed": "Seed counts as cost only: no revenue is claimed for it.",
                         "asset": "Asset is shown separately and is never in the portfolio: the report states no cost for it."}.get(s)
                st.toggle(STAGE_LABEL[s], key=f"lab_on_{s}", help=help_)
        st.slider("Reach, as a multiple of the assumed reach", 0.25, 3.0, step=0.05, key="lab_reach", format="%.2f×",
                  help="1× is the reach assumed in the report (a triangular range per stage). 2× doubles the share of each stage's population reached within the ramp period.")
        st.slider("Uptake effect, as a multiple of the assumed uplift", 0.0, 2.0, step=0.05, key="lab_uptake", format="%.2f×",
                  help="Multiplies the assumed log odds-ratio uplift of each stage's mapped intervention. 0× means the intervention changes nothing; 1× is the report's assumption.")
        st.radio("Persistence (share of registrants still paying each year)", ["Draws as assumed", "Fixed value"], key="lab_pers_mode", horizontal=True,
                 help="As assumed: a triangular range (low, most likely, high) drawn in each simulation. Fixed: one value for every draw.")
        if st.session_state["lab_pers_mode"] == "Fixed value":
            st.slider("Fixed persistence", PERSIST_LO, PERSIST_HI, step=0.05, key="lab_pers_value", format="%.2f")
        st.radio("Horizon", list(HORIZONS), key="lab_horizon", horizontal=True,
                 help="10 years: the report's headline, a flat tax per registrant. 20 years: registrants age, and the tax they pay follows the cohort's age-earnings path.")
        st.radio("Discount rate", RATES, key="lab_rate", horizontal=True, format_func=lambda r: f"{r * 100:.0f}%")
        st.selectbox("Income basis (Active and Enterprise)", list(sh["income_bases"]), key="lab_basis", format_func=lambda b: f"{BASIS_NAME[b]}: {sh['income_basis_labels'][b]}",
                     help="Revenue per registrant of the business-owner stages. Central is the report's headline; Low and High bracket it.")
        st.button("Reset to report defaults", on_click=_reset, width="stretch")

controls = {
    "stages_on": {s: bool(st.session_state[f"lab_on_{s}"]) for s in STAGE_ORDER},
    "reach_mult": float(st.session_state["lab_reach"]), "uptake_mult": float(st.session_state["lab_uptake"]),
    "persistence": float(st.session_state["lab_pers_value"]) if st.session_state["lab_pers_mode"] == "Fixed value" else None,
    "horizon": HORIZONS[st.session_state["lab_horizon"]], "rate": float(st.session_state["lab_rate"]), "basis": st.session_state["lab_basis"],
}
at_defaults = sl.is_default(inputs, controls)
n_draws = REPORT_DRAWS if at_defaults else LIVE_DRAWS            # at the report's settings the lab runs the report's own number of draws, so its figures ARE Table 5.1
res = _run(n_draws, json.dumps(controls, sort_keys=True))


def _matches_report(res) -> bool:
    """True when every stage's ROI and the portfolio's (median, 80% interval) equal stage_economics.json (relative 1e-9)."""
    pipe = PipelineData()
    try:
        for s in sh["revenue_stages"]:
            fig = pipe.stage_economics(s)
            for k in ("median", "p10", "p90"):
                a, b = res["stages"][s]["roi"][k], fig.value["monte_carlo_at_10pct"]["roi"][k]
                if abs(a - b) > 1e-9 * abs(b):
                    return False
        port = pipe.stage_economics_portfolio().value["monte_carlo_at_10pct"]["roi"]
        return all(abs(res["portfolio"]["roi"][k] - port[k]) <= 1e-9 * abs(port[k]) for k in ("median", "p10", "p90"))
    except Exception:
        return False


def _iv(d, fmt):
    return f"{fmt(d['median'])} ({fmt(d['p10'])} to {fmt(d['p90'])})"


def _x(v):
    return f"{v:.2f}×"


with out:
    if at_defaults:
        if _matches_report(res):
            st.markdown('<span class="tdj-badge-ok">✓ Matches report Table 5.1</span>', unsafe_allow_html=True)
            st.caption(f"Report settings: the lab runs the report's own {REPORT_DRAWS:,} draws and reproduces the portfolio and stage figures of Table 5.1.")
        else:
            st.warning("At the report's settings the lab should reproduce Table 5.1, but the figures differ: the inputs file and the report's outputs are out of step. Re-run the pipeline.")
    else:
        st.caption(f"Live run with {LIVE_DRAWS:,} draws; the report's figures use {REPORT_DRAWS:,} draws, so the medians can differ slightly.")

    pf = res["portfolio"]
    if pf is None:
        st.info("Switch on at least one of Seed, Entry, Active, Enterprise or Legacy to see the portfolio.")
    else:
        st.markdown("#### Portfolio")
        evidence_tag("modelled")
        m1, m2, m3 = st.columns(3)
        m1.metric("Portfolio ROI (median)", _x(pf["roi"]["median"]), help="Discounted revenue / cost of the switched-on stages of the report's portfolio: Entry, Active, Enterprise and Legacy revenue plus Seed's cost; Asset is excluded. 1.0× = break-even.")
        m2.metric("80% interval", f"{pf['roi']['p10']:.2f}–{pf['roi']['p90']:.2f}×", help="10th to 90th percentile of the Monte Carlo.")
        m3.metric("Chance ROI ≥ 1", f"{pf['p_roi_ge_1'] * 100:.0f}%", help="Share of the simulated draws in which discounted revenue covers cost.")
        st.caption("Report definition: the four revenue-earning stages plus Seed's cost, excluding Asset. Seed counts as cost only."
                   + (" Seed is switched off, so its cost is not counted." if not controls["stages_on"]["seed"] else ""))

    # ---- table of stages ----
    rows = []
    for s in ("seed", "entry", "active", "enterprise", "legacy"):
        d, label = res["stages"][s], getattr(N, s).swahili
        if not d["on"]:
            rows.append({"Stage": f"{STAGE_LABEL[s]} · {label}", "New registrants": "off", "Discounted revenue, TZS": "off", "Cost, TZS": "off", "ROI": "off"})
        elif s == "seed":
            rows.append({"Stage": f"{STAGE_LABEL[s]} · {label}", "New registrants": "none claimed", "Discounted revenue, TZS": "none claimed", "Cost, TZS": _iv(d["cost"], _tzs), "ROI": "cost only"})
        else:
            rows.append({"Stage": f"{STAGE_LABEL[s]} · {label}", "New registrants": f"{d['registrants']['median']:,.0f}", "Discounted revenue, TZS": _iv(d["revenue_pv"], _tzs),
                         "Cost, TZS": _iv(d["cost"], _tzs), "ROI": _iv(d["roi"], _x)})
    if pf is not None:
        rows.append({"Stage": "Portfolio (without Asset)", "New registrants": f"{pf['registrants']['median']:,.0f}", "Discounted revenue, TZS": _iv(pf["revenue_pv"], _tzs),
                     "Cost, TZS": _iv(pf["cost"], _tzs), "ROI": _iv(pf["roi"], _x)})
    st.markdown("#### By stage")
    cols_ = list(rows[0])
    _nl = chr(10)
    st.markdown(_nl.join(["| " + " | ".join(cols_) + " |", "|" + "---|" * len(cols_)] + ["| " + " | ".join(str(r[c]) for c in cols_) + " |" for r in rows]))      # a wrapping table: every column stays visible
    evidence_tag("modelled")
    st.caption("Each cell shows the median, then the 80% interval (10th to 90th percentile) in brackets. Discounted revenue is the present value of the income and presumptive tax of the new registrants over the horizon; ROI = discounted revenue / cost. Constant TZS, no wage growth or inflation.")

    # ---- chart ----
    bars = [(STAGE_LABEL[s], res["stages"][s]["roi"], CHART_GREEN) for s in sh["revenue_stages"] if res["stages"][s]["on"]]
    if pf is not None:
        bars.append(("Portfolio", pf["roi"], CHART_NAVY))
    bars = [(f"{b[0]}<br>{_x(b[1]['median'])}", b[1], b[2]) for b in bars]
    if bars:
        fig = go.Figure(go.Bar(
            x=[b[0] for b in bars], y=[b[1]["median"] for b in bars], marker_color=[b[2] for b in bars],
            error_y=dict(type="data", symmetric=False, array=[b[1]["p90"] - b[1]["median"] for b in bars], arrayminus=[b[1]["median"] - b[1]["p10"] for b in bars]),
            hovertemplate="%{x}: median %{y:.2f}×<extra></extra>"))
        fig.add_hline(y=1.0, line_dash="dash", line_color="#E39A3B", annotation_text="Break-even 1.0×", annotation_position="top left")
        themed(fig, height=360, margin=dict(t=30, b=10), yaxis_title="ROI: median and 80% interval (×)", showlegend=False)
        st.plotly_chart(fig, width="stretch")
        evidence_tag("modelled")
        st.caption("Bars show the median ROI; the whiskers show the 80% interval (10th to 90th percentile). The dashed line is break-even: below it the discounted revenue does not cover the cost.")

    # ---- Asset, shown separately ----
    if controls["stages_on"]["asset"]:
        a = res["stages"]["asset"]["revenue_pv"]
        st.markdown("#### Asset, shown separately")
        evidence_tag("modelled")
        st.metric(f"Asset break-even programme cost (ROI = 1), {N.asset.swahili}", f"TZS {_tzs(a['median'])}", help="The programme cost at which Asset's ROI would be 1: its discounted revenue (median). It is not a cost the report states.")
        st.caption(f"Asset pays back at any programme cost below this (median; 80% interval TZS {_tzs(a['p10'])} to {_tzs(a['p90'])}). The report states no cost for Asset, so it has no ROI and is not in the portfolio.")

    # ---- caveats ----
    pending = inputs.get("assumptions_awaiting_signoff", [])
    signed = sorted({v for v in inputs.get("signoff", {}).values() if v})
    st.markdown("#### What this is, and is not")
    st.caption("A scenario calculation, not a forecast and not a measured outcome. The reach, uptake and persistence settings are assumptions; revenue per registrant is the statutory tax on survey earnings (COMPUTED).")
    st.caption(("Stage assumptions: " + "; ".join(signed) + ". " if signed else "")
               + ("Awaiting sign-off in the assumptions register: " + ", ".join(p["key"] for p in pending) + "." if pending else ""))

st.divider()
callout("HOW TO READ THIS",
        "Move one setting at a time. Reach and uptake scale the assumed values of Table 5.1; persistence, horizon, discount rate and income basis are the report's own sensitivities. "
        "At the report's default settings the lab shows Table 5.1 itself.")
