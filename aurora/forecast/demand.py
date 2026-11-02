"""Demand forecast: P10/P50/P90 of critical and flexible load, 48 h ahead.

TRAINED ON THE SYNTHETIC PHASE 1 LOAD (data/itbayat/load_synthetic_hourly.parquet).
Its skill says how well the model recovers the synthetic generator, not how
well it would forecast Itbayat. When plant logs exist
(``python -m aurora.data.build_itbayat --load LOG.csv`` writes
load_hourly.parquet) this module trains on them instead, unchanged.

Features: local hour, weekday, day of year, forecast air temperature (mean of
the NWP models at that lead day, and its daily mean over the issue window),
and the load at the same hour on the last observed day (t - 24 h for lead
day 1, t - 48 h for lead day 2). The target is the change from that lagged
value (seasonal-naive residual), which keeps step-shaped schedules such as the
critical load exact. One LightGBM quantile model per component, lead day and
level; split-conformal shift per lead day and season, as for solar.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from aurora.data import paths

from . import quantile as Qm
from .features import ALL_MODELS, LEAD_DAYS, issue_times
from .geometry import season

LEVELS = (0.1, 0.5, 0.9)
COMPONENTS = ("critical", "flex")
PARAMS = dict(num_leaves=15, min_data_in_leaf=50)


def load_series() -> tuple[pd.DataFrame, bool]:
    """Real logs if present, else the synthetic series. Returns (frame, synthetic flag)."""
    if paths.LOAD_REAL.exists():
        return pd.read_parquet(paths.LOAD_REAL), False
    if not paths.LOAD_SYNTH.exists():
        raise FileNotFoundError("no load series; run python -m aurora.data.build_itbayat")
    return pd.read_parquet(paths.LOAD_SYNTH), True


def features(load: pd.DataFrame, nwp: dict, ld: int, index: pd.DatetimeIndex) -> pd.DataFrame:
    X = pd.DataFrame(index=index)
    local = index.tz_convert(paths.LOCAL_TZ)
    X["hour_local"] = local.hour
    X["weekday"] = local.dayofweek
    doy = local.dayofyear.to_numpy()
    X["doy_sin"], X["doy_cos"] = np.sin(2 * np.pi * doy / 365.25), np.cos(2 * np.pi * doy / 365.25)
    temps = [nwp[m][f"temp_c_d{ld}"].reindex(index) for m in ALL_MODELS
             if m in nwp and f"temp_c_d{ld}" in nwp[m]]
    if temps:
        t = pd.concat(temps, axis=1).mean(axis=1)
        X["temp_fc"] = t
        X["temp_fc_daymean"] = t.groupby(issue_times(index, ld)).transform("mean")
    for c in ("critical_kW", "flex_kW", "total_kW"):
        X[f"{c}_lag"] = load[c].shift(24 * ld, freq="h").reindex(index)
    return X


def predict(models, X: pd.DataFrame, lag: pd.Series) -> np.ndarray:
    """Quantiles of load (kW) = lagged load + predicted change, sorted and clipped at 0."""
    R = Qm.predict(models, X, None, None)
    return np.sort(np.clip(R + lag.to_numpy()[:, None], 0, None), axis=1)


def backtest(nwp: dict, months: pd.DatetimeIndex, cutoff_gap=pd.Timedelta(days=3), verbose=True
             ) -> pd.DataFrame:
    load, synthetic = load_series()
    start = max(load.index.min(), min(df.index.min() for df in nwp.values()))
    end = min(load.index.max(), max(df.index.max() for df in nwp.values()))
    idx = pd.date_range(start, end, freq="h")
    tabs = {ld: features(load, nwp, ld, idx) for ld in LEAD_DAYS}
    seas = pd.Series(season(idx), index=idx)
    pieces, pool = [], []
    for M in months:
        cutoff = M - cutoff_gap
        for ld in LEAD_DAYS:
            X = tabs[ld]
            rows = X.index[(X.index >= M) & (X.index < M + pd.offsets.MonthBegin(1))]
            if not len(rows):
                continue
            P = pd.DataFrame(index=rows)
            P["issue_time"] = issue_times(rows, ld)
            P["lead_day"], P["season"] = ld, seas.loc[rows].to_numpy()
            for comp in COMPONENTS:
                y = load[f"{comp}_kW"].reindex(X.index)
                lag = X[f"{comp}_kW_lag"]
                r = y - lag
                tr = (X.index < cutoff) & r.notna().to_numpy()
                models = Qm.fit(X[tr], r[tr], LEVELS, PARAMS, 200)
                Q = predict(models, X.loc[rows], lag.loc[rows])
                cols = [f"{comp}_raw_p{round(100 * t)}" for t in LEVELS]
                P[cols] = Q
                P[f"{comp}_true"] = y.loc[rows].to_numpy()
                P[f"{comp}_naive"] = lag.loc[rows].to_numpy()   # seasonal-naive baseline
                pl = pd.concat(pool) if pool else pd.DataFrame()
                Qc, ok = Q, np.zeros(len(Q), bool)
                if len(pl):
                    pl = pl[(pl["lead_day"] == ld) & (pl.index < cutoff)
                            & (pl.index >= cutoff - pd.Timedelta(days=365))].dropna(subset=[f"{comp}_true"])
                    if len(pl) >= Qm.MIN_GROUP:
                        sc = pl[f"{comp}_true"].to_numpy()[:, None] - pl[cols].to_numpy()
                        g = pd.DataFrame({"lead_day": ld, "season": P["season"].to_numpy()})
                        Qc, ok = Qm.calibrate(Q, g, sc, pl[["lead_day", "season"]].reset_index(drop=True),
                                              lo=0.0, levels=LEVELS)
                P[[f"{comp}_p{round(100 * t)}" for t in LEVELS]] = Qc
                P[f"{comp}_calibrated"] = ok
            pieces.append(P)
            pool.append(P)
        if verbose:
            print(f"  demand {M:%Y-%m} done", flush=True)
    out = pd.concat(pieces).sort_values(["issue_time"])
    out.attrs["synthetic"] = str(synthetic)
    return out
