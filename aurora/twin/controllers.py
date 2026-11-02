"""Controllers A, B and C.

A  DieselOnly   status quo: no PV, no battery; commits the fewest units that
                carry the load.
B  SimpleRule   PV + battery, no forecast: solar -> load -> battery; deficit from
                battery down to soc_min, then diesel (units started as needed,
                minimum-load surplus charges the battery). Ported from
                aurora_skeleton.step / case_batanes.simulate("rule").
C  AuroraMPC    PV + battery, rolling-horizon MILP on the forecast (mpc.py), with
                Monte Carlo risk and fuel autonomy terms. Applies the first step
                and re-solves every hour.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import mpc, scenarios
from .plant import Decision


class DieselOnly:
    name = "A"
    has_pv = has_battery = False
    uses_forecast = False

    def __init__(self, p):
        self.p = p

    def decide(self, t, state, actual, fc=None):
        load = actual["crit"] + actual["flex"]
        n = min(self.p.n_units, max(1, math.ceil(load / self.p.unit_kw - 1e-9)))
        return Decision(n_on=n, p_diesel=load)


class SimpleRule:
    name = "B"
    has_pv = has_battery = True
    uses_forecast = False

    def __init__(self, p):
        self.p = p

    def decide(self, t, state, actual, fc=None):
        p = self.p
        r = actual["crit"] + actual["flex"] - actual["solar"]
        dis_max = min(p.bat_kw, max(state["soc"] - p.soc_min, 0) * p.bat_kwh * p.eta)
        if r <= dis_max + 1e-9:
            return Decision(n_on=0, p_diesel=0.0)
        gap = r - dis_max if dis_max > 1e-6 else r
        n = min(p.n_units, max(1, math.ceil(gap / p.unit_kw - 1e-9)))
        return Decision(n_on=n, p_diesel=gap)


class AuroraMPC:
    name = "C"
    has_pv = has_battery = True
    uses_forecast = True

    def __init__(self, p, horizon: int = 48, n_scen: int = 64, n_groups: int = 16, seed: int = 2026,
                 time_limit: float = 10.0):
        self.p, self.H, self.S, self.Qg = p, horizon, n_scen, n_groups
        self.rng = np.random.default_rng(seed)
        self.time_limit = time_limit
        self.last = {}

    def _need_groups(self, fc):
        p = self.p
        sol, crit = scenarios.draw(fc, self.S, self.rng, p.pv_kwp)
        need = scenarios.survival_need(sol, crit, p, p.risk_window_h)       # (S, H)
        self.last["need0"] = need[:, 0]
        srt = np.sort(need, axis=0)
        groups = np.array_split(np.arange(self.S), self.Qg)
        return np.vstack([srt[g].mean(axis=0) for g in groups])            # (Q, H)

    def _fuel_scenarios(self, fc, t, tank):
        """[(weight, delivery steps inside the horizon, critical kWh deficit after the
        horizon until the next delivery)] for each delivery-delay scenario."""
        p = self.p
        H = len(fc)
        end = t + pd.Timedelta(hours=H)
        tail = fc.iloc[-24:]
        deficit_day = float(np.clip(tail["demand_critical_kW_p90"] - tail["solar_kW_p10"], 0, None).sum())
        out = []
        for w, arr in tank.arrival_scenarios(t, end, p.overdue_delays, p.overdue_weights, p.overdue_days):
            steps = sorted({int(np.ceil((a - t) / pd.Timedelta(hours=1))) for a in arr if t < a < end})
            nxt = next((a for a in arr if a >= end), None)
            if steps or nxt is None:
                need = 0.0      # a delivery inside the horizon refills the tank
            else:
                need = deficit_day * ((nxt - end) / pd.Timedelta(hours=1)) / 24.0
            out.append((w, steps, need))
        return out

    def decide(self, t, state, actual, fc):
        p = self.p
        tank = state["tank"]
        fs = self._fuel_scenarios(fc, t, tank)
        self.last["fuel_scen"] = fs
        inp = mpc.MPCInput(
            solar=fc["solar_kW_p50"].to_numpy(), crit=fc["demand_critical_kW_p50"].to_numpy(),
            flex=fc["demand_flex_kW_p50"].to_numpy(), e0=state["soc"] * p.bat_kwh,
            n_prev=state["n_prev"], tank0=tank.level, fuel_scen=fs, need_q=self._need_groups(fc))
        plan = mpc.solve(inp, p, self.time_limit)
        self.last["plan"] = plan
        return Decision(n_on=int(plan["n_on"][0]), p_diesel=float(plan["p_diesel"][0]),
                        p_batt=float(plan["discharge"][0] - plan["charge"][0]),
                        shed_flex=float(plan["shed"][0]),
                        note="relaxed" if plan["relaxed"] else "")


CONTROLLERS = {"A": DieselOnly, "B": SimpleRule, "C": AuroraMPC}
