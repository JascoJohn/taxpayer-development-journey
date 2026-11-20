"""Interactive Figure 5.1: the modelled probability that an adult reports a TIN, if every adult were reached, for any set of the six interventions.

The same combination logic as src/04_models/economic_model.py (build_tax_morale_model), from the constants in outputs/stats/figure_5_1_inputs.json (nothing typed):
  p = expit(alpha + beta * index(driver scores)), index = weighted sum of the five driver scores clipped to [0, 1];
  no intervention: today's value; ONE intervention: its driver deltas added to the baseline scores (each score capped at 1);
  TWO OR MORE: every active intervention's deltas multiplied by combined_discount (diminishing returns), added, capped at 1.
The result for all six is the report's combined effect; the "naive sum" is today's rate plus the separate gains of the active interventions.
MODELLED; the effects are assumed uplifts, not measured.
"""

import json
import math
import os

_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
DEFAULT_INPUTS_PATH = os.path.join(_ROOT, "outputs", "stats", "figure_5_1_inputs.json")


def load_inputs(path=None):
    with open(path or DEFAULT_INPUTS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _index(inp, scores):
    return min(1.0, max(0.0, sum(scores[k] * inp["weights"][k] for k in scores)))


def _prob(inp, scores):
    return 1.0 / (1.0 + math.exp(-(inp["alpha"] + inp["beta"] * _index(inp, scores))))


def _scores(inp, active, factor):
    sc = dict(inp["baseline_scores"])
    for name in active:
        for driver, delta in inp["interventions"][name]["deltas"].items():
            sc[driver] = min(1.0, sc[driver] + delta * factor)
    return sc


def baseline_probability(inp):
    return _prob(inp, inp["baseline_scores"])


def combined_probability(inp, active):
    """Modelled probability that an adult reports a TIN with the interventions in `active` (names of figure_5_1_inputs.json `interventions`)."""
    active = list(active)
    if not active:
        return baseline_probability(inp)
    factor = 1.0 if len(active) == 1 else inp["combined_discount"]
    return _prob(inp, _scores(inp, active, factor))


def solo_probability(inp, name):
    return combined_probability(inp, [name])


def best_single(inp):
    """The intervention with the highest solo probability, and that probability."""
    best = max(inp["interventions"], key=lambda k: solo_probability(inp, k))
    return best, solo_probability(inp, best)


def separate_gains_sum(inp, active):
    """Today's rate plus the sum of the separate (solo) gains of the active interventions (the report's 'naive sum of parts' when all six are active)."""
    base = baseline_probability(inp)
    return base + sum(solo_probability(inp, k) - base for k in active)


def explain(inp, active):
    """The sentence that goes with the chart; it follows the set of active interventions."""
    active = list(active)
    base = baseline_probability(inp) * 100
    comb = combined_probability(inp, active) * 100
    if not active:
        return f"No stage is switched on, so the modelled value is today's observed (survey-reported) adult TIN rate, {base:.2f}%."
    naive = separate_gains_sum(inp, active) * 100
    gains = naive - base
    if len(active) == 1:
        return (f"One stage is on, so there is nothing to combine: today's rate ({base:.2f}%) plus its separate gain ({gains:.2f} percentage points) equals the combined rate ({comb:.2f}%). "
                "Switch on a second stage to see the model's diminishing returns.")
    if naive > comb + 1e-9:
        return (f"The combined effect ({comb:.2f}%) sits below what adding the {len(active)} separate gains to today's rate would give "
                f"({base:.2f}% + {gains:.2f} percentage points = {naive:.2f}%): the model assumes diminishing returns, so the gain comes from coverage, not from synergy.")
    return (f"With these {len(active)} stages the combined effect ({comb:.2f}%) is not below today's rate plus the separate gains ({naive:.2f}%): "
            "the drivers are capped at their maximum, so the diminishing-returns discount does not bind here.")
