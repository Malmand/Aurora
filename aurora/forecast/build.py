"""Rebuild every Phase 2 output from data/itbayat/raw_small/ (no network).

    python -m aurora.forecast.build            # backtest (~20 min), report, figures, models, sample CSVs
    python -m aurora.forecast.build --reuse    # reuse cached backtests where present, redo the rest

Outputs
  data/itbayat/forecast/backtest_solar.parquet   lean backtest: GHI and PV bands, truth, baselines
  data/itbayat/forecast/backtest_demand.parquet  demand bands (SYNTHETIC load)
  data/itbayat/forecast/issues/*.csv             sample 48 h forecast files (digital-twin schema)
  docs/validation_forecast.md, figures/forecast_*.pdf|png
  data/itbayat/forecast/cache/, models/          full backtest and fitted models (git-ignored)
"""
from __future__ import annotations

import argparse
import sys
import time

import numpy as np
import pandas as pd

from aurora.data import paths

from . import backtest as B, demand as D, operational as O, report
from .features import load_nwp, load_truth
from .geometry import hourly_clearsky
from .pv import pv_ac_per_kwp

CACHE = O.FC_DIR / "cache"
LEAN_SOLAR = O.FC_DIR / "backtest_solar.parquet"
LEAN_DEMAND = O.FC_DIR / "backtest_demand.parquet"


def lean_solar(bt: pd.DataFrame) -> pd.DataFrame:
    """Columns Phase 3/4 need: GHI and PV bands (per kWp), truth, raw NWP mean, persistence."""
    out = []
    for ld, g in bt.groupby("lead_day"):
        g = g.sort_index()
        geom = hourly_clearsky(g.index)
        gc = g["ghi_clear"]
        o = g[["issue_time", "lead_h", "lead_day", "regime", "calibrated", "ghi_clear", "ghi_true"]].copy()
        o = o.rename(columns={"ghi_true": "ghi_ref"})
        series = {f"p{p}": g[f"q{p}"] * gc for p in (10, 50, 90)}
        series["nwp_mean"] = g["ghi_nwp_mean"]
        series["persist"] = g["k_persist"] * gc
        series["ref"] = g["ghi_true"]
        for k, s in series.items():
            if k != "ref":
                o[f"ghi_{k}"] = s
            temp, wind = (g["temp_era5"], g["wind_era5"]) if k == "ref" else (g["temp_fc"], g["wind_fc"])
            pv = pv_ac_per_kwp(s.fillna(0.0) if k != "ref" else s, temp, wind, geom)
            o[f"pv_kw_per_kwp_{k}"] = pv.where(s.notna())
        out.append(o)
    o = pd.concat(out).sort_values(["issue_time", "lead_h"])
    o.index.name = "timestamp"
    o.attrs.update(description="AURORA Phase 2 solar backtest. GHI in W/m2 (hour mean, hour-ending UTC). "
                   "pv_kw_per_kwp_*: AC kW per kWp DC (multiply by array size). ghi_ref: satellite retrieval, "
                   "not a measurement. regime: full / reduced (no NWP GHI) / reduced_reverse (2022, trained "
                   "on 2023).")
    return o


def pv_scores(lean: pd.DataFrame, kwp=300.0) -> dict:
    d = lean[(lean.index >= B.EVAL_START) & (lean["regime"] == "full") & (lean["ghi_clear"] >= 50)]
    d = d.dropna(subset=["pv_kw_per_kwp_ref", "pv_kw_per_kwp_nwp_mean", "pv_kw_per_kwp_persist"])
    out = {}
    for ld, g in d.groupby("lead_day"):
        y = g["pv_kw_per_kwp_ref"] * kwp
        e = g["pv_kw_per_kwp_p50"] * kwp - y
        out[ld] = {"mae": e.abs().mean(), "rmse": np.sqrt((e ** 2).mean()),
                   "rmse_nwp": np.sqrt(((g["pv_kw_per_kwp_nwp_mean"] * kwp - y) ** 2).mean()),
                   "rmse_persist": np.sqrt(((g["pv_kw_per_kwp_persist"] * kwp - y) ** 2).mean()),
                   "picp": ((y >= g["pv_kw_per_kwp_p10"] * kwp) & (y <= g["pv_kw_per_kwp_p90"] * kwp)).mean()}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reuse", action="store_true", help="reuse cached backtests")
    a = ap.parse_args(argv)
    t0 = time.time()
    CACHE.mkdir(parents=True, exist_ok=True)
    full_p, dem_p = CACHE / "backtest_solar_full.parquet", CACHE / "backtest_demand_full.parquet"
    if a.reuse and full_p.exists():
        bt = pd.read_parquet(full_p)
    else:
        print("solar backtest")
        bt = B.run()
        bt.to_parquet(full_p)
    if a.reuse and dem_p.exists():
        dm = pd.read_parquet(dem_p)
    else:
        print("demand backtest")
        months = pd.date_range(B.FIRST_TEST, bt.index.max(), freq="MS")
        dm = D.backtest(load_nwp(), months, B.CUTOFF_GAP)
        dm.to_parquet(dem_p)
    lean = lean_solar(bt)
    lean.to_parquet(LEAN_SOLAR, compression="zstd")
    dcols = ["issue_time", "lead_day"] + [f"{c}_{x}" for c in D.COMPONENTS
                                          for x in ("p10", "p50", "p90", "true", "calibrated")]
    dl = dm[dcols].copy()
    dl.index.name = "timestamp"
    dl.attrs.update(description="AURORA Phase 2 demand backtest on the SYNTHETIC Phase 1 load (kW).",
                    synthetic=dm.attrs.get("synthetic", "True"))
    dl.to_parquet(LEAN_DEMAND, compression="zstd")
    print("report and figures")
    res = report.build(bt, dm, pv_scores(lean))
    print("final models")
    bundle = O.train_final(bt, dm)
    # sample CSVs: the typhoon week (backtest), the last issue (backtest), and a fallback demo
    O.ISSUE_DIR.mkdir(parents=True, exist_ok=True)
    for f in O.ISSUE_DIR.glob("forecast_*.csv"):
        f.unlink()
    written = []
    issues = []
    if "typhoon_week" in res:
        _, a0, b0 = res["typhoon_week"]
        issues += list(pd.date_range(a0 - pd.Timedelta(days=1), b0 - pd.Timedelta(days=1), freq="D")
                       + pd.Timedelta(hours=O.ISSUE_HOUR_UTC - a0.hour))
    end = dl.index.max()          # demand table holds every hour, night included
    last_issue = max(t for t in lean["issue_time"].unique() if t + pd.Timedelta(hours=48) <= end)
    issues.append(last_issue)
    for it in issues:
        if (lean["issue_time"] == it).any():
            written.append(O.write_csv(O.from_backtest(lean, dl, it)))
    truth = load_truth()["ghi_sat"]
    fb = O.forecast_issue(last_issue, bundle, nwp=None, ghi_obs=truth[truth.index <= last_issue])
    written.append(O.write_csv(fb, tag="_fallback_demo"))
    print(f"\nPhase 2 build done in {time.time() - t0:.0f} s")
    print(f"  {LEAN_SOLAR.relative_to(paths.ROOT)}: {len(lean)} rows")
    print(f"  {LEAN_DEMAND.relative_to(paths.ROOT)}: {len(dl)} rows (synthetic load)")
    print(f"  {report.OUT_MD.relative_to(paths.ROOT)}")
    print(f"  {len(written)} forecast CSVs in {O.ISSUE_DIR.relative_to(paths.ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
