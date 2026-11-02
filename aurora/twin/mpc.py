"""AURORA MILP for one rolling-horizon step (PuLP + HiGHS).

Hourly steps t = 0..H-1 on the P50 forecast. Decision variables per step:
diesel power P_d, committed units n (integer 0..N), starts s, battery charge
P_c and discharge P_x with a binary y (no simultaneous charge and discharge),
curtailment P_cur, flexible shedding L_shed; states battery energy e and fuel
level V at step boundaries.

    min  sum_t [ c_f F_t + c_deg (P_c + P_x) + c_shed L_shed + c_st s_t ]
         + c_risk / H * sum_t (1/Q) sum_q z_qt  +  c_sc w  -  v_e e_H

    s.t. PV_t - P_cur + P_d + P_x - P_c = D_crit + D_flex - L_shed   (critical never shed)
         e_{t+1} = e_t + eta P_c - P_x / eta,   E soc_min <= e <= E soc_max
         n_t P_u m <= P_d <= n_t P_u,   s_t >= n_t - n_{t-1}
         F_t = a P_u n_t + b P_d,   V_{t+1} = V_t - F_t (V reset to capacity at an
         expected delivery),   V >= 0
         z_qt >= N_qt - (e_t - E soc_cest),  z >= 0            (risk, Monte Carlo)
         w >= C_need - V_H / sfc_min - (e_H - E soc_cest), w >= 0 (fuel autonomy)

c_f is diesel price plus CO2 shadow cost per litre. N_qt is the energy needed
above the CEST reserve for the critical load to survive the risk window with
diesel off, in scenario group q (scenarios.survival_need, grouped into Q equal
quantile bins). C_need is the critical deficit (P90 critical minus P10 solar,
last forecast day repeated) from the horizon end to the next expected delivery.
v_e values stored energy at the diesel energy it displaces. If the hard model is
infeasible (fuel or battery physically cannot carry critical load), a relaxed
model with critical slack at 1e5 PHP/kWh is solved and flagged.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pulp

CRIT_SLACK_PHP = 1e5


def _var(m, name, lo=None, hi=None, cat="Continuous"):
    """Model-attached variable (PuLP 3.3 forward API), plain LpVariable on older PuLP."""
    if hasattr(m, "add_variable"):
        return m.add_variable(name, lo, hi, cat=cat)
    return pulp.LpVariable(name, lo, hi, cat)


@dataclass
class MPCInput:
    solar: np.ndarray           # P50 (H,)
    crit: np.ndarray
    flex: np.ndarray
    e0: float                   # battery energy now (kWh)
    n_prev: int                 # units on in the previous step
    tank0: float                # fuel now (L)
    delivery_steps: list        # steps at whose start the tank is refilled
    need_q: np.ndarray | None   # (Q, H) survival need per scenario group
    crit_need_after: float      # kWh of critical deficit after the horizon until next delivery


def solve(inp: MPCInput, p, time_limit: float = 10.0, relax_critical: bool = False,
          exclusive_battery: bool = False):
    H = len(inp.solar)
    E = p.bat_kwh
    m = pulp.LpProblem("aurora", pulp.LpMinimize)
    T = range(H)
    pd_ = [_var(m, f"pd{t}", 0, p.n_units * p.unit_kw) for t in T]
    n = [_var(m, f"n{t}", 0, p.n_units, cat="Integer") for t in T]
    st = [_var(m, f"s{t}", 0) for t in T]
    pc = [_var(m, f"pc{t}", 0, p.bat_kw) for t in T]
    px = [_var(m, f"px{t}", 0, p.bat_kw) for t in T]
    cu = [_var(m, f"cu{t}", 0, max(float(inp.solar[t]), 0.0)) for t in T]
    sh = [_var(m, f"sh{t}", 0, max(float(inp.flex[t]), 0.0)) for t in T]
    e = [None] + [_var(m, f"e{t}", E * p.soc_min, E * p.soc_max) for t in range(1, H + 1)]
    V = [None] + [_var(m, f"V{t}", 0, max(p.tank_l, inp.tank0)) for t in range(1, H + 1)]
    uc = [_var(m, f"uc{t}", 0, float(inp.crit[t])) for t in T] if relax_critical else None

    cf = p.fuel_cost_per_l
    fuel = [p.fuel_a * p.unit_kw * n[t] + p.fuel_b * pd_[t] for t in T]
    obj = []
    e_prev = inp.e0
    v_prev = inp.tank0
    n_prev = inp.n_prev
    deliveries = set(inp.delivery_steps)
    for t in T:
        lhs = float(inp.solar[t]) - cu[t] + pd_[t] + px[t] - pc[t]
        rhs = float(inp.crit[t]) + float(inp.flex[t]) - sh[t]
        if relax_critical:
            rhs = rhs - uc[t]
        m += lhs == rhs, f"bal{t}"
        m += e[t + 1] == e_prev + p.eta * pc[t] - (1.0 / p.eta) * px[t], f"soc{t}"
        m += pd_[t] >= p.min_load_frac * p.unit_kw * n[t], f"dmin{t}"
        m += pd_[t] <= p.unit_kw * n[t], f"dmax{t}"
        m += st[t] >= n[t] - n_prev, f"start{t}"
        v_start = p.tank_l if t in deliveries else v_prev
        m += V[t + 1] == v_start - fuel[t], f"tank{t}"
        if exclusive_battery and E > 0:
            y = _var(m, f"y{t}", cat="Binary")
            m += pc[t] <= p.bat_kw * y, f"chy{t}"
            m += px[t] <= p.bat_kw * (1 - y), f"dsy{t}"
        if E <= 0:
            m += pc[t] == 0
            m += px[t] == 0
        obj += [cf * fuel[t], p.deg_php_per_kwh * (pc[t] + px[t]), p.voll_flex * sh[t],
                p.start_cost_php * st[t]]
        if relax_critical:
            obj.append(CRIT_SLACK_PHP * uc[t])
        e_prev, v_prev, n_prev = e[t + 1], V[t + 1], n[t]

    floor = E * p.soc_cest
    if inp.need_q is not None and E > 0 and p.risk_php_per_kwh > 0:
        Qn = inp.need_q.shape[0]
        w_r = p.risk_php_per_kwh / (H * Qn)
        for t in range(1, H):        # e[t] is the energy at the start of step t
            for q in range(Qn):
                need = float(inp.need_q[q, t])
                if need <= 0:
                    continue
                z = _var(m, f"z{q}_{t}", 0)
                m += z >= need - (e[t] - floor), f"risk{q}_{t}"
                obj.append(w_r * z)
    if inp.crit_need_after > 0 and p.scarcity_php_per_kwh > 0:
        w = _var(m, "w", 0)
        m += w >= inp.crit_need_after - (1.0 / p.sfc_min_load) * V[H] - (e[H] - floor), "autonomy"
        obj.append(p.scarcity_php_per_kwh * w)
    v_e = 0.9 * p.eta * p.fuel_b * cf      # value of stored energy left at the horizon end
    if E > 0:
        obj.append(-v_e * e[H])
    m += pulp.lpSum(obj)

    solver = pulp.HiGHS(msg=False, timeLimit=time_limit, gapRel=5e-3)
    status = m.solve(solver)
    ok = pulp.LpStatus[status] == "Optimal"
    if not ok:
        if not relax_critical:
            return solve(inp, p, time_limit, relax_critical=True, exclusive_battery=exclusive_battery)
        raise RuntimeError(f"MPC failed: {pulp.LpStatus[status]}")
    val = lambda xs: np.array([x.value() or 0.0 for x in xs])  # noqa: E731
    plan = dict(p_diesel=val(pd_), n_on=np.rint(val(n)).astype(int), charge=val(pc), discharge=val(px),
                curtail=val(cu), shed=val(sh), energy=np.r_[inp.e0, val(e[1:])], tank=np.r_[inp.tank0, val(V[1:])],
                unserved=val(uc) if relax_critical else np.zeros(H),
                objective=pulp.value(m.objective), relaxed=relax_critical)
    return plan
