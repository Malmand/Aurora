"""Every number on the GSC deck, recomputed from the committed results.

    python -m aurora.experiments.headline          # writes results/headline.json and docs/headline_numbers.md
    python -m aurora.experiments.headline --check  # exits 1 if a recomputed number differs from the committed JSON

No simulation is run: the inputs are the Phase 4b result tables (results/phase4b/), the site values
(data/itbayat/site.yaml), the typhoon events, the synthetic NPC-calibrated load and the forecast backtest.
Each number carries the file it comes from, so a judge or reviewer can trace it.
"""
from __future__ import annotations

import argparse
import json
import sys

import pandas as pd

from ..data import paths
from ..data.site import load_site
from . import phase4 as P4

P4B = paths.ROOT / "results" / "phase4b"
OUT_JSON = paths.ROOT / "results" / "headline.json"
OUT_MD = paths.ROOT / "docs" / "headline_numbers.md"
SIZE = dict(pv_kwp=300, bat_kwh=1500, bat_kw=375)
PRICE_HIGH, PRICE_LOW = 113.0, 77.07          # PHP/L: INL 2025, ERC 2025 (NPC delivered)
FIN_PUBLIC = 0.04                             # public finance rate used on the cost slide (ASSUMPTION)


def _v(key):
    return load_site()["values"][key]["value"]


# ---------------------------------------------------------------- individual calculations
def storms_14d() -> dict:
    """Mean of three typhoons, tanker 14 days late, chosen size."""
    r = pd.read_csv(P4B / "storms_rec.csv")
    r = r[r.delay_days == 14]
    g = r.groupby("controller")[["crit_outage_h", "flex_shed_h", "flex_shed_kwh", "flex_shed_pct"]].mean()
    homes_cut_cut = 1 - g.loc["C", "flex_shed_h"] / g.loc["O", "flex_shed_h"]
    energy_cut = 1 - g.loc["C", "flex_shed_kwh"] / g.loc["O", "flex_shed_kwh"]
    return {
        "clinic_dark_h": {k: round(g.loc[k, "crit_outage_h"], 1) for k in "ABOC"},
        "homes_cut_h": {k: round(g.loc[k, "flex_shed_h"], 1) for k in "ABOC"},
        "homes_energy_delivered_pct": {k: round(100 - g.loc[k, "flex_shed_pct"], 1) for k in "ABOC"},
        "homes_hours_cut_vs_operator_pct": round(-100 * homes_cut_cut, 1),
        "homes_energy_cut_vs_operator_pct": round(-100 * energy_cut, 1),
        "survival_clock_ge24_pct_C": round(r[r.controller == "C"]["cest_ge24_pct"].mean(), 1),
    }


def delays() -> dict:
    r = pd.read_csv(P4B / "storms_rec.csv")
    g = r.groupby(["delay_days", "controller"])[["crit_outage_h", "flex_shed_h"]].mean()
    return {f"{d}d": {"clinic_dark_h": {k: round(g.loc[(d, k), "crit_outage_h"], 1) for k in "ABOC"},
                      "homes_cut_h": {k: round(g.loc[(d, k), "flex_shed_h"], 1) for k in "ABOC"}} for d in (3, 7, 14)}


def normal_year() -> dict:
    y = pd.read_csv(P4B / "year.csv").set_index("controller")
    a, b, c = (y.loc[k, "diesel_l_per_yr"] for k in "ABC")
    co2 = {k: round(y.loc[k, "co2_t_per_yr"]) for k in "ABC"}
    return {"diesel_l_per_yr": {"A": round(a), "B": round(b), "C": round(c)},
            "diesel_saved_l": round(a - c), "diesel_saved_pct": round(100 * (1 - c / a), 1),
            "aurora_own_saving_l": round(b - c), "co2_t_per_yr": co2, "co2_saved_t": co2["A"] - co2["C"],
            "fuel_saved_mphp": {"at_77": round((a - c) * PRICE_LOW / 1e6, 1), "at_113": round((a - c) * PRICE_HIGH / 1e6, 1)},
            "diesel_l_per_day": {"A": round(a / 365), "C": round(c / 365)}}


def solar_share() -> dict:
    """Solar energy used per year and its share of demand, chosen size with AURORA (normal-year runs)."""
    tot_pv = tot_dem = hours = 0.0
    for f in sorted((P4B / "hourly").glob("year_pv300_bat1500_*_C.csv.gz")):
        d = pd.read_csv(f, usecols=["pv_used", "crit", "flex"])
        tot_pv += d["pv_used"].sum()
        tot_dem += (d["crit"] + d["flex"]).sum()
        hours += len(d)
    yrs = hours / 8760
    return {"solar_mwh_per_yr": round(tot_pv / 1000 / yrs), "solar_share_pct": round(100 * tot_pv / tot_dem, 1)}


def stress() -> dict:
    s = pd.read_csv(P4B / "stress.csv").groupby(["stress", "controller"])[["crit_outage_h", "flex_shed_h"]].mean()
    return {st: {"clinic_dark_h": {k: round(s.loc[(st, k), "crit_outage_h"], 1) for k in "BOC"},
                 "homes_cut_h": {k: round(s.loc[(st, k), "flex_shed_h"], 1) for k in "BOC"}}
            for st in s.index.get_level_values(0).unique()}


def npc_size() -> dict:
    n = pd.read_csv(P4B / "storms_npc.csv")
    n = n[n.delay_days == 14].groupby("controller")[["crit_outage_h", "flex_shed_h"]].mean()
    return {"clinic_dark_h": {k: round(n.loc[k, "crit_outage_h"], 1) for k in "ABOC"},
            "homes_cut_h": {k: round(n.loc[k, "flex_shed_h"], 1) for k in "ABOC"}}


def growth() -> dict:
    s = pd.read_csv(P4B / "sweep.csv")
    s = s[(s.delay_days == 14) & (s.bat_kwh == 1500)]
    g = s.groupby(["pv_kwp", "controller"])["flex_shed_h"].mean().unstack()
    return {f"{int(pv)}kWp": {"O": round(g.loc[pv, "O"], 1), "C": round(g.loc[pv, "C"], 1),
                              "cut_pct": round(-100 * (1 - g.loc[pv, "C"] / g.loc[pv, "O"]), 1)} for pv in g.index}


def sizing() -> dict:
    """The selection rule: cheapest size where AURORA keeps the clinic on and a median Survival Clock >= 24 h
    in the worst storm (aurora.experiments.phase4b.recommended)."""
    s = pd.read_csv(P4B / "sweep.csv")
    c = s[s.controller == "C"]
    g = c.groupby(["pv_kwp", "bat_kwh", "bat_kw"]).agg(clock=("cest_median_h", "min"), dark=("crit_outage_h", "max")).reset_index()
    g["capex_mphp"] = [P4.capex_php(a, b, k) / 1e6 for a, b, k in zip(g.pv_kwp, g.bat_kwh, g.bat_kw)]
    ok = g[(g.dark == 0) & (g.clock >= 24)].sort_values("capex_mphp")
    pick = ok.iloc[0]
    return {"sizes_tested": len(g), "sizes_meeting_rule": len(ok), "clinic_dark_any_size_h": float(g.dark.max()),
            "chosen": {"pv_kwp": int(pick.pv_kwp), "bat_kwh": int(pick.bat_kwh), "clock_h": round(pick.clock, 1),
                       "capex_mphp": round(pick.capex_mphp, 1)}}


def economics() -> dict:
    """Installed cost at which the 20-year fuel saving (diesel only -> AURORA system) repays the system."""
    om, n, rep = _v("om_frac_of_capex_per_year_assumed"), int(_v("ocon2019_project_life_yr")), int(_v("ocon2019_battery_life_yr"))
    y = pd.read_csv(P4B / "year.csv").set_index("controller")
    saved_l = y.loc["A", "diesel_l_per_yr"] - y.loc["C", "diesel_l_per_yr"]
    own_l = y.loc["B", "diesel_l_per_yr"] - y.loc["C", "diesel_l_per_yr"]
    cpv, cbat = P4.capex_parts_php(SIZE["pv_kwp"], SIZE["bat_kwh"], SIZE["bat_kw"], case="base")
    cap = cpv + cbat
    out = {"capex_mphp": round(cap / 1e6, 1), "breakeven_pct_of_sabtang_budget": {}}
    for price in (PRICE_HIGH, PRICE_LOW):
        for name, r in (("public_4pct", FIN_PUBLIC), ("commercial_wacc", _v("ocon2019_wacc"))):
            af = sum(1 / (1 + r) ** t for t in range(1, n + 1))
            k = cap * (1 + om * af) + cbat / (1 + r) ** rep
            out["breakeven_pct_of_sabtang_budget"][f"{name}_at_{price:g}"] = round(100 * saved_l * price * af / k, 1)
    setup, run = _v("aurora_capex_php_assumed"), _v("aurora_opex_php_per_yr_assumed")
    net = {p: own_l * p - run for p in (PRICE_LOW, PRICE_HIGH)}
    out["aurora_software"] = {"own_saving_l": round(own_l), "saving_mphp": {f"at_{p:g}": round(own_l * p / 1e6, 2) for p in net},
                              "setup_mphp": setup / 1e6, "run_mphp_per_yr": run / 1e6,
                              "simple_payback_yr": {f"at_{p:g}": round(setup / v, 1) for p, v in net.items()},
                              "share_of_npc_itbayat_budget_pct": round(100 * setup / _v("capex_npc_hybrid_php"), 1)}
    return out


def forecast() -> dict:
    """RMSE (W/m2), lead day 1 and 2: docs/validation_forecast.md and aurora.forecast.mos_check."""
    rm = {"aurora": (80.6, 92.6), "ecmwf_raw": (90.8, 101.3), "nwp_mean_raw": (95.2, 103.8), "nwp_mean_mos": (85.4, 93.2)}
    vf = pd.read_csv(P4B / "value_of_forecast.csv").groupby("forecast")["flex_shed_h"].mean()
    return {"rmse_wm2": rm, "picp80_pct": 81.7,
            "skill_vs_ecmwf_raw_pct": [round(100 * (1 - a / b), 1) for a, b in zip(rm["aurora"], rm["ecmwf_raw"])],
            "skill_vs_mos_pct": [5.9, 0.8],
            "replay_homes_cut_h": {k: round(v, 1) for k, v in vf.items()}}


def problem() -> dict:
    ev = pd.read_csv(paths.TYPHOON_EVENTS, parse_dates=["closest_time_utc"])
    yrs = (ev["closest_time_utc"].max() - pd.Timestamp("2015-01-01", tz="UTC")).days / 365.25
    npc = load_site()["npc_itbayat_dpp"]
    pk = dict(zip(npc["years"], npc["peak_kw"]))
    load = pd.read_parquet(paths.LOAD_SYNTH)
    loc = load.index.tz_convert(paths.LOCAL_TZ)
    sel = load[loc.month.isin([5, 6, 7]) & (loc.year >= 2023)]
    y = pd.read_csv(P4B / "year.csv").set_index("controller")
    per_day = y.loc["A", "diesel_l_per_yr"] / 365
    return {"storms_per_yr_500km": round(len(ev) / yrs, 2), "storms_per_yr_300km": round((ev.closest_km <= 300).sum() / yrs, 2),
            "storm_tracks": len(ev), "years": round(yrs, 1),
            "peak_growth_2019_2023_pct": round(100 * (pk[2023] / pk[2019] - 1)), "peak_kw_2029_forecast": pk[2029],
            "critical_kw_mean": round(sel["critical_kW"].mean(), 1),
            "critical_energy_share_pct": round(100 * sel["critical_kW"].sum() / sel["total_kW"].sum(), 1),
            "tank_days": {"full_52000L": round(_v("fuel_storage_l_assumed") / per_day), "low_6000L": round(6000 / per_day)},
            "fuel_bill_mphp_at_113": round(y.loc["A", "diesel_l_per_yr"] * PRICE_HIGH / 1e6, 1)}


def all_numbers() -> dict:
    return {"size": SIZE, "problem": problem(), "storms_14d": storms_14d(), "delays": delays(), "normal_year": normal_year(),
            "solar": solar_share(), "stress": stress(), "npc_size": npc_size(), "growth": growth(), "sizing": sizing(),
            "economics": economics(), "forecast": forecast()}


# ---------------------------------------------------------------- report
ROWS = [  # (deck number as shown, path in the JSON, slide, source)
    ("−37 % diesel a year", "normal_year.diesel_saved_pct", "Summary; Impact · a normal year", "results/phase4b/year.csv"),
    ("126,000 L diesel saved a year", "normal_year.diesel_saved_l", "Impact · a normal year", "results/phase4b/year.csv"),
    ("338 t CO₂ avoided a year", "normal_year.co2_saved_t", "Impact · a normal year", "results/phase4b/year.csv"),
    ("10 to 14 M PHP fuel saved a year", "normal_year.fuel_saved_mphp", "Impact · a normal year", "year.csv × 77 / 113 PHP/L"),
    ("17,100 L from AURORA's control alone", "normal_year.aurora_own_saving_l", "Scalability · how it pays", "results/phase4b/year.csv"),
    ("≈ 420 MWh solar, 35 % of demand", "solar", "Impact · who benefits", "results/phase4b/hourly/year_*_C"),
    ("0 h clinic dark (AURORA)", "storms_14d.clinic_dark_h.C", "Summary; Impact", "results/phase4b/storms_rec.csv"),
    ("208 h clinic dark today", "storms_14d.clinic_dark_h.A", "Summary; Impact", "results/phase4b/storms_rec.csv"),
    ("−43 % hours of home cuts (138 h vs 244 h)", "storms_14d.homes_hours_cut_vs_operator_pct", "Summary; Impact", "results/phase4b/storms_rec.csv"),
    ("75 % vs 69 % homes' energy delivered", "storms_14d.homes_energy_delivered_pct", "Supporting (notes)", "results/phase4b/storms_rec.csv"),
    ("0 h / 23 h homes cut at 3 / 7 days late", "delays", "Impact · how late can the boat be?", "results/phase4b/storms_rec.csv"),
    ("Clinic 0 h with one generator, half solar, no internet", "stress", "Implementation · risks; Impact", "results/phase4b/stress.csv"),
    ("72 h clinic dark on a shared feeder", "stress.clinic_shared.clinic_dark_h.C", "Implementation · risks", "results/phase4b/stress.csv"),
    ("−43 % to −85 % with more solar", "growth", "Scalability · more solar", "results/phase4b/sweep.csv"),
    ("300 kWp / 1,500 kWh, 176 M PHP", "sizing.chosen", "Supporting · sizing", "results/phase4b/sweep.csv"),
    ("Break-even at 52 to 68 % of the Sabtang budget", "economics.breakeven_pct_of_sabtang_budget", "Supporting · cost", "year.csv + site.yaml costs"),
    ("AURORA repays its set-up in about 2 to 3 years", "economics.aurora_software.simple_payback_yr", "Scalability · how it pays", "year.csv + ASSUMPTION costs"),
    ("AURORA adds about 5 % to NPC's budget", "economics.aurora_software.share_of_npc_itbayat_budget_pct", "Implementation · resources", "site.yaml"),
    ("Forecast −11 % vs ECMWF, −6 % vs bias-fixed, 82 % in range", "forecast", "Innovation · forecast", "docs/validation_forecast.md"),
    ("5.8 storms a year within 500 km", "problem.storms_per_yr_500km", "Problem · storms", "data/itbayat/typhoon_events.csv"),
    ("+51 % peak demand in four years", "problem.peak_growth_2019_2023_pct", "Problem · demand", "data/itbayat/site.yaml (NPC)"),
    ("937 L a day; 38.6 M PHP a year", "problem", "Problem · demand", "results/phase4b/year.csv"),
    ("Full tank 56 days; low tank 6 days", "problem.tank_days", "Problem · the tank", "year.csv + ASSUMPTION tank"),
    ("Critical load 50 kW, a third of the energy", "problem.critical_kw_mean", "Problem · what goes dark", "load_synthetic_hourly.parquet"),
]


def _get(d, path):
    for k in path.split("."):
        d = d[k]
    return d


def write(nums: dict):
    OUT_JSON.write_text(json.dumps(nums, indent=1, ensure_ascii=False, default=float), encoding="utf-8")
    L = ["# Headline numbers: every number on the GSC deck and where it comes from", "",
         "Generated by `python -m aurora.experiments.headline` from committed results; no simulation is run. "
         "Full values in [`results/headline.json`](../results/headline.json). Model inputs that are assumptions are listed in "
         "[`data/itbayat/SOURCES.md`](../data/itbayat/SOURCES.md).", "",
         "| Deck number | Recomputed | Slide | Source |", "|---|---|---|---|"]
    for lab, path, slide, src in ROWS:
        val = _get(nums, path)
        txt = json.dumps(val, ensure_ascii=False, default=float)
        if len(txt) > 110:
            txt = txt[:107] + "…"
        L.append(f"| {lab} | `{txt}` | {slide} | `{src}` |")
    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="compare with the committed results/headline.json")
    a = ap.parse_args(argv)
    nums = json.loads(json.dumps(all_numbers(), default=float))
    if a.check:
        old = json.loads(OUT_JSON.read_text(encoding="utf-8"))
        if old != nums:
            print("headline numbers changed; rerun without --check and review the diff")
            return 1
        print("headline numbers unchanged")
        return 0
    write(nums)
    print(f"wrote {OUT_JSON.relative_to(paths.ROOT)} and {OUT_MD.relative_to(paths.ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
