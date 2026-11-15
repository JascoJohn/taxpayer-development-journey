# Environment

* Python **3.14.1** (Windows, 64-bit) - the interpreter used to run and verify the project.
* `requirements.txt` - exact versions (pip freeze of the `.venv` that ran the pipeline and the dashboard).
  Versions of packages that are also in the MultiAgent environment are identical to it
  (numpy 2.5.0, pandas 3.0.3, scipy 1.18.0, scikit-learn 1.9.0, streamlit 1.58.0, plotly 6.8.0, reportlab 5.0.0, PyYAML 6.0.3).
* `dashboard\requirements.txt` is the loose list used for deployment (streamlit, plotly, reportlab).

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r environment\requirements.txt
```

The scripts under `src\imported\` need extra packages that are **not** installed here (for example `pyreadstat`
for `ilfs_loader.py`); they are kept unchanged and are not part of the pipeline.
