"""Run the digital twin from the command line.

    python -m aurora.twin.run --demo
    python -m aurora.twin.run --controllers A B C --sizing inl --start "2023-05-27" --days 10 \
        --forecast persistence --tank0 6000 --delay-days 7 --out results/twin/my_run

--start is local time (PHT) at midnight unless a zone is given. --forecast is
perfect, persistence (twin baseline), phase2 (the Phase 2 backtest read directly
from data/itbayat/forecast/; phase2:nwp and phase2:persistence give the raw NWP
mean and Phase 2 persistence for value-of-forecasting runs), csv (the Phase 2
sample CSVs in data/itbayat/forecast/issues/) or csv:<folder> (other forecast files).
--delay-days delays the first planned delivery after the start (stress test).
--horizon-mode issue (default) sets the MPC horizon at each step to the end of
the newest issued forecast (25 to 48 h for the daily 48 h issues); fixed keeps
--horizon (48 h) at every step, with the tail past the issue from the
persistence fallback. Writes <out>/run_<ctl>.csv (hourly) and <out>/kpis.csv.

--demo reproduces docs/twin.md: typhoon Mawar (PAGASA: Betty), INL and case
sizings, tank at 10 % when the tanker due on 28 May 2023 is delayed 7 or 14 days.
--horizon-compare runs controller C on the same Mawar window (7-day delay) with
the Phase 2 forecast, once with the issue-aligned horizon and once with a fixed
48 h horizon, at both sizings (results/twin/horizon_compare_mawar2023_*).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from ..data import paths
from . import forecasts, inputs, metrics, params, plant, simulate

OUT = paths.ROOT / "results" / "twin"
PHASE2_CSV_KWP = 300.0  # the Phase 2 sample CSVs are written for the INL 300 kWp array


def make_forecast(kind: str, truth, p):
    if kind == "perfect":
        return forecasts.PerfectForecast(truth, p.pv_kwp)
    if kind == "persistence":
        return forecasts.PersistenceForecast(truth, p.pv_kwp)
    if kind == "csv":
        return forecasts.CSVForecast(paths.SITE_DIR / "forecast" / "issues", truth, p.pv_kwp, scale_kwp=PHASE2_CSV_KWP)
    if kind.startswith("csv:"):
        return forecasts.CSVForecast(kind[4:], truth, p.pv_kwp)
    if kind == "phase2" or kind.startswith("phase2:"):
        return forecasts.Phase2Forecast(truth, p.pv_kwp, kind.split(":", 1)[1] if ":" in kind else "aurora")
    raise ValueError(kind)


def local_start(s: str) -> pd.Timestamp:
    t = pd.Timestamp(s)
    return (t.tz_localize(paths.LOCAL_TZ) if t.tzinfo is None else t).tz_convert("UTC")


def run_case(
    controllers,
    sizing,
    start,
    days,
    forecast,
    tank0,
    delay_days,
    delivery_after_h,
    out: Path,
    horizon=48,
    horizon_mode="issue",
    progress=True,
):
    """Run the chosen controllers over one window with one tanker delay; write hourly CSVs and KPIs to `out`."""
    t0 = local_start(start)
    t1 = t0 + pd.Timedelta(days=days) + pd.Timedelta(hours=horizon + 1)
    truth = inputs.build(t0 - pd.Timedelta(days=35), t1)  # 35 days of history for persistence bands
    p = params.from_site(sizing)
    first = t0 + pd.Timedelta(hours=delivery_after_h)
    sched = plant.FuelSchedule(p.tank_l, p.resupply_days, first=first, delays={first: delay_days} if delay_days else {})
    fc = make_forecast(forecast, truth, p)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for c in controllers:
        r = simulate.run(
            truth,
            p,
            c,
            fc,
            start=t0,
            hours=24 * days,
            schedule=sched,
            tank0=tank0,
            horizon=horizon,
            horizon_mode=horizon_mode,
            progress=progress,
        )
        r.to_csv(out / f"run_{c}.csv", float_format="%.4g")
        k = metrics.kpis(r, p)
        rows.append(
            dict(
                controller=c,
                sizing=sizing,
                forecast=fc.name,
                horizon_mode=horizon_mode,
                **k,
                wall_s=float(r.attrs["wall_s"]),
                deliveries=r.attrs["deliveries"],
            )
        )
        print(
            f"{sizing} {c}: diesel {k['diesel_l']:.0f} L, flex shed {k['flex_shed_kwh']:.0f} kWh, "
            f"critical unserved {k['crit_unserved_kwh']:.1f} kWh ({k['crit_outage_h']} h), "
            f"CEST median {k['cest_median_h']} h, plans with fallback {k['plans_with_fallback_pct']} %, "
            f"wall {r.attrs['wall_s']} s",
            flush=True,
        )
    kp = pd.DataFrame(rows)
    kp.to_csv(out / "kpis.csv", index=False)
    meta = dict(
        start_local=start,
        days=days,
        sizing=sizing,
        forecast=forecast,
        tank0_l=tank0,
        first_delivery_utc=str(first),
        delay_days=delay_days,
        horizon_h=horizon,
        horizon_mode=horizon_mode,
        truth=truth.attrs,
        params=p.as_dict(),
    )
    (out / "meta.json").write_text(json.dumps(meta, indent=1, default=str), encoding="utf-8")
    return kp


DEMO = dict(start="2023-05-27", forecast="persistence", tank0=6000.0, delivery_after_h=24)
DEMO_DELAYS = (7, 14)  # days; each window runs until 3 days after the late tanker arrives
COMPARE = dict(start="2023-05-27", forecast="phase2", tank0=6000.0, delivery_after_h=24, delay_days=7, days=7 + 1 + 3)


def horizon_compare(sizings=("inl", "case")):
    """C on the Mawar window with the Phase 2 forecast: issue-aligned vs fixed 48 h horizon."""
    allk = []
    for sz in sizings:
        for mode in ("issue", "fixed"):
            kp = run_case(["C"], sz, out=OUT / f"horizon_compare_mawar2023_{mode}_{sz}", horizon_mode=mode, **COMPARE)
            allk.append(kp)
    k = pd.concat(allk)
    k.to_csv(OUT / "horizon_compare_mawar2023_kpis.csv", index=False)
    print(k.drop(columns=["deliveries"]).to_string(index=False))
    return k


def main(argv=None):
    """Command line for single twin runs, the Mawar demo and the horizon comparison."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--controllers", nargs="+", default=["A", "B", "C"])
    ap.add_argument("--sizing", default="inl", choices=list(params.SIZINGS))
    ap.add_argument("--start", default="2023-05-27")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--forecast", default="persistence")
    ap.add_argument("--tank0", type=float, default=None, help="litres at the start (default: full)")
    ap.add_argument("--delay-days", type=float, default=0.0)
    ap.add_argument(
        "--delivery-after-h",
        type=float,
        default=None,
        help="hours from start to the first planned delivery (default: half an interval)",
    )
    ap.add_argument("--horizon", type=int, default=48, help="MPC horizon in hours (the cap in issue mode)")
    ap.add_argument("--horizon-mode", default="issue", choices=list(simulate.HORIZON_MODES))
    ap.add_argument("--horizon-compare", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    if a.horizon_compare:
        horizon_compare()
        return
    if a.demo:
        allk = []
        for dly in DEMO_DELAYS:
            for sz in ("inl", "case"):
                kp = run_case(
                    ["A", "B", "C"],
                    sz,
                    out=OUT / f"demo_mawar2023_delay{dly}d_{sz}",
                    days=dly + 1 + 3,
                    delay_days=dly,
                    **DEMO,
                )
                allk.append(kp.assign(delay_days=dly))
        k = pd.concat(allk)
        k.to_csv(OUT / "demo_mawar2023_kpis.csv", index=False)
        print(k.drop(columns=["deliveries"]).to_string(index=False))
        return
    p = params.from_site(a.sizing)
    dah = a.delivery_after_h if a.delivery_after_h is not None else p.resupply_days * 12
    out = Path(a.out) if a.out else OUT / f"run_{a.sizing}_{a.start}"
    run_case(
        a.controllers,
        a.sizing,
        a.start,
        a.days,
        a.forecast,
        a.tank0,
        a.delay_days,
        dah,
        out,
        horizon=a.horizon,
        horizon_mode=a.horizon_mode,
    )


if __name__ == "__main__":
    main()
