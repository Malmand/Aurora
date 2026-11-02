"""Operational forecast: final models, live NWP input, comms-loss fallback, CSV output.

Output schema (one CSV per issue time, 48 hourly rows, digital-twin schema plus bands):

    issue_time, timestamp, solar_kW_p10, solar_kW_p50, solar_kW_p90,
    demand_critical_kW_p10, demand_critical_kW_p50, demand_critical_kW_p90,
    demand_flex_kW_p10, demand_flex_kW_p50, demand_flex_kW_p90, fallback

Times are UTC ISO 8601; ``timestamp`` is the end of the hour (hour-mean power).

Live mode (``python -m aurora.forecast.issue --live``) requests the latest run
of each NWP model from the Open-Meteo forecast API. If every request fails
(communications are often down in a typhoon), or no model returns GHI for the
window, the solar forecast falls back to climatology-conditioned persistence
with widened bands and ``fallback = True``. Demand then uses climatological
temperature. The models are trained once by ``train_final`` and cached in
``data/itbayat/forecast/models/`` (git-ignored, rebuilt on demand).
"""
from __future__ import annotations

import pickle

import numpy as np
import pandas as pd

from aurora.data import paths, rawio

from . import baselines, demand as D, quantile as Qm
from .backtest import POOL_DAYS, full_feature_cols, reduced_feature_cols
from .features import (ISSUE_HOUR_UTC, LEAD_DAYS, QUANTILES, lead_features, mslp_climatology,
                       target_frame)
from .geometry import K_MAX, clearsky_index, hourly_clearsky, season
from .pv import PV_KWP_INL, pv_ac_per_kwp

FC_DIR = paths.SITE_DIR / "forecast"
MODEL_DIR = FC_DIR / "models"
ISSUE_DIR = FC_DIR / "issues"
SCHEMA = (["issue_time", "timestamp", "solar_kW_p10", "solar_kW_p50", "solar_kW_p90"]
          + [f"demand_{c}_kW_p{p}" for c in D.COMPONENTS for p in (10, 50, 90)] + ["fallback"])
J = {t: QUANTILES.index(t) for t in (0.1, 0.5, 0.9)}
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
SATELLITE_URL = "https://satellite-api.open-meteo.com/v1/archive"


def window(issue_time: pd.Timestamp) -> pd.DatetimeIndex:
    return pd.date_range(issue_time + pd.Timedelta(hours=1), periods=48, freq="h")


def normalise_issue(t) -> pd.Timestamp:
    t = pd.Timestamp(t)
    t = t.tz_localize("UTC") if t.tz is None else t.tz_convert("UTC")
    if t.hour != ISSUE_HOUR_UTC or t.minute:
        raise ValueError(f"issue times are {ISSUE_HOUR_UTC:02d}:00 UTC (00:00 PHT); got {t}")
    return t


# ------------------------------------------------------------- from the backtest
def from_backtest(solar: pd.DataFrame, demand: pd.DataFrame, issue_time, pv_kwp=PV_KWP_INL) -> pd.DataFrame:
    """Forecast CSV rows for one issue time, read from the committed backtest tables."""
    it = normalise_issue(issue_time)
    w = window(it)
    out = pd.DataFrame({"issue_time": it, "timestamp": w})
    s = solar[solar["issue_time"] == it].reindex(w)
    for p in (10, 50, 90):
        out[f"solar_kW_p{p}"] = (s[f"pv_kw_per_kwp_p{p}"].fillna(0.0) * pv_kwp).to_numpy()
    dm = demand[demand["issue_time"] == it].reindex(w)
    for c in D.COMPONENTS:
        for p in (10, 50, 90):
            out[f"demand_{c}_kW_p{p}"] = dm[f"{c}_p{p}"].to_numpy()
    out["fallback"] = False
    return out[SCHEMA]


def write_csv(df: pd.DataFrame, out_dir=ISSUE_DIR, tag="") -> str:
    out_dir.mkdir(parents=True, exist_ok=True)
    it = df["issue_time"].iloc[0]
    path = out_dir / f"forecast_{it:%Y%m%dT%H%MZ}{tag}.csv"
    d = df.copy()
    for c in ("issue_time", "timestamp"):
        d[c] = pd.to_datetime(d[c]).dt.strftime("%Y-%m-%dT%H:%MZ")
    d.round(3).to_csv(path, index=False)
    return str(path)


# ------------------------------------------------------------- final models
def train_final(bt_full: pd.DataFrame, demand_bt: pd.DataFrame, verbose=True) -> dict:
    """Fit solar (full + reduced), demand and fallback on all data; conformal offsets
    from the last POOL_DAYS of backtest out-of-sample scores. Saved to MODEL_DIR."""
    from .backtest import build_tables

    base, nwp, tabs = build_tables()
    bundle = {"solar": {}, "offsets": {}, "demand": {}, "demand_offsets": {}}
    end = bt_full.index.max()
    for ld in LEAD_DAYS:
        X, T = tabs[ld]
        ok = T["daylight"] & T["k_true"].notna()
        for regime, cols, mask in (("full", full_feature_cols(X), ok & T["has_ghi_nwp"]),
                                   ("reduced", reduced_feature_cols(X), ok)):
            bundle["solar"][(regime, ld)] = (cols, Qm.fit(X.loc[mask, cols], T.loc[mask, "k_true"]))
            p = bt_full[(bt_full["regime"].str.startswith(regime)) & (bt_full["lead_day"] == ld)
                        & bt_full["daylight"] & bt_full["k_true"].notna()
                        & (bt_full.index >= end - pd.Timedelta(days=POOL_DAYS))]
            sc = p["k_true"].to_numpy()[:, None] - p[[f"raw_{c}" for c in Qm.qcols()]].to_numpy()
            offs = {}
            for s_ in p["season"].unique():
                sel = (p["season"] == s_).to_numpy()
                if sel.sum() >= Qm.MIN_GROUP:
                    offs[s_] = Qm.offsets(sc[sel])
            if len(p) >= Qm.MIN_GROUP:
                offs["all"] = Qm.offsets(sc)
            for o in offs.values():
                o[QUANTILES.index(0.5)] = 0.0
            bundle["offsets"][(regime, ld)] = offs
        if verbose:
            print(f"  final solar models, lead day {ld}")
    # demand
    load, synthetic = D.load_series()
    idx = pd.date_range(max(load.index.min(), min(df.index.min() for df in nwp.values())),
                        min(load.index.max(), max(df.index.max() for df in nwp.values())), freq="h")
    for ld in LEAD_DAYS:
        Xd = D.features(load, nwp, ld, idx)
        for comp in D.COMPONENTS:
            r = load[f"{comp}_kW"].reindex(idx) - Xd[f"{comp}_kW_lag"]
            m = r.notna().to_numpy()
            bundle["demand"][(comp, ld)] = (list(Xd.columns), Qm.fit(Xd[m], r[m], D.LEVELS, D.PARAMS, 200))
            p = demand_bt[(demand_bt["lead_day"] == ld)
                          & (demand_bt.index >= end - pd.Timedelta(days=POOL_DAYS))].dropna(subset=[f"{comp}_true"])
            sc = p[f"{comp}_true"].to_numpy()[:, None] - p[[f"{comp}_raw_p{round(100 * t)}" for t in D.LEVELS]].to_numpy()
            o = Qm.offsets(sc, D.LEVELS) if len(p) >= Qm.MIN_GROUP else np.zeros(len(D.LEVELS))
            o[D.LEVELS.index(0.5)] = 0.0
            bundle["demand_offsets"][(comp, ld)] = o
    # fallback and climatologies
    hist = base[base["daylight"]]
    tab = baselines.climatology_table(hist["k_sat"])
    kc = baselines.climatology(tab, hist.index)["mean"]
    fr = [pd.DataFrame({"p": base["k_sat"].shift(24 * ld, freq="h").reindex(hist.index), "c": kc,
                        "y": hist["k_sat"], "ld": ld, "s": hist["season"]}) for ld in LEAD_DAYS]
    d = pd.concat(fr)
    bundle["fallback"] = baselines.fit_fallback(d["p"], d["c"], d["y"], d["ld"], d["s"])
    bundle["clim_k"] = tab
    t = base["temp_era5"].dropna()
    bundle["clim_temp"] = t.groupby([t.index.month, t.index.hour]).mean()
    bundle["mslp_clim"] = mslp_climatology(base)
    bundle["trained_until"] = str(end)
    bundle["load_synthetic"] = synthetic
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    with open(MODEL_DIR / "bundle.pkl", "wb") as f:
        pickle.dump(bundle, f)
    (MODEL_DIR / "README.txt").write_text(
        "Cached final models from python -m aurora.forecast.build. Rebuilt on demand; not committed.\n",
        encoding="utf-8")
    return bundle


def load_bundle() -> dict:
    p = MODEL_DIR / "bundle.pkl"
    if not p.exists():
        raise FileNotFoundError("no trained models; run python -m aurora.forecast.build")
    with open(p, "rb") as f:
        return pickle.load(f)


# ------------------------------------------------------------- live input
def fetch_live_nwp(issue_time: pd.Timestamp, timeout=30) -> dict[str, pd.DataFrame]:
    """Latest run of each model, laid out like the previous-runs files (_d1 and _d2 hold
    the same live run, so lead day 1 rows read _d1 and lead day 2 rows read _d2).
    Raises DownloadBlocked if no model can be fetched."""
    from aurora.data.http import DownloadBlocked, get_json

    out, errors = {}, []
    for key, name in rawio.NWP_MODELS.items():
        try:
            js = get_json(FORECAST_URL, dict(latitude=paths.LAT, longitude=paths.LON, models=name,
                                             hourly=",".join(rawio.NWP_OM_VARS), timezone="GMT",
                                             past_days=2, forecast_days=3), timeout=timeout, retries=2)
        except DownloadBlocked as exc:
            errors.append(f"{key}: {exc}")
            continue
        df = rawio.om_hourly_to_frame(js["hourly"])
        df = df.drop(columns=[c for c in df.columns if df[c].isna().all()])
        out[key] = pd.concat({f"{c}_d{ld}": df[c] for c in df.columns for ld in LEAD_DAYS}, axis=1)
    if not out:
        raise DownloadBlocked("; ".join(errors))
    return out


def fetch_recent_satellite(issue_time: pd.Timestamp, timeout=30) -> pd.Series:
    from aurora.data.http import get_json

    a = (issue_time - pd.Timedelta(days=3)).date()
    js = get_json(SATELLITE_URL, dict(latitude=paths.LAT, longitude=paths.LON, start_date=str(a),
                                      end_date=str(issue_time.date()), hourly="shortwave_radiation",
                                      timezone="GMT"), timeout=timeout, retries=2)
    return rawio.om_hourly_to_frame(js["hourly"])["ghi_wm2"]


# ------------------------------------------------------------- one issue
def _apply_offsets(Q, offs, seasons, levels):
    out = Q.copy()
    for i, s in enumerate(seasons):
        o = offs.get(s, offs.get("all")) if isinstance(offs, dict) else offs
        if o is not None:
            out[i] = Q[i] + o
    return np.sort(out, axis=1)


def forecast_issue(issue_time, bundle: dict | None = None, nwp: dict | None = None,
                   ghi_obs: pd.Series | None = None, load_hist: pd.DataFrame | None = None,
                   pv_kwp=PV_KWP_INL) -> pd.DataFrame:
    """48 h forecast for one issue time from given inputs. ``nwp=None`` or no NWP GHI in
    the window -> fallback. ``ghi_obs``: reference GHI up to the issue time (persistence)."""
    it = normalise_issue(issue_time)
    b = bundle or load_bundle()
    w = window(it)
    hist_idx = pd.date_range(it - pd.Timedelta(days=3), w[-1], freq="h")
    base = hourly_clearsky(hist_idx)
    obs = ghi_obs.reindex(hist_idx) if ghi_obs is not None else pd.Series(np.nan, index=hist_idx)
    base["ghi_sat"] = obs.where(hist_idx <= it)
    base["k_sat"] = clearsky_index(base["ghi_sat"], base["ghi_clear"])
    base["season"] = season(hist_idx)
    nwp = nwp or {}
    out = pd.DataFrame({"issue_time": it, "timestamp": w})
    solar = np.zeros((48, 3))
    fallback = False
    for ld in LEAD_DAYS:
        rows = w[(np.arange(48) >= 24 * (ld - 1)) & (np.arange(48) < 24 * ld)]
        Xall = lead_features(base, nwp, ld, b["mslp_clim"])
        X, T = Xall.loc[rows], target_frame(base, Xall, ld).loc[rows]
        has = T["has_ghi_nwp"].to_numpy()
        seas = T["season"].to_numpy()
        day = (T["ghi_clear"] > 0).to_numpy()
        Qk = np.zeros((len(rows), len(QUANTILES)))
        if has[day].any():
            cols, models = b["solar"][("full", ld)]
            Q = Qm.predict(models, X[cols], 0.0, K_MAX)
            Qk = _apply_offsets(Q, b["offsets"][("full", ld)], seas, QUANTILES)
        else:
            fallback = True
            kc = baselines.climatology(b["clim_k"], rows)["mean"].to_numpy()
            Qk = baselines.predict_fallback(b["fallback"], X["k_persist"].to_numpy(), kc,
                                            np.full(len(rows), ld), seas)
        Qk = np.where(day[:, None], np.clip(Qk, 0, K_MAX), 0.0)
        ghiq = Qk * T["ghi_clear"].to_numpy()[:, None]
        temp = T["temp_fc"].copy()
        if temp.isna().all():
            temp = pd.Series(b["clim_temp"].reindex(pd.MultiIndex.from_arrays(
                [rows.month, rows.hour])).to_numpy(), index=rows)
        wind = T["wind_fc"].fillna(3.0)
        for jj, t in enumerate((0.1, 0.5, 0.9)):
            solar[np.isin(w, rows), jj] = pv_ac_per_kwp(pd.Series(ghiq[:, J[t]], index=rows), temp, wind,
                                                        base.loc[rows]).to_numpy() * pv_kwp
        # demand
        lh = load_hist if load_hist is not None else D.load_series()[0]
        lh = lh[lh.index <= it]
        nwp_d = nwp if any(f"temp_c_d{ld}" in df for df in nwp.values()) else {}
        Xd = D.features(lh, nwp_d, ld, rows)
        if "temp_fc" not in Xd or Xd["temp_fc"].isna().all():
            Xd["temp_fc"] = temp.to_numpy()
            Xd["temp_fc_daymean"] = float(np.nanmean(temp))
        for comp in D.COMPONENTS:
            cols, models = b["demand"][(comp, ld)]
            Xc = Xd.reindex(columns=cols)
            Q = D.predict(models, Xc, Xc[f"{comp}_kW_lag"])
            Q = np.sort(Q + b["demand_offsets"][(comp, ld)], axis=1).clip(min=0)
            for jj, p in enumerate((10, 50, 90)):
                out.loc[np.isin(w, rows), f"demand_{comp}_kW_p{p}"] = Q[:, jj]
    for jj, p in enumerate((10, 50, 90)):
        out[f"solar_kW_p{p}"] = solar[:, jj]
    out["fallback"] = fallback
    return out[SCHEMA]


def live(issue_time=None, pv_kwp=PV_KWP_INL) -> tuple[pd.DataFrame, str]:
    """Fetch live inputs and forecast; any fetch failure -> fallback (never raises on comms)."""
    from aurora.data.http import DownloadBlocked

    if issue_time is None:
        now = pd.Timestamp.now(tz="UTC")
        issue_time = now.floor("D") + pd.Timedelta(hours=ISSUE_HOUR_UTC)
        if issue_time > now:
            issue_time -= pd.Timedelta(days=1)
    it = normalise_issue(issue_time)
    note = "live NWP"
    try:
        nwp = fetch_live_nwp(it)
    except (DownloadBlocked, OSError, KeyError, ValueError) as exc:
        nwp, note = None, f"fallback: NWP unavailable ({exc})"
    try:
        obs = fetch_recent_satellite(it)
    except Exception as exc:  # noqa: BLE001 - persistence is optional
        obs, note = None, note + f"; no recent satellite GHI ({type(exc).__name__})"
    return forecast_issue(it, nwp=nwp, ghi_obs=obs, pv_kwp=pv_kwp), note

