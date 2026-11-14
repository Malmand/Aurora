"""Physical plant for one hourly step: PV, battery, diesel units, fuel tank, loads.

The controller hands over a Decision planned on its forecast. The plant applies
it to the ACTUAL solar and load with a real-time balancing layer (grid-forming
battery): diesel runs at its set point, the battery absorbs the mismatch; when
the battery cannot, diesel moves within its committed range, then more units
start (fuel permitting), then flexible load is shed, and only then critical
load goes unserved. A surplus goes to the battery, then diesel turns down
(and units stop), then PV is curtailed. The energy balance closes exactly:

    pv_used + diesel + discharge = charge + crit_served + flex_served
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

EPS = 1e-9


@dataclass
class Decision:
    n_on: int = 0               # diesel units committed
    p_diesel: float = 0.0       # diesel set point (kW)
    p_batt: float = 0.0         # planned battery power, + discharge / - charge (kW), informative
    shed_flex: float = 0.0      # planned flexible shedding (kW)
    note: str = ""


@dataclass
class FuelSchedule:
    """Planned deliveries every `interval_days`, each topping the tank up to capacity.
    `delays` maps a planned delivery time to a delay in days (stress tests)."""
    capacity_l: float
    interval_days: float
    first: pd.Timestamp
    delays: dict = field(default_factory=dict)

    def planned(self, t0, t1) -> list:
        out, k = [], 0
        step = pd.Timedelta(days=self.interval_days)
        t = self.first
        while t < t1:
            if t >= t0 - pd.Timedelta(days=60):
                out.append(t)
            k += 1
            t = self.first + k * step
        return out

    def actual(self, planned_t):
        return planned_t + pd.Timedelta(days=self.delays.get(planned_t, 0.0))


class FuelTank:
    def __init__(self, sched: FuelSchedule, level_l: float):
        self.s, self.level = sched, float(level_l)
        self.delivered = set()     # planned times already delivered
        self.log = []

    def arrivals(self, t):
        """Deliveries (planned times) that physically arrive at step start t."""
        out = []
        for pt in self.s.planned(t - pd.Timedelta(days=60), t + pd.Timedelta(hours=1)):
            if pt in self.delivered:
                continue
            at = self.s.actual(pt)
            if at <= t:
                out.append(pt)
        return out

    def receive(self, t):
        for pt in self.arrivals(t):
            self.delivered.add(pt)
            self.log.append((t, pt, self.s.capacity_l - self.level))
            self.level = self.s.capacity_l

    def arrival_scenarios(self, t, horizon_end, delays, weights, fallback_days: float) -> list:
        """Belief about future deliveries: [(weight, sorted arrival times), ...].

        Planned deliveries not yet due are taken as on time. An overdue delivery
        (planned time passed, not arrived) arrives at planned + d for each delay
        scenario d; scenarios already in the past are dropped and the weights
        renormalised. If none is left, it arrives `fallback_days` from now.
        """
        on_time, overdue = [], []
        for pt in self.s.planned(t - pd.Timedelta(days=60), horizon_end + pd.Timedelta(days=self.s.interval_days)):
            if pt in self.delivered:
                continue
            (on_time if pt > t else overdue).append(pt)
        if not overdue:
            return [(1.0, sorted(on_time))]
        scen = []
        for d, w in zip(delays, weights):
            arr = [pt + pd.Timedelta(days=d) for pt in overdue]
            if all(a > t for a in arr) and w > 0:
                scen.append((w, sorted(on_time + arr)))
        if not scen:
            return [(1.0, sorted(on_time + [t + pd.Timedelta(days=fallback_days)] * len(overdue)))]
        tot = sum(w for w, _ in scen)
        return [(w / tot, a) for w, a in scen]


def unit_range(p, n):
    return n * p.unit_kw * p.min_load_frac, n * p.unit_kw


def max_units_for_fuel(p, tank_l, n_req):
    """Most units (<= n_req) whose minimum-load fuel fits in the tank this hour."""
    n = n_req
    while n > 0 and p.fuel_l(n, unit_range(p, n)[0]) > tank_l + EPS:
        n -= 1
    return n


def diesel_cap_for_fuel(p, n, tank_l):
    """Highest diesel output of n committed units that the tank can fuel for one hour."""
    if n == 0:
        return 0.0
    return min(n * p.unit_kw, max((tank_l - p.fuel_a * p.unit_kw * n) / p.fuel_b, 0.0))


def _dispatch(p, n, pd0, solar, load, dis_max, ch_max, tank_l):
    """Best use of n committed units: diesel near its set point, battery absorbs the rest."""
    if n == 0:
        lo = hi = 0.0
    else:
        lo, hi = unit_range(p, n)
        hi = min(hi, diesel_cap_for_fuel(p, n, tank_l))
    pd_ = float(np.clip(pd0, lo, hi))
    r = load - solar - pd_
    if r > dis_max:
        pd_ = min(hi, pd_ + r - dis_max)
    elif r < -ch_max:
        pd_ = max(lo, pd_ - (-r - ch_max))
    r = load - solar - pd_
    dis = ch = curt = short = over = 0.0
    if r >= 0:
        dis = min(r, dis_max)
        short = r - dis
    else:
        ch = min(-r, ch_max)
        excess = -r - ch
        curt = min(excess, solar)
        over = excess - curt          # diesel minimum load that cannot be absorbed
    return pd_, dis, ch, curt, short, over


def step(p, soc: float, tank_l: float, solar: float, crit: float, flex: float, dec: Decision,
         has_battery: bool = True) -> dict:
    E = p.bat_kwh if has_battery else 0.0
    dis_max = min(p.bat_kw, max(soc - p.soc_min, 0) * E * p.eta) if E > 0 else 0.0
    ch_max = min(p.bat_kw, max(p.soc_max - soc, 0) * E / p.eta) if E > 0 else 0.0

    def balance(load):
        n = max_units_for_fuel(p, tank_l, int(np.clip(dec.n_on, 0, p.n_units)))
        res = _dispatch(p, n, dec.p_diesel, solar, load, dis_max, ch_max, tank_l)
        while res[4] > EPS and n < p.n_units and max_units_for_fuel(p, tank_l, n + 1) == n + 1:
            n += 1                                 # start another unit
            res = _dispatch(p, n, dec.p_diesel, solar, load, dis_max, ch_max, tank_l)
        while res[5] > EPS and n > 0:
            n -= 1                                 # stop a unit that cannot be loaded
            res = _dispatch(p, n, dec.p_diesel, solar, load, dis_max, ch_max, tank_l)
        return n, res

    B = int(getattr(p, "n_flex_blocks", 0) or 0)
    if B <= 0 or flex <= EPS:
        # model v1: flexible load shed by the exact kW
        shed = min(max(dec.shed_flex, 0.0), flex)
        n, res = balance(crit + flex - shed)
        pd_, dis, ch, curt, short, _ = res
        s2 = min(short, flex - shed)               # flexible first
        shed += s2
        unserved = short - s2                      # critical only as a last resort
    else:
        # model v2: whole feeder blocks; the planned cut is rounded up, the emergency
        # cut adds blocks until the shortfall is covered. With crit_shared_frac > 0 the
        # last block also carries that share of the critical load (stress test).
        blk = flex / B
        k = min(B, int(np.ceil(max(dec.shed_flex, 0.0) / blk - 1e-6)))
        fs = float(getattr(p, "crit_shared_frac", 0.0) or 0.0)
        while True:
            lost_crit = crit * fs if (k == B and fs > 0) else 0.0
            n, res = balance(crit - lost_crit + flex - k * blk)
            short = res[4]
            if short <= EPS or k == B:
                break
            k = min(B, k + max(1, int(np.ceil(short / blk - 1e-9))))
        pd_, dis, ch, curt, short, _ = res
        shed = k * blk
        unserved = lost_crit + short               # after every block is cut
    if n == 0:
        pd_ = 0.0

    flex_served = flex - shed
    crit_served = crit - unserved
    pv_used = solar - curt
    fuel = p.fuel_l(n, pd_) if n else 0.0
    soc_new = soc + (ch * p.eta - dis / p.eta) / E if E > 0 else 0.0
    resid = pv_used + pd_ + dis - ch - crit_served - flex_served
    return dict(solar=solar, pv_used=pv_used, curtail=curt, diesel=pd_, n_on=n, fuel_l=fuel,
                charge=ch, discharge=dis, soc_start=soc, soc_end=soc_new,
                crit=crit, flex=flex, shed=shed, unserved_crit=unserved,
                tank_start=tank_l, tank_end=tank_l - fuel, balance_resid=resid)
