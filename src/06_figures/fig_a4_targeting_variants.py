"""Targeting model variants: held-out weighted ROC-AUC of each feature set (outputs/tables/targeting_variants.csv)."""
import textwrap

import _style as S
import matplotlib.pyplot as plt


def make():
    rows = sorted(S.read_csv(S.paths.TARGETING_VARIANTS_CSV), key=lambda r: float(r["roc_auc_weighted"]))
    y = range(len(rows))
    auc = [float(r["roc_auc_weighted"]) for r in rows]
    fig, ax = plt.subplots(figsize=(9.2, 0.7 * len(rows) + 1.4))
    bars = ax.barh(list(y), auc, color=[S.NAVY if r["model"].startswith("PRIMARY") else S.SLATE for r in rows], height=0.55)
    ax.set_yticks(list(y))
    ax.set_yticklabels([r["model"].split(":")[0] + ("\n" + "\n".join(textwrap.wrap(r["model"].split(":", 1)[1].strip(), 46)) if ":" in r["model"] else "") for r in rows], fontsize=7.5)
    ax.set_xlim(0.5, 1.0)
    ax.set_xlabel("Held-out ROC-AUC (survey-weighted); 0.5 = no skill")
    for b, v, r in zip(bars, auc, rows):
        ax.text(v + 0.004, b.get_y() + b.get_height() / 2, "%.3f  (%d features)" % (v, int(r["n_encoded_features"])), va="center", fontsize=8, color=S.SLATE)
    return S.save(fig, "fig_a4_targeting_variants")
