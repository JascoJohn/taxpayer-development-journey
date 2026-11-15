"""W3 - macro inputs from the World Bank WDI snapshots (no network access: reads the files named in config.yaml).

Reads the snapshots under `worldbank.snapshots`:
  GC.TAX.TOTL.GD.ZS  tax revenue, % of GDP (Tanzania and the four peers GHA, KEN, RWA, UGA)
  NY.GDP.MKTP.CN     GDP, current LCU (TZS), Tanzania
  NY.GDP.MKTP.CD     GDP, current US$, Tanzania (reported only where a US$ figure is shown)
  PA.NUS.FCRF        official exchange rate, LCU per US$, period average (US$ equivalents only)

Computes (all COMPUTED, nothing typed):
  * Tanzania's latest tax-to-GDP ratio (latest year with a value);
  * the benchmark year: the latest year in which Tanzania AND all four peers report;
  * the peer-average benchmark: the simple mean of the four peers in that year;
  * the revenue gap in TZS = (benchmark - Tanzania in the SAME year) x GDP in TZS of that year (no exchange-rate step);
  * US$ equivalents, converting with PA.NUS.FCRF of the same year.

Benchmark policy (config.yaml macro.benchmark_source): `peer_average` (default) or `cited_target` (a published Tanzanian
target; none is adopted yet, so selecting it without `macro.cited_target_pct` and `macro.cited_target_source` stops the
run). With a cited target there is no common year: the gap uses the cited ratio and Tanzania's ratio in its latest year.

Output: outputs/stats/macro_inputs.json
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # src/
import paths

TAX = "GC.TAX.TOTL.GD.ZS"
GDP_LCU = "NY.GDP.MKTP.CN"
GDP_USD = "NY.GDP.MKTP.CD"
FX = "PA.NUS.FCRF"


def load_series(path):
    """{ISO3: {year: value}} from a raw WDI v2 response (null values skipped); also returns the file's lastupdated."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    meta, rows = data[0], data[1]
    out = {}
    for r in rows:
        if r.get("value") is None:
            continue
        out.setdefault(r["countryiso3code"], {})[int(r["date"])] = float(r["value"])
    return out, meta.get("lastupdated")


def load_snapshots(snapshots=None):
    snapshots = snapshots or paths.WB_SNAPSHOTS
    series, updated = {}, {}
    for ind in (TAX, GDP_LCU, GDP_USD, FX):
        if ind not in snapshots:
            raise KeyError("worldbank.snapshots in config.yaml has no entry for %s" % ind)
        if not os.path.exists(snapshots[ind]):
            raise FileNotFoundError("%s not found: run `python run_all.py --fetch` once, then name the snapshot in config.yaml" % snapshots[ind])
        series[ind], updated[ind] = load_series(snapshots[ind])
    return series, updated


def compute(series, country, peers, benchmark_source="peer_average", cited_target_pct=None, cited_target_source=None,
            context_target_pct=None, context_target_source=None):
    tax = series[TAX]
    tza = tax[country]
    latest_year = max(tza)
    common = [y for y in tza if all(y in tax.get(p, {}) for p in peers)]
    if not common:
        raise ValueError("no year in which %s and all peers report %s" % (country, TAX))
    bench_year = max(common)
    peer_vals = {p: tax[p][bench_year] for p in peers}
    peer_avg = sum(peer_vals.values()) / len(peer_vals)

    gdp_lcu, gdp_usd, fx = series[GDP_LCU][country], series[GDP_USD][country], series[FX][country]

    if benchmark_source == "peer_average":
        gap_year = bench_year
        benchmark_pct = peer_avg
        benchmark_note = "simple mean of %s in %d (latest year all five countries report)" % (", ".join(peers), bench_year)
    elif benchmark_source == "cited_target":
        if cited_target_pct is None or not cited_target_source:
            raise ValueError("macro.benchmark_source is cited_target but macro.cited_target_pct / cited_target_source are not set: "
                             "no citable Tanzanian target has been adopted (see _archive/process_records/BLOCK_C_REPORT.md)")
        gap_year = latest_year
        benchmark_pct = float(cited_target_pct)
        benchmark_note = "cited target: %s" % cited_target_source
    else:
        raise ValueError("macro.benchmark_source must be peer_average or cited_target, not %r" % benchmark_source)

    tza_gap_year = tza[gap_year]
    gap_pp = benchmark_pct - tza_gap_year
    gdp_gap_year = gdp_lcu[gap_year]
    gap_tzs = gap_pp / 100.0 * gdp_gap_year
    fx_gap_year = fx[gap_year]
    target_rev_tzs = benchmark_pct / 100.0 * gdp_gap_year
    current_rev_tzs = tza[latest_year] / 100.0 * gdp_lcu[latest_year]

    return {
        "source": "World Bank WDI snapshots named in config.yaml (CC BY 4.0)",
        "type": "COMPUTED",
        "tanzania": {
            "latest_year": latest_year,
            "tax_to_gdp_pct": tza[latest_year],
            "gdp_lcu_tzs": gdp_lcu[latest_year],
            "gdp_usd": gdp_usd[latest_year],
            "fx_tzs_per_usd": fx[latest_year],
            "tax_revenue_tzs": current_rev_tzs,
            "tax_revenue_usd": current_rev_tzs / fx[latest_year],
        },
        "benchmark": {
            "policy": benchmark_source,
            "year": gap_year,
            "benchmark_pct": benchmark_pct,
            "note": benchmark_note,
            "peers": {p: {"year": bench_year, "tax_to_gdp_pct": v} for p, v in peer_vals.items()},
            "peer_average_pct": peer_avg,
            "common_year_all_five": bench_year,
            "tanzania_same_year_pct": tza_gap_year,
            "gap_pp": gap_pp,
            "gdp_lcu_tzs_that_year": gdp_gap_year,
            "revenue_gap_tzs": gap_tzs,
            "target_tax_revenue_tzs": target_rev_tzs,
            "fx_tzs_per_usd_that_year": fx_gap_year,
            "revenue_gap_usd": gap_tzs / fx_gap_year,
            "target_tax_revenue_usd": target_rev_tzs / fx_gap_year,
            "formula": "(benchmark - Tanzania, same year) / 100 x GDP in TZS of that year; no exchange-rate step in the TZS gap",
        },
        # published MoF target, shown for context only; it is not used in the gap
        "context_target": {"tax_to_gdp_pct": context_target_pct, "source": context_target_source, "used_in_gap": False},
        "series_coverage": {c: {"first_year": min(v), "last_year": max(v), "n_years": len(v)} for c, v in tax.items()},
    }


def run_macro_inputs(out_path=None, snapshots=None, cfg=None):
    cfg = cfg or paths.MACRO_CFG
    series, updated = load_snapshots(snapshots)
    result = compute(series, cfg["country"], cfg["peers"], cfg.get("benchmark_source", "peer_average"),
                     cfg.get("cited_target_pct"), cfg.get("cited_target_source"),
                     cfg.get("context_target_pct"), cfg.get("context_target_source"))
    result["snapshots"] = {k: os.path.basename(v) for k, v in (snapshots or paths.WB_SNAPSHOTS).items()}
    result["snapshots_lastupdated_by_wdi"] = updated
    out_path = out_path or paths.MACRO_INPUTS
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    t, b = result["tanzania"], result["benchmark"]
    print("  Tanzania tax-to-GDP %d: %.2f%%; benchmark (%s) %d: %.2f%% vs Tanzania %.2f%% -> gap %.2f pp = TZS %.2f trillion" % (
        t["latest_year"], t["tax_to_gdp_pct"], b["policy"], b["year"], b["benchmark_pct"], b["tanzania_same_year_pct"], b["gap_pp"], b["revenue_gap_tzs"] / 1e12))
    return result


if __name__ == "__main__":
    run_macro_inputs()
