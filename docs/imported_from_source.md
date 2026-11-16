# Files imported from the MultiAgent project

These files were copied **unchanged** from the MultiAgent project and are **not wired into** `run_all.py`.
They are the raw sources and producing scripts behind report values that this project's own pipeline does not compute.
Scripts sit in `src\imported\`, raw data in `data\raw\`, database exports in `data\external\`.

Database exports were made read-only (`mode=ro&immutable=1`) from the MultiAgent evidence database; the whole database was not copied.
Export files are named `db_export_<table>.csv`. Row counts below are those of the export.

| # | Report value (report location) | Imported file(s) | What the files show |
|---|---|---|---|
| 1 | **46.9% of business owners hold a government registration / licence** (s4.4) | `data\raw\ilfs\ILFS2024-URT-FINAL - Anonymized.sav`; `src\imported\ilfs_loader.py`; `data\external\db_export_ilfs_indicators.csv` (234 rows); `data\external\db_export_verified_data_imported_subset.csv` | The source row is `biz_registered_not registered` = 46.88, label "Business registered: Not registered". The report states the opposite meaning (holds a registration), so the direction of this figure needs checking against the ILFS variable coding. |
| 2 | **ILFS 2024 informality 94.6% (92.5% in 2020/21) and 74.8% self-employed** (s4.3) | same ILFS files as row 1 | None of 94.6, 92.5 or 74.8 occurs in the exported ILFS indicators. The database holds `ilfs_self_employment_rate_pct` = 27.73 and `ilfs_formal_employment_rate_pct` = 3.68. The microdata (.sav) is included so the report figures can be recomputed. |
| 3 | **8.77% tax-exemption rate** (hard-coded in `src\04_models\economic_model.py`, `load_exemption_params`; funnel Payment-stage leakage) | `data\raw\tax_exemptions\en-1709023578-All_Reliefs and Exemptions FY2023_24 MoF-Q1.XLSX`; `src\imported\tax_exemptions_loader.py`; `data\external\db_export_verified_data_imported_subset.csv` (indicator `tax_exemption_pct_of_collection_2023_24_q1` = 8.77); `data\external\db_export_tax_exemption_category_breakdown.csv` (16 rows) | Source of the constant. The original loader also reads two PDFs (Tax Expenditure Report 2024, Dondoo) that were not copied because the 8.77 figure comes from the XLSX. |
| 4 | **Monte Carlo revenue ranges in Table 40: Entry "8.7-9B", Active "12.8-13B"** | `src\imported\economic_model_per_intervention.py`; `data\external\db_export_intervention_economic_results.csv` (14 rows) | Entry-stage record INT-1539E9: mean 8.705B TZS, 80% interval 6.19B-11.52B. Active-stage record INT-A78BB9: mean 12.808B TZS, 80% interval 9.11B-16.94B. Eight of the 14 records are flagged `data_gap` (no revenue estimate). The script also reads the `evidence_items` and `causal_evidence` tables, which were not exported. |
| 5 | **Tax morale 59.8% (Afrobarometer) and the 28 pp reciprocity gap (71% civic duty vs 43% government listens)** (Table 5, s1) | `src\imported\data_layer_expansion.py` (`fetch_afrobarometer_data`); `data\external\afrobarometer_summary.json`; `data\external\db_export_tax_morale.csv` (10 rows) | Hand-entered published Round 8 figures; no microdata exists. The 59.8% is a composite with assumed weights (civic duty 30 / trust 35 / non-avoidance 20 / reciprocity 15). |
| 6 | **Tax morale 61.8% (World Values Survey)** (Executive Summary, s1, Table 5) | `src\imported\wvs_loader.py` (disabled in its source project on 2026-07-04: Tanzania is not in WVS-7); `data\external\db_export_wvs_indicators.csv` (**0 rows**) | No data source exists for this figure. The loader header records that the cited report "does not appear to exist". Kept as evidence of the gap, not as a source. |

## Not covered by any imported file

* Table 40: Enterprise revenue 4.1B (ROI ~5.5x) and Legacy revenue 2.5B (ROI ~3.6x): the exported Monte Carlo table flags those records as `data_gap`. (A different record, INT-F03EC0 "Visible Tax Returns Campaign", has a 4.10B base estimate; whether the Enterprise figure came from it is unverified.)
* The DiD, propensity-score and synthetic-control figures (s5.3): produced by hard-coded or simulated inputs inside `economic_model.py`, not by imported data.

Nothing here was run, edited or wired in. See `_archive/process_records/REORG_REPORT.md` for context.
