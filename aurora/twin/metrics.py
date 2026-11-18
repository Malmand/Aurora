"""Per-run KPIs (brief, Phase 4 list)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def kpis(run: pd.DataFrame, p) -> dict:
    fuel = run["fuel_l"].sum()
    served = (run["crit"] - run["unserved_crit"] + run["flex"] - run["shed"]).sum()
    has_bat = run["discharge"].abs().sum() > 0 or run["charge"].abs().sum() > 0
    c = run["cest_h"]
    return dict(
        hours=len(run),
        diesel_l=round(fuel, 0),
        fuel_cost_mphp=round(fuel * p.diesel_php_per_l / 1e6, 3),
        co2_t=round(fuel * p.co2_kg_per_l / 1000, 1),
        diesel_kwh=round(run["diesel"].sum(), 0),
        renewable_share_pct=round(100 * (1 - run["diesel"].sum() / served), 1) if served else np.nan,
        curtail_kwh=round(run["curtail"].sum(), 0),
        flex_shed_kwh=round(run["shed"].sum(), 1),
        flex_shed_h=int((run["shed"] > 1e-3).sum()),
        flex_shed_pct=round(100 * float(run["shed"].sum() / run["flex"].sum()), 1) if run["flex"].sum() else 0.0,
        crit_unserved_kwh=round(run["unserved_crit"].sum(), 1),
        crit_outage_h=int((run["unserved_crit"] > 1e-3).sum()),
        battery_throughput_kwh=round(run["discharge"].sum(), 0),
        battery_cycles=round(run["discharge"].sum() / p.bat_kwh, 1) if p.bat_kwh else 0.0,
        diesel_starts=int(np.clip(np.diff(np.r_[0, run["n_on"].to_numpy()]), 0, None).sum()),
        cest_median_h=round(float(c.median()), 1) if has_bat else 0.0,
        cest_min_h=round(float(c.min()), 1) if has_bat else 0.0,
        cest_ge12_pct=round(100 * float((c >= 12).mean()), 1) if has_bat else 0.0,
        cest_ge24_pct=round(100 * float((c >= 24).mean()), 1) if has_bat else 0.0,
        risk_mean=round(float(run["risk"].mean()), 3),
        tank_min_l=round(float(run["tank_end"].min()), 0),
        relaxed_steps=int(run["relaxed"].sum()),
        fallback_steps=int(run["fallback"].sum()),
        horizon_mean_h=round(float(run["horizon_h"].mean()), 1) if "horizon_h" in run else np.nan,
        plans_with_fallback_pct=round(100 * float((run["plan_fallback_h"] > 0).mean()), 1)
        if "plan_fallback_h" in run else np.nan,
        plan_fallback_h_mean=round(float(run["plan_fallback_h"].mean()), 1) if "plan_fallback_h" in run else np.nan,
        max_balance_resid_kw=float(run["balance_resid"].abs().max()),
    )
