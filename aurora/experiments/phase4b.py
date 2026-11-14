"""Phase 4b: model v2 (realism fixes) and stress tests.

    python -m aurora.experiments.phase4b run --stage A --workers 8
    python -m aurora.experiments.phase4b run --stage B --workers 8   # needs stage A (picks the size)
    python -m aurora.experiments.phase4b tables

What changed from Phase 4 (model v1), all ASSUMPTIONs in site.yaml:
  1. A fair human baseline, controller O (RationingOperator): the simple rule plus
     rotating brownouts once the tanker is overdue, sized so the fuel lasts to the
     latest plausible arrival. NPC and BATANELCO did this in 2022 and 2023.
  2. Household load is cut in whole feeder blocks (4), not by the exact kW.
  3. Critical demand varies around its synthetic schedule (AR(1), SD 12 %), and
     AURORA's forecast carries matching critical bands.
  4. AURORA's plan keeps a 250 L fuel reserve so a generator can still start.
  5. The size is chosen on all three storms, not on Mawar alone.
Stress tests at the chosen size, tanker 14 days late, all three storms:
  gen_fail      two of the three working diesel units out: one generator left
  pv_damage     solar output halved from the storm's closest approach on
  comms_down    no weather forecast: AURORA runs on the backup persistence forecast
  clinic_shared the clinic shares the last household feeder (cut with it)

Stage A: sizing sweep on all three storms (B, O, C) and the three storms at the
INL size and at NPC's own planned size, 180 kWp / 120 kWh (A, B, O, C). Stage B: at the chosen size, the three storms at 3, 7 and
14 days late, two full years (Nov 2024 to Oct 2026), the stress tests and the
value of forecasting. Jobs write results/phase4b/jobs/<id>.json and are skipped
if that file exists, so a stopped run resumes.

Inputs are not measurements: ERA5 weather, pvlib PV, the Phase 1 SYNTHETIC load
(calibrated to NPC's annual peak and gross generation for Itbayat DPP).
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import time

import numpy as np
import pandas as pd

from ..data import paths
from ..data.site import load_site, value
from ..twin import forecasts, inputs, metrics, params, plant, simulate
from . import phase4 as P4

OUT = paths.ROOT / "results" / "phase4b"
JOBS = OUT / "jobs"
HOURLY = OUT / "hourly"
N_SCEN = 32
DELAYS = P4.DELAYS
TANK0_STORM = P4.TANK0_STORM
PV_GRID = (300, 400, 500, 600)
BAT_GRID = (500, 750, 1000, 1250, 1500, 2000)
CEST_TARGET_H = 24.0
ALL = ("A", "B", "O", "C")
STRESS = ("gen_fail", "pv_damage", "comms_down", "clinic_shared")


def clinic_share(site=None) -> float:
    s = site or load_site()
    names = ("crit_clinic_kw", "crit_water_kw", "crit_telecom_kw", "crit_municipal_kw", "crit_cold_storage_kw")
    kw = {n: float(value(s, n)) for n in names}
    return kw["crit_clinic_kw"] / sum(kw.values())


def system(spec):
    p = P4.sized(spec["pv_kwp"], spec["bat_kwh"]) if "pv_kwp" in spec else params.from_site(spec["sizing"])
    p = params.v2(p)
    sc = spec.get("stress")
    if sc == "gen_fail":
        p = p.with_(n_units=1)                     # only one of the three working units left
    elif sc == "clinic_shared":
        p = p.with_(crit_shared_frac=clinic_share())
    return p


def make_forecast(kind, truth, p, sigma):
    if kind == "comms_down":
        fc = forecasts.PersistenceForecast(truth, p.pv_kwp, widen=1.5, fallback=True)
    else:
        fc = P4.make_forecast(kind, truth, p)
    return forecasts.CriticalBand(fc, sigma) if kind != "perfect" else fc


def run_job(spec: dict) -> list[dict]:
    path = JOBS / f"{spec['id']}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    t_wall = time.time()
    s = load_site()
    sigma = float(value(s, "crit_noise_sigma"))
    p = system(spec)
    t0 = P4.local_utc(spec["start"])
    horizon = 48
    t1 = t0 + pd.Timedelta(days=spec["days"]) + pd.Timedelta(hours=horizon + 1)
    truth = inputs.build(t0 - pd.Timedelta(days=35), t1, crit_noise=True)
    sc = spec.get("stress")
    fk = "comms_down" if sc == "comms_down" else spec["forecast"]
    if sc == "pv_damage":
        hit = pd.Timestamp(spec["t_hit"])
        truth.loc[truth.index >= hit, "pv_kw_per_kwp"] *= 0.5
    fc = make_forecast(fk, truth, p, sigma)
    if sc == "pv_damage":
        fc = forecasts.ScaledSolarAfter(fc, hit, 0.5)
    if spec["kind"] == "storm":
        first = t0 + pd.Timedelta(hours=P4.DELIVERY_AFTER_H)
        sched = plant.FuelSchedule(p.tank_l, p.resupply_days, first=first,
                                   delays={first: spec["delay_days"]} if spec["delay_days"] else {})
        tank0 = spec.get("tank0", TANK0_STORM)
    else:
        sched, tank0 = None, None
    rows = []
    for c in spec["controllers"]:
        r = simulate.run(truth, p, c, fc, start=t0, hours=24 * spec["days"], schedule=sched, tank0=tank0,
                         horizon=horizon, horizon_mode="issue", n_scen_risk=N_SCEN,
                         **({"n_scen": N_SCEN} if c == "C" else {}))
        if spec.get("hourly"):
            HOURLY.mkdir(parents=True, exist_ok=True)
            r.to_csv(HOURLY / f"{spec['id']}_{c}.csv.gz", float_format="%.4g")
        k = metrics.kpis(r, p)
        rows.append(dict(job=spec["id"], group=spec["group"], controller=c, sizing=p.sizing,
                         pv_kwp=p.pv_kwp, bat_kwh=p.bat_kwh, bat_kw=p.bat_kw, forecast=fc.name,
                         **{k_: spec.get(k_) for k_ in ("storm", "delay_days", "period", "stress")},
                         start_local=spec["start"], days=spec["days"], n_scen=N_SCEN, model="v2", **k,
                         flex_total_kwh=round(float(r["flex"].sum()), 0),
                         crit_total_kwh=round(float(r["crit"].sum()), 0),
                         deliveries=r.attrs["deliveries"]))
    rows[0]["wall_s"] = round(time.time() - t_wall, 1)
    JOBS.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=1, default=str), encoding="utf-8")
    print(f"done {spec['id']} in {time.time() - t_wall:.0f}s", flush=True)
    return rows


# ---------------------------------------------------------------- job lists
def storms():
    return P4.select_storms()


def storm_job(key, ev, d, ctls, group, hourly=True, forecast="phase2", **size):
    tag = size.get("sizing") or f"pv{size['pv_kwp']}_bat{size['bat_kwh']}"
    return dict(id=f"{group}_{key}_{tag}_d{d}" + ("" if forecast == "phase2" else f"_{forecast.replace(':', '-')}"),
                group=group, kind="storm", storm=key, start=ev["start"], days=P4.storm_days(d), delay_days=d,
                forecast=forecast, controllers=list(ctls), hourly=hourly, **size)


def sweep_jobs(st):
    return [storm_job(key, ev, 14, ("B", "O", "C"), "sweep", hourly=False, pv_kwp=pv, bat_kwh=b)
            for key, ev in st.iterrows() for pv in PV_GRID for b in BAT_GRID]


def year_jobs(pv, b):
    out = []
    for start, days, per in P4.YEAR_CHUNKS:
        if days is None:
            days = int(((P4.DATA_END - pd.Timedelta(hours=49)) - P4.local_utc(start)) // pd.Timedelta(days=1))
        out.append(dict(id=f"year_pv{pv}_bat{b}_{start}", group="year", kind="year", start=start, days=days,
                        period=per, forecast="phase2", controllers=list(ALL), hourly=True, delay_days=0,
                        pv_kwp=pv, bat_kwh=b))
    return out


def load_rows(prefix=None) -> pd.DataFrame:
    rows = []
    for f in sorted(JOBS.glob("*.json")):
        if prefix is None or f.stem.startswith(prefix):
            rows += json.loads(f.read_text(encoding="utf-8"))
    return pd.DataFrame(rows)


def recommended(sw: pd.DataFrame | None = None) -> pd.Series:
    """Cheapest size where AURORA (C) has 0 critical outage h in all three storms
    (14 days late) and median CEST >= 24 h in each. If no size meets it, the size
    with the fewest worst-case outage hours, then the cheapest."""
    sw = load_rows("sweep_") if sw is None else sw
    c = sw[sw["controller"] == "C"]
    g = c.groupby(["pv_kwp", "bat_kwh", "bat_kw"]).agg(worst_outage_h=("crit_outage_h", "max"),
                                                       min_cest_median_h=("cest_median_h", "min"),
                                                       n_storms=("storm", "nunique")).reset_index()
    g = g[g["n_storms"] == g["n_storms"].max()]
    g["capex_mphp"] = [P4.capex_php(a, b, k) / 1e6 for a, b, k in zip(g.pv_kwp, g.bat_kwh, g.bat_kw)]
    ok = g[(g["worst_outage_h"] == 0) & (g["min_cest_median_h"] >= CEST_TARGET_H)]
    pick = (ok.sort_values(["capex_mphp", "bat_kwh"]) if not ok.empty
            else g.sort_values(["worst_outage_h", "capex_mphp"]))
    r = pick.iloc[0].copy()
    r["meets_target"] = not ok.empty
    return r


def stage_jobs(stage):
    st = storms()
    if stage == "A":
        jobs = sweep_jobs(st)
        jobs += [storm_job(k, ev, d, ALL, "inl", sizing="inl") for k, ev in st.iterrows() for d in DELAYS]
        jobs += [storm_job(k, ev, d, ALL, "npc", sizing="npc") for k, ev in st.iterrows() for d in DELAYS]
        return jobs
    r = recommended()
    pv, b = int(r.pv_kwp), int(r.bat_kwh)
    size = dict(pv_kwp=pv, bat_kwh=b)
    jobs = [storm_job(k, ev, d, ALL, "rec", **size) for k, ev in st.iterrows() for d in DELAYS]
    jobs += year_jobs(pv, b)
    for k, ev in st.iterrows():
        for sc in STRESS:
            j = storm_job(k, ev, 14, ALL, f"stress-{sc}", **size)
            j.update(stress=sc, t_hit=str(ev["closest_time_utc"]))
            jobs.append(j)
        for f in ("perfect", "phase2:nwp"):
            jobs.append(storm_job(k, ev, 14, ("C",), "vof", hourly=False, forecast=f, **size))
    return jobs


def cost_estimate(spec):
    w = {"A": 0.002, "B": 0.003, "O": 0.004, "C": 0.3}
    return spec["days"] * 24 * sum(w[c] for c in spec["controllers"])


def run_stage(stage, workers):
    jobs = [j for j in stage_jobs(stage) if not (JOBS / f"{j['id']}.json").exists()]
    jobs.sort(key=cost_estimate, reverse=True)
    print(f"phase4b stage {stage}: {len(jobs)} jobs to run, about {sum(map(cost_estimate, jobs)) / 3600:.1f} CPU-h",
          flush=True)
    with mp.get_context("fork").Pool(workers, maxtasksperchild=4) as pool:
        for _ in pool.imap_unordered(run_job, jobs):
            pass


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--stage", choices=["A", "B"], required=True)
    r.add_argument("--workers", type=int, default=4)
    sub.add_parser("tables")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        run_stage(a.stage, a.workers)
    else:
        from . import phase4b_tables
        phase4b_tables.write_all()


if __name__ == "__main__":
    main()
