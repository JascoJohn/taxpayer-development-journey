"""Data-source adapters for Mzani wa Kodi (Active stage) benchmarking.

Every adapter implements the same contract -- region + activity in, a BenchmarkResult out -- so the page never touches a raw data source directly.
Since Pass 6B-1 the adapter is `mzani_adapter`: turnover bands IN SHILLINGS from the Household Budget Survey 2017/18 (CPI-uprated to 2024, last-month receipts annualised by months
operated, owners with receipts), by zone x activity (three activity groups); a region cell is shown only with at least 30 businesses with receipts, else the zone cell, else the national
cell, always labelled. The presumptive tax is the schedule in force applied to the P25, median and P75 turnover of the cell. FinScope's registration rate by region is kept as CONTEXT
only. The FinScope access-strand bridge (a score mapped onto the presumptive bands) is retired. Farmers and fishers and Zanzibar are not covered by this source.
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


@dataclass
class BenchmarkResult:
    """What every adapter returns. Nothing in here is specific to any one data source -- the page renders this shape, never a source's raw fields directly."""

    available: bool
    region: str
    sector: str
    level: str = "region"                              # which geography the estimate is for: region, zone or national
    geography: str = ""                                # name of that geography (the region, "<zone> zone", or "Tanzania")
    level_label: str = ""                              # shown when the region cell was not usable and a wider cell is used
    sample_size: int = 0                               # businesses with receipts in the cell (HBS 2017/18, unweighted)
    low_precision: bool = False
    low_precision_note: str = ""

    # The turnover band (TZS a year, 2024 prices) and the presumptive tax it implies.
    p25_tzs: Optional[float] = None
    median_tzs: Optional[float] = None
    p75_tzs: Optional[float] = None
    tax_p25_tzs: Optional[float] = None                # None above the presumptive ceiling (the ordinary schedule applies)
    tax_median_tzs: Optional[float] = None
    tax_p75_tzs: Optional[float] = None
    share_below_4m_pct: Optional[float] = None
    share_4m_to_11m_pct: Optional[float] = None
    share_above_11m_pct: Optional[float] = None
    evidence_tier: str = "computed"
    source_label: str = ""
    coverage: Optional[list] = None                    # what this source does NOT cover

    # CONTEXT only (not used in the bands): FinScope 2023 registration rate of business owners in the region.
    formality_rate_pct: Optional[float] = None
    formality_label: str = ""

    taxpayer_note: str = ""
    officer_note: str = ""
    note: str = ""                                     # explains gaps / fallbacks


def _finscope_registration_context(pipeline, region):
    """FinScope 2023: weighted share of the region's business owners whose business is registered (cells with a suppressed rate are left out). Context only."""
    fig = pipeline.active_benchmark_regions()
    num = den = 0.0
    for act in (pipeline.active_benchmark_activities().value or []):
        c = pipeline.active_benchmark_cell(region, act)
        if c.available and not c.value.get("suppressed") and c.value.get("registered_pct") is not None and c.value.get("weighted_population"):
            num += c.value["registered_pct"] * c.value["weighted_population"]
            den += c.value["weighted_population"]
    return (num / den) if den else None


def mzani_adapter(region: str, sector: str, pipeline: Optional[PipelineData] = None) -> BenchmarkResult:
    """Turnover band of businesses like these (HBS 2017/18) with the fallback region -> zone -> national, each cell under the disclosure and minimum-size rules."""
    pipeline = pipeline or PipelineData()
    meta = pipeline.mzani_meta()
    if not meta.available:
        return BenchmarkResult(available=False, region=region, sector=sector, note=meta.note)
    m = meta.value
    min_region = int(m["min_businesses_with_receipts_region_cell"])
    cell = pipeline.mzani_cell("region", region, sector)
    level, geography, level_label = "region", region, ""

    def _usable(c):
        return c.available and not c.value.get("suppressed")

    if not _usable(cell):
        zone = _zone_of(region)
        zcell = pipeline.mzani_cell("zone", zone, sector) if zone else Figure(value=None, available=False)
        why = (f"{region} has fewer than {min_region} businesses with receipts of this kind in the HBS 2017/18" if cell.available
               else f"{region} is not covered by the HBS 2017/18 (a Mainland survey)")
        if _usable(zcell):
            cell, level, geography = zcell, "zone", f"{zone} zone"
            level_label = f"Zone estimate: {why} ({region} is in the {zone} zone)."
        else:
            ncell = pipeline.mzani_cell("national", None, sector)
            if _usable(ncell):
                cell, level, geography = ncell, "national", "Mainland Tanzania"
                level_label = f"National (Mainland) estimate: {why}, and the zone cell ({zone or 'zone not listed'}) is too thin to publish."
            else:
                return BenchmarkResult(available=False, region=region, sector=sector, note=f"Insufficient data: too few businesses with receipts in the HBS 2017/18 for {sector.lower()} to publish a band; none is guessed.")
    v = cell.value
    n = int(v["n_with_receipts"])
    ctx = _finscope_registration_context(pipeline, region)
    return BenchmarkResult(
        available=True, region=region, sector=sector, level=level, geography=geography, level_label=level_label, sample_size=n,
        low_precision=bool(v.get("low_precision")),
        low_precision_note=(f"Low precision: the band rests on {n} businesses with receipts (fewer than {min_region})." if v.get("low_precision") else ""),
        p25_tzs=v["p25_tzs"], median_tzs=v["median_tzs"], p75_tzs=v["p75_tzs"], tax_p25_tzs=v["tax_at_p25_tzs"], tax_median_tzs=v["tax_at_median_tzs"], tax_p75_tzs=v["tax_at_p75_tzs"],
        share_below_4m_pct=v["share_below_4m_pct"], share_4m_to_11m_pct=v["share_4m_to_11m_pct"], share_above_11m_pct=v["share_above_11m_pct"],
        evidence_tier="computed", source_label=m["label"], coverage=m["coverage"],
        formality_rate_pct=ctx, formality_label=(f"FinScope Tanzania 2023: {ctx:.1f}% of business owners in {region} have a registered business (context only; not used in the band)" if ctx is not None else ""),
        taxpayer_note="This shows where businesses like yours sit in a national survey of household businesses; it is not a calculation of your turnover and is not your tax bill.",
        officer_note="This is a survey-based reference band for discussion with the taxpayer, not an assessment. Use it alongside your own judgement and any records the taxpayer can provide.",
        note=f"Based on {n} businesses with receipts in the reference month in this {level}/activity cell ({geography}), weighted to the HBS 2017/18 population of such businesses.",
    )
