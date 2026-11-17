# The Taxpayer Development Journey — A Behavioral Lifecycle Architecture for Tax Compliance: Evidence from Tanzania

Author: Jasco John, MBA, CPA(T) (ORCID https://orcid.org/0009-0007-3630-7943). Code: MIT. Report and figures: CC BY-NC-ND 4.0. Aggregate data: CC BY 4.0 (see `LICENSE`).

## Links

* **Report** (Zenodo record, PDF): DOI [Report DOI]
* **Dataset** (Zenodo record, aggregate data only): DOI [Dataset DOI]
* **Archived code** (Zenodo record created automatically from each GitHub release; first release v0.9.0): DOI [Code DOI]
* **Dashboard**: https://taxpayer-development-journey.streamlit.app
* **Repository**: https://github.com/JascoJohn/taxpayer-development-journey
* The publication copy of the report is added to `report/final/` (Word and PDF) with release v1.0.0; release v0.9.0 holds the code, the aggregate data, the outputs, the dashboard and the documentation.

(The DOIs are filled in when the Zenodo records exist; the literal strings `[Report DOI]`, `[Dataset DOI]` and `[Code DOI]` stand in until then. `.zenodo.json` holds the metadata of the automatic code record.)

## Purpose

Tanzania collects about 12% of GDP in tax and fewer than 4 in 100 adults hold a Taxpayer Identification Number (TIN). This project asks whether a **behavioural lifecycle architecture** can widen the tax base: six
stages (Seed, Entry, Active, Enterprise, Asset, Legacy), each with one tool built for the moment in a person's life at which they meet the tax system. The repository contains

* the **pipeline** that regenerates every number of the analysis from survey and published data (`run_all.py`, `src/`),
* the **figures** (`src/06_figures/`, `outputs/figures/`),
* the **Streamlit dashboard** that reads the pipeline's outputs (`dashboard/`),
* the **tests** (`tests/`), and the records that make every number traceable (`docs/`).

Every number in the report is one of three types: **COMPUTED** (real data and a script in this project), **MODELLED** (a scenario output from stated assumptions in `config.yaml`; each assumption is in
`docs/assumptions_register.csv` with its class, source, sensitivity and the owner's sign-off), or **CITED** (a published figure with a full reference, no computation). Anything else was removed.
`docs/claims_map.csv` lists every number of the report with its current value, type, source script and output file.

## Folder structure

| Folder or file | Content |
|---|---|
| `run_all.py` | the single entry point (see "Run modes") |
| `config.yaml` | every location, the disclosure rule, the simulation settings and the assumptions block (value, basis class, source, what it feeds, sign-off) |
| `src/` | the code: `01_ingest` (World Bank fetch), `03_features` (survey and census aggregates), `04_models` (targeting model, tax-morale model, agent simulations, digital twin, Table 40), `06_figures` (one script per figure and the dashboard screenshot script), `tools` (register, sensitivity, sign-off sheet, one-off extractions), `paths.py`, `assumptions.py`, `disclosure.py` |
| `data/raw/` | the raw inputs (NOT in the repository except `SOURCES.csv`, READMEs and the World Bank snapshots; see "How to obtain the raw data") |
| `data/interim/`, `data/processed/` | aggregates written by the pipeline; `data/processed/README.md` describes every file |
| `outputs/stats/`, `outputs/tables/` | model outputs and tables (aggregates only; a cell with fewer than 10 respondents carries no estimate) |
| `outputs/figures/` | the figures (PNG and SVG, `fig_<id>_<name>`) and, with `--screenshots`, `dashboard_<page>.png` |
| `dashboard/` | the Streamlit app (7 pages) |
| `tests/` | the tests (pytest); tests that need restricted raw data skip with a message when it is absent |
| `docs/` | `data_terms.md`, `assumptions_register.csv`, `claims_map.csv`, `interventions.yaml`, `mobile_money_levy.md`, `known_issues.md`, `publishing_checklist.md`, the sign-off sheet and the code-change records of each work block |
| `environment/` | pinned requirements (`requirements.txt`, and `requirements-screenshots.txt` for the optional screenshots) |
| `report/final/` | the publication copy of the report (Word and PDF), added with release v1.0.0; the rest of `report/` is private working material and is not published |
| `_archive/` | superseded material and process records (git-ignored) |

## Install

Python 3.14 (developed on 3.14.1). From the project folder:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r environment/requirements.txt      # Windows; on Linux / macOS: .venv/bin/python
```

Optional, only for dashboard screenshots: `pip install -r environment/requirements-screenshots.txt` and `python -m playwright install chromium`.

## Run modes

```bash
python run_all.py                    # --from-raw (default): every step, from the files in data/raw/
python run_all.py --clean            # empty the generated folders first (never data/raw, docs, report), then run
python run_all.py --from-processed   # no raw data needed: read data/interim, data/processed and the tracked outputs; regenerate the model outputs, Table 40, the figures
python run_all.py --fetch            # refresh the World Bank WDI snapshots (the only network call; nothing else touches the network)
python run_all.py --screenshots      # also take Playwright screenshots of the 7 dashboard pages (outputs/figures/dashboard_*.png)
python -m pytest                     # the tests
python -m streamlit run dashboard/Home.py
```

`--from-processed` needs no restricted data. The steps that read the restricted microdata (FinScope, ILFS, Census, Afrobarometer, the MoF workbook) are skipped with a message, and their published aggregates
are used instead. Timestamps and the run id go to `outputs/stats/run_meta.json`, so two runs give identical data files and figures.

## How to obtain the raw data

The raw data are not redistributed (terms: `docs/data_terms.md`; file-by-file provenance, hashes and citations: `data/raw/SOURCES.csv`). Put each file where `config.yaml` (`files:`) expects it.

| Data | Owner | How to obtain |
|---|---|---|
| FinScope Tanzania 2023 respondent file and data map (`data/raw/finscope/`) | FSDT (with NBS approval) | request form on https://www.fsdt.or.tz/finscope/ |
| ILFS 2024 microdata, anonymised (`data/raw/ilfs/`) | NBS | free account on the NBS microdata portal, https://microdata.nbs.go.tz/index.php/catalog/63 |
| Census 2022 10% sample (`data/raw/census/`) | NBS | the same portal, https://microdata.nbs.go.tz/index.php/catalog/45 (confirm with NBS which entry holds the 10% sample) |
| Afrobarometer Round 8, Tanzania (`data/raw/afrobarometer/`) | Afrobarometer | public download, https://www.afrobarometer.org/survey-resource/tanzania-round-8-data-2021/ |
| MoF tax exemptions and reliefs workbook (`data/raw/tax_exemptions/`) | Ministry of Finance | public page https://www.mof.go.tz/publications/tax-exemptions |
| Published reports and statutes (`data/raw/nbs`, `tra`, `bot`, `tcra`, `mof`, `gsma`, `ey`) | NBS, TRA, Bank of Tanzania, TCRA, MoF, GSMA, EY | public downloads; the URL of each is in `data/raw/SOURCES.csv` and in `config.yaml` (`twin_inputs.documents`) |
| World Bank WDI snapshots (`data/raw/worldbank/`) | World Bank | in the repository (CC BY 4.0); refresh with `--fetch` |

## Which output backs which report table or figure

| Report item | Output |
|---|---|
| Fig 5.1 (modelled compliance probability) | `outputs/stats/economic_model.json` (`tax_morale_model`), `outputs/figures/fig_5_1_modelled_compliance` |
| Fig 5.2 (ten-year digital twin) | `outputs/stats/economic_model.json` (`digital_twin_baseline`, `digital_twin_policy`), `outputs/figures/fig_5_2_digital_twin` |
| Table 40 (cost, revenue, NPV, ROI by stage) and the persistence sensitivity | `outputs/tables/table40_stage_economics.csv`, `outputs/stats/stage_economics.json`, `outputs/figures/fig_5_3_table40_roi_by_stage`, `fig_5_4_persistence_sensitivity` |
| TIN rates by lifecycle segment, the TIN reconciliation callout | `outputs/tables/tin_by_segment.csv`, `outputs/stats/tin_reconciliation.json`, `outputs/figures/fig_a1_tin_by_segment` |
| Mobile money and TIN holding | `outputs/stats/tin_mobile_money.json`, `outputs/tables/tin_mobile_money.csv` |
| Targeting model (AUC, Entry multiplier, deciles) | `outputs/stats/targeting_model.json`, `outputs/tables/targeting_variants.csv`, `targeting_deciles.csv`, `outputs/figures/fig_a3_targeting_deciles`, `fig_a4_targeting_variants` |
| Tax-morale components (Afrobarometer) | `outputs/tables/tax_morale_components.csv`, `outputs/figures/fig_a2_tax_morale_components` |
| Informality, registration, earnings (ILFS 2024) | `outputs/tables/ilfs_informality.csv`, `outputs/stats/ilfs_summary.json` |
| Macro: tax-to-GDP and the gap | `outputs/stats/macro_inputs.json`, `outputs/figures/fig_a5_macro_gap` |
| Seed population | `outputs/stats/seed_population.json` |
| Tier migration and agent simulation (Enterprise page) | `outputs/stats/economic_model.json` (`tier_migration_simulation`, `agent_based_simulation`) |
| Dashboard screenshots (report Figs 4.16, 4.21, 4.26) | `outputs/figures/dashboard_<page>.png` (`--screenshots`) |
| Every number, claim by claim | `docs/claims_map.csv` |

## Evidence types

* **COMPUTED**: calculated from real data by a script here (survey-weighted; the disclosure rule suppresses cells with fewer than 10 respondents).
* **MODELLED**: a scenario, never a forecast. Its assumptions are in `config.yaml` and in `docs/assumptions_register.csv` (basis class DATA, CALIBRATED, ASSUMPTION or UNKNOWN; label; sensitivity; the owner's sign-off). Outputs say "MODELLED scenario".
* **CITED**: a published figure with its source and page, not recomputed.

## How to cite

Cite the report, and the dataset or the code where you use them (the machine-readable form is `CITATION.cff`):

* **Report**: John, J. (2026). *The Taxpayer Development Journey — A Behavioral Lifecycle Architecture for Tax Compliance: Evidence from Tanzania*. Independent project report. Zenodo. [Report DOI]
* **Dataset (aggregate data)**: John, J. (2026). *The Taxpayer Development Journey: Aggregate Data* [Data set]. Zenodo. [Dataset DOI]
* **Code**: John, J. (2026). *The Taxpayer Development Journey: Code* (version 1.0) [Computer software]. Zenodo. [Code DOI]

Cite the datasets that underlie the analysis as each owner requires (`docs/data_terms.md`, section 4; `data/raw/SOURCES.csv`, column `citation`).

## Licences

* **Code** (`run_all.py`, `src/`, `dashboard/`, `tests/`, configuration and documentation files): MIT (`LICENSE`).
* **Report and figures** (`report/final/`, `outputs/figures/`): CC BY-NC-ND 4.0, attribution to Jasco John: they may be read, shared and cited with attribution, but not used commercially or adapted without the author's written permission. Third-party materials keep their owners' terms.
* **Aggregate data** (`data/processed/`, `data/interim/`, `outputs/stats/`, `outputs/tables/`): CC BY 4.0, attribution to Jasco John.
* **Raw data**: not covered by these licences; the raw data belong to their owners and are not redistributed. World Bank WDI snapshots are CC BY 4.0. Aggregates derived from restricted data follow the disclosure rule and the terms in `docs/data_terms.md`.

(c) 2026 Jasco John. For permissions, collaboration or institutional engagement: jasco.john98@gmail.com.
