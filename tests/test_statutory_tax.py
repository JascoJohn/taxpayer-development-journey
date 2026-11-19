"""F1 / F2: the twin's tax is the statutory schedule applied to the earnings DISTRIBUTION; the schedule year; the new-TIN holiday sensitivity; the mobile-money levy lever."""
import csv
import hashlib
import json
import os
import sys

import numpy as np
import pytest

from conftest import ROOT, requires_documents

sys.path.insert(0, os.path.join(ROOT, "src"))
import paths  # noqa: E402,F401
import assumptions  # noqa: E402
import statutory_tax as st  # noqa: E402


def _twin_inputs():
    with open(paths.TWIN_INPUTS, encoding="utf-8") as f:
        return json.load(f)


def test_the_presumptive_schedule_is_that_of_the_finance_act_2026():
    spec = assumptions.A("tax.presumptive_schedule")
    assert spec["threshold_turnover"] == 200_000_000 and spec["above_11m_rate"] == 0.04          # Finance Act 2026, s. 27: ceiling 200M (was 100M), 4.0% (was 3.5%)
    assert "Finance Act 2026" in assumptions.entry("tax.presumptive_schedule")["source"] and "NIL" in assumptions.entry("tax.presumptive_schedule")["source"]
    t = np.array([3_000_000.0, 5_000_000, 7_000_000, 9_000_000, 11_000_000, 50_000_000, 200_000_000])
    got = st.presumptive(t)
    assert got[0] == 0 and got[1] == pytest.approx(30_000) and got[2] == pytest.approx(90_000) and got[3] == pytest.approx(150_000) and got[4] == pytest.approx(210_000)
    assert got[5] == pytest.approx(0.04 * 50_000_000) and got[6] == pytest.approx(0.04 * 200_000_000)                    # the ceiling itself is inside the regime
    assert st.presumptive(np.array([250_000_000.0]))[0] == pytest.approx(st.pit(np.array([250_000_000.0]))[0])             # above it the individual schedule applies
    # the resident schedule is unchanged since the R.E. 2023 text (Finance Acts 2024-2026 do not amend para 1)
    assert list(st.pit(np.array([3_240_000.0, 6_240_000, 9_120_000, 12_000_000]))) == [0, 240_000, 816_000, 1_536_000]
    assert "unchanged" in assumptions.entry("tax.pit_schedule")["source"] or "none amends" in assumptions.entry("tax.pit_schedule")["source"]


def test_owner_tax_uses_turnover_below_the_ceiling_and_net_earnings_above_it():
    assert st.owner_tax(np.array([20e6]), np.array([2e6]))[0] == pytest.approx(0.04 * 20e6)
    assert st.owner_tax(np.array([300e6]), np.array([40e6]))[0] == pytest.approx(st.pit(np.array([40e6]))[0])


def test_the_tax_follows_the_distribution_not_the_mean():
    ti = _twin_inputs()
    c = ti["tax_base_cells"]
    non, own = c["informal_nonowner"], c["informal_owner"]
    mean_earn = non["share"] * np.mean(non["annual_earnings"]) + own["share"] * np.mean(own["net_earnings"])
    flat = float(st.pit(np.array([mean_earn]))[0])                                    # the schedule applied to the MEAN: what a flat-rate-on-the-mean calculation would give
    dist = st.informal_mean_tax()
    assert dist > 3 * flat                                                            # the progressive schedule and the owners' presumptive tax make the mean of the tax far larger
    eff = st.effective_rates()
    assert eff["informal_mean_tax_tzs"] == pytest.approx(dist) and 0.05 < eff["informal_effective_rate_on_earnings"] < 0.2
    assert 0.02 < eff["msme_effective_rate_on_turnover"] < 0.045                       # between the 3% and the 4% marginal rates of the presumptive schedule
    # scaling the earnings scales the tax more than proportionally (progressivity)
    assert st.informal_mean_tax(1.5) > 1.5 * st.informal_mean_tax(1.0) * 0.99


def test_cells_are_aggregates_with_enough_respondents():
    c = _twin_inputs()["tax_base_cells"]
    for g, key in (("informal_nonowner", "annual_earnings"), ("informal_owner", "turnover"), ("all_owner", "turnover")):
        assert len(c[g][key]) == 100 and c[g]["min_cell_n"] >= paths.CFG["disclosure"]["min_base"]
    assert c["informal_nonowner"]["share"] + c["informal_owner"]["share"] == pytest.approx(1.0)
    assert "DISTRIBUTION" in c["definition"]


def test_the_flat_rates_are_retired_and_the_twin_reads_the_derived_means():
    for k in ("base.personal_income_tax_rate", "base.presumptive_tax_rate"):
        assert k not in assumptions.keys() and paths.CFG["retired_assumptions"][k]["retired_in"] == "Block F1"
    for k in ("base.new_taxpayer_mean_tax_tzs", "base.msme_mean_presumptive_tax_tzs"):
        e = assumptions.entry(k)
        assert e["basis"] == "DATA" and "value" not in e and e["from"].endswith("twin_inputs.json")
    assert assumptions.A("base.new_taxpayer_mean_tax_tzs") == pytest.approx(st.informal_mean_tax(), rel=1e-9)
    assert assumptions.A("base.msme_mean_presumptive_tax_tzs") == pytest.approx(st.msme_mean_tax(), rel=1e-9)
    code = open(os.path.join(ROOT, "src", "04_models", "economic_model.py"), encoding="utf-8").read()
    assert "personal_income_tax_rate" not in code and "presumptive_tax_rate" not in code and "def run_digital_twin" not in code


def test_the_new_tin_holiday_is_reported_as_a_sensitivity_only():
    with open(paths.STAGE_ECONOMICS, encoding="utf-8") as f:
        d = json.load(f)
    h = d["new_tin_holiday_sensitivity"]
    assert "NOT applied" in h["note"] and "twelve months" in h["note"]
    assert h["enterprise"]["with_holiday"]["median"] < h["enterprise"]["headline"]["median"]
    assert "horizon_10_flat_new_tin_holiday" in d["stages"]["enterprise"]["variants"]


# ------------------------------------------------------------------------------ F2: the mobile-money levy
def test_the_policy_twin_has_no_mobile_money_levy_lever():
    """Editing Pass 1 (P0): the owner removed the levy from the policy twin (not a framework lever); the real levy is documented in docs/mobile_money_levy.md only."""
    for k in ("twin.policy.mobile_money_levy", "twin.policy.hypothetical_additional_levy"):
        assert k not in assumptions.keys() and k in paths.CFG["retired_assumptions"], k
    assert paths.CFG["retired_assumptions"]["twin.policy.hypothetical_additional_levy"]["retired_reason"] == "removed by owner: not a framework lever"
    code = open(os.path.join(ROOT, "src", "04_models", "economic_model.py"), encoding="utf-8").read()
    assert "hypothetical_additional_levy" not in code and "mm_revenue" not in code and "levy_context" not in code
    with open(paths.ECONOMIC_MODEL, encoding="utf-8") as f:
        m = json.load(f)
    assert "digital_twin_baseline" not in m and "digital_twin_policy" not in m                      # the twin is retired (Pass 6B-1)


def test_the_levy_document_records_the_basis_the_schedule_and_the_citation():
    text = open(os.path.join(ROOT, "docs", "mobile_money_levy.md"), encoding="utf-8").read()
    for needle in ("Section 46A", "National Payment Systems Act", "Finance Act 2021", "GN 496A", "GN 642A", "GN 478V", "GN 596C", "Finance Act 2023", "withdrawals", "tiered fixed fee",
                   "Paul, Revocatus, and Dhiraj Sharma", "Policy Research Working Paper 11228", "GSMA. (2021)", "EPOCA"):
        assert needle in text, needle
    assert "No effective rate can be derived for the current regime" in text and "0.22%" in text


@requires_documents
def test_the_levy_schedule_in_the_document_is_the_one_in_the_gazette():
    import pymupdf
    pdf = os.path.join(ROOT, "data", "raw", "mof", "GN_596C_NPS_Electronic_Money_Transactions_Levy_Amendment_Regulations_2022.pdf")
    text = " ".join(pymupdf.open(pdf)[1].get_text().split())
    doc = open(os.path.join(ROOT, "docs", "mobile_money_levy.md"), encoding="utf-8").read()
    for band, rate in (("100-2,999", "10"), ("3,000-3,999", "14"), ("40,000-49,999", "419"), ("900,000-1,000,000", "1,776"), ("3,000,001 and above", "2,000")):
        assert "| %s | %s |" % (band, rate) in doc.replace("| 100,000-199,999 | 707 |", "")  or band in doc
    for rate in ("10", "14", "27", "54", "56", "102", "195", "306", "351", "419", "573", "707", "821", "838", "982", "1,245", "1,532", "1,700", "1,750", "1,776", "1,875", "2,000"):
        assert rate in text and rate in doc, rate


def test_the_new_source_documents_are_recorded_with_their_hashes():
    with open(os.path.join(ROOT, "data", "raw", "SOURCES.csv"), encoding="utf-8-sig", newline="") as f:
        rows = {r["file"]: r for r in csv.DictReader(f)}
    for rel in ("tra/Finance_Act_2024.pdf", "tra/THE_FINANCE_ACT,_2026.pdf", "tra/Taxes_and_Duties_at_a_Glance_2025_2026.pdf", "gsma/Tanzania-Mobile-Money-Levy-Impact-Assessment.pdf",
                "gsma/spec_tanzania_mm_report_02_22-1.pdf", "mof/GN_478V_NPS_Electronic_Money_Transaction_Levy_Regulations_2022.pdf",
                "mof/GN_596C_NPS_Electronic_Money_Transactions_Levy_Amendment_Regulations_2022.pdf", "mof/Kauli_ya_Serikali_Sept_2022_mobile_money_levy.pdf", "ey/EY_Tax_Alert_Finance_Act_2023_7_July_2023.pdf"):
        r = rows["data/raw/" + rel]
        assert len(r["sha256"]) == 64 and r["origin URL"].startswith("http") and r["citation"]
        p = os.path.join(ROOT, "data", "raw", *rel.split("/"))
        if os.path.exists(p):
            assert hashlib.sha256(open(p, "rb").read()).hexdigest() == r["sha256"], rel
