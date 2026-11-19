"""The stage masks are mutually exclusive and cover all FinScope respondents; the weights sum to 34,134,251."""
import os
import sys

import numpy as np
import pandas as pd
import pytest

from conftest import requires_raw

pytestmark = requires_raw          # needs the restricted microdata: skipped with a message when they are absent

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import paths  # noqa: E402,F401  (puts the stage folders on sys.path)
import finscope_segments as seg  # noqa: E402


@pytest.fixture(scope="module")
def df():
    return pd.read_csv(os.path.join(ROOT, "data", "raw", "finscope", "FinScope.csv"), low_memory=False)


def test_respondent_count(df):
    assert len(df) == 9915


def test_weights_sum(df):
    assert int(round(seg.survey_weights(df).sum())) == 34134251


def test_stages_are_exclusive_and_exhaustive(df):
    stage = seg.lifecycle_stage(df)
    assert set(np.unique(stage)) <= set(seg.LIFECYCLE_STAGES)          # no 'unknown'
    masks = np.column_stack([stage == s for s in seg.LIFECYCLE_STAGES])
    assert (masks.sum(axis=1) == 1).all()                              # exactly one stage per respondent
    w = seg.survey_weights(df)
    assert int(round(w.sum())) == int(round(sum(w[stage == s].sum() for s in seg.LIFECYCLE_STAGES)))


def test_seed_is_empty_in_finscope(df):
    # FinScope covers respondents aged 16+; the Seed stage (6-15) is not in the file
    assert (seg.lifecycle_stage(df) == "seed").sum() == 0


def test_stage_populations_match_the_published_values(df):
    stage = seg.lifecycle_stage(df)
    w = seg.survey_weights(df)
    pops = {s: int(w[stage == s].sum()) for s in ("entry", "active", "enterprise", "workers", "asset", "legacy")}
    # int() truncation, as in finscope_analysis.funnel_by_stage. Stage mapping B (Pass 6B-1): Active = business owners without a formal step, Enterprise = owners with D6_4a == 'Yes',
    # Non-business owners 25-44 = non-owners 25-44 (the former Active), Entry / Asset / Legacy unchanged. The six populations add up to the 34,134,251 adults.
    assert pops == {"entry": 10605005, "active": 2916164, "enterprise": 572735, "workers": 12110885, "asset": 5590836, "legacy": 2338624}
    assert abs(sum(pops.values()) - 34134251) <= 6


def test_tin_mask(df):
    w = seg.survey_weights(df)
    rate = w[seg.tin_holder_mask(df)].sum() / w.sum() * 100
    assert round(rate, 1) == 3.8
