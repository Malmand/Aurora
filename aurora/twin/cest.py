"""Community Energy Survival Time (CEST).

Hours that critical load can run on battery plus forecast P10 solar, with diesel
off and flexible load off, until SOC reaches the reserve line (cest_reserve_soc).
Critical demand is taken at P90 (pessimistic on both sides). Beyond the forecast
the last 24 h are repeated. Capped at `cap` hours (censored).
Ported from digital_twin/aurora_skeleton.py:cest (team repo, Mohamed), with
battery power limits on both charge and discharge.
"""

from __future__ import annotations

import numpy as np


def cest_hours(soc: float, solar_p10, crit_p90, p, cap: int = 72) -> float:
    """Survival Clock: hours the critical load (P90) lasts on battery plus P10 solar, diesel off, capped at `cap`."""
    if p.bat_kwh <= 0:
        return 0.0
    sol = np.asarray(solar_p10, float)
    crit = np.asarray(crit_p90, float)
    n = len(sol)
    e = soc * p.bat_kwh
    floor, emax = p.soc_cest * p.bat_kwh, p.soc_max * p.bat_kwh
    if e <= floor:
        return 0.0
    for k in range(cap):
        j = k if k < n else n - 24 + (k - n) % 24 if n >= 24 else k % n
        net = sol[j] - crit[j]
        if net >= 0:
            e = min(e + min(net, p.bat_kw) * p.eta, emax)
            continue
        if -net > p.bat_kw + 1e-9:
            return float(k)  # battery inverter too small for the deficit
        need = -net / p.eta
        if e - need <= floor:
            return k + (e - floor) / need
        e -= need
    return float(cap)
