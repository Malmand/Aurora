"""LightGBM quantile regression, split-conformal calibration and scoring rules.

Quantile models: one LightGBM booster per quantile level and lead day
(objective 'quantile'). Crossing quantiles are fixed by sorting each row.

Calibration (split conformal, per quantile level). For level tau the
calibrated quantile is q_tau + c_tau, where c_tau is the finite-sample
corrected tau-quantile of the scores y - q_tau on a calibration set that the
model never saw. Scores are grouped by lead day and season; a group with fewer
than ``MIN_GROUP`` scores falls back to all seasons of that lead day. For the
80 % band this gives P(q10 + c10 <= y <= q90 + c90) of about 0.8 (an
asymmetric conformalised quantile regression), using the split-conformal
argument of Lei et al. (2018), J. Am. Stat. Assoc. 113, 1094-1111,
doi:10.1080/01621459.2017.1307116. Coverage holds if the calibration scores
are exchangeable with the test scores, which a changing climate or archive
only approximates.

Scores: pinball loss per level, CRPS approximated from the 19 levels
0.05..0.95 as 2/K * sum_tau pinball_tau (Gneiting and Raftery 2007,
doi:10.1198/016214506000001437). For a deterministic forecast this reduces
exactly to the MAE, so point baselines are scored on the same scale.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .features import QUANTILES

LGB_PARAMS = dict(learning_rate=0.05, num_leaves=15, min_data_in_leaf=100, bagging_fraction=0.8,
                  bagging_freq=1, feature_fraction=0.7, lambda_l2=1.0, verbose=-1, num_threads=4,
                  seed=2026, deterministic=True, force_row_wise=True)
N_ROUNDS = 250
MIN_GROUP = 150


def qcols(prefix: str = "q", levels=QUANTILES) -> list[str]:
    return [f"{prefix}{round(100 * t):02d}" for t in levels]


def fit(X: pd.DataFrame, y: pd.Series, levels=QUANTILES, params=None, rounds=N_ROUNDS) -> dict:
    import lightgbm as lgb

    p = {**LGB_PARAMS, **(params or {})}
    ds = lgb.Dataset(X, y.to_numpy(), free_raw_data=False)
    return {t: lgb.train({**p, "objective": "quantile", "alpha": float(t)}, ds, rounds) for t in levels}


def predict(models: dict, X: pd.DataFrame, lo=0.0, hi=None) -> np.ndarray:
    Q = np.column_stack([models[t].predict(X) for t in sorted(models)])
    if lo is not None or hi is not None:
        Q = np.clip(Q, lo, hi)
    return np.sort(Q, axis=1)


def _conf_level(tau: float, n: int) -> float:
    """Finite-sample corrected level for the empirical quantile of n scores."""
    if tau >= 0.5:
        return min(1.0, math.ceil((n + 1) * tau) / n)
    return max(0.0, (math.floor((n + 1) * tau) - 1) / n)


def offsets(scores: np.ndarray, levels=QUANTILES) -> np.ndarray:
    """Conformal shifts c_tau from scores y - q_tau (n x K)."""
    n = scores.shape[0]
    return np.array([np.quantile(scores[:, j], _conf_level(t, n)) for j, t in enumerate(levels)])


def calibrate(Q: np.ndarray, groups: pd.DataFrame, pool_scores: np.ndarray, pool_groups: pd.DataFrame,
              keys=("lead_day", "season"), fallback_keys=("lead_day",), keep_median=True,
              lo=0.0, hi=None, levels=QUANTILES) -> tuple[np.ndarray, np.ndarray]:
    """Shift each quantile by its conformal offset for the row's group. Returns (Q_cal, ok flag)."""
    out = Q.copy()
    ok = np.zeros(len(Q), bool)
    levels = tuple(levels)
    j50 = levels.index(0.5) if 0.5 in levels else None
    gkeys = list(keys)
    for gval, rows in groups.groupby(gkeys).groups.items():
        gval = gval if isinstance(gval, tuple) else (gval,)
        sel = np.ones(len(pool_groups), bool)
        for k, v in zip(gkeys, gval):
            sel &= pool_groups[k].to_numpy() == v
        if sel.sum() < MIN_GROUP:
            sel = np.ones(len(pool_groups), bool)
            for k in fallback_keys:
                sel &= pool_groups[k].to_numpy() == gval[gkeys.index(k)]
        if sel.sum() < MIN_GROUP:
            continue
        c = offsets(pool_scores[sel], levels)
        if keep_median and j50 is not None:
            c[j50] = 0.0
        ii = groups.index.get_indexer(rows)
        out[ii] = Q[ii] + c
        ok[ii] = True
    if lo is not None or hi is not None:
        out = np.clip(out, lo, hi)
    return np.sort(out, axis=1), ok


# ---------------------------------------------------------------- scores
def pinball(y: np.ndarray, q: np.ndarray, tau: float) -> np.ndarray:
    d = y - q
    return np.maximum(tau * d, (tau - 1) * d)


def crps_quantiles(y: np.ndarray, Q: np.ndarray, levels=QUANTILES) -> np.ndarray:
    """Per-row CRPS from quantile forecasts (n x K); equals |y - q| when all columns are equal."""
    y = np.asarray(y, float)[:, None]
    return 2.0 / len(levels) * sum(pinball(y[:, 0], Q[:, j], t) for j, t in enumerate(levels))


def crps_ensemble(y: np.ndarray, E: np.ndarray) -> np.ndarray:
    """Exact CRPS of an equally weighted ensemble (n x m), NaN members ignored."""
    y = np.asarray(y, float)
    out = np.full(len(y), np.nan)
    for i in range(len(y)):
        e = E[i][~np.isnan(E[i])]
        if len(e) == 0 or np.isnan(y[i]):
            continue
        out[i] = np.abs(e - y[i]).mean() - 0.5 * np.abs(e[:, None] - e[None, :]).mean()
    return out


def point_scores(y, f) -> dict:
    e = np.asarray(f, float) - np.asarray(y, float)
    return {"n": int(np.isfinite(e).sum()), "MAE": np.nanmean(np.abs(e)),
            "RMSE": float(np.sqrt(np.nanmean(e ** 2))), "bias": np.nanmean(e)}


def band_scores(y, lo, hi) -> dict:
    y, lo, hi = (np.asarray(a, float) for a in (y, lo, hi))
    return {"PICP80": float(np.mean((y >= lo) & (y <= hi))), "width80": float(np.mean(hi - lo))}
