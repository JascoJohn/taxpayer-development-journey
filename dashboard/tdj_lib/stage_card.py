"""Cost / revenue / ROI card of a stage, read from outputs/stats/stage_economics.json (Block E2.5, Table 40; 20-year sensitivity added in Block E3.4).

Replaces the typed cost and revenue figures the stage pages used to show (Entry 420M / 8.7-9B / 20.7x, Active 600M / 12.8-13B / 21.3x, Enterprise 750M / 4.1B / ~5.5x,
Legacy 700M / 2.5B / ~3.6x). The figures are the median and 80% interval of a Monte Carlo over assumed reach, uptake and persistence, with the statutory tax on ILFS
earnings as revenue per registrant. A scenario calculation, not a forecast; the assumptions await the owner's sign-off.
"""


def _tzs(x: float) -> str:
    x = float(x)
    if abs(x) >= 1e9:
        return f"{x / 1e9:.2f}B"
    if abs(x) >= 1e6:
        return f"{x / 1e6:.0f}M"
    return f"{x:,.0f}"


def show_stage_economics(st, pipeline, stage: str) -> None:
    fig = pipeline.stage_economics(stage)
    if not fig.available:
        st.caption(f"Cost, revenue and ROI are not connected right now ({fig.note}).")
        return
    s = fig.value
    mc = s["monte_carlo_at_10pct"]
    st.metric("Cost (report-stated)", f"TZS {_tzs(s['central_at_10pct']['cost'])}", help=f"The report's own figure; Monte Carlo 80% interval with a cost-overrun risk: TZS {_tzs(mc['cost']['p10'])} to {_tzs(mc['cost']['p90'])}.")
    if "revenue_note" in s:
        st.caption(s["revenue_note"].capitalize() + ".")
    else:
        rev, roi = mc["revenue_pv"], mc["roi"]
        st.metric("Modelled revenue (10 years, discounted)", f"TZS {_tzs(rev['median'])}", help=f"Median; 80% interval TZS {_tzs(rev['p10'])} to {_tzs(rev['p90'])}.")
        st.metric("ROI (discounted revenue / cost)", f"{roi['median']:.2f}x", help=f"Median; 80% interval {roi['p10']:.2f}x to {roi['p90']:.2f}x. 1.0x = break-even.")
        st.caption(f"80% interval: revenue TZS {_tzs(rev['p10'])} to {_tzs(rev['p90'])}; ROI {roi['p10']:.2f}x to {roi['p90']:.2f}x.")
    v20 = s.get("variants", {}).get("horizon_20_aged", {}).get("0.1")
    if v20 and "roi" in v20:
        r20 = v20["roi"]
        p90 = s["variants"].get("horizon_20_aged_persistence_0.90", {}).get("0.1", {}).get("roi", {}).get("median")
        st.caption(f"20-year sensitivity (earnings follow the cohort's age path, persistence as signed off): ROI median {r20['median']:.2f}x, 80% interval {r20['p10']:.2f}x to {r20['p90']:.2f}x"
                   + (f"; at persistence 0.90: {p90:.2f}x." if p90 is not None else "."))
    st.caption(f"Mechanism in the report: {s.get('report_name', '')} (internal reference: {s.get('morale_model_key')}).")
    st.caption("Scenario calculation (MODELLED): statutory tax on survey earnings x reach and uptake (signed-off assumptions), 10% discount rate. Not a forecast.")
