# Retired code

Code that is no longer part of the pipeline. Nothing here is imported by `run_all.py`, tested, or shown in the dashboard.

## `digital_twin_v0.py`: the system-dynamics digital twin (Figure 5.2 of the submitted report)

Retired in Pass 6B-1 on the owner's decision.

* **PASS6A D2**: the twin's year-10 incremental revenue was about TZS 6.15 trillion, about 22 times the whole FY2023/24 individuals' income tax collection, and its registration and tax-rate
  inputs were assumptions that no data fix.
* **PASS6C E1**: the arithmetic of that result, and the scale comparison with the TRA collections.
* **PASS6D F4 / F5**: the rescued twin (stage population x reach x uplift, persistence, TRA trend as its own component) and its scale checks against TRA collections.

Its replacement is `src/04_models/reach_scenarios.py`, which draws Figure 5.2 (incremental revenue and active payers owing tax at Table 5.1's reach and at 10, 25 and 50% reach, with 80% bands, and the TRA
registration trend as its own dashed line). The `twin.*` constants of `config.yaml` that only the twin read are listed under `retired_assumptions:`; the base parameters in
`data/processed/twin_inputs.json` (population, registered taxpayers, growth) are still used by the pipeline and keep their name.
