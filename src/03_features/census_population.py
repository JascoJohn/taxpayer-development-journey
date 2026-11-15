"""W4 - Seed population (and the 16-24 check) from the 2022 Census 10% sample.

Reads data/raw/census/TPHC2022_TenPercent_DEMOGRAPHICS.sav (NBS, 2022 Population and Housing Census, 10% sample,
6,181,772 person records) with pyreadstat, columns AGE and SEX only.

EXPANSION: weighted or x10? Neither the DEMOGRAPHICS file nor the household file (TPHC2022_TenPercent_HHDs.sav,
inspected in place: 52 household variables, 1,431,674 households) holds a weight, strata or cluster variable. The data
support only a simple expansion by the nominal sampling fraction: counts x 10. The sample is 10.012% of the published
total (6,181,772 x 10 = 61,817,720 against 61,741,120), so the x10 counts run 0.12% above the published ones. A
ratio-calibrated factor (published total / sample size = 9.9876) is reported as a sensitivity case. Because the file has
no design variables no sampling error is attached to the counts.

Seed band: config.yaml seed_age_band (6-15). Reported alongside: 16-24 (checked against the FinScope Entry population,
10,605,005, which is census-calibrated) and the old 6-18 band for reference.

PUBLISHED FIGURES (CITED, not computed): National Bureau of Statistics and Office of the Chief Government Statistician
Zanzibar, "The 2022 Population and Housing Census: Age and Sex Distribution Report, Tanzania", December 2022 -
Table 0 1 (United Republic of Tanzania: Population Distribution by Age, Sex and Place of Residence), printed p. 44
(PDF p. 66): total 61,741,120; single years of age; Table 3.1 (five-year groups, printed p. 13) and Table 1
(printed p. viii) give the same total. The published 6-15, 16-24 and 6-18 counts below are sums of the single-year rows
of Table 0 1 (arithmetic done here; the report prints no 6-15 total).

Outputs: data/processed/census_age_counts.json (aggregates only, safe to publish), outputs/stats/seed_population.json.
"""

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # src/
import paths

EXPANSION_FACTOR = 10
MAX_AGE = 97

PUBLISHED = {
    "citation": ("National Bureau of Statistics and Office of the Chief Government Statistician, Zanzibar. The 2022 Population and Housing "
                 "Census: Age and Sex Distribution Report, Tanzania. Dodoma, December 2022"),
    "url": "https://www.nbs.go.tz/uploads/statistics/documents/en-1705484562-Age_and_Sex_Distribution_Report_Tanzania_volume2a.pdf",
    "table": "Table 0 1 'United Republic of Tanzania: Population Distribution by Age, Sex and Place of Residence; 2022 PHC', printed p. 44 (PDF p. 66)",
    "total_population": 61741120,
    "total_where": "Table 0 1, p. 44; also Table 3.1 (p. 13) and Table 1 (p. viii)",
    "ages_6_15_both": 16346387, "ages_6_15_male": 8180683, "ages_6_15_female": 8165704,
    "ages_16_24_both": 10574268,
    "ages_6_18_both": 20255298,
    "ages_0_14_both": 26399989,
    "sums_note": "6-15, 16-24, 6-18 and 0-14 are sums of the published single-year rows (both sexes; male; female), computed here",
}
OLD_TYPED_SEED_POPULATION = 15_000_000


def read_age_sex(sav_path):
    import pyreadstat
    df, _ = pyreadstat.read_sav(sav_path, usecols=["AGE", "SEX"])
    return df["AGE"].to_numpy(), df["SEX"].to_numpy()


def count_by_age_sex(age, sex):
    """sample counts by single year of age 0..97 and sex (1 male, 2 female); returns (both, male, female) arrays of length 98."""
    ok = ~np.isnan(age) & (age >= 0) & (age <= MAX_AGE)
    a = age[ok].astype(int)
    s = sex[ok]
    both = np.bincount(a, minlength=MAX_AGE + 1)
    male = np.bincount(a[s == 1], minlength=MAX_AGE + 1)
    female = np.bincount(a[s == 2], minlength=MAX_AGE + 1)
    return both, male, female, int(len(age)), int((~ok).sum())


def band(arr, lo, hi):
    return int(arr[lo:hi + 1].sum())


def compute(age, sex, finscope_entry_population=None, factor=EXPANSION_FACTOR):
    both, male, female, n_records, n_bad = count_by_age_sex(age, sex)
    lo, hi = paths.SEED_AGE_BAND
    total_sample = int(both.sum())
    f = factor
    calib = PUBLISHED["total_population"] / total_sample
    bands = {
        "seed_%d_%d" % (lo, hi): (lo, hi),
        "entry_%d_24" % (hi + 1): (hi + 1, 24),
        "ages_6_18": (6, 18),
        "ages_0_14": (0, 14),
    }
    result_bands = {}
    for name, (a, b) in bands.items():
        s_both, s_m, s_f = band(both, a, b), band(male, a, b), band(female, a, b)
        result_bands[name] = {"age_from": a, "age_to": b, "sample_count": s_both, "expanded_x10": s_both * f,
                              "male_expanded": s_m * f, "female_expanded": s_f * f,
                              "calibrated_expanded": round(s_both * calib)}
    by_age = {str(i): {"sample": int(both[i]), "expanded": int(both[i]) * f, "male": int(male[i]) * f, "female": int(female[i]) * f}
              for i in range(MAX_AGE + 1)}
    counts = {
        "source": "TPHC2022_TenPercent_DEMOGRAPHICS.sav (NBS, 2022 Population and Housing Census, 10% sample)",
        "type": "COMPUTED",
        "aggregates_only": True,
        "expansion": {"method": "x10 (nominal sampling fraction)", "factor": f,
                      "why": "the sample files hold no weight, strata or cluster variable; the only supported expansion is by the sampling fraction",
                      "sample_records": n_records, "records_with_valid_age": total_sample, "records_without_valid_age": n_bad,
                      "expanded_total": total_sample * f,
                      "ratio_calibrated_factor": calib, "calibrated_total": PUBLISHED["total_population"]},
        "bands": result_bands,
        "by_age": by_age,
        "seed_age_band": [lo, hi],
    }
    seed_key = "seed_%d_%d" % (lo, hi)
    entry_key = "entry_%d_24" % (hi + 1)
    seed = result_bands[seed_key]
    pub6_15 = PUBLISHED["ages_6_15_both"]
    cmp_ = {
        "seed_age_band": [lo, hi],
        "seed_population_x10": seed["expanded_x10"],
        "seed_population_calibrated": seed["calibrated_expanded"],
        "seed_male_x10": seed["male_expanded"], "seed_female_x10": seed["female_expanded"],
        "published": {"citation": PUBLISHED["citation"], "table": PUBLISHED["table"], "url": PUBLISHED["url"],
                      "total_population": PUBLISHED["total_population"], "ages_6_15_both": pub6_15, "ages_16_24_both": PUBLISHED["ages_16_24_both"],
                      "sums_note": PUBLISHED["sums_note"]},
        "difference_vs_published": {
            "total_x10_minus_published": counts["expansion"]["expanded_total"] - PUBLISHED["total_population"],
            "total_x10_pct": (counts["expansion"]["expanded_total"] / PUBLISHED["total_population"] - 1) * 100,
            "ages_6_15_x10_minus_published": seed["expanded_x10"] - pub6_15 if (lo, hi) == (6, 15) else None,
            "ages_6_15_x10_pct": (seed["expanded_x10"] / pub6_15 - 1) * 100 if (lo, hi) == (6, 15) else None,
            "ages_16_24_x10_minus_published": result_bands[entry_key]["expanded_x10"] - PUBLISHED["ages_16_24_both"],
            "ages_16_24_x10_pct": (result_bands[entry_key]["expanded_x10"] / PUBLISHED["ages_16_24_both"] - 1) * 100,
        },
        "reference_6_18_x10": result_bands["ages_6_18"]["expanded_x10"],
        "previous_typed_value": OLD_TYPED_SEED_POPULATION,
        "seed_x10_vs_previous_typed_pct": (seed["expanded_x10"] / OLD_TYPED_SEED_POPULATION - 1) * 100,
        "entry_16_24_x10": result_bands[entry_key]["expanded_x10"],
    }
    if finscope_entry_population:
        e = result_bands[entry_key]["expanded_x10"]
        cmp_["finscope_entry_check"] = {"finscope_entry_population": finscope_entry_population, "census_16_24_x10": e,
                                        "difference": e - finscope_entry_population, "difference_pct": (e / finscope_entry_population - 1) * 100,
                                        "within_1pct": bool(abs(e / finscope_entry_population - 1) <= 0.01)}
    return counts, cmp_


def finscope_entry_population():
    try:
        with open(paths.FINSCOPE_SUMMARY, "r", encoding="utf-8") as f:
            return int(json.load(f)["by_stage"]["entry"]["population"])
    except (FileNotFoundError, KeyError, ValueError):
        return None


def seed_population_from_processed(path=None):
    """The Seed count for the configured age band, read from data/processed/census_age_counts.json (None if absent)."""
    path = path or paths.CENSUS_AGE_COUNTS
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
    except FileNotFoundError:
        return None
    lo, hi = d["seed_age_band"]
    if [lo, hi] != list(paths.SEED_AGE_BAND):
        raise ValueError("census_age_counts.json was built for the age band %s but config.yaml says %s: rerun the census step" % ([lo, hi], list(paths.SEED_AGE_BAND)))
    return int(d["bands"]["seed_%d_%d" % (lo, hi)]["expanded_x10"])


def run_census_population(sav_path=None, counts_path=None, seed_path=None):
    sav_path = sav_path or paths.CENSUS_SAV
    counts_path = counts_path or paths.CENSUS_AGE_COUNTS
    seed_path = seed_path or paths.SEED_POPULATION
    age, sex = read_age_sex(sav_path)
    counts, cmp_ = compute(age, sex, finscope_entry_population())
    for p in (counts_path, seed_path):
        os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(counts_path, "w", encoding="utf-8") as f:
        json.dump(counts, f, indent=1, ensure_ascii=False)
    with open(seed_path, "w", encoding="utf-8") as f:
        json.dump(cmp_, f, indent=2, ensure_ascii=False)
    d = cmp_["difference_vs_published"]
    print("  Seed %d-%d: %s (x10); published %s; 16-24: %s; total x10 %s (%.2f%% vs published)" % (
        cmp_["seed_age_band"][0], cmp_["seed_age_band"][1], format(cmp_["seed_population_x10"], ","), format(PUBLISHED["ages_6_15_both"], ","),
        format(cmp_["entry_16_24_x10"], ","), format(counts["expansion"]["expanded_total"], ","), d["total_x10_pct"]))
    return counts, cmp_


if __name__ == "__main__":
    run_census_population()
