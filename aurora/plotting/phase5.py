"""Phase 5 figures for the deck, from committed Phase 2 to 4 outputs (no simulation).

    python -m aurora.plotting.phase5

Writes figures/final/fig{a..h}_*.pdf and .png (300 dpi) and the small tables they
plot to results/phase5/. Style: CLAUDE.md (L-frame axes, outward ticks, no grid,
Okabe-Ito, panel labels A, B, C).

Inputs: results/phase4/*.csv and hourly/*.csv.gz, docs/validation_forecast.md
(skill table, parsed), data/itbayat/typhoon_events.csv and raw_small/ibtracs.
Load in every run is SYNTHETIC; weather truth is ERA5 reanalysis.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from ..data import paths
from . import style

P4 = paths.ROOT / "results" / "phase4"
OUT = paths.ROOT / "results" / "phase5"
FIG = paths.FIG_DIR / "final"
OI = style.OKABE_ITO
CTL = {"A": dict(color=OI["black"], ls="-", marker="o", label="A  diesel only"),
       "B": dict(color=OI["orange"], ls="--", marker="s", label="B  PV + battery, simple rule"),
       "C": dict(color=OI["blue"], ls="-", marker="^", label="C  AURORA")}
REC = "pv500_bat1000"
REC_LABEL = "500 kWp, 375 kW / 1,000 kWh"
STORMS = {"mawar2023": "Mawar 2023", "ragasa2025": "Ragasa 2025", "mekkhala2026": "Mekkhala 2026"}
CAP_H = 72.0
LOC = paths.LOCAL_TZ


def _plt():
    style.apply()
    import matplotlib.pyplot as plt
    return plt


def hourly(job, ctl):
    return pd.read_csv(P4 / "hourly" / f"{job}_{ctl}.csv.gz", index_col=0, parse_dates=True)


def _days(idx, t0):
    return (idx - t0) / pd.Timedelta(days=1)


# ---------------------------------------------------------------- (a) site and system
def fig_a_site_system():
    plt = _plt()
    ev = pd.read_csv(paths.SITE_DIR / "typhoon_events.csv", parse_dates=["closest_time_utc"])
    tr = pd.read_parquet(paths.SITE_DIR / "raw_small" / "ibtracs_wp_tracks.parquet")
    lat0, lon0 = paths.LAT, paths.LON
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.1), gridspec_kw={"width_ratios": [1.0, 1.15]})
    ax = axes[0]
    k = np.cos(np.radians(lat0))
    styles = {"MAWAR": (OI["orange"], "--"), "RAGASA": (OI["blue"], "-"), "MEKKHALA": (OI["purple"], ":")}
    rows = []
    for key, nm in (("mawar2023", "MAWAR"), ("ragasa2025", "RAGASA"), ("mekkhala2026", "MEKKHALA")):
        yr = int(key[-4:])
        e = ev[(ev["name"] == nm) & (ev["closest_time_utc"].dt.year == yr)].iloc[0]
        t = tr[tr["SID"] == e["sid"]].sort_index()
        c, ls = styles[nm]
        ax.plot(t["LON"], t["LAT"], color=c, ls=ls, lw=1.0, label=f"{STORMS[key]} (closest {e['closest_km']:.0f} km)")
        rows.append(dict(storm=key, sid=e["sid"], closest_km=e["closest_km"], min_pres_hpa=e["min_pres_hpa_within_500km"]))
    for r_km, ls in ((300, ":"), (500, "--")):
        th = np.linspace(0, 2 * np.pi, 200)
        dlat = r_km / 111.2 * np.sin(th)
        dlon = r_km / (111.2 * k) * np.cos(th)
        ax.plot(lon0 + dlon, lat0 + dlat, color="0.5", lw=0.6, ls=ls)
        ax.text(lon0 + r_km / (111.2 * k) * 0.71, lat0 + r_km / 111.2 * 0.71, f"{r_km} km", fontsize=6, color="0.35")
    ax.plot(lon0, lat0, marker="*", color="black", ms=9, zorder=5)
    ax.text(lon0 - 0.3, lat0 + 0.45, "Itbayat", fontsize=7, fontweight="bold", ha="right")
    bol = (119.9, 16.4)            # Bolinao, Pangasinan (approximate); tanker stranded there in two disruptions
    ax.plot(*bol, marker="D", color=OI["vermillion"], ms=4)
    ax.text(bol[0] + 0.35, bol[1] - 0.2, "Bolinao (approx.): tanker\nstranded in two disruptions", fontsize=6, va="top")
    ax.annotate("", xy=(lon0 - 0.1, lat0 - 0.15), xytext=(bol[0] + 0.1, bol[1] + 0.15),
                arrowprops=dict(arrowstyle="->", color=OI["vermillion"], lw=0.8, ls="--"))
    ax.set_xlim(115, 129)
    ax.set_ylim(13, 26)
    ax.set_aspect(1 / k)
    ax.set_xlabel("Longitude (°E)")
    ax.set_ylabel("Latitude (°N)")
    ax.legend(loc="upper left", fontsize=6, handlelength=2.2)
    ax.text(115.2, 13.3, "IBTrACS tracks; coastlines not shown", fontsize=5.5, color="0.35")
    style.panel_label(ax, "A")

    ax = axes[1]
    ax.set_xlim(-0.3, 10)
    ax.set_ylim(0, 7)
    ax.axis("off")

    def box(x, y, w, h, txt, c, **kw):
        ax.add_patch(plt.Rectangle((x, y), w, h, fill=False, ec=c, lw=1.0, **kw))
        ax.text(x + w / 2, y + h / 2, txt, ha="center", va="center", fontsize=5.8)

    box(0.0, 4.9, 3.0, 1.2, "Solar PV\n500 kWp", OI["orange"])
    box(0.0, 2.9, 3.0, 1.2, "Battery\n375 kW / 1,000 kWh", OI["blue"])
    box(-0.2, 0.9, 3.2, 1.2, "Diesel, 3 units, 560 kW\n(tank filled by sea)", OI["black"])
    box(3.9, 2.9, 1.7, 1.2, "Island grid\n480 V", "0.3")
    box(6.6, 4.0, 3.3, 1.4, "Critical load\nclinic, water, telecoms", OI["vermillion"])
    box(6.6, 1.6, 3.3, 1.4, "Flexible load\nhomes, shops", "0.4")
    for y in (5.5, 3.5, 1.5):
        ax.annotate("", xy=(3.9, 3.5), xytext=(3.0, y), arrowprops=dict(arrowstyle="->", lw=0.7, color="0.3"))
    ax.annotate("", xy=(6.6, 4.7), xytext=(5.6, 3.5), arrowprops=dict(arrowstyle="->", lw=0.7, color="0.3"))
    ax.annotate("", xy=(6.6, 2.3), xytext=(5.6, 3.5), arrowprops=dict(arrowstyle="->", lw=0.7, color="0.3"))
    ax.add_patch(plt.Rectangle((3.3, 5.7), 6.6, 1.2, fill=False, ec=OI["blue"], lw=1.2, ls="--"))
    ax.text(6.6, 6.3, "AURORA: 48 h forecast,\nMPC every hour, CEST", ha="center", va="center", fontsize=6.5,
            color=OI["blue"], fontweight="bold")
    ax.text(5.0, 0.15, "Recommended size from the Phase 4 sweep; diesel plant: INL (2025) current state",
            ha="center", fontsize=5.5, color="0.35")
    style.panel_label(ax, "B")
    fig.tight_layout()
    style.save(fig, FIG / "figa_site_system")
    pd.DataFrame(rows).to_csv(OUT / "figa_storms.csv", index=False)


# ---------------------------------------------------------------- (b) dispatch
def fig_b_dispatch():
    plt = _plt()
    job = "rec_mawar2023_d14"
    h = {c: hourly(job, c) for c in "ABC"}
    t0 = h["C"].index[0]
    fig, axes = plt.subplots(3, 1, figsize=(7.0, 5.2), sharex=True, gridspec_kw={"height_ratios": [1, 1, 1]})
    x = _days(h["C"].index, t0)
    due, arrive = 1.0, 15.0                       # tanker due 24 h after start, 14 days late
    for ax in axes:
        for xv, lab in ((due, "tanker due"), (arrive, "tanker arrives")):
            ax.axvline(xv, color="0.5", lw=0.6, ls=":")
    ax = axes[0]
    for c in "ABC":
        tk = h[c]["tank_end"].where(x < arrive) / 1000          # after the refill the tank is full (60 kL)
        ax.plot(x, tk, color=CTL[c]["color"], ls=CTL[c]["ls"], lw=1.0, label=CTL[c]["label"])
    ax.text(arrive + 0.15, 3.0, "refilled\nto 60 kL", fontsize=6, color="0.35")
    ax.set_ylabel("Fuel in tank (kL)")
    ax.set_ylim(0, 7)
    ax.text(due + 0.1, 6.4, "tanker due", fontsize=6, color="0.35")
    ax.text(arrive - 2.6, 6.4, "tanker arrives", fontsize=6, color="0.35")
    ax.legend(loc="upper right", fontsize=6, ncol=1, bbox_to_anchor=(1.0, 0.9))
    style.panel_label(ax, "A")
    ax = axes[1]
    for c in "BC":
        ax.plot(x, 100 * h[c]["soc_end"], color=CTL[c]["color"], ls=CTL[c]["ls"], lw=0.9, label=CTL[c]["label"])
    ax.axhline(30, color="0.5", lw=0.6, ls="--")
    ax.text(0.1, 32, "CEST reserve (30 %)", fontsize=6, color="0.35")
    ax.set_ylabel("Battery state of charge (%)")
    ax.set_ylim(0, 100)
    style.panel_label(ax, "B")
    ax = axes[2]
    for i, c in enumerate("ABC"):
        u = h[c]["unserved_crit"].to_numpy()
        out = u > 1e-3
        ax.fill_between(x, i, i + 0.8, where=out, step="post", color=CTL[c]["color"], alpha=0.85, lw=0)
        ax.text(x.max() + 0.2, i + 0.4, f"{c}: {int(out.sum())} h", va="center", fontsize=6.5)
    ax.set_yticks([0.4, 1.4, 2.4])
    ax.set_yticklabels(["A", "B", "C"])
    ax.set_ylim(-0.1, 3.0)
    ax.set_ylabel("Critical load lost\n(shaded hours)")
    ax.set_xlabel("Days from 27 May 2023, 00:00 PHT (typhoon Mawar, tanker 14 days late)")
    ax.set_xlim(0, x.max())
    style.panel_label(ax, "C")
    fig.tight_layout()
    style.save(fig, FIG / "figb_dispatch_mawar14d")
    pd.DataFrame({c: [int((h[c]["unserved_crit"] > 1e-3).sum()), round(h[c]["tank_end"].min(), 1)] for c in "ABC"},
                 index=["crit_outage_h", "tank_min_l"]).to_csv(OUT / "figb_dispatch_summary.csv")


# ---------------------------------------------------------------- (c) outage bars
def fig_c_outage():
    plt = _plt()
    d = pd.read_csv(P4 / "rec_storms.csv")
    fig, axes = plt.subplots(1, 3, figsize=(7.0, 2.6), sharey=True)
    w = 0.26
    for ax, (key, nm), lab in zip(axes, STORMS.items(), "ABC"):
        g = d[d.storm == key]
        for i, c in enumerate("ABC"):
            y = [g[(g.controller == c) & (g.delay_days == dd)]["crit_outage_h"].iloc[0] for dd in (3, 7, 14)]
            xs = np.arange(3) + (i - 1) * w
            ax.bar(xs, y, w, color=CTL[c]["color"] if c != "B" else "white", edgecolor=CTL[c]["color"],
                   hatch="////" if c == "B" else None, lw=0.8, label=CTL[c]["label"])
            for xx, yy in zip(xs, y):
                ax.text(xx, yy + 3, f"{yy:.0f}", ha="center", fontsize=5.5)
        ax.set_xticks(range(3))
        ax.set_xticklabels(["3", "7", "14"])
        ax.set_xlabel("Tanker delay (days)")
        ax.set_title(nm, fontsize=8)
        style.panel_label(ax, lab)
    axes[0].set_ylabel("Critical outage (h)")
    axes[0].set_ylim(0, 250)
    h_, l_ = axes[0].get_legend_handles_labels()
    fig.legend(h_, l_, loc="upper center", ncol=3, fontsize=6.5, bbox_to_anchor=(0.5, 1.07))
    fig.text(0.5, -0.02, f"Recommended system ({REC_LABEL}); tank at 6,000 L when the tanker is delayed",
             ha="center", fontsize=6, color="0.35")
    fig.tight_layout()
    style.save(fig, FIG / "figc_outage_storms")


# ---------------------------------------------------------------- (d) CEST over the event
def fig_d_cest():
    plt = _plt()
    job = "rec_mawar2023_d14"
    fig, ax = plt.subplots(figsize=(7.0, 2.6))
    for c in "BC":
        h = hourly(job, c)
        x = _days(h.index, h.index[0])
        ax.plot(x, np.minimum(h["cest_h"], CAP_H), color=CTL[c]["color"], ls=CTL[c]["ls"], lw=1.0, label=CTL[c]["label"])
    ax.axhline(CAP_H, color="0.4", lw=0.6, ls=":")
    ax.text(0.2, CAP_H + 2, "72 h model cap (true value may be higher)", fontsize=6, color="0.3")
    for xv in (1.0, 15.0):
        ax.axvline(xv, color="0.5", lw=0.6, ls=":")
    ax.set_ylim(0, 82)
    ax.set_xlim(0, x.max())
    ax.set_xlabel("Days from 27 May 2023, 00:00 PHT (typhoon Mawar, tanker 14 days late)")
    ax.set_ylabel("CEST (h)")
    ax.legend(loc="upper center", fontsize=6.5, ncol=2, bbox_to_anchor=(0.5, 1.2))
    fig.tight_layout()
    style.save(fig, FIG / "figd_cest_mawar14d")


# ---------------------------------------------------------------- (e) full-year diesel and CO2
def fig_e_year():
    plt = _plt()
    y = pd.read_csv(P4 / "year.csv")
    yp = pd.read_csv(P4 / "year_by_period.csv")
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.6))
    sizes = [("inl", "INL\n300 kWp / 300 kWh"), (REC, "Recommended\n500 kWp / 1,000 kWh")]
    w = 0.26
    rows = []
    for ax, col, ylab, k, lab in ((axes[0], "diesel_l_per_yr", "Diesel (kL/yr)", 1e3, "A"),
                                  (axes[1], "co2_t_per_yr", "CO$_2$ (t/yr)", 1.0, "B")):
        for i, c in enumerate("ABC"):
            vals, lo, hi = [], [], []
            for sz, _ in sizes:
                g = yp[(yp.sizing == sz) & (yp.controller == c)][col] / k
                vals.append(g.mean()), lo.append(g.mean() - g.min()), hi.append(g.max() - g.mean())
                rows.append(dict(metric=col, sizing=sz, controller=c, mean=g.mean() * k, min=g.min() * k, max=g.max() * k))
            xs = np.arange(2) + (i - 1) * w
            ax.bar(xs, vals, w, yerr=[lo, hi], capsize=2, error_kw=dict(lw=0.6),
                   color=CTL[c]["color"] if c != "B" else "white", edgecolor=CTL[c]["color"],
                   hatch="////" if c == "B" else None, lw=0.8, label=CTL[c]["label"])
        ax.set_xticks(range(2))
        ax.set_xticklabels([s for _, s in sizes], fontsize=6.5)
        ax.set_ylabel(ylab)
        style.panel_label(ax, lab)
    h_, l_ = axes[0].get_legend_handles_labels()
    fig.legend(h_, l_, loc="upper center", ncol=3, fontsize=6.5, bbox_to_anchor=(0.5, 1.07))
    fig.text(0.5, -0.03, "Mean of Nov 2024 to Oct 2025 and Nov 2025 to Oct 2026; error bars = range of the two years",
             ha="center", fontsize=6, color="0.35")
    fig.tight_layout()
    style.save(fig, FIG / "fige_year_diesel_co2")
    pd.DataFrame(rows).to_csv(OUT / "fige_year.csv", index=False)
    return y


# ---------------------------------------------------------------- (f) forecast skill
def forecast_skill_table() -> pd.DataFrame:
    """Parse the skill table of docs/validation_forecast.md (written by aurora.forecast.report)."""
    text = (paths.DOCS_DIR / "validation_forecast.md").read_text(encoding="utf-8")
    pat = re.compile(r"^\| (Raw NWP: [^|]+|Smart persistence) \| (\d) \| ([+-][\d.]+) % \(([+-][\d.]+) % to ([+-][\d.]+) %\) "
                     r"\| ([+-][\d.]+) % \(([+-][\d.]+) % to ([+-][\d.]+) %\) \|$", re.M)
    rows = [dict(reference=m[0].strip(), lead_day=int(m[1]), rmse_skill=float(m[2]), rmse_lo=float(m[3]),
                 rmse_hi=float(m[4]), crps_skill=float(m[5]), crps_lo=float(m[6]), crps_hi=float(m[7]))
            for m in pat.findall(text)]
    t = pd.DataFrame(rows)
    t.to_csv(OUT / "figf_forecast_skill.csv", index=False)
    return t


def fig_f_skill():
    plt = _plt()
    t = forecast_skill_table()
    refs = [("Raw NWP: ECMWF IFS", "vs ECMWF IFS", OI["blue"], None), ("Smart persistence", "vs smart persistence",
                                                                       OI["purple"], "////")]
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.5), sharey=True)
    w = 0.35
    for ax, m, lab, title in ((axes[0], "rmse", "A", "Point forecast (RMSE)"),
                              (axes[1], "crps", "B", "Probabilistic forecast (CRPS)")):
        for i, (ref, name, c, hatch) in enumerate(refs):
            g = t[t.reference == ref].sort_values("lead_day")
            v = g[f"{m}_skill"].to_numpy()
            err = [v - g[f"{m}_lo"].to_numpy(), g[f"{m}_hi"].to_numpy() - v]
            xs = np.arange(2) + (i - 0.5) * w
            ax.bar(xs, v, w, yerr=err, capsize=2, error_kw=dict(lw=0.6), color="white" if hatch else c,
                   edgecolor=c, hatch=hatch, lw=0.8, label=name)
            for xx, vv in zip(xs, v):
                ax.text(xx, vv + 3, f"+{vv:.0f} %", ha="center", fontsize=6)
        ax.axhline(0, color="black", lw=0.5)
        ax.set_xticks(range(2))
        ax.set_xticklabels(["Day 1 (0 to 24 h)", "Day 2 (24 to 48 h)"])
        ax.set_xlabel("Lead day")
        ax.set_title(title, fontsize=8)
        style.panel_label(ax, lab)
    axes[0].set_ylabel("Skill of AURORA forecast (%)")
    axes[0].set_ylim(0, 75)
    axes[0].legend(loc="upper left", fontsize=6)
    fig.text(0.5, -0.03, "Solar irradiance, daylight hours, Nov 2024 to Oct 2026; error bars = 5 to 95 % block bootstrap; "
             "positive = AURORA better", ha="center", fontsize=6, color="0.35")
    fig.tight_layout()
    style.save(fig, FIG / "figf_forecast_skill")


# ---------------------------------------------------------------- (g) sizing sweep
def fig_g_sweep():
    plt = _plt()
    sw = pd.read_csv(P4 / "sweep.csv")
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.7))
    pvs = [(300, OI["sky"], ":", "o"), (400, OI["orange"], "-.", "s"), (500, OI["blue"], "-", "^"),
           (600, OI["black"], "--", "D")]
    for pv, c, ls, mk in pvs:
        g = sw[(sw.controller == "C") & (sw.pv_kwp == pv)].sort_values("bat_kwh")
        axes[0].plot(g.bat_kwh, np.minimum(g.cest_median_h, CAP_H), color=c, ls=ls, marker=mk, ms=3, lw=0.9,
                     label=f"C, {pv} kWp")
        axes[1].plot(g.bat_kwh, g.crit_outage_h, color=c, ls=ls, marker=mk, ms=3, lw=0.9, label=f"C, {pv} kWp")
    g = sw[(sw.controller == "B") & (sw.pv_kwp == 500)].sort_values("bat_kwh")
    axes[1].plot(g.bat_kwh, g.crit_outage_h, color=OI["vermillion"], ls="--", marker="x", ms=3, lw=0.9,
                 label="B, 500 kWp")
    axes[0].axhline(CAP_H, color="0.4", lw=0.6, ls=":")
    axes[0].text(20, CAP_H + 2, "72 h model cap", fontsize=6, color="0.3")
    axes[0].axhline(24, color="0.6", lw=0.6, ls="--")
    axes[0].text(20, 26, "target 24 h", fontsize=6, color="0.3")
    for ax in axes:
        ax.axvline(1000, color="0.6", lw=0.6, ls=":")
        ax.set_xlabel("Battery energy (kWh)")
    axes[0].annotate("recommended:\n500 kWp, 1,000 kWh", xy=(1000, CAP_H), xytext=(80, 48), fontsize=6,
                     arrowprops=dict(arrowstyle="->", lw=0.6))
    axes[0].set_ylabel("Median CEST (h)")
    axes[0].set_ylim(0, 82)
    axes[1].set_ylabel("Critical outage (h)")
    axes[1].set_ylim(0, 80)
    axes[0].legend(loc="lower right", fontsize=6)
    axes[1].legend(loc="upper right", fontsize=6)
    style.panel_label(axes[0], "A")
    style.panel_label(axes[1], "B")
    fig.text(0.5, -0.03, "Typhoon Mawar 2023, tanker 14 days late; battery power = min(kWh per hour, 375 kW)",
             ha="center", fontsize=6, color="0.35")
    fig.tight_layout()
    style.save(fig, FIG / "figg_sizing_sweep")


# ---------------------------------------------------------------- (h) hardware payback
def fig_h_payback():
    plt = _plt()
    h = pd.read_csv(P4 / "costs_hardware.csv")
    h = h[(h.diesel_price_php_per_l == 113) & h.wacc.notna()]
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.7), sharey=True)
    cases = [("low", "Low: Ocon and Bertheau (2019)", OI["green"], None),
             ("base", "Base: NPC Sabtang bid", OI["blue"], None),
             ("high", "High: bid x 1.25", OI["vermillion"], "////")]
    w = 0.26
    rows = []
    for ax, (sz, nm), lab in zip(axes, (("inl", "INL 300 kWp / 300 kWh"), (REC, "Recommended 500 kWp / 1,000 kWh")), "AB"):
        g = h[h.sizing == sz].sort_values("wacc")
        for i, (case, cl, c, hatch) in enumerate(cases):
            v = g[f"disc_payback_{case}_yr"].to_numpy()
            xs = np.arange(len(g)) + (i - 1) * w
            for xx, vv, ww in zip(xs, v, g.wacc):
                rows.append(dict(sizing=sz, case=case, wacc=ww, disc_payback_yr=vv))
                if np.isfinite(vv):
                    ax.bar(xx, vv, w, color="white" if hatch else c, edgecolor=c, hatch=hatch, lw=0.8)
                    ax.text(xx, vv + 0.5, f"{vv:.0f}", ha="center", fontsize=5.5)
                else:
                    ax.bar(xx, 20, w, color="none", edgecolor=c, lw=0.8, ls="--")
                    ax.text(xx, 20.6, "none", ha="center", fontsize=5.5, rotation=90, va="bottom")
            pass
        ax.axhline(20, color="0.4", lw=0.6, ls=":")
        ax.set_xticks(range(len(g)))
        ax.set_xticklabels([f"{100 * x:.2f} %".replace(".00", "") for x in g.wacc])
        ax.set_xlabel("WACC")
        ax.set_title(nm, fontsize=8)
        style.panel_label(ax, lab)
    axes[0].set_ylabel("Discounted payback (years)")
    axes[0].set_ylim(0, 27)
    axes[0].text(-0.4, 20.4, "20-year life", fontsize=6, color="0.3")
    from matplotlib.patches import Patch
    hd = [Patch(facecolor="white" if hatch else c, edgecolor=c, hatch=hatch, lw=0.8, label=cl) for _, cl, c, hatch in cases]
    fig.legend(handles=hd, loc="upper center", ncol=3, fontsize=6.5, bbox_to_anchor=(0.5, 1.08))
    fig.text(0.5, -0.03, "PV + battery (A to B) at 113 PHP/L diesel; dashed empty bar = no payback within 20 years; "
             "battery replaced in year 15", ha="center", fontsize=6, color="0.35")
    fig.tight_layout()
    style.save(fig, FIG / "figh_hardware_payback")
    pd.DataFrame(rows).to_csv(OUT / "figh_payback.csv", index=False)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    for f in (fig_a_site_system, fig_b_dispatch, fig_c_outage, fig_d_cest, fig_e_year, fig_f_skill, fig_g_sweep,
              fig_h_payback):
        f()
        print("done", f.__name__)


if __name__ == "__main__":
    main()
