"""One place for the look of every Plotly chart: transparent background, theme-neutral grid lines, and the font colour left to Streamlit's own theme (st.plotly_chart's default
theme="streamlit" applies the active Light / Dark theme's text colour), so a chart reads on both themes. No chart sets a fixed white background."""

GRID = "rgba(128, 128, 128, 0.25)"
ZERO = "rgba(128, 128, 128, 0.45)"


def themed(fig, **layout):
    """Transparent paper and plot background, grey grid lines that work on a light or a dark page. Extra keyword arguments go to update_layout."""
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", **layout)
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=ZERO, linecolor=ZERO)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=ZERO, linecolor=ZERO)
    return fig
