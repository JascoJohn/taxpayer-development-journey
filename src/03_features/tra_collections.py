"""W-TRA (Pass 6B-1) - TRA tax collections FY2024/25 as AGGREGATES: the scale check of the reach scenarios (Figure 5.2) compares the modelled year-10 revenue with what the TRA collects.

Source: TRA, "TAX COLLECTION FOR THE FINANCIAL YEAR 2024-25" (quarterly workbook, million TZS, nominal, gross collections), data/raw/tra/ (public, not redistributed with the repository).
  * departmental sheet (first sheet): Domestic Revenue, Customs and Excise, Large Taxpayers, TOTAL 1 (GROSS), TOTAL (NET); annual = the sum of the four quarterly 'Total' columns
  * tax-item sheet (second sheet): Individuals (income tax of individuals), Rental tax, PAYE, Total (Gross) of the direct taxes
Evidence type: CITED (read from the TRA workbook, not estimated). Only the FY2024/25 workbook is held (owner decision, Pass 6B-1).

Outputs: data/processed/tra_collections_2024_25.json
"""
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # src/
import paths

LABEL = "CITED: TRA quarterly collections workbook FY2024/25, million TZS nominal, gross; annual = sum of the four quarterly 'Total' columns"


def _quarter_total_cols(d, header_label):
    """Header row (first column starts with header_label) and the column indices of the four quarterly 'Total' columns."""
    for i in range(0, 8):
        if str(d.iloc[i, 0]).strip().upper().startswith(header_label):
            for j in range(i, min(i + 3, len(d))):
                cols = [c for c, v in enumerate(d.iloc[j].values) if str(v).strip().lower() == "total"]
                if len(cols) >= 4:
                    return j, cols[:4]
    raise ValueError("layout of the TRA workbook not recognised (header %r)" % header_label)


def _annual(d, row, cols):
    v = pd.to_numeric(d.iloc[row, cols], errors="coerce")
    if not v.notna().all() or int((v.fillna(0) != 0).sum()) < 4:
        raise ValueError("fewer than four quarters reported")
    return float(v.sum())


def read_workbook(path):
    x = pd.ExcelFile(path)
    dep = x.parse(x.sheet_names[0], header=None)
    hj, hc = _quarter_total_cols(dep, "DEPARTMENT")
    rows = {}
    for r in range(hj + 1, len(dep)):
        lab = str(dep.iloc[r, 0]).strip().lower()
        for key, start in (("domestic_revenue", "domestic revenue"), ("customs_excise", "customs and excise"), ("large_taxpayers", "large taxpayers"), ("total_gross", "total 1"), ("total_net", "total (net)")):
            if lab.startswith(start) and key not in rows:
                rows[key] = _annual(dep, r, hc)
    ti = x.parse(x.sheet_names[1], header=None)
    hj, hc = _quarter_total_cols(ti, "TAX ITEM")
    for r in range(hj + 1, min(len(ti), hj + 45)):
        lab = str(ti.iloc[r, 0]).strip().lower()
        for key, ok in (("individuals_income_tax", lab.startswith("individuals")), ("rental_tax", lab.startswith("rental tax")), ("paye", lab.replace(" ", "").replace(".", "").startswith("paye")),
                        ("direct_tax_gross", lab.startswith("total (gross)"))):
            if ok and key not in rows:
                rows[key] = _annual(ti, r, hc)
    need = {"domestic_revenue", "customs_excise", "large_taxpayers", "total_gross", "total_net", "individuals_income_tax", "rental_tax", "paye", "direct_tax_gross"}
    assert need <= set(rows), sorted(need - set(rows))
    return rows


def run_tra_collections(from_processed=False, json_path=None):
    json_path = json_path or paths.TRA_COLLECTIONS_JSON
    if from_processed:
        with open(json_path, encoding="utf-8") as f:
            return json.load(f)
    m = read_workbook(paths.TRA_COLLECTIONS_XLSX)
    result = {"label": LABEL, "type": "CITED", "fiscal_year": "2024/25", "source": "Tanzania Revenue Authority, quarterly tax collections workbook FY2024/25 (data/raw/SOURCES.csv)", "unit_of_source": "million TZS",
              "million_tzs": m, "tzs": {k: v * 1e6 for k, v in m.items()}}
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1, ensure_ascii=False)
    print("  TRA FY2024/25: individuals' income tax TZS %.1fB; domestic revenue TZS %.2fT; total gross TZS %.2fT" % (m["individuals_income_tax"] / 1e3, m["domestic_revenue"] / 1e6, m["total_gross"] / 1e6))
    return result


if __name__ == "__main__":
    run_tra_collections()
