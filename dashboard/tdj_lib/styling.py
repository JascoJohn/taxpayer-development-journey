"""Pure presentation layer for the Taxpayer Development Journey dashboard --
palette, CSS injection, and the evidence-tier tagging convention. No
dependency on Streamlit's multipage state, stage metadata, or any data
source: this module can be dropped into any Streamlit app unmodified.
"""

import streamlit as st

NAVY = "#1B3A5C"
GOLD = "#96591A"
SLATE = "#44546A"
CREAM = "#F7F1E5"
GRAY = "#595959"
WHITE = "#FFFFFF"

# The project's brand palette, sampled from the report's own
# section-header graphics -- distinct from the NAVY/GOLD site chrome above,
# used for the stage-specific hero/card treatment introduced in the Seed
# build and reused as-is here (not a per-stage palette; every stage's hero
# uses these same values). AMBER is the one color not sourced from the
# document -- a warm accent for "here's the caveat" / illustrative-bridge
# moments, chosen to complement the green rather than clash with it.
GREEN = "#256E29"
GREEN_DARK = "#123815"
TINT = "#D8E7D8"
TINT_LIGHT = "#E5EFE6"
AMBER = "#C97A1D"

EVIDENCE_TIER_HELP = (
    "Every figure on this dashboard carries the same labels as the report: "
    "**COMPUTED** (from data), **MODELLED** (a scenario from stated assumptions) "
    "or **CITED** (a published figure). Demo inputs are marked **ILLUSTRATIVE**."
)

# Evidence types (the report's three labels) and the one non-evidence tag for demo inputs (visually distinct: outlined, not filled).
_TIER_NAMES = {
    "computed": ("COMPUTED", "tier-computed"),
    "modelled": ("MODELLED", "tier-modelled"),
    "cited": ("CITED", "tier-cited"),
    "illustrative": ("ILLUSTRATIVE", "tier-illustrative"),
}


# Theme-aware colour tokens. Streamlit sets `color-scheme` on .stApp from the theme (Settings > Theme, or .streamlit/config.toml), so CSS light-dark(light, dark)
# follows the app's own Light / Dark choice. Pages use var(--tdj-...) for any colour of their own, never a fixed light colour.
THEME_TOKENS = {
    "--tdj-heading":      f"light-dark({NAVY}, #A9C7E8)",
    "--tdj-text-muted":   "light-dark(#595959, #AEB4C0)",
    "--tdj-muted":        "light-dark(#6B6B6B, #A3A8B3)",
    "--tdj-green":        f"light-dark({GREEN}, #7CC480)",
    "--tdj-green-strong": f"light-dark({GREEN_DARK}, #A5D6A7)",
    "--tdj-amber":        f"light-dark({AMBER}, #E8A04C)",
    "--tdj-callout-bg":   f"light-dark({CREAM}, #2B2618)",
    "--tdj-callout-bar":  f"light-dark({GOLD}, #D9953F)",
    "--tdj-card-bg":      f"light-dark({TINT_LIGHT}, #1B2A1E)",
    "--tdj-card-border":  f"light-dark({TINT}, #2F4A33)",
    "--tdj-note-bg":      "light-dark(#FDF3E7, #33281A)",
    "--tdj-quiet-bg":     "light-dark(#F4F4F4, #24262B)",
    "--tdj-quiet-border": "light-dark(#9A9A9A, #6A6D75)",
    "--tdj-quiet-text":   "light-dark(#555555, #B8BBC2)",
    "--tdj-tile-off-bg":  "light-dark(#EFEFEF, #2B2E36)",
    "--tdj-tile-off-text": "light-dark(#707070, #9CA3AF)",
    "--tdj-hairline":     "light-dark(#E6E6E6, #343842)",
    "--tdj-dot-off":      "light-dark(#CFCFCF, #4A4E58)",
    "--tdj-strong-text":  "light-dark(#222222, #ECEFF4)",
    "--tdj-tag-cited":    f"light-dark({NAVY}, #2F5F96)",
    "--tdj-tag-modelled": f"light-dark({GOLD}, #A8691F)",
}
_TOKEN_CSS = " ".join(f"{k}: {v};" for k, v in THEME_TOKENS.items())

# Colours for Plotly traces: mid-tones that read on both a light and a dark background (the chart background itself is transparent, see charts.py).
CHART_GREEN = "#3F9B46"
CHART_GREEN_DARK = "#2C7A33"
CHART_GREEN_LIGHT = "#8FCB93"
CHART_GREY = "#8E959F"
CHART_AMBER = "#E39A3B"
CHART_NAVY = "#4C7DB8"


def inject_base_style():
    st.markdown(
        f"""
        <style>
        .stApp {{ {_TOKEN_CSS} }}
        h1, h2, h3 {{ color: var(--tdj-heading); font-family: Georgia, 'Cambria', serif; }}
        .tdj-callout {{
            background-color: var(--tdj-callout-bg);
            border-left: 6px solid var(--tdj-callout-bar);
            padding: 0.9rem 1.1rem;
            border-radius: 2px;
            margin: 0.6rem 0 1.1rem 0;
        }}
        .tdj-callout .label {{
            color: var(--tdj-heading); font-weight: 700; letter-spacing: 0.05em;
            font-size: 0.78rem; text-transform: uppercase; margin-bottom: 0.3rem;
        }}
        .tdj-tag {{
            display: inline-block; font-size: 0.72rem; font-weight: 700;
            letter-spacing: 0.03em; text-transform: uppercase;
            padding: 0.12rem 0.5rem; border-radius: 3px; color: white;
            margin-right: 0.4rem;
        }}
        .tier-computed {{ background-color: #2E7D32; }}
        .tier-modelled {{ background-color: var(--tdj-tag-modelled); }}
        .tier-cited {{ background-color: var(--tdj-tag-cited); }}
        .tier-illustrative {{ background-color: transparent; color: var(--tdj-muted) !important; border: 1.5px dashed var(--tdj-quiet-border); }}
        .tdj-stagehead {{
            background-color: {NAVY}; color: white; padding: 0.6rem 1rem;
            border-radius: 4px; font-size: 0.95rem; margin-bottom: 0.4rem;
            border: 1px solid light-dark(transparent, #3A4F6B);
        }}
        /* persona thumbnail beside the stage header (about 160-200 px): a rounded container, so no image shows a hard box on a dark background */
        .stApp [data-testid="stImage"] img {{ border-radius: 12px; }}
        .tdj-thumb {{ border-radius: 12px; overflow: hidden; border: 1px solid var(--tdj-hairline); }}
        .tdj-kicker {{ color: var(--tdj-text-muted); font-size: 0.85rem; margin: 0 0 0.6rem 0; }}
        .tdj-linkline {{ font-size: 0.9rem; margin: 0.2rem 0 0.6rem 0; }}
        .tdj-ladder-tile {{
            text-align: center; padding: 0.5rem 0.2rem; border-radius: 6px; font-size: 0.72rem; font-weight: 700;
            background: var(--tdj-tile-off-bg); color: var(--tdj-tile-off-text);
        }}
        .tdj-ladder-tile.done {{ background: {GREEN}; color: white; }}
        .tdj-badge-ok {{
            display: inline-block; background: #2E7D32; color: white; font-weight: 700; font-size: 0.8rem;
            padding: 0.15rem 0.7rem; border-radius: 99px; margin: 0.2rem 0.4rem 0.2rem 0;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_hero_style(texture_b64: str = ""):
    """The green hero-banner + card system introduced in the Seed build
    (composed CSS gradient + a real network-texture asset via
    mix-blend-mode, rather than a static per-stage banner image -- see
    pages/1_Seed.py for why). Centralized here once it was clearly a
    reused pattern rather than a one-off, so a third/fourth stage can
    adopt it without copy-pasting this block again. Call once per page,
    after inject_base_style(). texture_b64 is the base64-encoded
    contents of assets/network_texture.png (or "" to render the hero
    as a flat gradient with no texture overlay).

    Grey (not a third accent hue) marks the "insufficient/unavailable"
    state -- deliberately matching the existing evidence_tag()
    illustrative tag's grey, not introducing a new color for the same
    idea of "lowest confidence / nothing to show here."
    """
    st.markdown(
        f"""
        <style>
        .tdj-hero {{
            position: relative; border-radius: 10px; overflow: hidden;
            padding: 2.1rem 2.3rem; margin: 0.4rem 0 1.4rem 0;
            background: linear-gradient(135deg, {GREEN} 0%, {GREEN_DARK} 100%);
            border-bottom: 5px solid {AMBER};
        }}
        .tdj-hero::before {{
            content: ""; position: absolute; inset: 0;
            background-image: url("data:image/png;base64,{texture_b64}");
            background-size: cover; background-position: center;
            mix-blend-mode: multiply; opacity: 0.9; pointer-events: none;
        }}
        .tdj-hero-inner {{ position: relative; z-index: 1; }}
        .tdj-hero-title {{
            color: white; font-family: Georgia, 'Cambria', serif;
            font-size: 2rem; font-weight: 700; margin: 0 0 0.3rem 0; line-height: 1.15;
        }}
        .tdj-hero-sub {{ color: {TINT}; font-size: 1.02rem; max-width: 46rem; margin: 0; }}
        .tdj-card {{
            background: var(--tdj-card-bg); border: 1px solid var(--tdj-card-border); border-radius: 8px;
            padding: 1rem 1.2rem; margin: 0.6rem 0;
        }}
        .tdj-note-card {{
            background: var(--tdj-note-bg); border-left: 5px solid var(--tdj-amber); border-radius: 6px;
            padding: 0.9rem 1.1rem; margin: 0.8rem 0;
        }}
        .tdj-note-label {{
            color: var(--tdj-amber); font-weight: 700; font-size: 0.74rem;
            letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 0.3rem;
        }}
        .tdj-insufficient-card {{
            background: var(--tdj-quiet-bg); border: 1px dashed var(--tdj-quiet-border); border-radius: 8px;
            padding: 1rem 1.2rem; margin: 0.8rem 0; color: var(--tdj-quiet-text);
        }}
        .tdj-insufficient-label {{
            color: var(--tdj-muted); font-weight: 700; font-size: 0.74rem;
            letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 0.3rem;
        }}
        .tdj-badge {{
            display: inline-block; background: {GREEN}; color: white;
            font-family: Georgia, 'Cambria', serif; font-weight: 700;
            padding: 0.35rem 0.9rem; border-radius: 99px; font-size: 0.95rem;
            margin: 0.2rem 0.3rem 0.2rem 0;
        }}
        .tdj-section-tag {{
            display: inline-block; color: var(--tdj-green); font-weight: 700;
            font-size: 0.76rem; letter-spacing: 0.08em; text-transform: uppercase;
            border: 1px solid var(--tdj-green); border-radius: 99px;
            padding: 0.15rem 0.7rem; margin-bottom: 0.6rem;
        }}
        .tdj-demo-note {{ color: var(--tdj-muted); font-size: 0.8rem; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def callout(label: str, body_markdown: str):
    st.markdown(
        f"""<div class="tdj-callout">
        <div class="label">{label}</div>
        {body_markdown}
        </div>""",
        unsafe_allow_html=True,
    )


def evidence_tag(tier: str):
    """tier: one of 'computed', 'modelled', 'cited' (the report's evidence types) or 'illustrative' (demo inputs; not an evidence type)."""
    text, cls = _TIER_NAMES[tier]
    st.markdown(f'<span class="tdj-tag {cls}">{text}</span>', unsafe_allow_html=True)
