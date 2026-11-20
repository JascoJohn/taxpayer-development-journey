# The Taxpayer Development Journey — Interactive Dashboard

A Streamlit app: one page per lifecycle stage (six) plus a Scenario Lab, matching the figures and
mechanisms in the report. Most pages now read **real, live data**
from this project's own pipeline (`../outputs/stats/` and `../data/processed/`) rather than hardcoded
numbers — every page still captions clearly which figures are real and which
remain illustrative, and why.

## Project layout

```
<project root>/
├── config.yaml                ← every file location, seeds and simulation sizes
├── run_all.py                 ← regenerates every file the dashboard reads
├── src/                       ← pipeline code by stage (03_features, 04_models) and paths.py
├── data/ , outputs/           ← raw/interim/processed data, model outputs
└── dashboard/                 ← this Streamlit app
    ├── Home.py
    ├── common.py              ← thin re-export shim, kept for backward compatibility
    ├── tdj_lib/               ← the actual reusable code
    │   ├── styling.py         ← palette, theme-aware CSS tokens (light-dark), evidence-label tags: COMPUTED, MODELLED, CITED, ILLUSTRATIVE (no data dependency)
    │   ├── charts.py          ← one look for every Plotly chart (transparent background, neutral grid)
    │   ├── layout.py          ← stage header with persona thumbnail and the collapsed "About this stage" section
    │   ├── scenario_lab.py    ← pure-NumPy copy of the Table 5.1 Monte Carlo; reads only outputs/stats/scenario_lab_inputs.json
    │   ├── fig51.py           ← interactive Figure 5.1 (the tax morale model's combination rule); reads outputs/stats/figure_5_1_inputs.json
    │   ├── turnover_check.py  ← Mzani wa Kodi turnover check (pure functions; nothing is stored)
    │   ├── stages.py          ← 6-stage registry + cross-page nav (no data dependency)
    │   └── pipeline_data.py   ← reads the pipeline's JSON output (via config.yaml), never guesses
    ├── pages/
    │   ├── 0_Scenario_Lab.py  (MODELLED: change reach, uptake, persistence, horizon, discount rate, income basis)
    │   ├── 1_Seed.py       (illustrative — see "Current status" below)
    │   ├── 2_Entry.py      (live)
    │   ├── 3_Active.py     (live)
    │   ├── 4_Enterprise.py (live)
    │   ├── 5_Asset.py      (illustrative)
    │   └── 6_Legacy.py     (partially live)
    └── requirements.txt
```

## Theme

`.streamlit/config.toml` (repository root, where Community Cloud reads it for the entry point `dashboard/Home.py`) defines a light and a dark theme, so the app menu offers System, Light and Dark. A single `[theme]` section would lock the app to one mode. All custom CSS uses `light-dark()` colour tokens (`tdj_lib/styling.py`) and every chart goes through `tdj_lib/charts.py`, so both themes are readable. Run the app from the repository root: `streamlit run dashboard/Home.py`.

## Run locally

```bash
pip install -r requirements.txt
streamlit run Home.py
```

That's it for the dashboard itself — `pipeline_data.py` reads the already-generated
JSON files at startup (locations come from `config.yaml` through `src/paths.py`).
You don't need to run the pipeline to see live data; it ships with output already in place.

## Regenerating the underlying data

Everything the dashboard reads is computed by the project's own pipeline, fully
standalone — no dependency on any other project. To regenerate all of it from
the raw FinScope microdata, from the project root:

```bash
pip install -r environment/requirements.txt
python run_all.py            # add --clean to start from empty outputs
```

This runs, in order: FinScope summary statistics → the 15-component economic
model → a standalone tier-migration simulation (Enterprise's tier chart) →
the intervention register (parses the 8 LLM-generated interventions in
`outputs/frozen/report_sections.json` plus the 6 Python-modelled ones) → the FinScope
region×activity prevalence table (Active's page) → the active-stage benchmark → the
Entry targeting population. See `run_all.py` for the exact order and why it matters, and
the docstring at the top of each script for what it computes and from what real source.
`python run_all.py --from-processed` skips the FinScope ingestion steps and reads `data/interim/`
and `data/processed/` instead.

Note: the intervention register is rebuilt on every run and intervention IDs are
deterministic (`INT-` plus six hex characters of a SHA-1 over stage and title), so
re-running does not accumulate entries or change IDs. Timestamps are kept in
`outputs/stats/run_meta.json`, not in the data files.

## Current status per page

- **Seed** (`1_Seed.py`): fully illustrative by design — no real model exists
  for this mechanism (labelled ILLUSTRATIVE here and MODELLED in the report; revenue is deliberately not scored for this stage).
- **Entry** (`2_Entry.py`): **live.** Cost/revenue/ROI read from
  `economic_model.json`. The scoring gauge uses the real trained logistic
  regression's coefficients (held-out weighted ROC-AUC 0.946, read live from `targeting_model.json`) — the *scaling* is
  illustrative (no trained intercept is stored in the JSON), captioned as
  such on the page.
- **Active** (`3_Active.py`): **live.** Cost/revenue/ROI read from
  `economic_model.json`. The region selector shows a real, weighted
  FinScope-derived business-activity prevalence table (31 regions × 4
  activity categories). This is a prevalence table, not a turnover-band
  calculator — FinScope 2023 has no turnover/income-amount variable at all
  (checked exhaustively against the codebook and raw columns), so a real
  turnover calculator isn't buildable from this dataset, not just "not yet
  wired in."
- **Enterprise** (`4_Enterprise.py`): **live cost**, from
  `intervention_register.json`. Revenue/ROI remain illustrative — seen
  below. The tier-migration chart is MODELLED: a standalone 500,000-agent
  simulation (`src/04_models/economic_model.py`'s `run_tier_migration_simulation`)
  using the exact tier thresholds shown on the page. The metrics and chart show the tier distribution among registered taxpayers, with the registration rate stated beside them.
- **Asset** (`5_Asset.py`): a reciprocity mechanism, MODELLED in the report as a
  break-even programme cost; the demo score inputs are ILLUSTRATIVE.
- **Legacy** (`6_Legacy.py`): **live cost**, from `intervention_register.json`.
  Revenue/ROI remain illustrative — see below. Component weights in the
  score-builder are corrected to sum to a true 100 (the report's
  own example sums to 100 but is labeled 92/100 — worth fixing there too).

**Known real gap, not a "todo":** Enterprise's and Legacy's revenue/ROI have
no live source. Computing those requires
`economic_model_per_intervention.py`, which is kept unchanged in `src/imported/`
but is deliberately *not* wired into the pipeline — it depends on a much broader evidence
base (a separate evidence database) that is not part of this project.
`pipeline_data.py` returns this as an honest, captioned gap rather than reusing a stale figure.

## Deploying to share.streamlit.io

1. Create a new **public** GitHub repo containing the `dashboard/` folder contents —
   `Home.py`, `common.py`, `tdj_lib/`, `pages/`, `assets/` and
   `requirements.txt` all need to be at the repo root.
2. Go to **share.streamlit.io**, sign in with GitHub, click **New app**.
3. Point it at your repo, branch `main`, main file path `Home.py`. Deploy.
4. You'll get one link, e.g. `https://tra-taxpayer-journey.streamlit.app` —
   every stage page is reachable under it (`/Seed`, `/Entry`, `/Active`,
   `/Enterprise`, `/Asset`, `/Legacy`).

**Important:** the raw FinScope data (40MB+) is deliberately
**not** part of the dashboard's own repo. On a deploy that does not include the
pipeline's JSON output files, every page automatically falls back to its illustrative values (the
same honest-gap behavior as running locally without the pipeline present) —
nothing breaks, it just reads as a fresh, un-migrated checkout. If you want
live data on the deployed version too, either include the project's small
JSON outputs (not the 40MB CSV) together with `config.yaml` and `src/paths.py`, or point
`TDJ_PIPELINE_DIR` at wherever you host them.

## Live Demo
https://taxpayer-development-journey.streamlit.app

## Licences

Code: MIT. Aggregate data the dashboard reads: CC BY 4.0. Report and figures: CC BY-NC-ND 4.0. (c) 2026 Jasco John; see the repository `LICENSE`.
