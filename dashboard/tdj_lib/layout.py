"""Shared page layout of the stage pages (Dashboard v1.1, "tools first"): the stage header with a small persona thumbnail beside it, and one collapsed "About this stage" section
that holds the hero banner text, the "Why ... exists" section, the economics card and the limitation notes (moved, not rewritten)."""

import os

import streamlit as st

from .stages import stage_header
from .names import N

SCENARIO_LAB_PAGE = "pages/0_Scenario_Lab.py"
THUMB_WIDTH = 180                                    # px; the brief asks for about 160-200


def stage_top(icon, stage_name, verb, mechanism, position, stage_key, persona_path):
    """Stage header (left) and the persona thumbnail (right, about 180 px) on one row; the page's main tool follows directly below."""
    left, right = st.columns([5, 1.3], vertical_alignment="center")
    with left:
        stage_header(icon, stage_name, verb, mechanism, position)
        st.caption(getattr(N, stage_key).full)
    with right:
        if persona_path and os.path.exists(persona_path):
            st.image(persona_path, width=THUMB_WIDTH)


def about_stage():
    """The collapsed section; use as `with about_stage():`."""
    return st.expander("About this stage", expanded=False)


def scenario_lab_link(label="Change these assumptions in the Scenario Lab →"):
    st.page_link(SCENARIO_LAB_PAGE, label=label, icon="🧪")
