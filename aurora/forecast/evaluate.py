"""Scores for the solar and demand backtests (tables used by report.py)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from aurora.data import paths

from . import quantile as Qm
from .features import GHI_MODELS, QUANTILES

QC = Qm.qcols()
J10, J50, J90 = QUANTILES.index(0.1), QUANTILES.index(0.5), QUANTILES.index(0.9)
POINT_NAMES = {
    "aurora": "AURORA P50",
    "nwp_ecmwf": "Raw NWP: ECMWF IFS",
    "nwp_gfs": "Raw NWP: GFS",
    "nwp_icon": "Raw NWP: ICON",
    "nwp_mean": "Raw NWP: mean of 3",
    "persist": "Smart persistence",
    "clim": "Climatology",
    "fallback": "Fallback P50",
}
PROB_NAMES = {
    "aurora": "AURORA (calibrated)",
    "aurora_raw": "AURORA (before conformal)",
    "nwp_ens": "Raw NWP: 3-model ensemble",
    "clim": "Climatology (quantiles)",
    "fallback": "Fallback (widened)",
}


def add_typhoon_flags(bt: pd.DataFrame) -> pd.DataFrame:
    f = pd.read_parquet(paths.TYPHOON_HOURLY) if paths.TYPHOON_HOURLY.exists() else None
    out = bt.copy()
    if f is None:
        out["tc500"] = out["tc300"] = False
        return out
    out["tc500"] = f["tc_within_500km"].reindex(out.index).fillna(False).astype(bool).to_numpy()
    out["tc300"] = f["tc_within_300km"].reindex(out.index).fillna(False).astype(bool).to_numpy()
    return out


def eval_sample(bt: pd.DataFrame, start, regime="full", common=True) -> pd.DataFrame:
    d = bt[(bt.index >= start) & bt["daylight"] & bt["k_true"].notna() & (bt["regime"] == regime)]
    if common:
        need = [f"ghi_nwp_{m}" for m in GHI_MODELS] + ["k_persist"]
        d = d.dropna(subset=[c for c in need if c in d])
    return d


def ghi_quantiles(d: pd.DataFrame, prefix="") -> np.ndarray:
    return d[[f"{prefix}{c}" for c in QC]].to_numpy() * d["ghi_clear"].to_numpy()[:, None]


def forecasts(d: pd.DataFrame) -> tuple[dict, dict]:
    """Point and probabilistic GHI forecasts (W/m2) for the rows of d."""
    gc = d["ghi_clear"].to_numpy()
    Qa, Qr = ghi_quantiles(d), ghi_quantiles(d, "raw_")
    Qc, Qf = ghi_quantiles(d, "clim_"), ghi_quantiles(d, "fb_")
    pt = {"aurora": Qa[:, J50]}
    for m in GHI_MODELS:
        if f"ghi_nwp_{m}" in d:
            pt[f"nwp_{m}"] = d[f"ghi_nwp_{m}"].to_numpy()
    pt["nwp_mean"] = d["ghi_nwp_mean"].to_numpy()
    pt["persist"] = d["k_persist"].to_numpy() * gc
    pt["clim"] = d["k_clim"].to_numpy() * gc
    pt["fallback"] = Qf[:, J50]
    pr = {"aurora": Qa, "aurora_raw": Qr, "clim": Qc, "fallback": Qf}
    return pt, pr


def score_table(d: pd.DataFrame) -> pd.DataFrame:
    """One row per forecast: MAE, RMSE, bias, CRPS, PICP80, width80 (W/m2)."""
    y = d["ghi_true"].to_numpy()
    pt, pr = forecasts(d)
    rows = {}
    for k, f in pt.items():
        s = Qm.point_scores(y, f)
        s["CRPS"] = s["MAE"]  # deterministic forecast
        rows[k] = s
    for k, Q in pr.items():
        s = rows.get(k, Qm.point_scores(y, Q[:, J50]))
        s.update({"CRPS": float(np.mean(Qm.crps_quantiles(y, Q))), **Qm.band_scores(y, Q[:, J10], Q[:, J90])})
        s["pinball_P10"] = float(np.mean(Qm.pinball(y, Q[:, J10], 0.1)))
        s["pinball_P50"] = float(np.mean(Qm.pinball(y, Q[:, J50], 0.5)))
        s["pinball_P90"] = float(np.mean(Qm.pinball(y, Q[:, J90], 0.9)))
        rows[k] = s
    E = np.column_stack([d[f"ghi_nwp_{m}"].to_numpy() for m in GHI_MODELS if f"ghi_nwp_{m}" in d])
    ens = Qm.point_scores(y, np.nanmean(E, axis=1))
    ens["CRPS"] = float(np.nanmean(Qm.crps_ensemble(y, E)))
    rows["nwp_ens"] = ens
    t = pd.DataFrame(rows).T
    return t


def skill(t: pd.DataFrame, metric: str, ref: str, model="aurora") -> float:
    return 1.0 - t.loc[model, metric] / t.loc[ref, metric]


def split_scores(d: pd.DataFrame, by) -> dict:
    return {k: score_table(g) for k, g in d.groupby(by) if len(g) >= 30}


def reliability(d: pd.DataFrame, prefix="") -> np.ndarray:
    """Observed frequency of y <= q_tau for every level."""
    y = d["k_true"].to_numpy()[:, None]
    Q = d[[f"{prefix}{c}" for c in QC]].to_numpy()
    return (y <= Q).mean(axis=0)


def daily_block_bootstrap(d: pd.DataFrame, fn, n_boot=300, seed=2026) -> tuple[float, float]:
    """5-95 % range of fn(sample) over bootstrap resamples of issue days."""
    rng = np.random.default_rng(seed)
    days = d["issue_time"].unique()
    groups = dict(d.groupby("issue_time").indices)
    vals = []
    for _ in range(n_boot):
        pick = rng.choice(days, len(days), replace=True)
        ii = np.concatenate([groups[p] for p in pick])
        vals.append(fn(d.iloc[ii]))
    return float(np.nanpercentile(vals, 5)), float(np.nanpercentile(vals, 95))


def demand_scores(dm: pd.DataFrame, start) -> pd.DataFrame:
    """MAE, RMSE, bias and P10-P90 coverage of the demand forecast, by component and lead day."""
    d = dm[dm.index >= start]
    rows = []
    for comp in ("critical", "flex"):
        for ld, g in d.groupby("lead_day"):
            g = g.dropna(subset=[f"{comp}_true", f"{comp}_p50"])
            y = g[f"{comp}_true"].to_numpy()
            s = Qm.point_scores(y, g[f"{comp}_p50"])
            s.update(Qm.band_scores(y, g[f"{comp}_p10"], g[f"{comp}_p90"]))
            s["mean_kW"] = float(np.mean(y))
            if f"{comp}_naive" in g:
                s["MAE_naive"] = float(np.nanmean(np.abs(g[f"{comp}_naive"].to_numpy() - y)))
            rows.append({"component": comp, "lead_day": ld, **s})
    return pd.DataFrame(rows)
