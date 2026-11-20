# Data terms: what we may do with the raw data, what is published, how others get it

Updated 2026-11-20 (Publishing Step 0b: the Household Budget Survey 2017/18 and the TRA FY2024/25 collections workbook added, sections 2, 4 and 9); earlier: 2026-11-12 (Block E2: TRA, BoT, TCRA and NBS publications added; Block E1: Afrobarometer added, aggregate-only combination of surveys stated; Block D0.2; first written in Block C0.4). Exact catalogue texts, URLs and the verbatim terms are in `data/raw/SOURCES.csv` (columns `licence/terms`, `citation`, `redistributable`, `publication_copy_obligation`). Audit details: `_archive/process_records/BLOCK_C_REPORT.md`.

## 1. The terms (National Data Archive, verbatim)

These are the terms recorded for **FinScope 2023 (FSDT), the ILFS 2024 and the Census 2022 (NBS) and the MoF reliefs workbook**. They are the terms stated by the data user (the project owner); the user states they **apply equally to FSDT and MoF**. For NBS they match the catalogue text read on the portal (redistribution, research use, no re-identification, citation); no separate FSDT or MoF terms text exists on their sites (searched 2026-11-11/12).

> 1. The data and other materials provided by the National Data Archive will not be redistributed or sold to other individuals, institutions, or organizations without the written agreement of the National Data Archive. 2. The data will be used for statistical and scientific research purposes only. They will be used solely for reporting of aggregated information, and not for investigation of specific individuals or organizations. 3. No attempt will be made to re-identify respondents, and no use will be made of the identity of any person or establishment discovered inadvertently. Any such discovery would immediately be reported to the National Data Archive. 4. No attempt will be made to produce links among datasets provided by the National Data Archive, or among data from the National Data Archive and other datasets that could identify individuals or organizations. 5. Any books, articles, conference papers, theses, dissertations, reports, or other publications that employ data obtained from the National Data Archive will cite the source of data in accordance with the Citation Requirement provided with each dataset. 6. An electronic copy of all reports and publications based on the requested data will be sent to the National Data Archive. 7. The original collector of the data, the National Data Archive, and the relevant funding agencies bear no responsibility for use of the data or for interpretations or inferences based upon such uses.

**Consequences for this project**

| Clause | What it means here |
|---|---|
| 1 | No raw file is redistributed. `redistributable = no` for all four sources. |
| 2 | Outputs are aggregates; the disclosure rule (`config.yaml disclosure`) suppresses any cell with fewer than 10 unweighted respondents. |
| 3 | No attempt to re-identify; the synthetic-population and decile outputs never write respondents as rows. |
| 4 | **No record linkage** between the datasets. FinScope, ILFS, the census and Afrobarometer are used for separate aggregates. Where the agent-based simulations combine surveys (Block E1), only AGGREGATE cell distributions are combined: agents take the age band and urban/rural residence of a FinScope cell (`data/processed/agent_cells.json`) and draw trust and morale from Afrobarometer cell distributions (`data/processed/agent_trust_morale.json`) and income from ILFS age-band distributions (`data/processed/agent_income.json`). No respondent of one survey is matched to a respondent of another, no person-level row is written, and the cells are published only above the disclosure threshold. |
| 5 | Cite each dataset per its Citation Requirement (section 4). |
| 6 | **Publication-copy obligation: CONFIRMED.** An electronic copy of the publication goes to NBS and FSDT (and MoF, whose workbook is used). Contacts printed in the sources: NBS Statistician General, sg@nbs.go.tz; FSDT, info@fsdt.or.tz. |
| 7 | The disclaimer is carried in the report acknowledgement. |

## 2. Status of each raw file

| File | Owner | Redistribute raw? | How a third party obtains it |
|---|---|---|---|
| `finscope/FinScope.csv`, `FinScope Datamap.xlsx` | FSDT (with NBS approval) | **no** | request form on https://www.fsdt.or.tz/finscope/ ("Download the Finscope Tanzania 2023 Datasets": name, organisation, e-mail) |
| `ilfs/ILFS2024-URT-FINAL - Anonymized.sav` | NBS | **no** | free account on the NBS microdata portal, accept the confidentiality declaration, https://microdata.nbs.go.tz/index.php/catalog/63 |
| `census/TPHC2022_TenPercent_DEMOGRAPHICS.sav` | NBS | **no** | same portal, https://microdata.nbs.go.tz/index.php/catalog/45 (the page does not name a 10% sample file; confirm with NBS which entry holds it) |
| `tax_exemptions/...MoF-Q1.XLSX` | Ministry of Finance | **no** | public page https://www.mof.go.tz/publications/tax-exemptions |
| `afrobarometer/afrobarometer_release-data_tan_r8_en_2021-06-10.sav` | Afrobarometer | **not stated**; treated as no | public download, https://www.afrobarometer.org/survey-resource/tanzania-round-8-data-2021/ (see section 6) |
| `hbs_2017_18/*.dta` (individual file, consumption aggregate, Form I sections) | NBS | **no** | NBS microdata catalogue, https://microdata.nbs.go.tz/ (register and accept the confidentiality declaration; see section 9) |
| `tra/TAX_COLLECTION_FOR_THE_FINANCIAL_YEAR_2024-25.xlsx` | Tanzania Revenue Authority | **no** (TRA terms: no commercial copying; no open licence) | public download from tra.go.tz, https://www.tra.go.tz/images/uploads/pages/Tax_Revenue_Collection_Statistics_2024_25FY.xlsx (see section 9) |
| `worldbank/*.json` | World Bank | **yes**, CC BY 4.0 (attribute the World Bank, WDI) | public API |

## 3. What this repository publishes and does not publish

**Published (aggregates only, disclosure rule applied)**: `data/processed/*.json`, `data/interim/*.json`, everything in `outputs/stats` and `outputs/tables`. **Not published**: everything under `data/raw/` except `SOURCES.csv`, READMEs and the World Bank snapshots (enforced by `.gitignore`). Synthetic data are never published as rows either (Block D3 replaced the synthetic 5,000-row population by decile aggregates). Zenodo receives processed and aggregate data only.

## 4. How to cite (catalogue text, verbatim; see SOURCES.csv)

* ILFS 2024: the catalogue field reads "National Bureau of Statistics (NBS) [Tanzania] 2022. Tanzania Integrated Labour Force Survey 2020/21, Dodoma, Tanzania: NBS". **OPEN ITEM: it names the 2020/21 round, not 2024; ask NBS which wording applies.** Until then cite the published report as well: NBS (2025), *The Labour Market: Key Findings from the ILFS 2024*.
* Census 2022: "National Bureau of Statistics (NBS) [Tanzania]2022 National Demographic Socio Economic Profile.Dodoma, Tanzania: NBS" (names a publication, not the microdata). The age counts are checked against NBS (2022), *The 2022 Population and Housing Census: Age and Sex Distribution Report*.
* FinScope 2023: no citation requirement found; working wording "FinScope Tanzania 2023 (FSDT)", to be confirmed with FSDT. The acknowledgement text in `economic_model.json` (`finscope_acknowledgement`) stays.
* Household Budget Survey 2017/18: "National Bureau of Statistics (NBS), Tanzania. Household Budget Survey 2017/18, Tanzania Mainland. Dodoma: NBS"; NBS is acknowledged as the original collector.
* TRA tax collections workbook FY2024/25: "Tanzania Revenue Authority. Tax revenue collection statistics, FY2024/25. tra.go.tz resource centre."
* MoF workbook: no requirement; cite title, publisher and the publication page.
* Afrobarometer Round 8 Tanzania: "Afrobarometer Data, Tanzania, Round 8, 2021, available at http://www.afrobarometer.org" (the form given by the Afrobarometer data usage and access policy).

## 5. Items flagged by the audit (Block C), status

1. **Raw FinScope files were in an earlier version of the git history** (`pipeline/FinScope.csv`, `pipeline/FinScope Datamap.xlsx`). They were removed from every commit with git-filter-repo (2026-11-15) before anything was published; the cleaned history is pushed to a new repository (`docs/publishing_checklist.md`), and no raw file of FSDT, NBS, Afrobarometer or the Ministry of Finance is tracked.
2. **Small cells**: handled by the disclosure rule (Block D1); counts per file are in `_archive/process_records/BLOCK_D_REPORT.md`.

## 6. Afrobarometer Round 8, Tanzania (added in Block E1; not a National Data Archive dataset)

* Downloaded 2026-11-12 from the Afrobarometer site (URL, SHA-256 and the policy text are in `data/raw/SOURCES.csv`). The National Data Archive terms in section 1 were stated for FSDT, ILFS, the census and MoF; they are not assumed to govern Afrobarometer, whose own **data usage and access policy** applies: the data are "free for you to use", are protected by copyright, and published work must acknowledge the source (citation form in section 4). The policy asks that a copy of any publication be e-mailed to Afrobarometer's head of publications.
* **The policy has no clause on redistribution.** The raw file is therefore treated like the other raw data: not published (`data/raw/**` is git-ignored). Published: aggregates only (`data/processed/afrobarometer_morale.json`, `outputs/tables/tax_morale_components.csv`, `data/processed/agent_trust_morale.json`), disclosure rule applied.
* Clause 4 of section 1 (no record linkage) is observed for this dataset as well: it is combined with FinScope and ILFS through aggregate cell distributions only (see the table in section 1).

## 7. Published reports and statutes used in Block E2 (TRA, BoT, TCRA, NBS)

These are PUBLIC PUBLICATIONS (statistical reports, annual reports, statutes), not microdata. They were downloaded or copied into `data/raw/<publisher>/` (git-ignored) and are listed file by file in `data/raw/SOURCES.csv` with URL, SHA-256, access and citation.

| Publisher | Files | Terms found | How to cite |
|---|---|---|---|
| NBS | Tax Statistics Reports 2022/23 and 2023/24, Mainland Tanzania (registered taxpayers, source TRA) | no terms of use read; public download | National Bureau of Statistics, *Tax Statistics Report 2022/23 / 2023/24, Mainland Tanzania*, Dodoma (URL in SOURCES.csv); the figures are TRA's |
| TRA / Government of Tanzania | Sixth Corporate Plan (revised June 2024); Income Tax Act Cap. 332 R.E. 2023; Finance Act 2025 | public documents; the statute PDFs carry a Government of Tanzania copyright notice (no reproduction without OAG permission) | Tanzania Revenue Authority, *Sixth Corporate Plan 2021/22-2025/26 (revised June 2024)*; *The Income Tax Act, Cap. 332 R.E. 2023*; *The Finance Act, 2025* |
| Bank of Tanzania | National Payment Systems Annual Reports 2022, 2023 (Swahili), 2024, 2025 | no terms of use read; public download | Bank of Tanzania, *National Payment Systems Annual Report <year>*, Dar es Salaam (URLs in SOURCES.csv) |
| TCRA | Quarterly communications statistics, December quarters 2015-2025 and September 2019 (copied from the MultiAgent project) | no terms of use read | Tanzania Communications Regulatory Authority, *Quarterly Communications Statistics, quarter ending <month year>* |

* **Redistribution is not stated** for any of them; the raw files are not published. What the repository publishes is the transcribed figures with their provenance (`data/processed/tra_registered_taxpayers.csv`, `data/processed/twin_inputs.json`).
* The National Data Archive clauses of section 1 do not apply to these publications (they are not NDA datasets); the no-linkage rule is not engaged because no microdata are involved. The ILFS 2024 microdata used for informal earnings, MSME receipts and revenue per registrant remain under the NDA terms and only aggregates (means, percentiles, shares of at least 10 respondents) are published.
* No publication-copy obligation was found for these publishers; the Afrobarometer request (section 6) and the NDA clause 6 (section 1) still apply to the publications that use those data.

## 8. Licences of what is published (Pass 5, 2026-11-16)

Code: MIT. Report and figures: CC BY-NC-ND 4.0. The project's aggregate data (`data/processed/`, `data/interim/`, `outputs/stats/`, `outputs/tables/`): CC BY 4.0. The raw data are not covered by any of these licences, belong to their owners and are not redistributed (section 2); aggregates derived from them are published under the disclosure rule (section 3) and the terms above. Third-party data, publications and materials keep their owners' terms. See `LICENSE`.

## 9. Household Budget Survey 2017/18 and the TRA FY2024/25 collections workbook (added in Publishing Step 0b)

### Household Budget Survey (HBS) 2017/18, Tanzania Mainland (NBS)

* **Source and terms.** Microdata of the National Bureau of Statistics (individual file, consumption aggregate with weights, Form I section 10C; section 10A is context only). The National Data Archive terms of section 1 are taken to apply, as for the other NBS files (file-by-file record, hashes and the verbatim terms in `data/raw/SOURCES.csv`). Clause 6 (publication copy to NBS) applies.
* **Raw files are private and not redistributed.** `data/raw/hbs_2017_18/` is git-ignored and is not in any public release or in the dataset record. A third party obtains the files from the NBS microdata catalogue, https://microdata.nbs.go.tz/ (register and accept the confidentiality declaration).
* **Aggregates only.** What is published is `data/processed/hbs_turnover.json` and the tables and statistics derived from it (`outputs/stats/taxable_capacity.json`, `outputs/stats/mzani_turnover.json`, `outputs/tables/taxable_capacity*.csv`, `outputs/tables/mzani_turnover_*.csv`): percentiles, shares and bands of the monthly receipts of non-farm household-business owners, by zone, region and activity, and the presumptive tax at those values. The disclosure rule applies: a region-by-activity cell needs at least 30 businesses with receipts and otherwise falls back to the zone cell (at least 10), then to the national cell; cells below these thresholds carry no estimate (withheld), and low-precision shares are flagged. No respondent is written as a row.
* **No record linkage (clause 4).** HBS is not linked at respondent level to FinScope, ILFS, the Census or Afrobarometer. It is used on its own to produce aggregates; those aggregates are then applied to the stage populations that FinScope gives (revenue per registrant x number of registrants), and the only other input is the World Bank consumer price index. No respondent of one survey is matched to a respondent of another.
* **Use.** Revenue per registrant of the Active and Enterprise stages (central income basis), taxable capacity and the Mzani wa Kodi reference bands; the 2017/18 values are expressed in 2024 prices with a general price index, which is a stated assumption (`config.yaml`, `hbs.cpi_uprating`).

### TRA tax collections workbook, FY2024/25 (Tanzania Revenue Authority)

* **Source and terms.** Public download from tra.go.tz (URL in section 2 and in `data/raw/SOURCES.csv`). The TRA website terms and conditions (intellectual property) say content may not be copied, reproduced or distributed for commercial purposes without prior written permission from TRA; there is no open licence. No publication-copy obligation was found.
* **The raw workbook is not redistributed.** `data/raw/tra/` is git-ignored and is not in any public release or in the dataset record. This project is non-commercial research and cites the workbook with attribution.
* **What is published.** The transcribed collection totals with their provenance (`data/processed/tra_collections_2024_25.json`, `outputs/stats/reach_scenarios.json`): CITED figures used to scale-check the reach scenarios (Figure 5.2), not a copy of the workbook. Anyone who reuses them commercially needs TRA's permission.
* **Obtain it.** Download the workbook from tra.go.tz and rename it to the `config.yaml` file name `TAX_COLLECTION_FOR_THE_FINANCIAL_YEAR_2024-25.xlsx`.
