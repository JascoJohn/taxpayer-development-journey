"""Stage mapping B (Pass 6B-1): Active = business owners without a formal step; Enterprise = owners with D6_4a == 'Yes'; Workers 25-44 = non-owners, no revenue lever. Runs on a small
synthetic respondent table, so it needs no restricted data."""
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import paths  # noqa: E402,F401
import finscope_segments as seg  # noqa: E402


def _frame(rows):
    return pd.DataFrame(rows, columns=["c8c", "BusO", "D6_4a"])


def test_the_seven_stages_in_order():
    assert seg.LIFECYCLE_STAGES == ["seed", "entry", "active", "enterprise", "workers", "asset", "legacy"]
    assert seg.ADULT_STAGES == ["entry", "active", "enterprise", "workers", "asset", "legacy"]


def test_each_respondent_gets_the_stage_of_mapping_b():
    own, non = "Business owners", "Not a business owner"
    df = _frame([
        (20, own, "Yes"),        # entry whoever they are
        (20, non, None),         # entry
        (25, own, "No"),         # active
        (64, own, "No"),         # active (upper age bound inclusive of 64)
        (40, own, None),         # active: not asked counts as no formal step
        (40, own, ""),           # active: blank counts as no formal step
        (30, own, "Yes"),        # enterprise
        (64, own, "yes"),        # enterprise (case-insensitive)
        (25, non, "Yes"),        # workers: a non-owner never reaches Enterprise, whatever D6_4a says
        (44, non, None),         # workers
        (45, non, None),         # asset
        (64, non, None),         # asset
        (65, own, "Yes"),        # legacy whoever they are
        (80, non, None),         # legacy
    ])
    got = list(seg.lifecycle_stage(df))
    assert got == ["entry", "entry", "active", "active", "active", "active", "enterprise", "enterprise",
                   "workers", "workers", "asset", "asset", "legacy", "legacy"]


def test_missing_formal_step_answer_counts_as_no_formal_step():
    df = _frame([(30, "Business owners", None), (30, "Business owners", "No"), (30, "Business owners", "Yes")])
    assert list(seg.formal_step_mask(df)) == [False, False, True]
    no_column = df.drop(columns=["D6_4a"])                      # a table without the question at all: nobody has a formal step
    assert not seg.formal_step_mask(no_column).any()


def test_stages_are_exclusive_and_exhaustive_on_every_age():
    rows = [(a, b, f) for a in range(6, 100) for b in ("Business owners", "Not a business owner") for f in ("Yes", "No", None)]
    df = _frame(rows)
    stage = seg.lifecycle_stage(df)
    assert set(stage) <= set(seg.LIFECYCLE_STAGES)
    assert "unknown" not in set(stage)


def test_workers_have_a_name_and_no_tool():
    assert paths.CFG["names"]["workers"]["english"] == "Workers 25–44 (no revenue lever)"
    assert paths.CFG["names"]["workers"]["swahili"] == ""
