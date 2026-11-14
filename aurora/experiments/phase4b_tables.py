"""Phase 4b tables and the impact numbers for the deck.

    python -m aurora.experiments.phase4b tables

Writes results/phase4b/*.csv, impact.json and tables.md from the committed job
files. Controllers: A diesel only, B solar + battery with the simple rule,
O the same with a rationing operator, C AURORA. Model v2 (see phase4b.py).
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from ..data.site import load_site, value
from . import phase4 as P4
from .phase4b import OUT, load_rows, recommended

NAMES = {"A": "Diesel only", "B": "Solar + battery, simple rule", "O": "Solar + battery, rationing operator",
         "C": "AURORA"}
COLS = ["crit_outage_h", "crit_unserved_kwh", "flex_shed_h", "flex_shed_kwh", "flex_shed_pct", "diesel_l",
        "tank_min_l", "cest_median_h", "cest_ge24_pct", "relaxed_steps"]


def _md(df, floatfmt="{:,.1f}"):
    def f(x):
        if isinstance(x, (float, np.floating)):
            return floatfmt.format(x) if np.isfinite(x) else ""
        return str(x)
    head = "| " + " | ".join(map(str, df.columns)) + " |\n|" + "---|" * len(df.columns) + "\n"
    return head + "".join("| " + " | ".join(f(v) for v in r) + " |\n" for r in df.itertuples(index=False))


def storm_table(rows, group):
    d = rows[rows["group"] == group]
    if d.empty:
        return d
    return d[["storm", "delay_days", "controller"] + COLS].sort_values(["storm", "delay_days", "controller"])


def year_table(rows):
    d = rows[rows["group"] == "year"]
    if d.empty:
        return d, d
    num = ["hours", "diesel_l", "co2_t", "fuel_cost_mphp", "flex_shed_kwh", "flex_shed_h", "crit_outage_h"]
    per = d.groupby(["period", "controller"])[num].sum().reset_index()
    per["diesel_l_per_yr"] = per["diesel_l"] * 8760 / per["hours"]
    per["co2_t_per_yr"] = per["co2_t"] * 8760 / per["hours"]
    per["fuel_cost_mphp_per_yr"] = per["fuel_cost_mphp"] * 8760 / per["hours"]
    # CEST: hour-weighted over chunks
    d = d.assign(w=d["hours"])
    c = d.groupby(["period", "controller"]).apply(
        lambda g: pd.Series({"cest_median_h": np.average(g["cest_median_h"], weights=g["w"]),
                             "cest_ge24_pct": np.average(g["cest_ge24_pct"], weights=g["w"])}),
        include_groups=False).reset_index()
    per = per.merge(c, on=["period", "controller"])
    mean = per.groupby("controller")[["diesel_l_per_yr", "co2_t_per_yr", "fuel_cost_mphp_per_yr", "cest_median_h",
                                      "cest_ge24_pct", "crit_outage_h", "flex_shed_h"]].mean().reset_index()
    return per, mean


def impact(rows, rec) -> dict:
    s = load_site()
    st = storm_table(rows, "rec")
    d14 = st[st["delay_days"] == 14]
    piv = lambda col: d14.pivot(index="storm", columns="controller", values=col)  # noqa: E731
    out = dict(model="v2", size=dict(pv_kwp=int(rec.pv_kwp), bat_kwh=int(rec.bat_kwh), bat_kw=float(rec.bat_kw),
                                     capex_mphp_base=round(float(rec.capex_mphp), 1),
                                     meets_target=bool(rec.meets_target)))
    if not d14.empty:
        for col, key in (("crit_outage_h", "clinic_dark_h"), ("flex_shed_h", "homes_cut_h"),
                         ("flex_shed_pct", "homes_energy_cut_pct"), ("cest_median_h", "survival_median_h"),
                         ("diesel_l", "diesel_l")):
            p = piv(col)
            out[f"storm14_{key}"] = {c: {k: float(v) for k, v in p[c].items()} for c in p.columns}
            out[f"storm14_{key}_mean"] = {c: round(float(p[c].mean()), 1) for c in p.columns}
    stress = rows[rows["group"].str.startswith("stress-")]
    if not stress.empty:
        g = stress.groupby(["stress", "controller"]).agg(clinic_dark_h_max=("crit_outage_h", "max"),
                                                          clinic_dark_h_mean=("crit_outage_h", "mean"),
                                                          homes_cut_h_mean=("flex_shed_h", "mean")).reset_index()
        out["stress"] = g.to_dict(orient="records")
    _, ym = year_table(rows)
    if not ym.empty:
        y = ym.set_index("controller")
        a, c = y.loc["A"], y.loc["C"]
        price = float(value(s, "diesel_price_php_per_l"))
        out["year"] = dict(diesel_l={k: round(float(v)) for k, v in y["diesel_l_per_yr"].items()},
                           co2_t={k: round(float(v)) for k, v in y["co2_t_per_yr"].items()},
                           survival_median_h={k: round(float(v), 1) for k, v in y["cest_median_h"].items()},
                           diesel_saved_l_A_to_C=round(float(a.diesel_l_per_yr - c.diesel_l_per_yr)),
                           co2_saved_t_A_to_C=round(float(a.co2_t_per_yr - c.co2_t_per_yr)),
                           fuel_saved_mphp_A_to_C=round(float((a.diesel_l_per_yr - c.diesel_l_per_yr) * price / 1e6), 1),
                           diesel_price_php_per_l=price)
    out["population"] = int(value(s, "population")) if "population" in load_site()["values"] else None
    return out


def write_all():
    rows = load_rows()
    if rows.empty:
        raise SystemExit("no Phase 4b jobs yet: run python -m aurora.experiments.phase4b run --stage A")
    OUT.mkdir(parents=True, exist_ok=True)
    md = ["# Phase 4b results (model v2)\n",
          "Controllers: " + "; ".join(f"**{k}** {v}" for k, v in NAMES.items()) + ".\n",
          "Inputs are not measurements: ERA5 weather, pvlib PV, SYNTHETIC load with critical-demand variability. "
          "CEST is capped at 72 h (≥72 h).\n"]
    sw = rows[rows["group"] == "sweep"]
    if not sw.empty:
        sw.to_csv(OUT / "sweep.csv", index=False)
        rec = recommended(sw)
        md += [f"## Chosen size\n\n{int(rec.pv_kwp)} kWp PV, {rec.bat_kw:.0f} kW / {int(rec.bat_kwh)} kWh battery, "
               f"base capex {rec.capex_mphp:.0f} M PHP. Criterion met on all three storms: {bool(rec.meets_target)} "
               f"(AURORA worst-case clinic outage {rec.worst_outage_h:.0f} h, lowest median CEST "
               f"{rec.min_cest_median_h:.0f} h).\n"]
        # battery needed by each controller for 0 h in all storms at the chosen PV size
        need = []
        for c in ("B", "O", "C"):
            g = sw[(sw.controller == c) & (sw.pv_kwp == rec.pv_kwp)].groupby("bat_kwh")["crit_outage_h"].max()
            okb = g[g == 0]
            need.append(dict(controller=c, name=NAMES[c], battery_kwh_for_0h=int(okb.index.min()) if len(okb) else None,
                             worst_outage_h_at_chosen=int(g.get(rec.bat_kwh, np.nan))))
        nd = pd.DataFrame(need)
        nd.to_csv(OUT / "battery_needed.csv", index=False)
        md += ["### Battery each strategy needs for 0 h clinic outage in all three storms (14 days late)\n",
               _md(nd), ""]
    else:
        rec = None
    for grp, title in (("rec", "Storms at the chosen size"), ("inl", "Storms at the INL size (300 kWp / 300 kWh)")):
        t = storm_table(rows, grp)
        if not t.empty:
            t.to_csv(OUT / f"storms_{grp}.csv", index=False)
            md += [f"## {title}\n", _md(t), ""]
    st = rows[rows["group"].str.startswith("stress-")]
    if not st.empty:
        t = st[["stress", "storm", "controller"] + COLS].sort_values(["stress", "storm", "controller"])
        t.to_csv(OUT / "stress.csv", index=False)
        md += ["## Stress tests (chosen size, tanker 14 days late)\n", _md(t), ""]
    v = rows[rows["group"] == "vof"]
    if not v.empty:
        t = pd.concat([v, rows[(rows["group"] == "rec") & (rows["delay_days"] == 14) & (rows["controller"] == "C")]])
        t = t[["storm", "forecast"] + COLS].sort_values(["storm", "forecast"])
        t.to_csv(OUT / "value_of_forecast.csv", index=False)
        md += ["## Value of forecasting (AURORA, 14 days late)\n", _md(t), ""]
    per, mean = year_table(rows)
    if not per.empty:
        per.to_csv(OUT / "year_by_period.csv", index=False)
        mean.to_csv(OUT / "year.csv", index=False)
        md += ["## Normal years, chosen size (mean of Nov 2024 to Oct 2025 and Nov 2025 to Oct 2026)\n", _md(mean), ""]
    if rec is not None and not storm_table(rows, "rec").empty:
        imp = impact(rows, rec)
        (OUT / "impact.json").write_text(json.dumps(imp, indent=1), encoding="utf-8")
    (OUT / "tables.md").write_text("\n".join(md), encoding="utf-8")
    print("wrote", OUT / "tables.md")
