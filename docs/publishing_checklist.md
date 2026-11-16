# Publishing checklist (started 2026-11-12, Block D0.4; rewritten in Editing Pass 5, 2026-11-17)

Do these before the repository and the Streamlit app are made public again. History rewriting, visibility changes and the sending of copies are the owner's actions; nothing below marked `[ ]` has been done by the pipeline work.

## Done in the project (ticked by Block F)

- [x] **Raw data are not tracked**: `.gitignore` excludes `data/raw/**` except `SOURCES.csv`, READMEs and the World Bank snapshots; provenance, hashes and citations of every raw file are in `data/raw/SOURCES.csv`; terms in `docs/data_terms.md`.
- [x] **README** (purpose, structure, install, run modes, how to obtain each raw dataset, output-to-report map, evidence types, citation, licences), **LICENSE** (MIT for the code, CC BY 4.0 note for the report and figures), **CITATION.cff**, `data/processed/README.md`.
- [x] **Final claims map** `docs/claims_map.csv` (79 claims: current value, type, label, source script, output file, status); the working draft is in `_archive/`.
- [x] **Every assumption classified and signed**: `docs/assumptions_register.csv` (class, label, feeds with current values, sensitivity, sign-off); none awaits sign-off (the levy lever was removed from the policy twin in Editing Pass 1).
- [x] **Figures are scripted** (`src/06_figures`, run by `run_all.py`; PNG and SVG; byte-reproducible) and **dashboard screenshots are scripted** (`run_all.py --screenshots`, Playwright).
- [x] **No absolute paths** in code, tests or config; tests that need restricted raw data skip with a message when it is absent (`tests/conftest.py`).
- [x] **`run_all.py --from-processed`** regenerates the model outputs, Table 40 and the figures without the restricted raw data (steps that need them are skipped with a message).
- [x] **Outsider simulation**: a copy of the files git would track, a fresh virtual environment from `environment/requirements.txt`, `run_all.py --from-processed` and the full test suite (result in `_archive/process_records/BLOCK_F_REPORT.md`).
- [x] Frozen LLM report sections and `src/imported/` are out of the pipeline (`_archive/frozen`, `_archive/imported`); the interventions come from `docs/interventions.yaml` (reviewed by the owner 2026-11-13; the LLM drafts are in `_archive/interventions_llm_drafts.yaml`).

## Done in Editing Pass 5 (release v0.9.0 prepared, nothing pushed)

- [x] **History cleaned and rebuilt locally**: `pipeline/FinScope.csv`, `pipeline/FinScope Datamap.xlsx` and two local editor-configuration files were removed from every commit (git-filter-repo) and neutral wording replaced the competition wording; the 8 earlier commits keep their authors, dates and messages; the later work is recreated as logical commits; the annotated tag `v0.9.0` is on the last commit (no tag `v1.0.0` yet). Checks are in `_archive/publishing/history_p5_verification.md`.
- [x] **Licences**: code MIT; report and figures CC BY-NC-ND 4.0; aggregate data CC BY 4.0 (README, LICENSE, CITATION.cff, `data/processed/README.md`, `dashboard/README.md`, `docs/data_terms.md` section 8, the report).
- [x] **Placeholders** that stay until the Zenodo records exist: `[Report DOI]`, `[Dataset DOI]`, `[Code DOI]` (yellow in the report) and `[date-released]` in CITATION.cff.
- [x] **Zenodo**: `.zenodo.json` (code record), the data-only dataset package and the metadata of the three records are in `_archive/publishing/zenodo/` (git-ignored; not published by git).
- [x] **ORCID, repository URL, dashboard URL and version (0.9.0)** are set in `CITATION.cff` (ORCID since Editing Pass 1).
- [x] **Report**: working copy v6 (Track Changes by "Claude Code - Pass 5"), claims check `docs/claims_map_v5_check.csv` (80 OK), publication candidate `report/final/` (untracked until release v1.0.0).

## To do by the owner (in this order; the exact commands are in `_archive/publishing/OWNER_STEPS.md`)

- [ ] **A. During the review of the report**: rename the repository to `taxpayer-development-journey`, point the remote at it, force-push the cleaned history with lease and the tag `v0.9.0`; send the GitHub Support request to purge the old cached views and forks; keep the repository PRIVATE until GitHub confirms.
- [ ] **B. After the confirmation**: make the repository public, switch the GitHub-Zenodo integration ON, publish the release `v0.9.0` (creates the code DOI), check the record against `.zenodo.json`.
- [ ] **C. Dataset record**: upload `record_B_dataset/` (zip and DATA_README.md) to Zenodo with `metadata_B.md`; reserve the report record with `metadata_A.md` to obtain the reserved DOI.
- [ ] **D. Dashboard**: deploy on Streamlit Community Cloud (repository, branch `main`, main file `dashboard/Home.py`, Python 3.14, subdomain `taxpayer-development-journey`), make it public, delete the old app.
- [ ] **E. Final pass**: give the three DOIs (Report, Dataset, Code) so the placeholders are replaced, the final report is added to `report/final/`, and release v1.0.0 is made.
- [ ] **Send an electronic copy of the publication to NBS and FSDT** (and to the Ministry of Finance, whose reliefs workbook is used). Clause 6 of the National Data Archive terms (`docs/data_terms.md`). Contacts printed in the sources: NBS Statistician General sg@nbs.go.tz; FSDT info@fsdt.or.tz.
- [ ] **Cite each dataset per its Citation Requirement** (`data/raw/SOURCES.csv`, column `citation`; `docs/data_terms.md` section 4). NBS also requires acknowledging NBS as the original collector of the data.
- [ ] **Resolve the citation wording** of the ILFS 2024 (ask NBS) and of FinScope (ask FSDT); open items in `data/raw/SOURCES.csv`.
- [ ] **Retrieve the texts not retrieved in Block F2** if the report will cite them: Finance Act 2023 (levy on transfers removed), GN 496A and GN 642A of 2021 (`docs/mobile_money_levy.md`).
- [ ] **Decide whether to request the FinScope 2017 microdata** (variable Q27, code 13) for a 2017 TIN level as a third calibration target.
- [ ] **Decide the open wording items** listed in `docs/known_issues.md` (items 17 and 18).
