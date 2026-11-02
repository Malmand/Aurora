"""Phase 4: results with ERA5 weather truth and the Phase 2 backtest forecasts.

    python -m aurora.experiments.phase4 run --stage A --workers 4
    python -m aurora.experiments.phase4 run --stage B --workers 4   # needs the sweep from stage A
    python -m aurora.experiments.phase4 tables

Stage A: storm runs (A/B/C, Phase 2 forecast), value of forecasting (C with
perfect, phase2:nwp, phase2:persistence), the Mawar 7-day INL decomposition,
full years Nov 2024 to Oct 2026 at INL and case sizing, and the sizing sweep.
Stage B: the recommended size (smallest capex in the sweep that meets the
criterion): sensitivity, full years and the other storms.

Every job writes results/phase4/jobs/<id>.json (one KPI row per controller) and
is skipped if that file exists, so a stopped run resumes. Hourly runs of the
storm and full-year jobs go to results/phase4/hourly/<id>_<ctl>.csv.gz.
`tables` writes the CSV tables in results/phase4/ and results/phase4/tables.md.

Settings for every run: MPC horizon aligned to the newest forecast issue (25 to
48 h), 32 Monte Carlo scenarios (in the MILP risk term and for R(t)), except the
decomposition, which repeats the Phase 3 settings (64 scenarios) to reproduce
the 2,649 and 1,718 kWh results exactly.

Inputs are not measurements: ERA5 reanalysis weather, pvlib PV and the Phase 1
SYNTHETIC load. Costs in PHP: NPC Sabtang bid ceiling split with Ocon and Bertheau (2019) (site.yaml).
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import time
from pathlib import Path

import numpy as np
import pandas as pd

from ..data import paths
from ..data.site import load_site, value
from ..twin import forecasts, inputs, metrics, params, plant, simulate

OUT = paths.ROOT / "results" / "phase4"
JOBS = OUT / "jobs"
HOURLY = OUT / "hourly"
N_SCEN = 32
DELAYS = (3, 7, 14)
TANK0_STORM = 6000.0           # litres when the tanker is delayed (Phase 3 stress assumption)
DELIVERY_AFTER_H = 24          # the delayed tanker was due 24 h after the window start
DATA_END = pd.Timestamp("2026-10-25 23:00", tz="UTC")   # last hour of ERA5, load and Phase 2 files
PV_GRID = (0, 100, 200, 300, 400, 500, 600)
BAT_GRID = (0, 250, 500, 750, 1000, 1250, 1500, 2000)
CEST_TARGET_H = 24.0


# ---------------------------------------------------------------- storms
def storm_start(closest_utc) -> str:
    """Window start: local (PHT) midnight three days before the closest approach."""
    loc = pd.Timestamp(closest_utc).tz_convert(paths.LOCAL_TZ)
    return str((loc.normalize() - pd.Timedelta(days=3)).date())


def select_storms(n: int = 2, after="2024-11-01") -> pd.DataFrame:
    """Mawar 2023 plus the n strongest storms after `after` whose 14-day-delay
    window fits the data. Strength = lowest central pressure while within 500 km."""
    ev = pd.read_csv(paths.SITE_DIR / "typhoon_events.csv", parse_dates=["closest_time_utc"])
    ev["start"] = ev["closest_time_utc"].map(storm_start)
    days_max = max(DELAYS) + 1 + 3
    t0 = pd.to_datetime(ev["start"]).dt.tz_localize(paths.LOCAL_TZ).dt.tz_convert("UTC")
    ev["fits"] = t0 + pd.Timedelta(days=days_max) + pd.Timedelta(hours=49) <= DATA_END
    late = ev[ev["closest_time_utc"] >= pd.Timestamp(after, tz="UTC")].sort_values("min_pres_hpa_within_500km")
    pick = late[late["fits"]].head(n)
    maw = ev[(ev["name"] == "MAWAR") & (ev["closest_time_utc"].dt.year == 2023)]
    out = pd.concat([maw, pick])
    out["key"] = [f"{nm.lower().replace('-', '')}{t.year}" for nm, t in zip(out["name"], out["closest_time_utc"])]
    out["forecast_regime"] = np.where(out["closest_time_utc"] < pd.Timestamp("2024-07-30", tz="UTC"),
                                      "backup (reduced Phase 2 model, no NWP GHI)", "full Phase 2 model")
    out.attrs["skipped"] = late[~late["fits"]].head(n)["name"].tolist()
    return out.set_index("key")


# ---------------------------------------------------------------- forecast wrappers
class HybridForecast:
    """Solar bands from one provider, demand bands from another (decomposition)."""

    def __init__(self, solar, demand):
        self.s, self.d = solar, demand
        self.name = f"solar:{solar.name}+demand:{demand.name}"
        self.issue_end = solar.issue_end

    def __call__(self, t, horizon):
        a, b = self.s(t, horizon), self.d(t, horizon)
        dc = [c for c in forecasts.COLS if c.startswith("demand")]
        a[dc] = b[dc].to_numpy()
        a["fallback"] = a["fallback"].to_numpy() | b["fallback"].to_numpy()
        return a


class ScaledDemand:
    """Demand bands times a factor (load growth known to the operator)."""

    def __init__(self, fc, factor):
        self.fc, self.k, self.name = fc, factor, fc.name
        self.issue_end = fc.issue_end

    def __call__(self, t, horizon):
        out = self.fc(t, horizon)
        dc = [c for c in forecasts.COLS if c.startswith("demand")]
        out[dc] = out[dc] * self.k
        return out


def make_forecast(kind, truth, p):
    if kind == "perfect":
        return forecasts.PerfectForecast(truth, p.pv_kwp)
    if kind == "persistence":
        return forecasts.PersistenceForecast(truth, p.pv_kwp)
    if kind.startswith("phase2"):
        return forecasts.Phase2Forecast(truth, p.pv_kwp, kind.split(":", 1)[1] if ":" in kind else "aurora")
    if kind.startswith("hybrid:"):                       # hybrid:<solar kind>/<demand kind>
        s, d = kind[7:].split("/")
        return HybridForecast(make_forecast(s, truth, p), make_forecast(d, truth, p))
    raise ValueError(kind)


# ---------------------------------------------------------------- one job
def sized(pv_kwp, bat_kwh, site=None):
    cap = value(site or load_site(), "sweep_battery_c_rate_cap_kw_assumed")
    return params.from_site("inl").with_(pv_kwp=float(pv_kwp), bat_kwh=float(bat_kwh),
                                         bat_kw=float(min(bat_kwh, cap)), sizing=f"pv{pv_kwp}_bat{bat_kwh}")


def system(spec):
    if "pv_kwp" in spec:
        p = sized(spec["pv_kwp"], spec["bat_kwh"])
    else:
        p = params.from_site(spec["sizing"])
    ov = dict(spec.get("overrides", {}))
    if "bat_kwh_factor" in ov:
        p = p.with_(bat_kwh=p.bat_kwh * ov.pop("bat_kwh_factor"))
    for k in ("overdue_weights", "overdue_delays"):
        if k in ov:
            ov[k] = tuple(ov[k])
    return p.with_(**ov) if ov else p


def local_utc(s):
    return pd.Timestamp(s).tz_localize(paths.LOCAL_TZ).tz_convert("UTC")


def run_job(spec: dict) -> list[dict]:
    path = JOBS / f"{spec['id']}.json"
    if path.exists():
        return json.loads(path.read_text())
    t_wall = time.time()
    p = system(spec)
    t0 = local_utc(spec["start"])
    horizon = 48
    t1 = t0 + pd.Timedelta(days=spec["days"]) + pd.Timedelta(hours=horizon + 1)
    truth = inputs.build(t0 - pd.Timedelta(days=35), t1)
    ls = spec.get("load_scale", 1.0)
    if ls != 1.0:
        truth[["crit_kW", "flex_kW"]] *= ls
    fc = make_forecast(spec["forecast"], truth, p)
    if ls != 1.0:
        fc = ScaledDemand(fc, ls)
    if spec["kind"] == "storm":
        first = t0 + pd.Timedelta(hours=DELIVERY_AFTER_H)
        sched = plant.FuelSchedule(p.tank_l, p.resupply_days, first=first,
                                   delays={first: spec["delay_days"]} if spec["delay_days"] else {})
        tank0 = spec.get("tank0", TANK0_STORM)
    else:
        sched, tank0 = None, None                        # deliveries every 30 days, tank full at start
    n_scen = spec.get("n_scen", N_SCEN)
    rows = []
    for c in spec["controllers"]:
        r = simulate.run(truth, p, c, fc, start=t0, hours=24 * spec["days"], schedule=sched, tank0=tank0,
                         horizon=horizon, horizon_mode="issue", n_scen_risk=n_scen,
                         **({"n_scen": n_scen} if c == "C" else {}))
        if spec.get("hourly"):
            HOURLY.mkdir(parents=True, exist_ok=True)
            r.to_csv(HOURLY / f"{spec['id']}_{c}.csv.gz", float_format="%.4g")
        k = metrics.kpis(r, p)
        rows.append(dict(job=spec["id"], group=spec["group"], controller=c, sizing=p.sizing,
                         pv_kwp=p.pv_kwp, bat_kwh=p.bat_kwh, bat_kw=p.bat_kw, forecast=fc.name,
                         **{k_: spec.get(k_) for k_ in ("storm", "delay_days", "label", "period")},
                         start_local=spec["start"], days=spec["days"], n_scen=n_scen, **k,
                         flex_total_kwh=round(float(r["flex"].sum()), 0),
                         deliveries=r.attrs["deliveries"]))
    rows[0]["wall_s"] = round(time.time() - t_wall, 1)
    JOBS.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=1, default=str))
    print(f"done {spec['id']} in {time.time() - t_wall:.0f}s", flush=True)
    return rows


# ---------------------------------------------------------------- job lists
def storm_days(d):
    return d + 1 + 3          # window ends 3 days after the late tanker arrives


def storm_jobs(storms, sizings=("inl", "case"), forecast="phase2", ctls=("A", "B", "C"), group="storm",
               hourly=True, **extra):
    out = []
    for key, ev in storms.iterrows():
        for sz in sizings:
            for d in DELAYS:
                fk = forecast.replace(":", "-")
                out.append(dict(id=f"{group}_{key}_{sz}_d{d}_{fk}", group=group, kind="storm", storm=key,
                                sizing=sz, start=ev["start"], days=storm_days(d), delay_days=d,
                                forecast=forecast, controllers=list(ctls), hourly=hourly, **extra))
    return out


YEAR_CHUNKS = (("2024-11-01", 181, "Y1"), ("2025-05-01", 184, "Y1"), ("2025-11-01", 181, "Y2"),
               ("2026-05-01", None, "Y2"))


def year_jobs(sizing=None, pv_kwp=None, bat_kwh=None, ctls=("A", "B", "C")):
    out = []
    for start, days, per in YEAR_CHUNKS:
        if days is None:      # last chunk: up to the end of the data, leaving one 48 h horizon
            days = int(((DATA_END - pd.Timedelta(hours=49)) - local_utc(start)) // pd.Timedelta(days=1))
        base = dict(group="year", kind="year", start=start, days=days, period=per, forecast="phase2",
                    controllers=list(ctls), hourly=True, delay_days=0)
        if sizing:
            out.append(dict(base, id=f"year_{sizing}_{start}", sizing=sizing))
        else:
            out.append(dict(base, id=f"year_pv{pv_kwp}_bat{bat_kwh}_{start}", pv_kwp=pv_kwp, bat_kwh=bat_kwh))
    return out


def sweep_jobs(storm, start):
    out = []
    for pv in PV_GRID:
        for b in BAT_GRID:
            out.append(dict(id=f"sweep_pv{pv}_bat{b}", group="sweep", kind="storm", storm=storm, start=start,
                            days=storm_days(14), delay_days=14, forecast="phase2", controllers=["B", "C"],
                            pv_kwp=pv, bat_kwh=b))
    return out


def decomposition_jobs(start):
    out = []
    for fk in ("persistence", "phase2", "hybrid:phase2/persistence", "hybrid:persistence/phase2"):
        out.append(dict(id=f"decomp_{fk.replace(':', '-').replace('/', '-')}", group="decomp", kind="storm",
                        storm="mawar2023", sizing="inl", start=start, days=storm_days(7), delay_days=7,
                        forecast=fk, controllers=["C"], n_scen=64, hourly=True))
    return out


def sensitivity_jobs(start, pv, b):
    base = dict(group="sens", kind="storm", storm="mawar2023", start=start, days=storm_days(14), delay_days=14,
                forecast="phase2", controllers=["A", "B", "C"], pv_kwp=pv, bat_kwh=b)
    cases = [("base", {}, 1.0, TANK0_STORM),
             ("diesel_65", {"diesel_php_per_l": 65.0}, 1.0, TANK0_STORM),
             ("diesel_140", {"diesel_php_per_l": 140.0}, 1.0, TANK0_STORM),
             ("weights_0.7_0.2_0.1", {"overdue_weights": [0.7, 0.2, 0.1]}, 1.0, TANK0_STORM),
             ("voll_50", {"voll_flex": 50.0}, 1.0, TANK0_STORM),
             ("voll_300", {"voll_flex": 300.0}, 1.0, TANK0_STORM),
             ("voll_500", {"voll_flex": 500.0}, 1.0, TANK0_STORM),
             ("tank_-50pct", {}, 1.0, 0.5 * TANK0_STORM),
             ("tank_+50pct", {}, 1.0, 1.5 * TANK0_STORM),
             ("battery_80pct", {"bat_kwh_factor": 0.8}, 1.0, TANK0_STORM),
             ("load_+12pct", {}, 1.12, TANK0_STORM)]
    return [dict(base, id=f"sens_{lab}", label=lab, overrides=ov, load_scale=ls, tank0=t0)
            for lab, ov, ls, t0 in cases]


COST_CASES = ("low", "base", "high")


def unit_costs(site_values=None) -> dict:
    """PHP unit costs per case: {case: (PHP/kWp PV, PHP/kWh battery, PHP/kW battery)}.

    base: NPC Sabtang ABC (PHP 57,697,900 for 180 kWp + 120 kW / 120 kWh) split with
          the Ocon and Bertheau (2019) Table 1 cost structure: every Table 1 component
          is scaled by k = ABC / (Table 1 cost of the Sabtang system in USD).
    low:  Ocon and Bertheau (2019) Table 1 as published, times php_per_usd.
    high: base times cost_high_factor_assumed.
    """
    s = site_values or load_site()["values"]
    v = lambda k: s[k]["value"]  # noqa: E731
    ocon = np.array([v("ocon2019_pv_capex_usd_per_kw"), v("ocon2019_battery_capex_usd_per_kwh"),
                     v("ocon2019_battery_capex_usd_per_kw")], float)
    sab = np.array([v("npc_sabtang_pv_kwp"), v("npc_sabtang_battery_kwh"), v("npc_sabtang_battery_kw")], float)
    k = v("npc_sabtang_abc_php") / float(ocon @ sab)              # PHP per Table 1 USD
    base = k * ocon
    return {"low": ocon * v("php_per_usd"), "base": base, "high": base * v("cost_high_factor_assumed"),
            "k_php_per_table1_usd": k}


def capex_parts_php(pv_kwp, bat_kwh, bat_kw, site=None, case="base"):
    """(PV capex, battery capex) in PHP; battery = energy part + power part."""
    pv, e, w = unit_costs(site)[case]
    return pv_kwp * pv, bat_kwh * e + bat_kw * w


def capex_php(pv_kwp, bat_kwh, bat_kw, site=None, case="base"):
    return sum(capex_parts_php(pv_kwp, bat_kwh, bat_kw, site, case))


def load_rows(prefix=None) -> pd.DataFrame:
    rows = []
    for f in sorted(JOBS.glob("*.json")):
        if prefix is None or f.stem.startswith(prefix):
            rows += json.loads(f.read_text())
    return pd.DataFrame(rows)


def recommended(sw: pd.DataFrame | None = None) -> pd.Series:
    """Smallest capex in the sweep where C has 0 critical outage h and median CEST >= 24 h."""
    sw = load_rows("sweep_") if sw is None else sw
    c = sw[sw["controller"] == "C"].copy()
    c["capex_mphp"] = [capex_php(a, b, k) / 1e6 for a, b, k in zip(c.pv_kwp, c.bat_kwh, c.bat_kw)]
    ok = c[(c["crit_outage_h"] == 0) & (c["cest_median_h"] >= CEST_TARGET_H)]
    if ok.empty:
        raise RuntimeError("no size in the sweep meets the criterion")
    return ok.sort_values(["capex_mphp", "bat_kwh"]).iloc[0]


def stage_jobs(stage):
    st = select_storms()
    maw = st.loc["mawar2023", "start"]
    if stage == "A":
        jobs = year_jobs("inl") + year_jobs("case") + sweep_jobs("mawar2023", maw) + storm_jobs(st)
        jobs += decomposition_jobs(maw)
        for f in ("perfect", "phase2:nwp", "phase2:persistence"):
            jobs += storm_jobs(st, forecast=f, ctls=("C",), group="vof", hourly=False)
        return jobs
    r = recommended()
    pv, b = int(r.pv_kwp), int(r.bat_kwh)
    jobs = year_jobs(pv_kwp=pv, bat_kwh=b) + sensitivity_jobs(maw, pv, b)
    for key, ev in st.iterrows():
        for d in DELAYS:
            jobs.append(dict(id=f"rec_{key}_d{d}", group="rec", kind="storm", storm=key, start=ev["start"],
                             days=storm_days(d), delay_days=d, forecast="phase2", controllers=["A", "B", "C"],
                             pv_kwp=pv, bat_kwh=b, hourly=True))
    return jobs


def cost_estimate(spec):
    steps = spec["days"] * 24
    w = {"A": 0.002, "B": 0.003, "C": 0.22}
    return steps * sum(w[c] for c in spec["controllers"])


def run_stage(stage, workers):
    jobs = [j for j in stage_jobs(stage) if not (JOBS / f"{j['id']}.json").exists()]
    jobs.sort(key=cost_estimate, reverse=True)                # longest first for packing
    print(f"stage {stage}: {len(jobs)} jobs to run, about {sum(map(cost_estimate, jobs)) / 3600:.1f} CPU-h",
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
    sub.add_parser("storms")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        run_stage(a.stage, a.workers)
    elif a.cmd == "storms":
        st = select_storms()
        print(st[["name", "start", "closest_km", "min_pres_hpa_within_500km", "forecast_regime"]])
        print("skipped (window past the data end):", st.attrs["skipped"])
    else:
        from . import phase4_tables
        phase4_tables.write_all()


if __name__ == "__main__":
    main()
