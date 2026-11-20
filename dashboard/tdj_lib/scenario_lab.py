"""Scenario lab simulator: a pure-NumPy copy of the Table 5.1 Monte Carlo (src/04_models/stage_economics.py: draw_inputs, central_inputs, simulate, _portfolio).

Reads ONLY outputs/stats/scenario_lab_inputs.json (written by src/04_models/dashboard_inputs.py); nothing is typed here and nothing is imported from the pipeline, so it runs on the
deployed app. With the pipeline's own seed and number of draws and the default controls it reproduces stage_economics.json (tests/test_scenario_lab.py).

MODELLED scenario calculation: statutory tax on survey earnings x assumed reach and uptake; not a forecast.
"""

import json
import math
import os

import numpy as np

_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
DEFAULT_INPUTS_PATH = os.path.join(_ROOT, "outputs", "stats", "scenario_lab_inputs.json")


def load_inputs(path=None):
    with open(path or DEFAULT_INPUTS_PATH, encoding="utf-8") as f:
        return json.load(f)


def default_controls(inputs):
    sh = inputs["shared"]
    return {"stages_on": {s: True for s in sh["stage_order"]}, "reach_mult": 1.0, "uptake_mult": 1.0, "persistence": None, "horizon": int(sh["horizon_years"]),
            "rate": float(sh["discount_rate"]), "basis": sh["central_income_basis"]}


def is_default(inputs, controls):
    d = default_controls(inputs)
    return (all(controls["stages_on"].get(s, True) for s in d["stages_on"]) and controls["reach_mult"] == 1.0 and controls["uptake_mult"] == 1.0 and controls["persistence"] is None
            and int(controls["horizon"]) == d["horizon"] and abs(controls["rate"] - d["rate"]) < 1e-12 and controls["basis"] == d["basis"])


def _tri(rng, spec, n):
    lo, mode, hi = spec
    return rng.triangular(lo, mode, hi, n)


def _summ(x):
    return {"mean": float(np.mean(x)), "median": float(np.median(x)), "p10": float(np.percentile(x, 10)), "p90": float(np.percentile(x, 90))}


class Lab:
    """One set of random draws per (income basis, number of draws); the controls are applied to the draws, never to the stream (common random numbers, as in the pipeline)."""

    def __init__(self, inputs, n_draws=None):
        self.inputs = inputs
        self.sh = inputs["shared"]
        self.n_draws = int(n_draws or self.sh["n_draws"])
        self._draws = {}

    # ---- random inputs (stage_economics.draw_inputs / draw_all) ----------------------------------------------------------------------------------------------------------------
    def draws(self, basis):
        if basis not in self._draws:
            sh, n = self.sh, self.n_draws
            rng = np.random.default_rng(int(sh["seed"]))
            out = {}
            for s in sh["stage_order"]:
                spec = self.inputs["stages"][s]
                if s == "seed":
                    lo, hi = spec["cost_range_tzs"]
                    out[s] = {"cost": rng.uniform(lo, hi, n)}
                    continue
                reach, persist = _tri(rng, spec["reach_triangle"], n), _tri(rng, sh["persistence_triangle"], n)
                p = np.clip(rng.normal(spec["p"], spec["p_se"], n), 1e-4, 0.5)
                lnor = np.maximum(rng.normal(math.log(spec["odds_ratio"]), sh["uptake_log_odds_sd"], n), 0.0)
                tx = spec["tax_per_registrant_tzs"][basis]
                tax = np.clip(rng.normal(tx["mean"], tx["se"], n), 0.0, None)
                overrun = np.exp(rng.normal(0.0, sh["cost_overrun_sigma"], n))          # drawn for Asset too (the stream is kept; Asset has no stated cost)
                inp = {"reach": reach, "persist": persist, "p": p, "lnor": lnor, "tax": tax}
                if s != "asset":
                    inp["cost"] = spec["stated_cost_tzs"] * overrun
                out[s] = inp
            self._draws[basis] = out
        return self._draws[basis]

    def central(self, basis):
        """The central point (stage_economics.central_inputs): mode of the triangles, the published estimates, the middle of the Seed cost range."""
        out = {}
        for s in self.sh["stage_order"]:
            spec = self.inputs["stages"][s]
            if s == "seed":
                lo, hi = spec["cost_range_tzs"]
                out[s] = {"cost": np.array([(lo + hi) / 2])}
                continue
            inp = {"reach": np.array([spec["reach_triangle"][1]]), "persist": np.array([self.sh["persistence_triangle"][1]]), "p": np.array([spec["p"]]),
                   "lnor": np.array([math.log(spec["odds_ratio"])]), "tax": np.array([spec["tax_per_registrant_tzs"][basis]["mean"]])}
            if s != "asset":
                inp["cost"] = np.array([spec["stated_cost_tzs"]])
            out[s] = inp
        return out

    # ---- the simulation (stage_economics.simulate) ---------------------------------------------------------------------------------------------------------------------------
    def simulate(self, stage, inp, rate, horizon, aged, persist=None, reach_mult=1.0, uptake_mult=1.0):
        spec = self.inputs["stages"][stage]
        ramp = int(self.sh["ramp_years"])
        if stage == "seed":
            z = np.zeros_like(inp["cost"])
            return {"registrants": z, "revenue_pv": z, "cost": inp["cost"], "npv": -inp["cost"], "roi": z}
        pers = inp["persist"] if persist is None else np.full_like(inp["persist"], float(persist))
        reach = inp["reach"] * reach_mult
        lnor = inp["lnor"] * uptake_mult
        delta = np.maximum(1.0 / (1.0 + np.exp(-(np.log(inp["p"] / (1 - inp["p"])) + lnor))) - inp["p"], 0.0)
        new_total = spec["population"] * reach * delta
        mult = spec["age_earnings_multiplier"] if aged else None
        rev = np.zeros_like(new_total)
        for t in range(1, horizon + 1):
            stock_value = np.zeros_like(new_total)
            for c in range(1, min(t, ramp) + 1):
                k = t - c
                stock_value = stock_value + pers ** k * (mult[min(k, len(mult) - 1)] if mult is not None else 1.0) * 1.0
            rev = rev + new_total / ramp * inp["tax"] * stock_value * (1 + rate) ** (-t)
        out = {"registrants": new_total, "revenue_pv": rev}
        if "cost" in inp:
            out.update({"cost": inp["cost"], "npv": rev - inp["cost"], "roi": rev / inp["cost"]})
        return out

    def _portfolio(self, sims, on):
        keys = [s for s in self.sh["portfolio_stages"] if on.get(s, True)]
        if not keys:
            return None
        port = {k: sum(sims[s][k] for s in keys) for k in ("registrants", "revenue_pv", "cost", "npv")}
        port["roi"] = port["revenue_pv"] / port["cost"]
        return port

    def run(self, controls=None, with_central=True):
        """Results of one setting of the controls. controls: see default_controls(). Returns per-stage summaries, the portfolio (the enabled stages of the report's portfolio:
        Seed as cost only, Entry, Active, Enterprise, Legacy; Asset is never in it) and the central case."""
        c = dict(default_controls(self.inputs), **(controls or {}))
        horizon = int(c["horizon"])
        aged = horizon != int(self.sh["horizon_years"])                         # 10 years: flat tax per registrant (signed off); 20 years: the age-earnings path
        kw = dict(rate=float(c["rate"]), horizon=horizon, aged=aged, persist=c["persistence"], reach_mult=float(c["reach_mult"]), uptake_mult=float(c["uptake_mult"]))
        on = c["stages_on"]
        draws = self.draws(c["basis"])
        sims = {s: self.simulate(s, draws[s], **kw) for s in self.sh["stage_order"]}
        res = {"controls": c, "n_draws": self.n_draws, "stages": {}}
        for s in self.sh["stage_order"]:
            d = {k: _summ(v) for k, v in sims[s].items()}
            if "roi" in sims[s] and s != "seed":
                d["p_roi_ge_1"] = float(np.mean(sims[s]["roi"] >= 1.0))
            d["on"] = bool(on.get(s, True))
            res["stages"][s] = d
        port = self._portfolio(sims, on)
        res["portfolio"] = None if port is None else {**{k: _summ(v) for k, v in port.items()}, "p_roi_ge_1": float(np.mean(port["roi"] >= 1.0))}
        if with_central:
            cen = self.central(c["basis"])
            csims = {s: self.simulate(s, cen[s], **kw) for s in self.sh["stage_order"]}
            res["central_stages"] = {s: {k: float(v[0]) for k, v in csims[s].items()} for s in self.sh["stage_order"]}
            cp = self._portfolio(csims, on)
            res["central_portfolio"] = None if cp is None else {k: float(v[0]) for k, v in cp.items()}
        return res
