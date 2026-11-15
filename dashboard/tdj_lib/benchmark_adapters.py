"""Data-source adapters for Mzani wa Kodi (Active stage) benchmarking.

Every adapter implements the same contract -- region + sector in,
a BenchmarkResult out -- so the page never touches a raw data source
directly and never hardcodes which source it's looking at. FinScope is
the only data source available today (finscope_adapter, below); TRA's
own tax-collection records and BRELA business-registration data are
realistic future additions, and each would be a *stronger* evidence
tier than a survey proxy (an actual observed assessment for a
comparable business, vs. a survey-implied one). Adding a second
adapter later means writing one more function with this same
signature and letting the page's evidence-tier-driven copy pick up the
new source_label/evidence_tier automatically -- not touching
pages/3_Active.py's rendering logic at all.

No UI for choosing between sources exists yet, on purpose -- there's
only one. This module is the seam, not a plugin system.
"""

import os
from dataclasses import dataclass
from typing import Optional

from .pipeline_data import Figure, PipelineData

def _disclosure_min_base() -> int:
    """The disclosure threshold lives in config.yaml (disclosure.min_base); the dashboard never hard-codes it."""
    import yaml
    root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    with open(os.path.join(root, "config.yaml"), "r", encoding="utf-8") as f:
        return int(yaml.safe_load(f)["disclosure"]["min_base"])


def _zone_of(region: str) -> Optional[str]:
    """Statistical zone of a region (config.yaml zones.regions: the nine NBS TDHS-MIS 2022 zones); None when the region is not listed."""
    import yaml
    root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    with open(os.path.join(root, "config.yaml"), "r", encoding="utf-8") as f:
        zones = yaml.safe_load(f)["zones"]["regions"]
    for zone, regions in zones.items():
        if region in regions:
            return zone
    return None


# Below this many respondents in a cell, no estimate is shown at all --
# a visible "insufficient data" result, not a number built on too few
# people to mean anything. Read from config.yaml (disclosure.min_base = 10).
MIN_N_FOR_ANY_ESTIMATE = _disclosure_min_base()
# Below this, an estimate is shown but flagged small-sample.
MIN_N_FOR_CONFIDENT_ESTIMATE = 20

def presumptive_schedule() -> dict:
    """The presumptive schedule in force (Finance Act 2026), read from config.yaml assumptions['tax.presumptive_schedule']; the dashboard never types its own copy."""
    import yaml
    root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    with open(os.path.join(root, "config.yaml"), "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["assumptions"]["tax.presumptive_schedule"]["value"]


def _tzs(v) -> str:
    return "{:,}".format(int(v))


def presumptive_caption() -> str:
    """One-line statement of the schedule for the Active page (all figures from the configured schedule)."""
    s = presumptive_schedule()
    lo, mid, top = s["bands"][0][0], s["bands"][-1][1], s["threshold_turnover"]
    return (f"0% (nil) up to TZS {_tzs(lo)} · graduated amounts TZS {_tzs(lo)}–{_tzs(mid)} · "
            f"{s['above_11m_rate'] * 100:.1f}% for TZS {_tzs(mid)}–{_tzs(top)} (Finance Act 2026). "
            "A new TIN holder starting a business pays no presumptive tax for the first twelve months.")


def _presumptive_bands():
    s = presumptive_schedule()
    lo, mid, top = s["bands"][0][0], s["bands"][-1][1], s["threshold_turnover"]
    return [("Likely below TZS %s (no presumptive tax due)" % _tzs(lo), 0.0, 0.34),
            ("Likely TZS %s – %s (graduated presumptive rates apply)" % (_tzs(lo), _tzs(mid)), 0.34, 0.67),
            ("Likely TZS %s – %s (%.1f%% presumptive rate applies)" % (_tzs(mid), _tzs(top), s["above_11m_rate"] * 100), 0.67, 1.01)]


# The illustrative bridge from a real strand/registration profile to a
# presumptive-tax category. This is NOT a turnover estimate -- see
# BenchmarkResult.presumptive_evidence_tier, always "illustrative" here.
PRESUMPTIVE_BANDS = _presumptive_bands()


@dataclass
class BenchmarkResult:
    """What every adapter returns. Nothing in here is specific to any
    one data source -- the page renders this shape, never a source's
    raw fields directly."""

    available: bool
    region: str
    sector: str
    level: str = "region"                              # which geography the estimate is for: region, zone or national
    geography: str = ""                                # name of that geography (the region, "<zone> zone", or "Tanzania")
    level_label: str = ""                              # shown when the region cell was suppressed and a wider cell is used
    sample_size: int = 0
    weighted_population: Optional[float] = None
    low_precision: bool = False                       # an estimate of this cell rests on fewer than 10 cases
    low_precision_note: str = ""

    # The real, source-derived comparison.
    strand_distribution: Optional[dict] = None      # e.g. {"Banked": 12.4, ...}
    formality_rate_pct: Optional[float] = None       # % registered/formal in this cell
    evidence_tier: str = "computed"                  # label for the fields above
    source_label: str = ""                            # e.g. "FinScope Tanzania 2023 ..."

    # The illustrative bridge to a presumptive-tax category.
    composite_score: Optional[float] = None            # 0..1
    presumptive_category: Optional[str] = None
    presumptive_evidence_tier: str = "illustrative"  # always a bridge, never an evidence type

    # Framing copy -- source-aware, so the page never writes its own
    # claim about what kind of evidence this is.
    taxpayer_note: str = ""
    officer_note: str = ""
    note: str = ""                                     # explains gaps / insufficient data


def _presumptive_category(score: float) -> str:
    for label, lo, hi in PRESUMPTIVE_BANDS:
        if lo <= score < hi:
            return label
    return PRESUMPTIVE_BANDS[-1][0]


def finscope_adapter(
    region: str, sector: str, pipeline: Optional[PipelineData] = None,
) -> BenchmarkResult:
    """The only adapter that exists today. Reads
    finscope_active_benchmark.json through PipelineData.active_benchmark_cell()
    -- see src/03_features/finscope_active_benchmark_loader.py for exactly how
    that file's strand_distribution_pct and registered_pct are computed
    from raw FinScope microdata. Every FinScope-specific column name
    (fasx, D6_4a, IncomeMain, reg_name) lives in that loader script;
    this function only ever touches the already-neutral JSON shape it
    produced, and returns the source-agnostic BenchmarkResult above."""
    pipeline = pipeline or PipelineData()
    cell: Figure = pipeline.active_benchmark_cell(region, sector)
    level, geography, level_label = "region", region, ""

    def _usable(c):
        return c.available and not c.value.get("suppressed") and c.value.get("respondent_count") is not None and c.value["respondent_count"] >= MIN_N_FOR_ANY_ESTIMATE

    # E6 fallback: region cell suppressed -> zone estimate -> national estimate, each under the same disclosure rule, always labelled
    if cell.available and not _usable(cell):
        zone = _zone_of(region)
        zcell = pipeline.active_benchmark_zone_cell(zone, sector) if zone else Figure(value=None, available=False)
        if _usable(zcell):
            cell, level, geography = zcell, "zone", f"{zone} zone"
            level_label = f"Zone estimate: region cell suppressed, fewer than {MIN_N_FOR_ANY_ESTIMATE} respondents ({region} is in the {zone} zone)."
        else:
            ncell = pipeline.active_benchmark_national_cell(sector)
            if _usable(ncell):
                cell, level, geography = ncell, "national", "Tanzania"
                level_label = (f"National estimate: region and zone cells suppressed, fewer than {MIN_N_FOR_ANY_ESTIMATE} respondents "
                               f"(region {region}, zone {zone or 'not listed'}).")

    if not cell.available:
        return BenchmarkResult(
            available=False, region=region, sector=sector,
            note=cell.note or "No data available for this combination.",
        )

    n = cell.value.get("respondent_count")
    if cell.value.get("suppressed") or n is None or n < MIN_N_FOR_ANY_ESTIMATE:
        return BenchmarkResult(
            available=False, region=region, sector=sector, sample_size=0,
            note=(
                f"Suppressed (fewer than {MIN_N_FOR_ANY_ESTIMATE} respondents): too few FinScope respondents matched "
                f"{sector.lower()} businesses in {region} to publish a comparison. "
                "Showing a number here would look precise without being reliable, "
                "so this combination is withheld instead of guessed."
            ),
        )

    strand = cell.value["strand_distribution_pct"]
    formality = cell.value.get("registered_pct")
    banked_like = strand.get("Banked", 0) + strand.get("Other formal non-bank", 0)
    formality_term = (formality / 100) if formality is not None else (banked_like / 100)
    score = round(0.6 * (banked_like / 100) + 0.4 * formality_term, 3)
    confident = n >= MIN_N_FOR_CONFIDENT_ESTIMATE

    return BenchmarkResult(
        available=True, region=region, sector=sector, sample_size=n,
        level=level, geography=geography, level_label=level_label,
        weighted_population=cell.value["weighted_population"],
        low_precision=bool(cell.value.get("low_precision")),
        low_precision_note=(
            "Low precision: " + ", ".join(f.replace("strand_distribution_pct:", "").replace("_pct", "") for f in cell.value.get("low_precision_fields", []))
            + " rest on fewer than 10 survey cases (95% intervals are in the published file)."
        ) if cell.value.get("low_precision") else "",
        strand_distribution=strand,
        formality_rate_pct=formality,
        evidence_tier="computed",
        source_label="FinScope Tanzania 2023 national survey sample",
        composite_score=score,
        presumptive_category=_presumptive_category(score),
        presumptive_evidence_tier="illustrative",
        taxpayer_note=(
            "This compares your business to others like it in a national survey — "
            "it is not a calculation of your income and is not your tax bill."
        ),
        officer_note=(
            "This is a survey-based reference point for discussion with the "
            "taxpayer, not a computed assessment. Use it alongside your own "
            "judgement and any records the taxpayer can provide."
        ),
        note=(
            f"Based on {n} FinScope respondents in this exact {'region' if level == 'region' else level}/sector "
            f"combination ({geography}) — {'a small sample, treat as indicative only' if not confident else 'a reasonable sample size for this survey'}."
        ),
    )
