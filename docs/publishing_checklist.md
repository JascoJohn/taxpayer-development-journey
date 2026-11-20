# Publishing checklist: a fresh GitHub repository, three Zenodo records

This is the plan for publishing the project: the code and the aggregate data first (release v0.9.0), then the report once the three DOIs exist (release v1.0.0). Publishing steps are actions of the maintainer; nothing in this repository pushes, publishes or uploads by itself.

Three Zenodo records are involved:

* **Code** (MIT): created automatically from each GitHub release; `.zenodo.json` holds its metadata.
* **Dataset** (CC BY 4.0): the aggregate data only (`data/processed/`, `data/interim/`, `outputs/stats/`, `outputs/tables/`, the World Bank snapshots, `data/raw/SOURCES.csv`, `docs/data_terms.md`, `docs/claims_map.csv`, `docs/assumptions_register.csv` and a `DATA_README.md`).
* **Report** (CC BY-NC-ND 4.0): the final PDF.

The DOIs appear in the README, `CITATION.cff` and the report as the placeholders `[Report DOI]`, `[Dataset DOI]` and `[Code DOI]` (and `[date-released]`) until step 7.

## What is checked before the first push

- [x] **Raw data are not tracked**: `.gitignore` excludes `data/raw/**` except `SOURCES.csv`, READMEs and the World Bank snapshots; provenance, hashes and citations of every raw file are in `data/raw/SOURCES.csv`; terms in `docs/data_terms.md`.
- [x] **No respondent-level data** anywhere in the tracked files; cells with fewer than 10 unweighted respondents carry no estimate (disclosure rule in `config.yaml`).
- [x] **No file over 10 MB; no keys, tokens or `.env` files** (`.env.example` holds no secrets).
- [x] **Nothing from the private working folders** (`_archive/`, `report/`) is tracked.
- [x] **Licences**: code MIT; report and figures CC BY-NC-ND 4.0; aggregate data CC BY 4.0 (`LICENSE`, README, `CITATION.cff`, `docs/data_terms.md` section 8).
- [x] **Claims and assumptions**: every number of the report is in `docs/claims_map.csv`; every assumption is in `docs/assumptions_register.csv`.
- [x] **Reproducibility**: the pipeline (`python run_all.py --from-raw`, or `--from-processed` without restricted data) and the test suite (`python -m pytest`) pass; figures and tables are byte-reproducible; no absolute paths in code, tests or configuration.

## Steps

### 1. Create the repository

GitHub > New repository: name `taxpayer-development-journey`, visibility **Private**. Do not add a README, licence or `.gitignore` (the project has them). Check: the new page shows "Quick setup" and no files.

### 2. Push `main` and the tag

```bash
cd <project folder>
git status --short
git remote add origin https://github.com/JascoJohn/taxpayer-development-journey.git
git push -u origin main
git push origin v0.9.0
```

`git status --short` should list only the untracked `report/` folder. Never run `git add .` or `git add report`. The repository is empty, so no force-push is needed. Check: GitHub shows the full history, the tag `v0.9.0`, and no `report/` or `_archive/` folder.

### 3. Make it public, link Zenodo, publish the release v0.9.0

1. Settings > General > Danger Zone > Change repository visibility > Make public.
2. https://zenodo.org/account/settings/github/ : find the repository (use "Sync now" if needed) and switch it **ON**.
3. GitHub > Releases > Draft a new release: tag `v0.9.0`, target `main`, title `v0.9.0: code and aggregate data`, notes: first public release (code, aggregate data, outputs, dashboard, documentation; the report follows in v1.0.0; code MIT, report and figures CC BY-NC-ND 4.0, aggregate data CC BY 4.0; no respondent-level data). Publish.

Check: Zenodo creates the code record within a minute or two; compare it with `.zenodo.json` (title "The Taxpayer Development Journey: Code", Software, MIT, creator, version 0.9.0). Copy the **code DOI**.

### 4. Dataset record (upload and reserve the DOI; do not publish yet)

Zenodo > New upload: the dataset zip `taxpayer-development-journey-aggregate-data-v1.0.0.zip` and `DATA_README.md`; fill the form from the dataset metadata; licence CC BY 4.0; version 1.0.0; add the code DOI under related works. Reserve the DOI and copy it. A published record cannot be deleted or have its files changed (only given a new version), so it is published in step 8, after the DOIs are in the files.

### 5. Report record (reserve the DOI; do not publish yet)

Zenodo > New upload: resource type Publication > Report; licence CC BY-NC-ND 4.0; version 1.0.0; no file yet. Reserve the DOI and copy it.

### 6. Dashboard on Streamlit Community Cloud

share.streamlit.io > Create app > deploy from GitHub: repository `JascoJohn/taxpayer-development-journey`, branch `main`, main file `dashboard/Home.py`, Python 3.14 (the pinned packages need 3.12 or newer), requirements from `dashboard/requirements.txt`, no secrets, custom subdomain `taxpayer-development-journey`. Open all seven pages (Home, Seed, Entry, Active, Enterprise, Asset, Legacy), check there are no error boxes and that they match the committed screenshots in `outputs/figures/dashboard_*.png`, then set the app to public.

### 7. Fill in the DOIs and prepare v1.0.0

Replace `[Report DOI]`, `[Dataset DOI]`, `[Code DOI]` and `[date-released]` in the report, `README.md`, `CITATION.cff` and `DATA_README.md`; set the version to 1.0.0; rebuild the dataset zip (its checksum changes); rebuild the final report PDF; run the tests; commit; tag `v1.0.0`.

### 8. Release v1.0.0 and publish the records

1. `git push origin main` and `git push origin v1.0.0`; publish the GitHub release `v1.0.0` (a new version of the code record, same concept DOI).
2. Dataset draft: replace the files with the rebuilt ones, check the SHA-256, publish.
3. Report draft: upload the final PDF, check the DOI printed in it matches the reserved one, publish.
4. Check that each record lists the other two DOIs under related works and that the dashboard still loads.

### 9. Send copies

Send the publication copy (the report PDF and the DOIs) to NBS, FSDT and the Ministry of Finance, as clause 6 of the data terms requires (contacts in `docs/data_terms.md`).
