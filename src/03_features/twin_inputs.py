"""E2.2 - TRA registered taxpayers and the base parameters of the digital twin, each from data.

Writes
  data/processed/tra_registered_taxpayers.csv   the longest available annual series of TRA registered taxpayers (published figures), with definitions
  data/processed/twin_inputs.json               the twin's base parameters with their value, basis class (DATA / CALIBRATED) and source

Sources (all aggregates; every transcribed published figure is verified against the saved source document by tests/test_tra_series.py):
  registered taxpayers   NBS Tax Statistics Reports 2022/23 and 2023/24 (source TRA), TRA Sixth Corporate Plan for the active / dormant definitions
  GDP growth, population growth, nominal GDP   World Bank WDI snapshots in data/raw/worldbank/
  population, working-age population           Census 2022 10% sample counts (data/processed/census_age_counts.json) projected to the base year with WDI population growth
  mobile-money users, value of transactions    Bank of Tanzania National Payment Systems Annual Reports (TCRA December-quarter reports corroborate)
  informal workers' average earnings, MSME revenue   ILFS 2024 microdata (aggregate mean of earnings / gross business receipts)
  formalisation rate   CALIBRATED: least-squares linear trend of the TRA series, per working-age adult

TRA's registered taxpayers are Mainland TIN registrations (a stock of registrations, individuals and entities, active or not). They are kept apart from
FinScope's 1.31 million ADULT TIN holders (a survey estimate of adults holding a TIN); the twin states the difference in its output.
"""

import csv
import json
import math
import os
import sys

import numpy as np
import pandas as pd
import pyreadstat

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # src/
import paths
import disclosure
from ilfs_indicators import classify
from finscope_segments import WEIGHT_VAR

CFG = paths.CFG["twin_inputs"]
LABEL = "published figures and survey aggregates; no respondent-level rows"


def _wdi(indicator):
    path = paths.WB_SNAPSHOTS[indicator]
    with open(path, "r", encoding="utf-8") as f:
        rows = json.load(f)[1]
    return {int(r["date"]): float(r["value"]) for r in rows if r.get("value") is not None}


def _last_mean(series, n):
    years = sorted(series)[-n:]
    return float(np.mean([series[y] for y in years])), years


def tra_series():
    docs = CFG["tra_registered_taxpayers"]["documents"]
    used = list(CFG["tra_registered_taxpayers"]["series"])
    rows, prev = [], None
    for r in used:
        d = docs[r["doc"]]
        row = {"fiscal_year": r["fy"], "registered_taxpayers_thousands": r["thousands"], "registered_taxpayers": r["thousands"] * 1000,
               "change_pct": None if prev is None else round((r["thousands"] / prev - 1) * 100, 2), "status": "used", "document": d["title"], "table": d["table"],
               "pdf_page": d["pdf_page"], "url": d["url"], "coverage": "Tanzania Mainland", "note": ""}
        prev = r["thousands"]
        rows.append(row)
    for r in CFG["tra_registered_taxpayers"]["superseded"]:
        d = docs[r["doc"]]
        rows.append({"fiscal_year": r["fy"], "registered_taxpayers_thousands": r["thousands"], "registered_taxpayers": r["thousands"] * 1000, "change_pct": None,
                     "status": "superseded vintage", "document": d["title"], "table": d["table"], "pdf_page": d["pdf_page"], "url": d["url"], "coverage": "Tanzania Mainland",
                     "note": r.get("note", "")})
    return rows


def quantile_cells(sort_key, weights, variables, ncell=100):
    """Aggregate quantile cells (Block F1): the respondents are ordered by `sort_key` and cut into `ncell` cells of equal weight; each cell carries the weighted mean of every variable.
    Only these cell means are published (each cell pools at least disclosure.min_base respondents)."""
    order = np.argsort(sort_key, kind="mergesort")
    w = np.asarray(weights, float)[order]
    cw = np.cumsum(w)
    idx = np.minimum(((cw - w / 2.0) / cw[-1] * ncell).astype(int), ncell - 1)
    wsum = np.bincount(idx, weights=w, minlength=ncell)
    n = np.bincount(idx, minlength=ncell)
    assert n.min() >= int(paths.CFG["disclosure"]["min_base"]), "a quantile cell has fewer respondents than the disclosure rule allows"
    return {k: [float(x) for x in np.bincount(idx, weights=w * np.asarray(v, float)[order], minlength=ncell) / wsum] for k, v in variables.items()}, int(n.min())


def ilfs_aggregates(sav_path=None):
    c = CFG["ilfs"]
    cols = ["Q06B_MEM_AGE", "WEIGHT", "Q25", "Q27A", "Q30", "Q31A", "Q34", "Q38A", "Q38C", "Q22B_MAIN_ISIC", c["employee_cash"], c["business_net"], c["business_net_period"],
            c["business_gross"], c["business_gross_period"], c["agri_net"], c["agri_net_period"]]
    df, _ = pyreadstat.read_sav(sav_path or paths.ILFS_SAV, usecols=cols, apply_value_formats=False)
    cl = classify(df)
    age = df["Q06B_MEM_AGE"].to_numpy(float)
    w = df["WEIGHT"].to_numpy(float)

    def monthly(col, per):
        v = np.where(df[col].fillna(0).to_numpy(float) > 0, df[col].fillna(0).to_numpy(float), 0.0)
        return v * np.where(df[per].to_numpy(float) == 1, 52.0 / 12.0, 1.0)
    annual = 12.0 * (np.where(df[c["employee_cash"]].fillna(0).to_numpy(float) > 0, df[c["employee_cash"]].fillna(0).to_numpy(float), 0.0)
                     + monthly(c["business_net"], c["business_net_period"]) + monthly(c["agri_net"], c["agri_net_period"]))
    informal = (cl["informal"].to_numpy(dtype=float) == 1.0) & (age >= 15) & (age <= 97)
    m = informal & (annual > 0)
    mean_inf = float(np.average(annual[m], weights=w[m]))
    order = np.argsort(annual[m])
    cw = np.cumsum(w[m][order]) / w[m].sum()
    med_inf = float(annual[m][order][np.searchsorted(cw, 0.5)])
    # MSME revenue: gross receipts of household businesses (self-employed, non-agricultural main job), annualised, winsorised
    gross = 12.0 * monthly(c["business_gross"], c["business_gross_period"])
    sm = (df["Q25"].to_numpy(float) == 2) & (gross > 0) & (age >= 15) & (age <= 97)
    cap = float(np.percentile(gross[sm], float(c["winsorise_pct"])))
    g = np.minimum(gross[sm], cap)
    mean_msme = float(np.average(g, weights=w[sm]))
    order = np.argsort(gross[sm])
    cw = np.cumsum(w[sm][order]) / w[sm].sum()
    med_msme = float(gross[sm][order][np.searchsorted(cw, 0.5)])
    for n in (int(m.sum()), int(sm.sum())):
        assert not disclosure.is_suppressed(n)

    # ---- quantile cells of the earnings distributions the statutory tax is applied to (Block F1)
    owner = df["Q25"].to_numpy(float) == 2                       # self-employed in non-agricultural activities = the FinScope business-owner proxy
    g_non, g_own = m & ~owner, m & owner                          # informal earners (positive earnings): non-owners pay the resident schedule, owners the presumptive tax
    cells_non, n_non = quantile_cells(annual[g_non], w[g_non], {"annual_earnings": annual[g_non]})
    cells_own, n_own = quantile_cells(gross[g_own], w[g_own], {"turnover": gross[g_own], "net_earnings": annual[g_own]})
    all_own = (owner) & (gross > 0) & (age >= 15) & (age <= 97)  # all household enterprises with turnover, informal or not (the twin's MSME presumptive base)
    cells_all, n_all = quantile_cells(gross[all_own], w[all_own], {"turnover": gross[all_own], "net_earnings": annual[all_own]})
    tax_cells = {
        "definition": "Weighted quantile cells (100 cells of equal weight, ordered by the earnings variable) of ILFS 2024 earnings, 15-97 years: the statutory tax schedules are applied to every cell (src/04_models/statutory_tax.py), "
                      "so the mean tax follows the earnings DISTRIBUTION, not its mean. Each cell carries the weighted mean of its respondents' variables; only cell means are published.",
        "informal_nonowner": {"share": float(w[g_non].sum() / w[m].sum()), "n_unweighted": int(g_non.sum()), "min_cell_n": n_non, **cells_non,
                              "group": "informal employment (ICLS-17, ilfs_indicators.classify), not a non-agricultural self-employed owner, positive annual earnings (cash + net business + net agricultural)"},
        "informal_owner": {"share": float(w[g_own].sum() / w[m].sum()), "n_unweighted": int(g_own.sum()), "min_cell_n": n_own, **cells_own,
                           "group": "informal employment, self-employed in non-agricultural activities (owner), positive annual earnings; cells ordered by annualised gross receipts (turnover)"},
        "all_owner": {"n_unweighted": int(all_own.sum()), "min_cell_n": n_all, **cells_all, "group": "all self-employed in non-agricultural main jobs with positive gross receipts (informal or not): the household enterprises the presumptive regime applies to"},
    }
    return {"tax_base_cells": tax_cells, "informal_mean": mean_inf, "informal_median": med_inf, "informal_n_unweighted": int(m.sum()),
            "msme_mean_winsorised": mean_msme, "msme_median": med_msme, "msme_winsor_cap": cap, "msme_n_unweighted": int(sm.sum())}


def finscope_mobile_money(csv_path=None):
    """FinScope 2023 weighted ADULT (16+) mobile-money users (the MM flag) and weighted adults: the twin's user base (Block E3.3). Aggregates only."""
    df = pd.read_csv(csv_path or paths.FINSCOPE_CSV, usecols=["MM", WEIGHT_VAR], low_memory=False)
    w = pd.to_numeric(df[WEIGHT_VAR], errors="coerce")
    ok = w.notna()
    mm = df["MM"].astype(str).str.strip() == "MM"
    users, adults = float(w[ok & mm].sum()), float(w[ok].sum())
    n_users, n_all = int((ok & mm).sum()), int(ok.sum())
    assert not disclosure.is_suppressed(n_users)
    return {"users": users, "adults": adults, "n_users": n_users, "n_adults": n_all, "share_pct": 100.0 * users / adults}


def run_twin_inputs(sav_path=None, csv_path=None, json_path=None, finscope_csv=None):
    csv_path = csv_path or paths.TRA_REGISTERED_TAXPAYERS_CSV
    json_path = json_path or paths.TWIN_INPUTS
    base_year, census_year, ny = int(CFG["base_year"]), int(CFG["census_year"]), int(CFG["growth_years"])

    # ---------------------------------------------------------- TRA series
    rows = tra_series()
    cols = ["fiscal_year", "registered_taxpayers_thousands", "registered_taxpayers", "change_pct", "status", "coverage", "document", "table", "pdf_page", "url", "note"]
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f, lineterminator="\n")
        wr.writerow(cols)
        for r in rows:
            wr.writerow(["" if r[c] is None else r[c] for c in cols])
    used = [r for r in rows if r["status"] == "used"]
    latest = used[-1]
    # least-squares linear trend over the last 7 fiscal years (2017/18 - 2023/24: the NBS 2023/24 report's own table)
    tail = used[-7:]
    x = np.arange(len(tail), dtype=float)
    yv = np.array([r["registered_taxpayers"] for r in tail], float)
    slope, intercept = np.polyfit(x, yv, 1)
    resid = yv - (slope * x + intercept)
    rmse_trend = float(np.sqrt(np.mean(resid ** 2)))

    # ---------------------------------------------------------- WDI, census
    gdp_g, gdp_years = _last_mean(_wdi("NY.GDP.MKTP.KD.ZG"), ny)
    pop_g, pop_years = _last_mean(_wdi("SP.POP.GROW"), ny)
    gdp_cn = _wdi("NY.GDP.MKTP.CN")
    gdp_year = max(y for y in gdp_cn if y <= base_year)
    with open(paths.CENSUS_AGE_COUNTS, encoding="utf-8") as f:
        census = json.load(f)
    by_age = census["by_age"]
    total_2022 = sum(v["expanded"] for v in by_age.values())
    lo, hi = [int(a) for a in CFG["working_age"]]
    wa_2022 = sum(v["expanded"] for k, v in by_age.items() if k.isdigit() and lo <= int(k) <= hi)
    grow = (1 + pop_g / 100.0) ** (base_year - census_year)
    population, working_age = total_2022 * grow, wa_2022 * grow

    # ---------------------------------------------------------- mobile money (BoT)
    bm = CFG["bot_mobile_money"]
    users = {int(k): v for k, v in bm["users_active"].items()}
    value = {int(k): v for k, v in bm["value_tzs_billion"].items()}
    mm_users = users[base_year]
    cagr = (users[base_year] / users[base_year - 5]) ** (1 / 5)
    mm_gdp = value[base_year] * 1e9 / gdp_cn[gdp_year]

    # ---------------------------------------------------------- FinScope adults and mobile-money users (Block E3.3)
    fm = finscope_mobile_money(finscope_csv)
    pop_growth_factor = 1.0 + pop_g / 100.0              # adult population is assumed to grow with the total population (WDI SP.POP.GROW, mean of the last years)

    # ---------------------------------------------------------- ILFS
    il = ilfs_aggregates(sav_path)
    import statutory_tax
    eff = statutory_tax.effective_rates(il["tax_base_cells"])             # the statutory schedules (config.yaml assumptions tax.*) applied to the earnings distribution

    # ---------------------------------------------------------- calibrated formalisation rate (per working-age adult per year)
    f_cal = float(slope) / working_age
    params = {
        "base.gdp_growth_rate": {"value": gdp_g / 100.0, "basis": "DATA", "source": "World Bank WDI NY.GDP.MKTP.KD.ZG (GDP growth, annual %%), Tanzania, mean of %d-%d" % (gdp_years[0], gdp_years[-1]),
                                 "detail": {"years": gdp_years}},
        "base.population": {"value": population, "basis": "DATA", "source": "Census 2022 10%% sample total %s (x10), projected to %d with the mean WDI population growth %.2f%% a year (%d-%d)" % (format(round(total_2022), ","), base_year, pop_g, pop_years[0], pop_years[-1]),
                            "detail": {"census_total_2022": total_2022, "growth_pct": pop_g}},
        "base.working_age_population": {"value": working_age, "basis": "DATA", "source": "Census 2022 10%% sample, ages %d-%d (x10: %s), projected to %d with the same growth" % (lo, hi, format(round(wa_2022), ","), base_year),
                                        "detail": {"census_working_age_2022": wa_2022}},
        "base.registered_taxpayers": {"value": float(latest["registered_taxpayers"]), "basis": "DATA", "source": "TRA registered taxpayers, Mainland, end of fiscal year %s, NBS Tax Statistics Report 2023/24 Table 3.1 (source TRA). %s" % (latest["fiscal_year"], CFG["tra_registered_taxpayers"]["definition"][:250])},
        "base.mobile_money_users": {"value": fm["users"], "basis": "DATA", "source": "FinScope Tanzania 2023, weighted number of ADULTS (16+) who use mobile money (MM flag; %s of %s respondents, %.1f%% of adults): persons, not accounts. Replaced the Bank of Tanzania active-account count (%s accounts in %d, now a context figure only) and the typed 35,000,000 (UNKNOWN)." % (format(fm["n_users"], ","), format(fm["n_adults"], ","), fm["share_pct"], format(mm_users, ","), base_year),
                                    "detail": {"weighted_adults": fm["adults"], "n_unweighted_users": fm["n_users"], "n_unweighted_adults": fm["n_adults"], "share_of_adults_pct": fm["share_pct"]}},
        "base.adult_population": {"value": fm["adults"], "basis": "DATA", "source": "FinScope Tanzania 2023, weighted number of adults aged 16 and over (%s respondents; Mainland and Zanzibar): the universe of the twin's registrations and mobile-money users, which can never exceed it" % format(fm["n_adults"], ",")},
        "twin.growth.adult_population": {"value": pop_growth_factor, "basis": "DATA", "source": "World Bank WDI SP.POP.GROW, mean %d-%d (%.2f%% a year): the adult population is assumed to grow with the total population" % (pop_years[0], pop_years[-1], pop_g)},
        "base.mobile_money_gdp_pct": {"value": mm_gdp, "basis": "DATA", "source": "BoT value of mobile payments %d (TZS %s billion, NPS Annual Reports 2024 / 2025) divided by nominal GDP %d (WDI NY.GDP.MKTP.CN): a gross transaction FLOW over GDP, so it can exceed 1" % (base_year, format(value[base_year], ","), gdp_year)},
        "base.informal_worker_avg_income_tzs": {"value": il["informal_mean"], "basis": "DATA", "source": "ILFS 2024: weighted MEAN annual earnings (12 x monthly cash earnings + net business + net agricultural income) of employed persons in informal employment (ICLS-17, ilfs_indicators.classify) with positive earnings; the median is %s TZS" % format(round(il["informal_median"]), ","),
                                                "detail": {"median": il["informal_median"], "n_unweighted": il["informal_n_unweighted"]}},
        "base.msme_avg_revenue_tzs": {"value": il["msme_mean_winsorised"], "basis": "DATA", "source": "ILFS 2024: weighted mean annual GROSS business receipts (Q87B, week or month, annualised) of self-employed persons in non-agricultural main jobs, winsorised at the %dth percentile (TZS %s); median %s TZS. It describes household enterprises (mostly micro), not registered MSMEs: no published MSME revenue figure was found" % (int(CFG["ilfs"]["winsorise_pct"]), format(round(il["msme_winsor_cap"]), ","), format(round(il["msme_median"]), ",")),
                                    "detail": {"median": il["msme_median"], "winsor_cap": il["msme_winsor_cap"], "n_unweighted": il["msme_n_unweighted"]}},
        "base.new_taxpayer_mean_tax_tzs": {"value": eff["informal_mean_tax_tzs"], "basis": "DATA", "source": "Mean statutory income tax per NEW taxpayer in the twin (Block F1; replaces the flat 15%% rate on the mean): the resident individual schedule (non-owners) and the presumptive schedule (business owners) applied to the DISTRIBUTION (100 quantile cells) of ILFS 2024 annual earnings of informal earners; effective average rate %.2f%% of the group's mean earnings (TZS %s mean tax on TZS %s mean earnings)" % (eff["informal_effective_rate_on_earnings"] * 100, format(round(eff["informal_mean_tax_tzs"]), ","), format(round(eff["informal_mean_earnings_tzs"]), ",")),
                                           "detail": eff},
        "base.msme_mean_presumptive_tax_tzs": {"value": eff["msme_mean_tax_tzs"], "basis": "DATA", "source": "Mean presumptive tax per household enterprise (Block F1; replaces the flat 3%% rate on mean receipts): the presumptive schedule applied to the DISTRIBUTION (100 quantile cells) of ILFS 2024 annual gross receipts of non-agricultural self-employed with turnover; effective average rate %.2f%% of mean turnover (TZS %s tax on TZS %s turnover)" % (eff["msme_effective_rate_on_turnover"] * 100, format(round(eff["msme_mean_tax_tzs"]), ","), format(round(eff["msme_mean_turnover_tzs"]), ","))},
        "twin.default.formalization_policy": {"value": f_cal, "basis": "CALIBRATED", "source": "slope of the least-squares line through TRA registered taxpayers %s-%s (%s per year) divided by the working-age population %s: new registrations per working-age adult per year in the no-policy scenario" % (tail[0]["fiscal_year"], tail[-1]["fiscal_year"], format(round(slope), ","), format(round(working_age), ",")),
                                              "calibration": {"target": "TRA registered taxpayers (NBS Tax Statistics), %d fiscal years" % len(tail), "method": "ordinary least squares, 1 free parameter (the slope) against %d points, closed form" % len(tail),
                                                              "slope_per_year": float(slope), "intercept": float(intercept), "rmse_of_trend": rmse_trend}},
    }
    result = {"label": LABEL, "type": "COMPUTED from published figures and survey aggregates", "base_year": base_year,
              "parameters": {k.replace(".", "_"): v for k, v in params.items()},
              "tra_registered_taxpayers": {"definition": CFG["tra_registered_taxpayers"]["definition"], "latest": {"fiscal_year": latest["fiscal_year"], "registered_taxpayers": latest["registered_taxpayers"]},
                                           "n_years_used": len(used), "first_year": used[0]["fiscal_year"], "file": "data/processed/tra_registered_taxpayers.csv",
                                           "trend": {"years": [r["fiscal_year"] for r in tail], "slope_per_year": float(slope), "rmse": rmse_trend},
                                           "cp6_definitions": CFG["tra_registered_taxpayers"]["tra_cp6"]},
              "kept_separate_from": {"finscope_adult_tin_holders": "about 1.31 million ADULTS (16+) who say they hold a TIN, weighted FinScope 2023 estimate (outputs/tables/tin_by_segment.csv); a survey estimate of persons, Mainland and Zanzibar",
                                     "difference": "TRA counts TIN registrations (stock, individuals and entities, business and non-business, active or dormant) on the Mainland: 6.27 million in 2023/24; FinScope counts adults reporting a TIN: the two are not the same quantity and are not reconciled"},
              "tax_base_cells": il["tax_base_cells"],
              "mobile_money_users_note": "CONTEXT ONLY (Block E3.3): BoT counts active mobile-money ACCOUNTS (several per person possible): %s in %d, against %s adults using mobile money in FinScope 2023 (%s of %s respondents). The twin's user base is the FinScope adult count; the BoT account count and its 2019-2024 growth (x%.3f a year) are not used by the model." % (format(mm_users, ","), base_year, format(round(fm["users"]), ","), format(fm["n_users"], ","), format(fm["n_adults"], ","), cagr),
              "bot_active_mobile_money_accounts_context": {"value": mm_users, "year": base_year, "annual_growth_factor_2019_2024": float(cagr)},
              "tcra_corroboration_dec_accounts": CFG["tcra_mobile_money_dec"]}
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1, ensure_ascii=False)
    print("  twin inputs: TRA registered taxpayers %s (%s, %d years of series); population %.1fM, working age %.1fM; mobile-money active accounts %.1fM (x%.3f a year); formalisation %.4f per working-age adult" % (
        format(round(latest["registered_taxpayers"]), ","), latest["fiscal_year"], len(used), population / 1e6, working_age / 1e6, mm_users / 1e6, cagr, f_cal))
    return result


if __name__ == "__main__":
    run_twin_inputs()
