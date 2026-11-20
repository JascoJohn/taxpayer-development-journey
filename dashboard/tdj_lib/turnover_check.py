"""Mzani wa Kodi turnover check (Active page): where an entered yearly turnover sits in the band shown, and the presumptive tax under the schedule in force.

Pure functions of their arguments. The entered value is not stored, not cached, not logged and not written to st.session_state: the page calls check() and renders the result.
The schedule is the one the pipeline uses (config.yaml assumptions tax.presumptive_schedule, Finance Act 2026), read through benchmark_adapters.presumptive_schedule(); nothing is typed
here. Same arithmetic as src/statutory_tax.py presumptive(): tests/test_dashboard_v11.py compares them.
"""

from .benchmark_adapters import presumptive_schedule


def presumptive_tax(turnover, schedule=None):
    """Presumptive income tax (TZS a year) at a yearly turnover; None above the ceiling, where the presumptive regime does not apply."""
    s = schedule or presumptive_schedule()
    t = float(turnover)
    if t > s["threshold_turnover"]:
        return None
    tax = 0.0
    for lo, hi, _fixed, base, rate in s["bands"]:
        if lo < t <= hi:
            tax = base + rate * (t - lo)
    if t > s["bands"][-1][1]:
        tax = s["above_11m_rate"] * t
    return float(tax)


def approx_percentile(turnover, p25, median, p75):
    """Approximate percentile, interpolated linearly from the three quartiles only; None outside the quartiles (nothing is extrapolated)."""
    t = float(turnover)
    if t < p25 or t > p75:
        return None
    if t <= median:
        return 25.0 + 25.0 * ((t - p25) / (median - p25) if median > p25 else 0.0)
    return 50.0 + 25.0 * ((t - median) / (p75 - median) if p75 > median else 0.0)


def check(turnover, p25, median, p75, schedule=None):
    """Position of `turnover` in the band (25th, 50th, 75th percentile of the cell) and its presumptive tax."""
    s = schedule or presumptive_schedule()
    t = float(turnover)
    position = "below" if t < p25 else ("above" if t > p75 else "between")
    pos_text = {"below": "below the 25th percentile (the lower quartile) of businesses like this",
                "between": "between the lower and the upper quartile of businesses like this",
                "above": "above the 75th percentile (the upper quartile) of businesses like this"}[position]
    tax = presumptive_tax(t, s)
    ceiling = int(s["threshold_turnover"])
    if tax is None:
        tax_text = f"above the presumptive ceiling of TZS {ceiling:,}: the presumptive regime does not apply"
    elif tax == 0:
        tax_text = f"TZS 0 (nil up to TZS {int(s['bands'][0][0]):,})"
    else:
        tax_text = f"TZS {tax:,.0f} a year"
    return {"turnover": t, "position": position, "position_text": pos_text, "approx_percentile": approx_percentile(t, p25, median, p75), "tax_tzs": tax, "tax_text": tax_text, "ceiling": ceiling}
