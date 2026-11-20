"""Bridge into this project's own data pipeline (economic_model.json,
intervention_register.json, finscope_region_activity.json) -- fully
migrated into this project (src/, outputs/), no cross-project dependency.

Originally this read across to a separate sibling project. It is now fully
migrated: the computation scripts (economic_model.py, finscope_analysis.py,
intervention_registrar.py, shared_context.py, assumption_ledger.py and the
FinScope loaders) live under src/, their raw source data (FinScope.csv, the
codebook) under data/raw/, and run_all.py at the project root regenerates
everything from scratch, standalone.

Every accessor here still returns a Figure with .available=False (never
a guess, never an exception) when a file or field can't be found -- kept
even after the migration because the dashboard is also meant to run
standalone on share.streamlit.io, where the project's large data files
(FinScope.csv is 40MB) may not be deployed alongside it.

Known gap: Enterprise's and Legacy's *revenue* figures have no live
source -- economic_model_per_intervention.py (which computes real
per-intervention revenue) was never migrated, since it isn't part of
this dashboard's own pipeline and depends on a separate,
broader evidence base. revenue_estimate_tzs is None on both current
register entries; intervention_figures() returns available=True (cost
is real) with revenue/roi as None and a note explaining the gap.
"""

import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Optional

# Project root = two levels above this file (dashboard/tdj_lib/pipeline_data.py).
_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

# TDJ_PIPELINE_DIR (optional) points at ONE flat folder holding the JSON files. When it is not set,
# each file is located through config.yaml via src/paths.py (outputs/stats, data/processed).
DEFAULT_PIPELINE_DIR = os.environ.get("TDJ_PIPELINE_DIR")


def _configured_location(filename: str) -> Optional[str]:
    """Where config.yaml says `filename` lives; None if src/paths.py or its dependencies are not available."""
    try:
        src_dir = os.path.join(_PROJECT_ROOT, "src")
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)
        import paths
        return paths.PIPELINE_FILES.get(filename)
    except Exception:
        return None


@dataclass
class Figure:
    """Every pipeline_data accessor returns one of these. Check
    .available before trusting .value; .note explains why when it's
    False. Never raises for a missing file or field."""
    value: Optional[Any]
    available: bool
    note: str = ""


def _load_json(pipeline_dir: Optional[str], filename: str) -> Optional[dict]:
    path = os.path.join(pipeline_dir, filename) if pipeline_dir else _configured_location(filename)
    if not path or not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class PipelineData:
    """One instance per pipeline directory. Construct once per page
    load: PipelineData() picks up TDJ_PIPELINE_DIR / the locations in
    config.yaml; pass pipeline_dir explicitly to point at a different checkout
    or an uploaded copy of the two JSON files."""

    def __init__(self, pipeline_dir: Optional[str] = DEFAULT_PIPELINE_DIR):
        self.pipeline_dir = pipeline_dir or "the locations set in config.yaml"
        self._econ = _load_json(pipeline_dir, "economic_model.json")
        self._register = _load_json(pipeline_dir, "intervention_register.json")
        self._region_activity = _load_json(pipeline_dir, "finscope_region_activity.json")
        self._active_benchmark = _load_json(pipeline_dir, "finscope_active_benchmark.json")
        self._mzani = _load_json(pipeline_dir, "mzani_turnover.json")
        self._targeting_bootstrap = _load_json(pipeline_dir, "targeting_bootstrap.json")
        self._targeting_model = _load_json(pipeline_dir, "targeting_model.json")
        self._afrobarometer = _load_json(pipeline_dir, "afrobarometer_morale.json")
        self._stage_economics = _load_json(pipeline_dir, "stage_economics.json")
        self._tin_mobile_money = _load_json(pipeline_dir, "tin_mobile_money.json")

    @property
    def connected(self) -> bool:
        """True if at least one real pipeline file was found. Pages can
        use this to show/hide a 'live data connected' indicator."""
        return self._econ is not None or self._register is not None

    def tin_mobile_money(self) -> Figure:
        """Observational association between mobile money and TIN holding on the real FinScope respondents (Block D2,
        src/04_models/tin_mobile_money.py): descriptives with the disclosure rule applied and a survey-weighted Firth logit with its
        average marginal effect. Observational, cross-sectional; COMPUTED; not a causal estimate."""
        if not self._tin_mobile_money:
            return Figure(value=None, available=False, note="tin_mobile_money.json not found in pipeline directory")
        return Figure(value=self._tin_mobile_money, available=True)

    def targeting_model(self) -> Figure:
        """The real-data targeting model (Block D3, src/04_models/targeting_model.py) behind Entry's targeting: held-out metrics, the small scoring card (coefficients + intercept) and the Entry segment's propensity deciles
        (aggregates only, disclosure rule applied), from targeting_model.json."""
        if not self._targeting_model:
            return Figure(
                value=None, available=False,
                note="targeting_model.json not found in pipeline directory",
            )
        return Figure(value=self._targeting_model, available=True)

    def tier_migration(self) -> Figure:
        """Real yearly Ngazi tier distribution (Entry/Bronze/Silver/Gold/
        Platinum, plus not-registered) from economic_model.json's
        tier_migration_simulation key -- a standalone 500k-agent
        simulation built specifically to back Enterprise's tier chart,
        using the exact tier thresholds already shown on that page."""
        if not self._econ or not self._econ.get("tier_migration_simulation"):
            return Figure(
                value=None, available=False,
                note="economic_model.json missing or has no tier_migration_simulation key",
            )
        return Figure(value=self._econ["tier_migration_simulation"], available=True)

    def available_regions(self) -> Figure:
        """Sorted list of regions with real business-activity prevalence
        data (from finscope_region_activity.json), for populating a
        region selector without the caller reaching into private state."""
        if not self._region_activity:
            return Figure(
                value=None, available=False,
                note="finscope_region_activity.json not found in pipeline directory",
            )
        regions = sorted({r["region"] for r in self._region_activity["rows"]})
        return Figure(value=regions, available=True)

    def region_activity_prevalence(self, region: str) -> Figure:
        """Real, weighted FinScope 2023 business-activity prevalence for
        one region -- e.g. {"Traders - non-agricultural": 50.6, ...} as
        percentages of that region's business-activity population.

        This is NOT a turnover/income-amount distribution: FinScope 2023
        has no such variable (checked exhaustively -- see
        finscope_region_activity_loader.py's docstring in the pipeline
        repo). It answers "what share of this region's business owners
        are in this activity" -- a targeting/prevalence question, not
        "what should this business's presumptive tax band be." Callers
        must not relabel this as a turnover estimate."""
        if not self._region_activity:
            return Figure(
                value=None, available=False,
                note="finscope_region_activity.json not found in pipeline directory",
            )
        rows = [r for r in self._region_activity["rows"] if r["region"] == region]
        if not rows:
            return Figure(
                value=None, available=False,
                note=f"region '{region}' not present in finscope_region_activity.json",
            )
        return Figure(
            value={
                r["activity"]: {
                    "pct": r["pct_of_region_business_activity"],
                    "respondent_count": r["respondent_count"],
                    "suppressed": bool(r.get("suppressed")),
                }
                for r in rows
            },
            available=True,
        )

    def active_benchmark_regions(self) -> Figure:
        """Sorted list of regions present in finscope_active_benchmark.json,
        for populating Active's region input without the caller reaching
        into private state."""
        if not self._active_benchmark:
            return Figure(
                value=None, available=False,
                note="finscope_active_benchmark.json not found in pipeline directory",
            )
        regions = sorted({r["region"] for r in self._active_benchmark["rows"]})
        return Figure(value=regions, available=True)

    def active_benchmark_activities(self) -> Figure:
        """The fixed list of business-activity categories the benchmark
        cells are built on (finscope_active_benchmark.json's own
        strand_categories/rows -- same four IncomeMain categories as
        finscope_region_activity.json)."""
        if not self._active_benchmark:
            return Figure(
                value=None, available=False,
                note="finscope_active_benchmark.json not found in pipeline directory",
            )
        activities = sorted({r["activity"] for r in self._active_benchmark["rows"]})
        return Figure(value=activities, available=True)

    def active_benchmark_cell(self, region: str, activity: str) -> Figure:
        """Raw region x activity benchmark cell (respondent_count,
        weighted_population, strand_distribution_pct, registered_pct) from
        finscope_active_benchmark.json -- see
        src/03_features/finscope_active_benchmark_loader.py for exactly how these
        are computed. This is the only accessor
        tdj_lib/benchmark_adapters.py's finscope_adapter() reads; every
        FinScope-specific field name (fasx, D6_4a, IncomeMain, reg_name)
        lives in the loader script that produced this JSON, not here and
        not in the adapter."""
        if not self._active_benchmark:
            return Figure(
                value=None, available=False,
                note="finscope_active_benchmark.json not found in pipeline directory",
            )
        for r in self._active_benchmark["rows"]:
            if r["region"] == region and r["activity"] == activity:
                return Figure(value=r, available=True)
        return Figure(
            value=None, available=False,
            note=f"no benchmark cell for {activity!r} in {region!r}",
        )

    def tax_morale_model(self) -> Figure:
        """The recalibrated tax-morale model (Block E2.3) from economic_model.json: baseline (the observed adult TIN rate), solo effects, combined effect, status."""
        if not self._econ or "tax_morale_model" not in self._econ:
            return Figure(value=None, available=False, note="economic_model.json has no tax_morale_model")
        return Figure(value=self._econ["tax_morale_model"], available=True)

    def stage_economics(self, stage: str) -> Figure:
        """Table 5.1 row of one stage (cost, discounted revenue, NPV, ROI: median and 80% interval of the Monte Carlo) from stage_economics.json (Block E2.5)."""
        if not self._stage_economics:
            return Figure(value=None, available=False, note="stage_economics.json not found in pipeline directory")
        s = self._stage_economics["stages"].get(stage)
        if not s:
            return Figure(value=None, available=False, note=f"stage '{stage}' not in stage_economics.json")
        return Figure(value=s, available=True)

    def stage_economics_portfolio(self) -> Figure:
        """The portfolio row of Table 5.1 (Seed as cost, Entry, Active, Enterprise, Legacy; Asset excluded) from stage_economics.json: Monte Carlo summaries, central case, P(ROI >= 1) of the central income basis."""
        if not self._stage_economics or "portfolio" not in self._stage_economics:
            return Figure(value=None, available=False, note="stage_economics.json has no portfolio")
        p = dict(self._stage_economics["portfolio"])
        p["p_roi_ge_1"] = self._stage_economics.get("income_bases", {}).get("central", {}).get("portfolio_excluding_asset", {}).get("p_roi_ge_1")
        return Figure(value=p, available=True)

    def stage_economics_bases(self, stage: str) -> Figure:
        """Table 5.1 bracket of one stage: {"central": ..., "high": ..., "low": ...}, each with the income basis, revenue per registrant, share owing tax, ROI (median, 80% interval) and P(ROI >= 1), from
        stage_economics.json (income_bases). Only Active and Enterprise differ between bases."""
        if not self._stage_economics or "income_bases" not in self._stage_economics:
            return Figure(value=None, available=False, note="stage_economics.json has no income_bases")
        out = {k: v["stages"].get(stage) for k, v in self._stage_economics["income_bases"].items()}
        if not all(out.values()):
            return Figure(value=None, available=False, note=f"stage '{stage}' not in the income bases")
        return Figure(value={k: dict(v, label=self._stage_economics["income_bases"][k]["label"]) for k, v in out.items()}, available=True)

    def tax_morale_components(self) -> Figure:
        """Tax-morale COMPONENTS from Afrobarometer Round 8 Tanzania (weighted percentages with 95% CIs, aggregates only; no composite):
        {indicator id: {"pct", "ci95_low_pct", "ci95_high_pct", "variable", "n_unweighted_base"}} for all adults 18+, plus the source citation."""
        if not self._afrobarometer:
            return Figure(value=None, available=False, note="afrobarometer_morale.json not found in pipeline directory")
        est = {e["indicator"]: e for e in self._afrobarometer["estimates"] if e["level"] == "All adults 18+" and not e.get("suppressed")}
        return Figure(value={"indicators": est, "citation": self._afrobarometer["source"]["citation"], "fieldwork": self._afrobarometer["source"]["fieldwork"]}, available=True)

    def targeting_bootstrap(self) -> Figure:
        """Cached respondent bootstrap of the Entry top-decile multiplier (register-only and survey model, 95% intervals), the leakage-adjusted AUC and the leave-one-zone-out AUC
        (outputs/cache/targeting_bootstrap.json, src/04_models/targeting_bootstrap.py). Aggregates only; the observed ratio is published only with its interval."""
        if not self._targeting_bootstrap:
            return Figure(value=None, available=False, note="targeting_bootstrap.json not found (run `python run_all.py --full-bootstrap`)")
        return Figure(value=self._targeting_bootstrap, available=True)

    def mzani_meta(self) -> Figure:
        """Label, coverage statements and cell minimum of the Mzani wa Kodi turnover bands (outputs/stats/mzani_turnover.json, written by src/03_features/hbs_turnover.py)."""
        if not self._mzani:
            return Figure(value=None, available=False, note="mzani_turnover.json not found in pipeline directory")
        return Figure(value=self._mzani, available=True)

    def mzani_activities(self) -> Figure:
        """The three activity groups of the HBS turnover bands."""
        if not self._mzani:
            return Figure(value=None, available=False, note="mzani_turnover.json not found in pipeline directory")
        return Figure(value=sorted({r["activity"] for r in self._mzani["national_activity"]}), available=True)

    def mzani_cell(self, level: str, key: Optional[str], activity: str) -> Figure:
        """One turnover-band cell: level 'region' (key = region), 'zone' (key = zone) or 'national' (key None) x activity group. A suppressed cell has suppressed=True and no numbers."""
        if not self._mzani:
            return Figure(value=None, available=False, note="mzani_turnover.json not found in pipeline directory")
        rows, field = {"region": (self._mzani["region_activity"], "region"), "zone": (self._mzani["zone_activity"], "zone"), "national": (self._mzani["national_activity"], None)}[level]
        for r in rows:
            if r["activity"] == activity and (field is None or r[field] == key):
                return Figure(value=r, available=True)
        return Figure(value=None, available=False, note=f"no {level} turnover cell for {activity!r} in {key!r}")

    def active_benchmark_zone_cell(self, zone: str, activity: str) -> Figure:
        """Zone x activity benchmark cell (same fields as the region cell; the disclosure rule is applied at this level too), used by the
        Mzani wa Kodi fallback when the region cell is suppressed (src/03_features/finscope_active_benchmark_loader.py, zone_rows)."""
        if not self._active_benchmark:
            return Figure(value=None, available=False, note="finscope_active_benchmark.json not found in pipeline directory")
        for r in self._active_benchmark.get("zone_rows", []):
            if r["zone"] == zone and r["activity"] == activity:
                return Figure(value=r, available=True)
        return Figure(value=None, available=False, note=f"no zone benchmark cell for {activity!r} in {zone!r}")

    def active_benchmark_national_cell(self, activity: str) -> Figure:
        """National x activity benchmark cell: the last fallback when the region and zone cells are both suppressed."""
        if not self._active_benchmark:
            return Figure(value=None, available=False, note="finscope_active_benchmark.json not found in pipeline directory")
        for r in self._active_benchmark.get("national_rows", []):
            if r["activity"] == activity:
                return Figure(value=r, available=True)
        return Figure(value=None, available=False, note=f"no national benchmark cell for {activity!r}")

    def targeting_deciles(self) -> Figure:
        """The Entry segment's propensity deciles (decile 1 = highest predicted propensity): weighted population, mean
        predicted propensity, observed TIN rate and mix (urban / business owner / mobile money), with the disclosure rule
        applied (suppressed deciles carry null estimates; low-precision ones are flagged). Aggregates only: no respondent-level
        rows exist in the pipeline output."""
        if not self._targeting_model:
            return Figure(
                value=None, available=False,
                note="targeting_model.json not found in pipeline directory",
            )
        seg = self._targeting_model.get("entry_segment")
        if not seg or not seg.get("deciles"):
            return Figure(value=None, available=False, note="targeting_model.json has no entry_segment deciles")
        return Figure(value=seg, available=True)
