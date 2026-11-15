"""Targeting model: observed TIN rate and mean predicted rate by decile of the predicted propensity (out-of-fold, survey-weighted; outputs/tables/targeting_deciles.csv)."""
import _style as S
import matplotlib.pyplot as plt


def make():
    rows = S.read_csv(S.paths.TARGETING_DECILES_CSV)
    x = [int(r["decile"]) for r in rows]
    obs = [float(r["observed_tin_rate_pct"]) if r["observed_tin_rate_pct"] else 0.0 for r in rows]
    pred = [float(r["mean_predicted_pct"]) for r in rows]
    fig, ax = plt.subplots(figsize=(8.4, 4.6))
    bars = ax.bar(x, obs, color=S.SLATE, width=0.6, label="Observed TIN rate (survey-weighted)")
    for b, r in zip(bars, rows):
        if r["low_precision"] == "True":
            b.set_hatch("//")
            b.set_edgecolor("white")
    ax.plot(x, pred, color=S.GOLD, marker="o", linewidth=2, label="Mean predicted rate (calibrated)")
    ax.set_xticks(x)
    ax.set_xlabel("Decile of predicted propensity (1 = highest ... 10 = lowest)")
    ax.set_ylabel("Adults holding a TIN (%)")
    ax.legend(loc="upper right", fontsize=8)
    ax.text(0.99, 0.66, "hatched: low precision (fewer than 10 TIN holders);\ndeciles without a bar have no TIN holder in the sample", transform=ax.transAxes, ha="right", va="top", fontsize=7.5, color=S.GREY)
    return S.save(fig, "fig_a3_targeting_deciles")
