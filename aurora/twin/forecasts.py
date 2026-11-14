"""Forecast providers for the twin.

Every provider returns, for an issue time t (start of the first step), a frame
indexed by step start t, t+1h, ..., t+(H-1)h with the Phase 2 schema:

    solar_kW_p10, solar_kW_p50, solar_kW_p90,
    demand_critical_kW_p10, _p50, _p90, demand_flex_kW_p10, _p50, _p90, fallback

Providers:
  PerfectForecast      oracle: truth, zero spread (value-of-forecast upper bound)
  PersistenceForecast  twin baseline: daily smart persistence of the clear-sky index,
                       bands from the last 30 days; load persistence. Stand-in until
                       the Phase 2 forecast exists. Uses only data before t.
  CSVForecast          Phase 2 output files (one CSV per issue time); falls back to
                       PersistenceForecast with widened bands and fallback=True
                       when no issue covers t.
  Phase2Forecast       the Phase 2 backtest in data/itbayat/forecast/ (every daily
                       issue, 2022 to Oct 2026), read directly; solar scaled to the
                       run's array. Variants: AURORA bands, raw NWP mean, persistence.
Every provider also has issue_end(t): the end of the newest forecast issued at
or before t (exclusive). The twin sets the MPC horizon to issue_end(t) - t, so a
plan never runs past the issued forecast into the persistence fallback tail
(simulate.plan_horizon). Phase 2 issues are daily at 00:00 PHT (16:00 UTC), 48 h
long, so the horizon runs from 48 h down to 25 h. Perfect and persistence have no
issue cycle of their own; they use the same daily cycle so that value-of-forecast
runs differ only in the forecast, not in the horizon.
The CSV loader is ported from digital_twin/forecast_io.py (team repo, Mohamed):
time column names, time zones, _p10/_p90 or _low/_high band names.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

Q = ("p10", "p50", "p90")
BASES = ("solar_kW", "demand_critical_kW", "demand_flex_kW")
COLS = [f"{b}_{q}" for b in BASES for q in Q]
TIME_COLS = ["timestamp", "time", "datetime", "date"]
BAND_ALIASES = {"p10": ["_p10", "_q10", "_low"], "p50": ["_p50", "_q50", ""], "p90": ["_p90", "_q90", "_high"]}


ISSUE_HOUR_UTC = 16     # Phase 2 issue time, 00:00 PHT
ISSUE_LEN_H = 48        # Phase 2 issue length
STEP = pd.Timedelta(hours=1)


def daily_issue_end(t, hour_utc: int = ISSUE_HOUR_UTC, length_h: int = ISSUE_LEN_H) -> pd.Timestamp:
    """End of the newest daily issue (at hour_utc, length_h long) at or before t."""
    t = pd.Timestamp(t)
    it = t.normalize() + pd.Timedelta(hours=hour_utc)
    if it > t:
        it -= pd.Timedelta(days=1)
    return it + pd.Timedelta(hours=length_h)


def monotone(fc: pd.DataFrame) -> pd.DataFrame:
    """Sort P10 <= P50 <= P90 per row and clip at zero (fixes quantile crossing)."""
    for b in BASES:
        c = [f"{b}_{q}" for q in Q]
        fc[c] = np.sort(np.clip(fc[c].to_numpy(float), 0, None), axis=1)
    return fc


class PerfectForecast:
    name = "perfect"
    issue_end = staticmethod(daily_issue_end)

    def __init__(self, truth: pd.DataFrame, pv_kwp: float):
        self.t, self.kwp = truth, pv_kwp

    def __call__(self, t, horizon: int) -> pd.DataFrame:
        i = self.t.index.get_loc(t)
        w = self.t.iloc[i:i + horizon]
        out = pd.DataFrame(index=w.index)
        for q in Q:
            out[f"solar_kW_{q}"] = w["pv_kw_per_kwp"].to_numpy() * self.kwp
            out[f"demand_critical_kW_{q}"] = w["crit_kW"].to_numpy()
            out[f"demand_flex_kW_{q}"] = w["flex_kW"].to_numpy()
        out["fallback"] = False
        return out


class PersistenceForecast:
    """Daily smart persistence of the clear-sky index with empirical bands.

    k = PV(last 24 h) / clear-sky PV(last 24 h). P50 = clear-sky PV x k.
    P10/P90 = clear-sky PV x the 10th/90th percentile of daily k over the last
    30 days, widened by `widen` (used for the comms-down fallback). Demand: the
    same hour on the last observed day; critical +-2 %, flexible +-10 %.
    """
    name = "persistence"
    issue_end = staticmethod(daily_issue_end)

    def __init__(self, truth: pd.DataFrame, pv_kwp: float, widen: float = 1.0, fallback: bool = False):
        self.t, self.kwp, self.widen, self.fb = truth, pv_kwp, widen, fallback
        pv, cs = truth["pv_kw_per_kwp"], truth["pv_clear_kw_per_kwp"]
        k24 = (pv.rolling(24, min_periods=12).sum() / cs.rolling(24, min_periods=12).sum()).clip(0, 1.2)
        kd = (pv.resample("D").sum() / cs.resample("D").sum()).clip(0, 1.2)
        # quantiles of the 30 complete days before each day, mapped back to hours
        q10 = kd.rolling(30, min_periods=5).quantile(0.1).shift(1)
        q90 = kd.rolling(30, min_periods=5).quantile(0.9).shift(1)
        day = truth.index.floor("D")
        self.k = np.nan_to_num(k24.to_numpy(), nan=0.7)
        self.k10 = np.nan_to_num(q10.reindex(day).to_numpy(), nan=0.3)
        self.k90 = np.nan_to_num(q90.reindex(day).to_numpy(), nan=1.0)
        self.cs = cs.to_numpy() * pv_kwp
        self.load = truth[["crit_kW", "flex_kW"]].to_numpy()

    def __call__(self, t, horizon: int) -> pd.DataFrame:
        i = self.t.index.get_loc(t)
        idx = pd.date_range(t, periods=horizon, freq="h")
        n = len(self.cs)
        j = np.arange(i, i + horizon)
        cs = np.where(j < n, self.cs[np.minimum(j, n - 1)], 0.0)
        if i == 0:
            k, k10, k90 = 0.7, 0.3, 1.0
        else:
            k, k10, k90 = self.k[i - 1], self.k10[i - 1], self.k90[i - 1]
        k10, k90 = min(k10, k), max(k90, k)
        k10 = max(k - (k - k10) * self.widen, 0.0)
        k90 = k + (k90 - k) * self.widen
        # same hour on the last observed day (series start: first day)
        src = (i - 24 + np.arange(horizon) % 24) if i >= 24 else (np.arange(horizon) % 24)
        d = self.load[src]
        wc, wf = 0.02 * self.widen, 0.10 * self.widen
        out = pd.DataFrame({
            "solar_kW_p10": cs * k10, "solar_kW_p50": cs * k, "solar_kW_p90": cs * k90,
            "demand_critical_kW_p10": d[:, 0] * (1 - wc), "demand_critical_kW_p50": d[:, 0],
            "demand_critical_kW_p90": d[:, 0] * (1 + wc),
            "demand_flex_kW_p10": d[:, 1] * (1 - wf), "demand_flex_kW_p50": d[:, 1],
            "demand_flex_kW_p90": d[:, 1] * (1 + wf)}, index=idx)
        out["fallback"] = self.fb
        return monotone(out)


def _first(cols, options):
    low = {c.lower(): c for c in cols}
    for o in options:
        if o.lower() in low:
            return low[o.lower()]
    return None


def read_forecast_csv(path) -> pd.DataFrame:
    """One Phase 2 forecast file -> frame indexed by step start (UTC), schema COLS + fallback.

    Accepts P10/P50/P90 named _p10/_q10/_low, _p50/_q50/(none), _p90/_q90/_high.
    Timestamps without a zone are taken as UTC. A file whose rows are labelled at
    the end of the hour must say so with a column `time_label` = "end".
    """
    df = pd.read_csv(path)
    tcol = _first(df.columns, TIME_COLS)
    if tcol is None:
        raise ValueError(f"{path}: no time column, expected one of {TIME_COLS}")
    t = pd.to_datetime(df[tcol], utc=True)
    if "time_label" in df.columns and str(df["time_label"].iloc[0]).lower() == "end":
        t = t - pd.Timedelta(hours=1)
    out = pd.DataFrame(index=pd.DatetimeIndex(t, name="timestamp"))
    for b in BASES:
        for q in Q:
            c = _first(df.columns, [b + s for s in BAND_ALIASES[q]])
            if c is None:
                raise ValueError(f"{path}: no column for {b} {q}")
            out[f"{b}_{q}"] = df[c].to_numpy(float)
    out["fallback"] = df["fallback"].astype(bool).to_numpy() if "fallback" in df else False
    if "issue_time" in df:
        out.attrs["issue_time"] = pd.Timestamp(pd.to_datetime(df["issue_time"].iloc[0], utc=True))
    out = out[~out.index.duplicated()].sort_index()
    gaps = out.index.to_series().diff().dropna()
    if (gaps != pd.Timedelta("1h")).any():
        out = out.resample("h").mean().interpolate(limit=3)
        out["fallback"] = out["fallback"].fillna(1).astype(bool)
    return monotone(out)


class CSVForecast:
    """Phase 2 forecasts from a directory of CSVs (one per issue time).

    At step t the newest issue with issue_time <= t is used. If it does not cover
    t..t+H-1, the missing tail (or the whole window) comes from the persistence
    fallback with bands widened 1.5x and fallback=True.
    """
    name = "csv"

    def __init__(self, folder, truth: pd.DataFrame, pv_kwp: float, scale_kwp: float | None = None):
        files = sorted(Path(folder).glob("*.csv"))
        if not files:
            raise FileNotFoundError(f"no forecast CSVs in {folder}")
        self.issues = {}
        for f in files:
            fc = read_forecast_csv(f)
            it = fc.attrs.get("issue_time", fc.index[0])
            self.issues[it] = fc
        self.keys = pd.DatetimeIndex(sorted(self.issues))
        # forecasts in kW for scale_kwp; rescale solar to this run's array
        self.solar_scale = pv_kwp / scale_kwp if scale_kwp else 1.0
        self.fb = PersistenceForecast(truth, pv_kwp, widen=1.5, fallback=True)

    def issue_end(self, t):
        """End of the newest issue at or before t (None if there is none)."""
        j = self.keys.searchsorted(t, side="right") - 1
        return None if j < 0 else self.issues[self.keys[j]].index[-1] + STEP

    def __call__(self, t, horizon: int) -> pd.DataFrame:
        idx = pd.date_range(t, periods=horizon, freq="h")
        fb = self.fb(t, horizon)
        j = self.keys.searchsorted(t, side="right") - 1
        if j < 0:
            return fb
        fc = self.issues[self.keys[j]].copy()
        for q in Q:
            fc[f"solar_kW_{q}"] *= self.solar_scale
        fc = fc.reindex(idx)
        miss = fc["solar_kW_p50"].isna()
        fc.loc[miss, COLS] = fb.loc[miss, COLS]
        fc["fallback"] = fc["fallback"].where(~miss, True).astype(bool)
        return fc


class Phase2Forecast:
    """Phase 2 forecasts read directly from data/itbayat/forecast/.

    Files: backtest_solar.parquet (PV in kW per kWp DC, so any array size works)
    and backtest_demand.parquet, both written by ``python -m aurora.forecast.build``.
    Their timestamps are hour-ending; here they are shifted to step start.

    At step t the newest daily issue with issue_time <= t is used (issues at
    16:00 UTC = 00:00 PHT, 48 h each). Solar hours inside the issue window but
    absent from the file are night hours (zero). With the default issue-aligned
    horizon the plan ends with the issue. With a fixed 48 h horizon, hours past
    the issue's 48 h (up to 23 h), or with no forecast at all, come from the
    persistence fallback with 1.5x bands and fallback=True, as in
    CSVForecast.

    variant:
      "aurora"       P10/P50/P90 from the AURORA quantile model (default)
      "nwp"          raw NWP mean converted to PV, zero spread
      "persistence"  Phase 2 smart persistence (satellite k) converted to PV, zero spread
    Demand bands are the Phase 2 demand forecast in every variant (SYNTHETIC load
    unless plant logs were used).
    """

    VARIANTS = {"aurora": ("p10", "p50", "p90"), "nwp": ("nwp_mean",) * 3, "persistence": ("persist",) * 3}

    def __init__(self, truth: pd.DataFrame, pv_kwp: float, variant: str = "aurora", folder=None):
        from ..data import paths

        if variant not in self.VARIANTS:
            raise ValueError(f"unknown Phase 2 variant {variant!r}; use one of {sorted(self.VARIANTS)}")
        folder = Path(folder) if folder else paths.SITE_DIR / "forecast"
        sp, dp = folder / "backtest_solar.parquet", folder / "backtest_demand.parquet"
        if not sp.exists() or not dp.exists():
            raise FileNotFoundError(f"{folder}: no Phase 2 backtest; run python -m aurora.forecast.build")
        self.name = "phase2" if variant == "aurora" else f"phase2_{variant}"
        step = pd.Timedelta(hours=1)
        src = self.VARIANTS[variant]
        so = pd.read_parquet(sp, columns=["issue_time"] + sorted({f"pv_kw_per_kwp_{c}" for c in src}))
        so.index = so.index - step
        so = so.set_index("issue_time", append=True)
        sol = pd.DataFrame({f"solar_kW_{q}": so[f"pv_kw_per_kwp_{c}"] * pv_kwp for q, c in zip(Q, src)})
        dm = pd.read_parquet(dp, columns=["issue_time"] + [f"{c}_{q}" for c in ("critical", "flex") for q in Q])
        dm.index = dm.index - step
        dm = dm.set_index("issue_time", append=True)
        dem = pd.DataFrame({f"demand_{c}_kW_{q}": dm[f"{c}_{q}"] for c in ("critical", "flex") for q in Q})
        self.by_issue = {}
        issues = sorted(set(dem.index.get_level_values(1)) | set(sol.index.get_level_values(1)))
        sol_g = dict(tuple(sol.groupby(level=1)))
        dem_g = dict(tuple(dem.groupby(level=1)))
        for it in issues:
            w = pd.date_range(it, periods=48, freq="h")
            s_ = sol_g[it].droplevel(1).reindex(w) if it in sol_g else pd.DataFrame(index=w, columns=sol.columns)
            # night hours are not stored: zero the hours absent from the file, keep real gaps NaN
            if it in sol_g:
                s_.loc[~s_.index.isin(sol_g[it].droplevel(1).index)] = 0.0
            d_ = dem_g[it].droplevel(1).reindex(w) if it in dem_g else pd.DataFrame(index=w, columns=dem.columns)
            self.by_issue[it] = pd.concat([s_, d_], axis=1)[COLS].astype(float)
        self.keys = pd.DatetimeIndex(sorted(self.by_issue))
        self.fb = PersistenceForecast(truth, pv_kwp, widen=1.5, fallback=True)

    def issue_end(self, t):
        """End of the newest daily issue at or before t (issue + 48 h), None if none."""
        j = self.keys.searchsorted(t, side="right") - 1
        return None if j < 0 else self.keys[j] + pd.Timedelta(hours=ISSUE_LEN_H)

    def __call__(self, t, horizon: int) -> pd.DataFrame:
        idx = pd.date_range(t, periods=horizon, freq="h")
        fb = self.fb(t, horizon)
        j = self.keys.searchsorted(t, side="right") - 1
        if j < 0:
            return fb
        fc = self.by_issue[self.keys[j]].reindex(idx)
        miss = fc.isna().any(axis=1)
        fc.loc[miss, COLS] = fb.loc[miss, COLS]
        fc["fallback"] = miss.to_numpy()
        return monotone(fc)


class CriticalBand:
    """Model v2: critical-demand bands that reflect real variability.

    The Phase 2 demand model was trained on the fixed synthetic critical schedule,
    so its critical bands have zero width. Here P10/P90 = P50 x (1 -/+ z sigma),
    z = 1.2816, with sigma the critical-demand variability (site.yaml); bands that
    are already wider are kept."""

    def __init__(self, fc, sigma: float):
        self.fc, self.k = fc, 1.2816 * float(sigma)
        self.name = fc.name
        self.issue_end = getattr(fc, "issue_end", None)

    def __call__(self, t, horizon):
        out = self.fc(t, horizon)
        p50 = out["demand_critical_kW_p50"]
        out["demand_critical_kW_p10"] = np.minimum(out["demand_critical_kW_p10"], p50 * (1 - self.k))
        out["demand_critical_kW_p90"] = np.maximum(out["demand_critical_kW_p90"], p50 * (1 + self.k))
        return out


class ScaledSolarAfter:
    """Stress test: solar bands times `factor` from `t_hit` on (the operator sees the
    damage in the meter readings and the forecast is scaled to match)."""

    def __init__(self, fc, t_hit, factor: float):
        self.fc, self.t_hit, self.k = fc, pd.Timestamp(t_hit), float(factor)
        self.name = fc.name
        self.issue_end = getattr(fc, "issue_end", None)

    def __call__(self, t, horizon):
        out = self.fc(t, horizon)
        hit = out.index >= self.t_hit
        for q in ("p10", "p50", "p90"):
            out.loc[hit, f"solar_kW_{q}"] = out.loc[hit, f"solar_kW_{q}"] * self.k
        return out
