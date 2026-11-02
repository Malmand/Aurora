"""Rolling-origin backtest of the solar forecast (expanding window, monthly refit).

For every test month M the models are trained on target hours before
M - 3 days (so every training truth was known before the first issue time
that covers M) and predict all hours of M for lead days 1 and 2.

Two input regimes:
* ``full``: at least one NWP model with GHI at that lead day (from Feb 2024).
  Trained on full-regime rows only.
* ``reduced``: no NWP GHI (2022-2023 and gaps). JMA cloud, humidity, rain,
  pressure and wind plus persistence and sun geometry. Trained on all rows.
  The 2022 months have no earlier data to train on; they are predicted by a
  model trained on 2023 (regime ``reduced_reverse``). That is out of sample
  but not causal in calendar time, and is flagged.

Conformal pool: out-of-sample scores of earlier folds, same regime and lead
day, from the 365 days before the cutoff. Rows without a big enough pool keep
their raw quantiles and get ``calibrated = False``.
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd

from aurora.data import paths, rawio

from . import baselines, quantile as Qm
from .features import (GHI_MODELS, LEAD_DAYS, QUANTILES, lead_features, load_nwp, load_truth,
                       mslp_climatology, target_frame)
from .geometry import K_MAX

FIRST_TEST = pd.Timestamp("2023-01-01", tz="UTC")
NWP_START = pd.Timestamp("2022-01-01", tz="UTC")
EVAL_START = pd.Timestamp("2024-11-01", tz="UTC")   # first month with >= 9 months of full-regime training
CUTOFF_GAP = pd.Timedelta(days=3)
POOL_DAYS = 365
MIN_FULL_TRAIN = 2000
QC = Qm.qcols()


def full_feature_cols(X: pd.DataFrame) -> list[str]:
    return list(X.columns)


def reduced_feature_cols(X: pd.DataFrame) -> list[str]:
    keep = ["hour_local", "doy_sin", "doy_cos", "cos_zenith", "ghi_clear", "k_persist", "k_prevday_mean"]
    return keep + [c for c in X.columns if c.endswith("_jma")]


def build_tables():
    base = load_truth()
    nwp = load_nwp()
    if not nwp:
        raise FileNotFoundError("no previous_runs_*.parquet in raw_small/")
    clim = mslp_climatology(base)
    b = base.loc[NWP_START:]
    tabs = {}
    for ld in LEAD_DAYS:
        X = lead_features(b, nwp, ld, clim)
        T = target_frame(b, X, ld)
        tabs[ld] = (X, T)
    return base, nwp, tabs


def _train_mask(T, cutoff, start=None):
    m = T["daylight"] & T["k_true"].notna() & (T.index < cutoff)
    if start is not None:
        m &= T.index >= start
    return m


def _calibrate_rows(Q, T_rows, pool: pd.DataFrame, regime: str, ld: int, cutoff):
    if pool.empty:
        return Q, np.zeros(len(Q), bool)
    p = pool[(pool["regime"].str.startswith(regime.split("_")[0])) & (pool["lead_day"] == ld)
             & (pool.index < cutoff) & (pool.index >= cutoff - pd.Timedelta(days=POOL_DAYS))]
    if len(p) < Qm.MIN_GROUP:
        return Q, np.zeros(len(Q), bool)
    scores = p["k_true"].to_numpy()[:, None] - p[[f"raw_{c}" for c in QC]].to_numpy()
    groups = pd.DataFrame({"lead_day": ld, "season": T_rows["season"].to_numpy()})
    return Qm.calibrate(Q, groups, scores, p[["lead_day", "season"]].reset_index(drop=True),
                        lo=0.0, hi=K_MAX)


def _predict_block(models, X, T, rows, cols, regime, ld, pool, cutoff):
    Xr = X.loc[rows, cols]
    Q = Qm.predict(models, Xr, 0.0, K_MAX)
    Qc, ok = _calibrate_rows(Q, T.loc[rows], pool, regime, ld, cutoff)
    out = pd.DataFrame(Q, index=rows, columns=[f"raw_{c}" for c in QC])
    out[QC] = Qc
    out["calibrated"] = ok
    out["regime"] = regime
    return out


def _baselines(base: pd.DataFrame, T: pd.DataFrame, X: pd.DataFrame, rows, cutoff) -> pd.DataFrame:
    hist = base.loc[: cutoff - pd.Timedelta(hours=1)]
    tab = baselines.climatology_table(hist["k_sat"][hist["daylight"]])
    cl = baselines.climatology(tab, rows)
    out = pd.DataFrame(index=rows)
    out["k_clim"] = cl["mean"].to_numpy()
    out[[f"clim_{c}" for c in QC]] = cl[QC].to_numpy()
    out["k_persist"] = X.loc[rows, "k_persist"].to_numpy()
    return out, tab


def _fit_fallback(base, tab, cutoff):
    """Fallback parameters from the reference product, all years before the cutoff."""
    hist = base.loc[: cutoff - pd.Timedelta(hours=1)]
    hist = hist[hist["daylight"]]
    kc = baselines.climatology(tab, hist.index)["mean"]
    frames = []
    for ld in LEAD_DAYS:
        kp = base["k_sat"].shift(24 * ld, freq="h").reindex(hist.index)
        frames.append(pd.DataFrame({"p": kp, "c": kc, "y": hist["k_sat"], "ld": ld, "s": hist["season"]}))
    d = pd.concat(frames)
    return baselines.fit_fallback(d["p"], d["c"], d["y"], d["ld"], d["s"])


def run(verbose=True) -> pd.DataFrame:
    t0 = time.time()
    base, nwp, tabs = build_tables()
    last = min(T.index.max() for _, T in tabs.values())
    months = pd.date_range(FIRST_TEST, last, freq="MS")
    pool = pd.DataFrame()
    pieces = []

    def emit(ld, X, T, rows, cutoff, models_full, models_red, regime_red="reduced"):
        nonlocal pool
        rows_full = rows[T.loc[rows, "has_ghi_nwp"].to_numpy()] if models_full else rows[:0]
        rows_red = rows.difference(rows_full)
        blocks = []
        if len(rows_full):
            blocks.append(_predict_block(models_full, X, T, rows_full, full_feature_cols(X), "full", ld, pool, cutoff))
        if len(rows_red) and models_red:
            blocks.append(_predict_block(models_red, X, T, rows_red, reduced_feature_cols(X), regime_red, ld,
                                         pool, cutoff))
        if not blocks:
            return None
        P = pd.concat(blocks).sort_index()
        bcut = min(cutoff, P.index.min() - CUTOFF_GAP)   # climatology never sees the test period
        bl, tab = _baselines(base, T, X, P.index, bcut)
        par = _fit_fallback(base, tab, bcut)
        fb = baselines.predict_fallback(par, bl["k_persist"], bl["k_clim"], np.full(len(P), ld),
                                        T.loc[P.index, "season"])
        P = P.join(bl)
        P[[f"fb_{c}" for c in QC]] = fb
        P = T.loc[P.index].join(P)
        pool = pd.concat([pool, P[P["daylight"] & P["k_true"].notna()]
                          [["regime", "lead_day", "season", "k_true"] + [f"raw_{c}" for c in QC]]])
        return P

    for M in months:
        cutoff = M - CUTOFF_GAP
        for ld in LEAD_DAYS:
            X, T = tabs[ld]
            rows = T.index[(T.index >= M) & (T.index < M + pd.offsets.MonthBegin(1)) & (T["ghi_clear"] > 0)]
            if not len(rows):
                continue
            need_full = T.loc[rows, "has_ghi_nwp"].any()
            need_red = (~T.loc[rows, "has_ghi_nwp"]).any()
            mf = mr = None
            if need_full:
                tr = _train_mask(T, cutoff) & T["has_ghi_nwp"]
                if tr.sum() >= MIN_FULL_TRAIN:
                    mf = Qm.fit(X.loc[tr, full_feature_cols(X)], T.loc[tr, "k_true"])
                else:
                    need_red = True
            if need_red:
                tr = _train_mask(T, cutoff)
                mr = Qm.fit(X.loc[tr, reduced_feature_cols(X)], T.loc[tr, "k_true"])
            P = emit(ld, X, T, rows, cutoff, mf, mr)
            if P is not None:
                pieces.append(P)
        if verbose:
            print(f"  {M:%Y-%m} done ({time.time() - t0:.0f} s)", flush=True)

    # 2022: reduced model trained on 2023 (out of sample, not causal in time)
    end22 = pd.Timestamp("2023-01-01", tz="UTC")
    for ld in LEAD_DAYS:
        X, T = tabs[ld]
        tr = T["daylight"] & T["k_true"].notna() & (T.index >= end22 + CUTOFF_GAP) & \
            (T.index < pd.Timestamp("2024-01-01", tz="UTC"))
        mr = Qm.fit(X.loc[tr, reduced_feature_cols(X)], T.loc[tr, "k_true"])
        rows = T.index[(T.index < end22) & (T["ghi_clear"] > 0)]
        P = emit(ld, X, T, rows, pd.Timestamp("2024-01-01", tz="UTC"), None, mr, "reduced_reverse")
        pieces.append(P)
    out = pd.concat(pieces).sort_values(["issue_time", "lead_h"])
    out.attrs["runtime_s"] = f"{time.time() - t0:.0f}"
    if verbose:
        print(f"backtest done in {time.time() - t0:.0f} s, {len(out)} rows")
    return out
