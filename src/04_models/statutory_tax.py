"""Statutory income-tax schedules applied to the DISTRIBUTION of ILFS 2024 earnings (Blocks E2.5 and F1).

One place for the schedules, used by Table 5.1 (stage_economics.py) and the agent simulation (economic_model.py):

  pit(income)                resident individual income tax on annual income (Income Tax Act Cap. 332 R.E. 2023, First Schedule para 1(1); unchanged by the Finance Acts
                             2024, 2025 and 2026: config.yaml assumptions tax.pit_schedule)
  presumptive(turnover)      presumptive income tax of an individual with turnover up to the ceiling (First Schedule para 2(3), as amended by the Finance Act 2026, in force from
                             1 July 2026: ceiling TZS 200 million, 4.0% above TZS 11 million; config.yaml assumptions tax.presumptive_schedule)
  owner_tax(turnover, net)   the tax of a business owner: presumptive tax on turnover up to the ceiling, income tax on net annual earnings above it

Schedule year used by every output: the schedule in force in 2026/27 (resident schedule of the R.E. 2023 text, presumptive schedule of the Finance Act 2026). The ILFS earnings are 2024
values in TZS and are not inflated; the thresholds are not indexed. The Finance Act 2026's twelve-month holiday for individuals who obtain a TIN to start a business (para 2(3) item 2 of
the new table) is NOT applied: the registrants modelled are existing informal workers and owners, not new businesses; Table 5.1 reports it as a sensitivity (the nil-period sensitivity).

The mean tax of a group is computed from AGGREGATE QUANTILE CELLS of the earnings distribution (data/processed/twin_inputs.json `tax_base_cells`: 100 weighted cells of the
group, each with the mean of the earnings variables of the respondents in it): the schedule is applied to every cell, so the tax follows the distribution and not its mean.
"""

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # src/
import paths
from assumptions import A


def pit(income):
    """Resident individual income tax (annual) on annual income (array)."""
    income = np.asarray(income, float)
    tax = np.zeros_like(income, dtype=float)
    for lo, base, rate in A("tax.pit_schedule"):
        tax = np.where(income > lo, base + rate * (income - lo), tax)
    return tax


def presumptive(turnover):
    """Presumptive income tax, records kept (First Schedule para 2(3)); above the ceiling the individual schedule is applied to the turnover (callers use owner_tax instead)."""
    spec = A("tax.presumptive_schedule")
    t = np.asarray(turnover, float)
    out = np.zeros_like(t)
    for lo, hi, fixed, base, rate in spec["bands"]:
        out = np.where((t > lo) & (t <= hi), base + rate * (t - lo), out)
    out = np.where((t > spec["bands"][-1][1]) & (t <= spec["threshold_turnover"]), spec["above_11m_rate"] * t, out)
    return np.where(t > spec["threshold_turnover"], pit(t), out)


def owner_tax(turnover, net_earnings):
    """Tax of a business owner: presumptive tax on turnover up to the ceiling, income tax on net annual earnings above it."""
    turnover, net_earnings = np.asarray(turnover, float), np.asarray(net_earnings, float)
    return np.where(turnover <= A("tax.presumptive_schedule")["threshold_turnover"], presumptive(turnover), pit(net_earnings))


_CELLS = {}


def cells():
    """The quantile cells of the earnings distributions (data/processed/twin_inputs.json)."""
    if "x" not in _CELLS:
        try:
            with open(paths.TWIN_INPUTS, encoding="utf-8") as f:
                _CELLS["x"] = json.load(f)["tax_base_cells"]
        except FileNotFoundError:
            raise SystemExit("%s is missing: run `python run_all.py --from-raw` (src/03_features/twin_inputs.py writes it)" % paths.TWIN_INPUTS) from None
    return _CELLS["x"]


def informal_mean_tax(scale=1.0, c=None):
    """Mean statutory tax per informal earner (ILFS 2024; informal employment, outside the formal net, positive earnings), earnings multiplied by `scale`: non-owners pay the resident
    schedule on annual earnings, business owners the presumptive tax on turnover (income tax on net earnings above the ceiling)."""
    c = c or cells()
    non, own = c["informal_nonowner"], c["informal_owner"]
    t_non = float(np.mean(pit(scale * np.array(non["annual_earnings"]))))
    t_own = float(np.mean(owner_tax(scale * np.array(own["turnover"]), scale * np.array(own["net_earnings"]))))
    return non["share"] * t_non + own["share"] * t_own


def msme_mean_tax(scale=1.0, c=None):
    """Mean presumptive tax per household enterprise (ILFS 2024; self-employed in non-agricultural main jobs with turnover), turnover multiplied by `scale`."""
    o = (c or cells())["all_owner"]
    return float(np.mean(owner_tax(scale * np.array(o["turnover"]), scale * np.array(o["net_earnings"]))))


def effective_rates(c=None):
    """Effective average rates of the two means, for the record: mean tax / mean annual earnings of the group (net earnings for owners), and mean tax / mean turnover of the owners."""
    c = c or cells()
    non, own = c["informal_nonowner"], c["informal_owner"]
    mean_earn = non["share"] * float(np.mean(non["annual_earnings"])) + own["share"] * float(np.mean(own["net_earnings"]))
    it, mt = informal_mean_tax(c=c), msme_mean_tax(c=c)
    mturn = float(np.mean(c["all_owner"]["turnover"]))
    return {"informal_mean_tax_tzs": it, "informal_mean_earnings_tzs": mean_earn, "informal_effective_rate_on_earnings": it / mean_earn,
            "msme_mean_tax_tzs": mt, "msme_mean_turnover_tzs": mturn, "msme_effective_rate_on_turnover": mt / mturn}
