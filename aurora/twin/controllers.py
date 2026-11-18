"""The four controllers compared in the study.

A  DieselOnly   status quo: no PV, no battery; commits the fewest units that
                carry the load.
B  SimpleRule   PV + battery, no forecast: solar -> load -> battery; deficit from
                battery down to soc_min, then diesel (units started as needed,
                minimum-load surplus charges the battery). Ported from
                aurora_skeleton.step / case_batanes.simulate("rule").
O  RationingOperator  B plus what a careful operator does when the tanker is late:
                rotating block cuts sized from the fuel gauge (model v2 baseline).
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
    """A: today's plant. No solar or battery; commits the fewest units that carry the load."""

    name = "A"
    has_pv = has_battery = False
    uses_forecast = False

    def __init__(self, p):
        self.p = p

    def decide(self, t, state, actual, fc=None):
        """Commit enough units for this hour's load."""
        load = actual["crit"] + actual["flex"]
        n = min(self.p.n_units, max(1, math.ceil(load / self.p.unit_kw - 1e-9)))
        return Decision(n_on=n, p_diesel=load)


class SimpleRule:
    """B: solar and battery with a simple rule, no forecast. Battery first, then diesel for the gap."""

    name = "B"
    has_pv = has_battery = True
    uses_forecast = False

    def __init__(self, p):
        self.p = p

    def decide(self, t, state, actual, fc=None):
        """Use the battery down to its minimum, then start units for the remaining gap."""
        p = self.p
        r = actual["crit"] + actual["flex"] - actual["solar"]
        dis_max = min(p.bat_kw, max(state["soc"] - p.soc_min, 0) * p.bat_kwh * p.eta)
        if r <= dis_max + 1e-9:
            return Decision(n_on=0, p_diesel=0.0)
        gap = r - dis_max if dis_max > 1e-6 else r
        n = min(p.n_units, max(1, math.ceil(gap / p.unit_kw - 1e-9)))
        return Decision(n_on=n, p_diesel=gap)


class RationingOperator:
    """O: the simple rule plus what a sensible operator does when the tanker is late.

    Model v2 baseline (Phase 4b). Once a planned delivery is overdue, the operator
    estimates the fuel needed to reach the latest plausible arrival (planned time +
    op_plan_delay_days) from the last 24 h of meter readings:

        F_full = (sum(load) - eta^2 sum(solar))+ per day x days left x sfc
        F_crit = (sum(crit) - eta^2 sum(solar))+ per day x days left x sfc

    If the tank holds less than F_full, a share f = (F_full - tank) / (F_full - F_crit)
    of the flexible load is cut, in whole feeder blocks, in every hour the battery
    cannot carry the load (rotating evening and night brownouts, as NPC and BATANELCO
    did in 2022 and 2023). sfc = fuel per kWh at the assumed average loading.
    It uses meters and the fuel gauge only, no forecast.
    """

    name = "O"
    has_pv = has_battery = True
    uses_forecast = False

    def __init__(self, p):
        self.p = p
        self.rule = SimpleRule(p)
        self.hist = []
        self.last = {}

    def _overdue(self, t, tank):
        s = tank.s
        return [
            pt
            for pt in s.planned(t - pd.Timedelta(days=60), t + pd.Timedelta(hours=1))
            if pt not in tank.delivered and pt <= t
        ]

    def cut_share(self, t, tank) -> float:
        """Share of flexible load to cut so the fuel lasts until the latest plausible tanker arrival."""
        p = self.p
        late = self._overdue(t, tank)
        if not late or not self.hist:
            return 0.0
        worst = min(late) + pd.Timedelta(days=p.op_plan_delay_days)
        days_left = max((worst - t) / pd.Timedelta(days=1), 1.0)
        h = np.array(self.hist[-24:])
        per_day = 24.0 / len(h)
        load, crit, sol = h[:, 0].sum(), h[:, 1].sum(), h[:, 2].sum()
        sfc = p.fuel_b + p.fuel_a / p.op_sfc_loading
        f_full = max(load - p.eta**2 * sol, 0.0) * per_day * days_left * sfc
        f_crit = max(crit - p.eta**2 * sol, 0.0) * per_day * days_left * sfc
        if tank.level >= f_full:
            return 0.0
        return float(np.clip((f_full - tank.level) / max(f_full - f_crit, 1e-6), 0.0, 1.0))

    def decide(self, t, state, actual, fc=None):
        """Simple rule, plus rotating block cuts in hours the battery cannot carry while fuel is short."""
        p = self.p
        self.hist.append((actual["crit"] + actual["flex"], actual["crit"], actual["solar"]))
        self.hist = self.hist[-24:]
        f = self.cut_share(t, state["tank"])
        self.last["cut_share"] = f
        if f <= 0:
            return self.rule.decide(t, state, actual)
        B = max(int(p.n_flex_blocks), 1)
        blocks = min(B, int(np.ceil(f * B - 1e-9)))
        r = actual["crit"] + actual["flex"] - actual["solar"]
        dis_max = min(p.bat_kw, max(state["soc"] - p.soc_min, 0) * p.bat_kwh * p.eta)
        if r <= dis_max + 1e-9:  # battery carries it: no brownout this hour
            return self.rule.decide(t, state, actual)
        shed = blocks * actual["flex"] / B
        dec = self.rule.decide(t, state, dict(actual, flex=actual["flex"] - shed))
        dec.shed_flex = shed
        dec.note = f"ration {blocks}/{B}"
        return dec


class AuroraMPC:
    """C: AURORA. Solves the MILP over the forecast horizon every hour and applies the first step."""

    name = "C"
    has_pv = has_battery = True
    uses_forecast = True

    def __init__(
        self, p, horizon: int = 48, n_scen: int = 64, n_groups: int = 16, seed: int = 2026, time_limit: float = 10.0
    ):
        self.p, self.H, self.S, self.Qg = p, horizon, n_scen, n_groups
        self.rng = np.random.default_rng(seed)
        self.time_limit = time_limit
        self.last = {}

    def _need_groups(self, fc):
        p = self.p
        sol, crit = scenarios.draw(fc, self.S, self.rng, p.pv_kwp)
        need = scenarios.survival_need(sol, crit, p, p.risk_window_h)  # (S, H)
        self.last["need0"] = need[:, 0]
        srt = np.sort(need, axis=0)
        groups = np.array_split(np.arange(self.S), self.Qg)
        return np.vstack([srt[g].mean(axis=0) for g in groups])  # (Q, H)

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
                need = 0.0  # a delivery inside the horizon refills the tank
            else:
                need = deficit_day * ((nxt - end) / pd.Timedelta(hours=1)) / 24.0
            out.append((w, steps, need))
        return out

    def decide(self, t, state, actual, fc):
        """Build the MPC input from the forecast, battery, units on and fuel belief, solve, return hour one."""
        p = self.p
        tank = state["tank"]
        fs = self._fuel_scenarios(fc, t, tank)
        self.last["fuel_scen"] = fs
        inp = mpc.MPCInput(
            solar=fc["solar_kW_p50"].to_numpy(),
            crit=fc["demand_critical_kW_p50"].to_numpy(),
            flex=fc["demand_flex_kW_p50"].to_numpy(),
            e0=state["soc"] * p.bat_kwh,
            n_prev=state["n_prev"],
            tank0=tank.level,
            fuel_scen=fs,
            need_q=self._need_groups(fc),
        )
        plan = mpc.solve(inp, p, self.time_limit)
        self.last["plan"] = plan
        return Decision(
            n_on=int(plan["n_on"][0]),
            p_diesel=float(plan["p_diesel"][0]),
            p_batt=float(plan["discharge"][0] - plan["charge"][0]),
            shed_flex=float(plan["shed"][0]),
            note="relaxed" if plan["relaxed"] else "",
        )


CONTROLLERS = {"A": DieselOnly, "B": SimpleRule, "O": RationingOperator, "C": AuroraMPC}
