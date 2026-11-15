"""Persistence as the key uncertainty: return on programme cost at the signed-off persistence and at fixed 0.75, 0.90 and 0.95, for 10 and 20 years, by stage and for the portfolio."""
import _style as S
import matplotlib.pyplot as plt

COL = {"entry": S.GOLD, "active": S.NAVY, "enterprise": "#4C8C6B", "legacy": S.GREY, "portfolio_excluding_asset": S.RED}
NAME = {"entry": "Entry", "active": "Active", "enterprise": "Enterprise", "legacy": "Legacy", "portfolio_excluding_asset": "Portfolio (without Asset)"}


def make():
    b = S.load_json(S.paths.STAGE_ECONOMICS)["persistence_sensitivity"]
    cats = ["signed_off_triangular_0.5_0.75_0.9", "fixed_0.75", "fixed_0.90", "fixed_0.95"]
    xt = ["signed off\n(0.5-0.9,\nmode 0.75)", "0.75", "0.90", "0.95"]
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 4.8), sharey=True)
    for ax, h, title in zip(axes, ("10", "20"), ("10 years (flat tax per registrant)", "20 years (age-earnings path)")):
        blk = b["horizons"][h]
        series = {s: [blk["stages"][s][c]["roi"]["median"] for c in cats] for s in ("entry", "active", "enterprise", "legacy")}
        series["portfolio_excluding_asset"] = [blk["portfolio_excluding_asset"][c]["roi"]["median"] for c in cats]
        for s, ys in series.items():
            ax.plot(range(4), ys, marker="o", color=COL[s], linewidth=2.4 if s.startswith("portfolio") else 1.4, label=NAME[s])
        ax.axhline(1.0, color=S.RED, linestyle="--", linewidth=1)
        ax.set_xticks(range(4))
        ax.set_xticklabels(xt, fontsize=8)
        ax.set_yscale("log")
        ax.set_title(title, fontsize=10, color=S.SLATE)
        ax.set_xlabel("Yearly persistence of a new registrant")
    axes[0].set_ylabel("Return on programme cost (x, median)")
    axes[0].set_yticks([0.3, 0.5, 1, 2, 5, 10, 30])
    axes[0].set_yticklabels(["0.3", "0.5", "1", "2", "5", "10", "30"])
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="center left", bbox_to_anchor=(0.995, 0.5), fontsize=8)
    fig.text(0.5, 1.02, "assumed; no data fixes it; key uncertainty", ha="center", color=S.RED, fontsize=10)
    return S.save(fig, "fig_5_4_persistence_sensitivity")
