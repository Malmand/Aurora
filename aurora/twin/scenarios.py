"""Monte Carlo scenarios from P10/P50/P90 and the critical-shortfall risk R(t).

CDF: piecewise linear through (0.1, P10), (0.5, P50), (0.9, P90), extended to
u = 0 and u = 1 with the slope of the nearest segment, clipped to [lo, hi].
Hours are tied together with a Gaussian copula with AR(1) correlation `rho`
(one draw per scenario and hour), so a cloudy morning tends to stay cloudy.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import norm

U_KNOTS = np.array([0.0, 0.1, 0.5, 0.9, 1.0])


def inverse_cdf(u: np.ndarray, q10, q50, q90, lo=0.0, hi=np.inf) -> np.ndarray:
    """u: (S, H) uniforms; q*: (H,) quantiles. Returns (S, H) values."""
    q = np.sort(np.vstack([q10, q50, q90]).astype(float), axis=0)
    s1 = (q[1] - q[0]) / 0.4
    s2 = (q[2] - q[1]) / 0.4
    knots = np.vstack([q[0] - 0.1 * s1, q[0], q[1], q[2], q[2] + 0.1 * s2])  # (5, H)
    k = np.clip(np.searchsorted(U_KNOTS, u, side="right") - 1, 0, 3)
    u0, u1 = U_KNOTS[k], U_KNOTS[k + 1]
    cols = np.arange(u.shape[1])[None, :]
    v0, v1 = knots[k, cols], knots[k + 1, cols]
    x = v0 + (u - u0) / (u1 - u0) * (v1 - v0)
    return np.clip(x, lo, hi)


def correlated_uniforms(n_scen: int, horizon: int, rho: float, rng) -> np.ndarray:
    z = np.empty((n_scen, horizon))
    z[:, 0] = rng.standard_normal(n_scen)
    e = rng.standard_normal((n_scen, horizon))
    a = np.sqrt(1 - rho ** 2)
    for h in range(1, horizon):
        z[:, h] = rho * z[:, h - 1] + a * e[:, h]
    return norm.cdf(z)


def draw(fc, n_scen: int, rng, pv_cap: float, rho_solar=0.9, rho_load=0.95):
    """Scenario arrays (S, H) of solar and critical demand from a forecast frame."""
    H = len(fc)
    us = correlated_uniforms(n_scen, H, rho_solar, rng)
    ul = correlated_uniforms(n_scen, H, rho_load, rng)
    sol = inverse_cdf(us, fc["solar_kW_p10"], fc["solar_kW_p50"], fc["solar_kW_p90"], 0.0, pv_cap)
    crit = inverse_cdf(ul, fc["demand_critical_kW_p10"], fc["demand_critical_kW_p50"],
                       fc["demand_critical_kW_p90"], 0.0)
    return sol, crit


def survival_need(sol: np.ndarray, crit: np.ndarray, p, window: int, big: float = 1e6) -> np.ndarray:
    """Battery energy above the CEST reserve needed at the start of each step so that,
    with diesel off and flexible load off, critical load is served for `window` hours
    (or to the end of the forecast). Backward recursion per start step:

        need_k = max(0, d_k + need_{k+1}),  d_k = deficit/eta  or  -min(surplus, P_bat)*eta

    A deficit above the battery power limit cannot be met at all (need = big).
    Storage capacity is not binding in the recursion (upper bound on survival).
    Returns (S, H)."""
    S, H = sol.shape
    net = sol - crit
    d = np.where(net < 0, -net / p.eta, -np.minimum(net, p.bat_kw) * p.eta)
    d = np.where(-net > p.bat_kw + 1e-9, big, d)
    need = np.zeros((S, H))
    for t in range(H):
        end = min(H, t + window)
        acc = np.zeros(S)
        for k in range(end - 1, t - 1, -1):
            acc = np.maximum(0.0, d[:, k] + acc)
        need[:, t] = acc
    return need


def risk_now(need0: np.ndarray, soc: float, p) -> float:
    """R(t): share of scenarios in which battery above the reserve cannot carry
    critical load through the window if diesel stopped now."""
    have = max(soc - p.soc_cest, 0.0) * p.bat_kwh
    return float(np.mean(need0 > have + 1e-9))
