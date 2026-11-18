"""Hourly simulation loop: forecast -> controller -> plant, with CEST and R(t).

Every controller is scored with the same forecast for CEST and R(t), so the
resilience numbers are comparable; only C uses the forecast to decide.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd

from . import cest as cest_mod
from . import plant, scenarios
from .controllers import CONTROLLERS


def utc(ts) -> pd.Timestamp:
    ts = pd.Timestamp(ts)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def default_schedule(p, start) -> plant.FuelSchedule:
    """Deliveries every resupply_days, the first one half an interval after the start."""
    start = utc(start)
    return plant.FuelSchedule(
        capacity_l=p.tank_l, interval_days=p.resupply_days, first=start + pd.Timedelta(days=p.resupply_days / 2)
    )


HORIZON_MODES = ("issue", "fixed")
MIN_ISSUE_HORIZON_H = 25  # shortest plan inside a daily 48 h issue


def plan_horizon(forecast, t, max_h: int = 48, mode: str = "issue") -> int:
    """MPC horizon at step t.

    "fixed": always max_h. "issue": hours from t to the end of the newest issued
    forecast (forecast.issue_end), capped at max_h, so no plan hour comes from the
    persistence fallback tail. If the provider has no issue, or the newest issue
    ends less than MIN_ISSUE_HORIZON_H ahead (an issue was missed, comms down),
    the horizon stays at max_h and the fallback fills the tail, flagged.
    """
    if mode not in HORIZON_MODES:
        raise ValueError(f"horizon mode {mode!r}; use one of {HORIZON_MODES}")
    if mode == "fixed":
        return max_h
    end_fn = getattr(forecast, "issue_end", None)
    end = end_fn(t) if end_fn else None
    if end is None:
        return max_h
    h = int((end - t) // pd.Timedelta(hours=1))
    return min(max_h, h) if h >= MIN_ISSUE_HORIZON_H else max_h


def run(
    truth: pd.DataFrame,
    p,
    controller: str,
    forecast,
    start=None,
    hours=None,
    schedule: plant.FuelSchedule | None = None,
    tank0: float | None = None,
    horizon: int = 48,
    horizon_mode: str = "issue",
    n_scen_risk: int = 64,
    seed: int = 2026,
    progress: bool = False,
    **ctrl_kw,
) -> pd.DataFrame:
    """Simulate one controller hour by hour over `truth` and return one row per hour.

    Each hour: deliveries arrive, the controller decides on its forecast (C) or on the meters (A, B, O), the
    plant applies the decision to the actual solar and load, and the Survival Clock is computed.
    """
    idx = truth.index
    i0 = 0 if start is None else idx.get_loc(utc(start))
    n_steps = len(idx) - i0 - horizon if hours is None else hours
    if i0 + n_steps + horizon > len(idx):
        raise ValueError("truth too short for the run plus forecast horizon")
    ctl = CONTROLLERS[controller](p, **ctrl_kw) if controller == "C" else CONTROLLERS[controller](p)
    sched = schedule or default_schedule(p, idx[i0])
    tank = plant.FuelTank(sched, p.tank_l if tank0 is None else tank0)
    soc = p.soc0 if ctl.has_battery else 0.0
    n_prev = 0
    rng = np.random.default_rng(seed + 1)
    rows = []
    t_wall = time.time()
    for k in range(n_steps):
        t = idx[i0 + k]
        tank.receive(t)
        r = truth.iloc[i0 + k]
        actual = dict(
            solar=float(r.pv_kw_per_kwp * p.pv_kwp) if ctl.has_pv else 0.0, crit=float(r.crit_kW), flex=float(r.flex_kW)
        )
        H = plan_horizon(forecast, t, horizon, horizon_mode)
        fc = forecast(t, H)
        if not ctl.has_pv:
            fc = fc.assign(solar_kW_p10=0.0, solar_kW_p50=0.0, solar_kW_p90=0.0)
        state = dict(soc=soc, tank=tank, n_prev=n_prev)
        dec = ctl.decide(t, state, actual, fc)
        out = plant.step(
            p, soc, tank.level, actual["solar"], actual["crit"], actual["flex"], dec, has_battery=ctl.has_battery
        )
        # resilience metrics at the start of the step
        if ctl.has_battery:
            c = cest_mod.cest_hours(soc, fc["solar_kW_p10"].to_numpy(), fc["demand_critical_kW_p90"].to_numpy(), p)
            if controller == "C" and "need0" in ctl.last:
                need0 = ctl.last["need0"]
            else:
                s_, c_ = scenarios.draw(fc, n_scen_risk, rng, p.pv_kwp)
                need0 = scenarios.survival_need(s_[:, : p.risk_window_h], c_[:, : p.risk_window_h], p, p.risk_window_h)[
                    :, 0
                ]
            risk = scenarios.risk_now(need0, soc, p)
        else:
            c, risk = 0.0, 1.0
        tank.level = out["tank_end"]
        soc = out["soc_end"]
        n_prev = out["n_on"]
        rows.append(
            dict(
                timestamp=t,
                **out,
                cest_h=c,
                risk=risk,
                fallback=bool(fc["fallback"].iloc[0]),
                horizon_h=H,
                plan_fallback_h=int(fc["fallback"].sum()),
                relaxed=dec.note == "relaxed",
                plan_shed=dec.shed_flex,
            )
        )
        if progress and k % 168 == 0:
            print(f"  {controller} {t:%Y-%m-%d %H}h  step {k}/{n_steps}  {time.time() - t_wall:.0f}s", flush=True)
    df = pd.DataFrame(rows).set_index("timestamp")
    df.attrs.update(
        controller=controller,
        sizing=p.sizing,
        forecast=getattr(forecast, "name", "?"),
        horizon_mode=horizon_mode,
        horizon_max_h=horizon,
        deliveries=str([(str(a), str(b), round(v)) for a, b, v in tank.log]),
        wall_s=f"{time.time() - t_wall:.1f}",
    )
    return df
