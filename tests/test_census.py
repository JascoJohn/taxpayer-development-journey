"""W4: the Seed count (ages 6-15) is reproducible from the Census 10% sample; 16-24 agrees with FinScope Entry within 1%."""
import json
import os
import sys

import numpy as np
import pytest

from conftest import requires_raw

pytestmark = requires_raw          # needs the restricted microdata: skipped with a message when they are absent

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import paths  # noqa: E402,F401
import census_population as cp  # noqa: E402


@pytest.fixture(scope="module")
def computed():
    age, sex = cp.read_age_sex(paths.CENSUS_SAV)
    return age, sex, cp.compute(age, sex, cp.finscope_entry_population())


def test_seed_band_comes_from_config():
    assert paths.SEED_AGE_BAND == (6, 15)
    with open(os.path.join(ROOT, "config.yaml"), encoding="utf-8") as f:
        assert "seed_age_band: [6, 15]" in f.read()


def test_seed_count_6_15_is_reproducible(computed):
    age, sex, (counts, cmp_) = computed
    expected = int(((age >= 6) & (age <= 15)).sum()) * 10
    assert cmp_["seed_population_x10"] == expected == counts["bands"]["seed_6_15"]["expanded_x10"]
    assert expected == 16_354_370
    assert cmp_["seed_male_x10"] + cmp_["seed_female_x10"] == expected
    # the same number sits in the file the pipeline wrote and is what the model reads
    assert cp.seed_population_from_processed() == expected
    with open(paths.ECONOMIC_MODEL, encoding="utf-8") as f:
        assert json.load(f)["base_parameters"]["seed_stage_population"] == expected


def test_expansion_is_x10_and_close_to_the_published_total(computed):
    _, _, (counts, cmp_) = computed
    exp = counts["expansion"]
    assert exp["factor"] == 10 and exp["sample_records"] == 6_181_772 and exp["records_without_valid_age"] == 0
    assert exp["expanded_total"] == 61_817_720
    assert abs(cmp_["difference_vs_published"]["total_x10_pct"]) < 0.2            # published total 61,741,120
    assert abs(cmp_["difference_vs_published"]["ages_6_15_x10_pct"]) < 0.2         # published 6-15 sum 16,346,387


def test_16_24_within_1_percent_of_the_finscope_entry_population(computed):
    _, _, (counts, cmp_) = computed
    chk = cmp_["finscope_entry_check"]
    assert chk["finscope_entry_population"] == 10_605_005
    assert chk["within_1pct"] is True
    assert abs(chk["census_16_24_x10"] / 10_605_005 - 1) <= 0.01


def test_published_citation_is_recorded(computed):
    _, _, (counts, cmp_) = computed
    pub = cmp_["published"]
    assert pub["total_population"] == 61_741_120 and "p. 44" in pub["table"] and "Age and Sex Distribution Report" in pub["citation"]


def test_count_by_age_sex_on_a_toy_sample():
    age = np.array([5.0, 6.0, 6.0, 15.0, 16.0, 97.0, np.nan])
    sex = np.array([1, 2, 2, 1, 2, 1, 1])
    both, male, female, n, bad = cp.count_by_age_sex(age, sex)
    assert n == 7 and bad == 1 and both[6] == 2 and female[6] == 2 and male[15] == 1 and both[97] == 1
    assert cp.band(both, 6, 15) == 3
