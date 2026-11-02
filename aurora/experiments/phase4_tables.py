"""Phase 4 tables from results/phase4/jobs/*.json and hourly/*.csv.gz.

Writes results/phase4/{storms,vof,decomposition,decomp_forecast_bias,year,sweep,
sweep_marginal_cest,recommended,sensitivity,rec_storms,costs}.csv, tables.md and
the trade-off figure results/phase4/tradeoff_shed_vs_outage.{pdf,png}.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..data.site import load_site
from ..plotting import style
from ..twin import forecasts, inputs, params
from . import phase4 as P

OUT = P.OUT
STORM_COLS = ["crit_outage_h", "crit_unserved_kwh", "flex_shed_kwh", "diesel_l", "fuel_cost_mphp",
              "cest_median_h", "cest_min_h", "tank_min_l"]


def md(df: pd.DataFrame, floatfmt=None) -> str:
    def f(x):
        if isinstance(x, (float, np.floating)):
            if np.isnan(x):
                return ""
            if abs(x) >= 100:
                return f"{x:,.0f}"
            return f"{x:.1f}" if floatfmt is None else format(x, floatfmt)
        return str(x)
    head = "| " + " | ".join(map(str, df.columns)) + " |"
    sep = "|" + "---|" * len(df.columns)
    return "\n".join([head, sep] + ["| " + " | ".join(f(v) for v in r) + " |" for r in df.itertuples(index=False)])


def storms_table():
    st = P.select_storms()
    d = P.load_rows("storm_")
    d["regime"] = d["storm"].map(st["forecast_regime"])
    t = d[["storm", "regime", "sizing", "delay_days", "controller"] + STORM_COLS]
    t = t.sort_values(["storm", "sizing", "delay_days", "controller"], key=_storm_order)
    t.to_csv(OUT / "storms.csv", index=False)
    return t


def _storm_order(s):
    order = {"mawar2023": 0, "ragasa2025": 1, "mekkhala2026": 2, "inl": 0, "case": 1}
    return s.map(lambda x: order.get(x, x))


def vof_table():
    d = pd.concat([P.load_rows("storm_"), P.load_rows("vof_")])
    d = d[d["controller"] == "C"].copy()
    d["forecast"] = d["forecast"].replace({"phase2": "phase2 (AURORA)", "phase2_nwp": "raw NWP mean",
                                           "phase2_persistence": "smart persistence", "perfect": "perfect"})
    cols = ["crit_outage_h", "flex_shed_kwh", "diesel_l", "cest_median_h", "cest_min_h", "fallback_steps"]
    t = d[["storm", "sizing", "delay_days", "forecast"] + cols].sort_values(
        ["storm", "sizing", "delay_days", "forecast"], key=_storm_order)
    t.to_csv(OUT / "vof.csv", index=False)
    agg = t.groupby(["storm", "forecast"], sort=False)[["crit_outage_h", "flex_shed_kwh", "diesel_l",
                                                         "cest_median_h"]].sum().reset_index()
    agg = agg.rename(columns={"cest_median_h": "sum_of_cest_medians_h"})
    agg.to_csv(OUT / "vof_by_storm.csv", index=False)
    return t, agg


def decomposition_table():
    d = P.load_rows("decomp_")
    out = []
    for r in d.itertuples():
        h = pd.read_csv(P.HOURLY / f"{r.job}_C.csv.gz", index_col=0, parse_dates=True)
        sh = h[h["shed"] > 1e-3]
        loc = h.index.tz_convert("Asia/Manila")
        by_day = h["shed"].groupby(loc.date).sum()
        out.append(dict(forecast=r.forecast, flex_shed_kwh=r.flex_shed_kwh, diesel_l=r.diesel_l,
                        crit_outage_h=r.crit_outage_h, cest_median_h=r.cest_median_h,
                        first_shed_local=str(sh.index[0].tz_convert("Asia/Manila"))[:16] if len(sh) else "",
                        shed_hours=int(len(sh)), tank_min_l=r.tank_min_l,
                        shed_by_day_kwh=" ".join(f"{v:.0f}" for v in by_day.to_numpy())))
    t = pd.DataFrame(out)
    t.to_csv(OUT / "decomposition.csv", index=False)
    return t


def decomp_forecast_bias():
    """Mean daily bias of what the MPC sees, per daily issue in the Mawar 7-day window, INL sizing."""
    st = P.select_storms()
    t0 = P.local_utc(st.loc["mawar2023", "start"])
    days = P.storm_days(7)
    truth = inputs.build(t0 - pd.Timedelta(days=35), t0 + pd.Timedelta(days=days + 3))
    p = params.from_site("inl")
    fcs = {"persistence": forecasts.PersistenceForecast(truth, p.pv_kwp),
           "phase2": forecasts.Phase2Forecast(truth, p.pv_kwp)}
    rows = []
    issues = [t0 - pd.Timedelta(hours=8) + pd.Timedelta(days=k) for k in range(days)]   # 16:00 UTC
    for name, f in fcs.items():
        acc = []
        for it in issues:
            fc = f(it, 48)
            tr = truth.reindex(fc.index)
            sol = tr["pv_kw_per_kwp"] * p.pv_kwp
            acc.append(dict(solar_p50=(fc["solar_kW_p50"] - sol).sum(), solar_p10=(fc["solar_kW_p10"] - sol).sum(),
                            crit_p50=(fc["demand_critical_kW_p50"] - tr["crit_kW"]).sum(),
                            crit_p90=(fc["demand_critical_kW_p90"] - tr["crit_kW"]).sum(),
                            flex_p50=(fc["demand_flex_kW_p50"] - tr["flex_kW"]).sum(),
                            solar_actual=sol.sum(), fallback_h=int(fc["fallback"].sum())))
        a = pd.DataFrame(acc)
        rows.append(dict(forecast=name, **{f"{k}_bias_kwh_per_day": round(a[k].mean() / 2, 0)
                                           for k in ("solar_p50", "solar_p10", "crit_p50", "crit_p90", "flex_p50")},
                         solar_actual_kwh_per_day=round(a["solar_actual"].mean() / 2, 0),
                         solar_p50_mae_kwh_per_day=round(np.abs(a["solar_p50"]).mean() / 2, 0),
                         fallback_h=int(a["fallback_h"].sum())))
    t = pd.DataFrame(rows)
    t.to_csv(OUT / "decomp_forecast_bias.csv", index=False)
    return t


def year_table():
    d = P.load_rows("year_")
    p = params.from_site("inl")
    out = []
    for (sz, c), g in d.groupby(["sizing", "controller"], sort=False):
        p0 = g.iloc[0]
        for per, gp in g.groupby("period"):
            h = pd.concat([pd.read_csv(P.HOURLY / f"{j}_{c}.csv.gz", index_col=0, parse_dates=True)
                           for j in sorted(gp["job"])])
            k = 8760.0 / len(h)
            served = (h["crit"] - h["unserved_crit"] + h["flex"] - h["shed"]).sum()
            has_bat = p0["bat_kwh"] > 0 and c != "A"
            ce = h["cest_h"] if has_bat else pd.Series(0.0, index=h.index)
            fuel = h["fuel_l"].sum() * k
            out.append(dict(sizing=sz, pv_kwp=p0["pv_kwp"], bat_kwh=p0["bat_kwh"], controller=c, period=per,
                            hours=len(h), diesel_l_per_yr=fuel, fuel_cost_mphp_per_yr=fuel * p.diesel_php_per_l / 1e6,
                            co2_t_per_yr=fuel * p.co2_kg_per_l / 1000,
                            renewable_share_pct=100 * (1 - h["diesel"].sum() / served),
                            crit_outage_h=int((h["unserved_crit"] > 1e-3).sum()),
                            flex_shed_mwh_per_yr=h["shed"].sum() * k / 1000,
                            curtail_mwh_per_yr=h["curtail"].sum() * k / 1000,
                            battery_throughput_mwh_per_yr=h["discharge"].sum() * k / 1000,
                            cycles_per_yr=h["discharge"].sum() * k / p0["bat_kwh"] if has_bat else 0.0,
                            cest_p10_h=ce.quantile(0.1), cest_p25_h=ce.quantile(0.25), cest_median_h=ce.median(),
                            cest_p75_h=ce.quantile(0.75), cest_p90_h=ce.quantile(0.9), cest_min_h=ce.min(),
                            cest_ge12_pct=100 * (ce >= 12).mean(), cest_ge24_pct=100 * (ce >= 24).mean(),
                            relaxed_steps=int(h["relaxed"].sum())))
    t = pd.DataFrame(out)
    t.to_csv(OUT / "year_by_period.csv", index=False)
    num = [c for c in t.columns if c not in ("sizing", "controller", "period", "pv_kwp", "bat_kwh")]
    g = t.groupby(["sizing", "pv_kwp", "bat_kwh", "controller"], sort=False)[num]
    mean, lo, hi = g.mean(), g.min(), g.max()
    summ = mean.copy()
    for c in ("diesel_l_per_yr", "renewable_share_pct", "cest_median_h"):
        summ[c + "_lo"], summ[c + "_hi"] = lo[c], hi[c]
    summ["crit_outage_h"] = g["crit_outage_h"].sum()
    summ = summ.reset_index()
    summ.to_csv(OUT / "year.csv", index=False)
    return t, summ


def sweep_table():
    d = P.load_rows("sweep_")
    d["capex_musd"] = [P.capex_usd(a, b, k) / 1e6 for a, b, k in zip(d.pv_kwp, d.bat_kwh, d.bat_kw)]
    t = d[["controller", "pv_kwp", "bat_kwh", "bat_kw", "capex_musd", "crit_outage_h", "flex_shed_kwh", "diesel_l",
           "cest_median_h", "cest_min_h", "cest_ge24_pct"]].sort_values(["controller", "pv_kwp", "bat_kwh"])
    t.to_csv(OUT / "sweep.csv", index=False)
    # marginal median CEST per extra battery step, at each PV size
    m = t.sort_values(["controller", "pv_kwp", "bat_kwh"]).copy()
    m["d_cest_median_h"] = m.groupby(["controller", "pv_kwp"])["cest_median_h"].diff()
    m["d_bat_kwh"] = m.groupby(["controller", "pv_kwp"])["bat_kwh"].diff()
    m["cest_h_per_100kwh"] = 100 * m["d_cest_median_h"] / m["d_bat_kwh"]
    m[["controller", "pv_kwp", "bat_kwh", "cest_median_h", "cest_h_per_100kwh"]].to_csv(
        OUT / "sweep_marginal_cest.csv", index=False)
    r = P.recommended(d)
    rec = pd.DataFrame([dict(pv_kwp=r.pv_kwp, bat_kwh=r.bat_kwh, bat_kw=r.bat_kw, capex_musd=r.capex_musd,
                             crit_outage_h=r.crit_outage_h, cest_median_h=r.cest_median_h,
                             flex_shed_kwh=r.flex_shed_kwh, diesel_l=r.diesel_l)])
    rec.to_csv(OUT / "recommended.csv", index=False)
    return t, m, rec


def pivot(t, ctl, col):
    x = t[t["controller"] == ctl].pivot(index="pv_kwp", columns="bat_kwh", values=col)
    x.columns = [f"{int(c)} kWh" for c in x.columns]
    x.index = [f"{int(i)} kWp" for i in x.index]
    return x.reset_index().rename(columns={"index": "PV \\ battery"})


def sensitivity_table():
    d = P.load_rows("sens_")
    if d.empty:
        return None
    t = d[["label", "controller"] + STORM_COLS].copy()
    order = [j["label"] for j in P.sensitivity_jobs("2023-05-27", 0, 0)]
    t["o"] = t["label"].map(order.index)
    t = t.sort_values(["o", "controller"]).drop(columns="o")
    t.to_csv(OUT / "sensitivity.csv", index=False)
    return t


def rec_storms_table():
    d = P.load_rows("rec_")
    if d.empty:
        return None
    t = d[["storm", "delay_days", "controller"] + STORM_COLS].sort_values(
        ["storm", "delay_days", "controller"], key=_storm_order)
    t.to_csv(OUT / "rec_storms.csv", index=False)
    return t


def costs_table(year_summ):
    s = load_site()["values"]
    om = s["om_frac_of_capex_per_year_assumed"]["value"]
    usd = s["php_per_usd"]["value"]
    a = year_summ[year_summ["controller"] == "A"]["diesel_l_per_yr"].mean()     # A has no PV: same for all sizes
    rows = []
    for r in year_summ[year_summ["controller"].isin(["B", "C"])].itertuples():
        bat_kw = min(r.bat_kwh, s["sweep_battery_c_rate_cap_kw_assumed"]["value"]) if r.sizing.startswith("pv") \
            else params.from_site(r.sizing).bat_kw
        cap = {w: P.capex_usd(r.pv_kwp, r.bat_kwh, bat_kw, which=w) for w in ("value", "low", "high")}
        saved_l = a - r.diesel_l_per_yr
        for price in (65, 113, 140):
            sav = saved_l * price / usd                       # USD per year
            net = sav - om * cap["value"]
            rows.append(dict(sizing=r.sizing, pv_kwp=r.pv_kwp, bat_kwh=r.bat_kwh, bat_kw=bat_kw,
                             controller=r.controller, diesel_price_php_per_l=price,
                             capex_musd=cap["value"] / 1e6, capex_low_musd=cap["low"] / 1e6,
                             capex_high_musd=cap["high"] / 1e6, diesel_saved_l_per_yr=saved_l,
                             fuel_saving_musd_per_yr=sav / 1e6, om_musd_per_yr=om * cap["value"] / 1e6,
                             simple_payback_yr=cap["value"] / sav if sav > 0 else np.nan,
                             simple_payback_low_capex_yr=cap["low"] / sav if sav > 0 else np.nan,
                             simple_payback_high_capex_yr=cap["high"] / sav if sav > 0 else np.nan,
                             net_payback_with_om_yr=cap["value"] / net if net > 0 else np.nan))
    t = pd.DataFrame(rows)
    t.to_csv(OUT / "costs.csv", index=False)
    return t


def tradeoff_figure():
    st = P.load_rows("storm_")
    se = P.load_rows("sens_")
    style.apply()
    fig, ax = style.plt.subplots(figsize=(3.4, 2.6))
    oi = style.OKABE_ITO
    for c, col, mk in (("B", oi["orange"], "o"), ("C", oi["blue"], "s")):
        x = st[(st.controller == c) & (st.delay_days == 14)]
        ax.scatter(x.flex_shed_kwh / 1000, x.crit_outage_h, s=14, marker=mk, facecolors="none", edgecolors=col,
                   linewidths=0.8, label=f"{c}, storm runs (14-day delay)")
        if not se.empty:
            y = se[se.controller == c]
            ax.scatter(y.flex_shed_kwh / 1000, y.crit_outage_h, s=14, marker=mk, color=col,
                       label=f"{c}, sensitivity at recommended size")
    ax.set_xlabel("Flexible load shed (MWh)")
    ax.set_ylabel("Critical outage (h)")
    ax.legend(loc="upper right", fontsize=6)
    style.save(fig, OUT / "tradeoff_shed_vs_outage")


def write_all():
    OUT.mkdir(parents=True, exist_ok=True)
    parts = []
    t = storms_table()
    parts += ["## Storm runs (Phase 2 forecast)", md(t)]
    v, agg = vof_table()
    parts += ["## Value of forecasting (controller C)", md(v), "### Totals per storm", md(agg)]
    parts += ["## Mawar 7-day INL decomposition (64 scenarios)", md(decomposition_table()),
              "### Forecast bias over the window", md(decomp_forecast_bias())]
    yp, ys = year_table()
    parts += ["## Full years", md(yp.round(2)), "### Mean of the two years (lo/hi = year range)", md(ys.round(2))]
    sw, mg, rec = sweep_table()
    parts += ["## Sizing sweep (Mawar, 14-day delay)", "### C critical outage (h)", md(pivot(sw, "C", "crit_outage_h")),
              "### C median CEST (h)", md(pivot(sw, "C", "cest_median_h")),
              "### B critical outage (h)", md(pivot(sw, "B", "crit_outage_h")),
              "### B median CEST (h)", md(pivot(sw, "B", "cest_median_h")),
              "### C flexible shed (kWh)", md(pivot(sw, "C", "flex_shed_kwh")),
              "### Capex (MUSD)", md(pivot(sw, "C", "capex_musd"), ".2f"),
              "### Recommended", md(rec)]
    se = sensitivity_table()
    if se is not None:
        parts += ["## Sensitivity at the recommended size (Mawar, 14-day delay)", md(se)]
    rs = rec_storms_table()
    if rs is not None:
        parts += ["## Recommended size on all storms", md(rs)]
    parts += ["## Costs", md(costs_table(ys).round(2))]
    tradeoff_figure()
    (OUT / "tables.md").write_text("# Phase 4 tables (generated by aurora.experiments.phase4 tables)\n\n"
                                   + "\n\n".join(parts) + "\n", encoding="utf-8")
    print("wrote", OUT / "tables.md")
