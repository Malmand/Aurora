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
BASEMAP = paths.ROOT / "data" / "basemap" / "luzon_strait_land.geojson"
LAND, SEA = "#E6E6E6", "white"


def _land(ax, lw=0.4):
    """Draw Natural Earth 1:10m land (public domain), clipped to 113-131 E, 10.5-27.5 N."""
    import json
    from matplotlib.patches import Polygon
    g = json.loads(BASEMAP.read_text(encoding="utf-8"))["features"][0]["geometry"]
    polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    for poly in polys:
        ax.add_patch(Polygon(np.asarray(poly[0]), closed=True, fc=LAND, ec="0.55", lw=lw, zorder=0))


def _km_circle(lon0, lat0, r_km):
    th = np.linspace(0, 2 * np.pi, 240)
    k = np.cos(np.radians(lat0))
    return lon0 + r_km / (111.2 * k) * np.cos(th), lat0 + r_km / 111.2 * np.sin(th)


def fig_a_site_system():
    plt = _plt()
    from matplotlib.patches import FancyBboxPatch
    ev = pd.read_csv(paths.SITE_DIR / "typhoon_events.csv", parse_dates=["closest_time_utc"])
    tr = pd.read_parquet(paths.SITE_DIR / "raw_small" / "ibtracs_wp_tracks.parquet")
    lat0, lon0 = paths.LAT, paths.LON
    k = np.cos(np.radians(lat0))
    fig = plt.figure(figsize=(7.2, 3.9))
    ax = fig.add_axes([0.07, 0.11, 0.42, 0.80])
    _land(ax)
    for r_km, ls in ((300, ":"), (500, "--")):
        x, y = _km_circle(lon0, lat0, r_km)
        ax.plot(x, y, color="0.45", lw=0.6, ls=ls, zorder=2)
        ang = np.radians(-90 if r_km == 300 else -50)          # label position on the circle
        ax.text(lon0 + r_km / (111.2 * k) * np.cos(ang), lat0 + r_km / 111.2 * np.sin(ang), f"{r_km} km", fontsize=5.8,
                color="0.3", ha="center", va="center", zorder=6, bbox=dict(fc="white", ec="none", pad=0.6, alpha=0.9))
    styles = {"MAWAR": (OI["orange"], "--"), "RAGASA": (OI["blue"], "-"), "MEKKHALA": (OI["purple"], "-.")}
    rows = []
    for key, nm in (("mawar2023", "MAWAR"), ("ragasa2025", "RAGASA"), ("mekkhala2026", "MEKKHALA")):
        yr = int(key[-4:])
        e = ev[(ev["name"] == nm) & (ev["closest_time_utc"].dt.year == yr)].iloc[0]
        t = tr[tr["SID"] == e["sid"]].sort_index()
        c, ls = styles[nm]
        ax.plot(t["LON"], t["LAT"], color=c, ls=ls, lw=1.2, zorder=3,
                label=f"{STORMS[key]}, closest {e['closest_km']:.0f} km")
        # direction of travel: small arrow on the track near its closest point
        d = (t["LAT"] - lat0) ** 2 + ((t["LON"] - lon0) * k) ** 2
        i0 = int(np.argmin(d.to_numpy()))
        i1 = min(i0 + 3, len(t) - 1)
        ax.annotate("", xy=(t["LON"].iloc[i1], t["LAT"].iloc[i1]), xytext=(t["LON"].iloc[i0], t["LAT"].iloc[i0]),
                    arrowprops=dict(arrowstyle="-|>", color=c, lw=1.0, mutation_scale=9), zorder=4)
        rows.append(dict(storm=key, sid=e["sid"], closest_km=e["closest_km"], min_pres_hpa=e["min_pres_hpa_within_500km"]))
    # schematic fuel route: Bolinao (Pangasinan) up the west coast of Luzon to Basco, then Itbayat
    route = np.array([(119.95, 16.40), (119.75, 17.4), (120.15, 18.55), (120.9, 19.35), (121.6, 19.95),
                      (121.97, 20.45), (121.84, 20.78)])
    ax.plot(route[:, 0], route[:, 1], color=OI["vermillion"], lw=1.3, ls=(0, (3, 2)), zorder=4)
    ax.plot(*route[0], marker="D", color=OI["vermillion"], ms=4.5, zorder=6)
    ax.text(route[0][0] + 0.3, route[0][1] - 0.02, "Bolinao (tanker port)", fontsize=6, ha="left", va="center",
            color=OI["vermillion"], zorder=6, bbox=dict(fc=LAND, ec="none", pad=0.3))
    ax.text(118.45, 17.35, "fuel route\n(schematic)", fontsize=6, color=OI["vermillion"], ha="center", zorder=6)
    ax.plot(lon0, lat0, marker="*", color="black", ms=10, mec="white", mew=0.5, zorder=7)
    ax.text(122.45, 20.95, "Itbayat", fontsize=7.5, fontweight="bold", zorder=7, va="center")
    for txt, (x, y) in {"LUZON": (121.45, 17.35), "TAIWAN": (120.95, 23.55)}.items():
        ax.text(x, y, txt, fontsize=7, color="0.45", ha="center", style="italic", zorder=1)
    ax.text(118.6, 21.55, "South China Sea", fontsize=6, color="0.55", ha="center", style="italic", zorder=1)
    ax.text(125.9, 16.4, "Philippine Sea", fontsize=6, color="0.55", ha="center", style="italic", zorder=1)
    ax.set_xlim(116.5, 127.5)
    ax.set_ylim(14.5, 25.5)
    ax.set_aspect(1 / k)
    ax.set_facecolor(SEA)
    ax.set_xlabel("Longitude (°E)")
    ax.set_ylabel("Latitude (°N)")
    # label the tracks directly instead of a legend box (keeps Luzon visible)
    for (x, y, ha), key, nm in (((117.0, 19.3, "left"), "ragasa2025", "RAGASA"),
                                ((124.45, 22.9, "right"), "mekkhala2026", "MEKKHALA"),
                                ((125.65, 21.45, "left"), "mawar2023", "MAWAR")):
        km = [r_["closest_km"] for r_ in rows if r_["storm"] == key][0]
        ax.text(x, y, f"{STORMS[key]}\n{km:.0f} km away", fontsize=5.8, ha=ha, va="center",
                color=styles[nm][0], fontweight="bold", zorder=6, linespacing=1.1,
                bbox=dict(fc="white", ec="none", pad=0.4, alpha=0.9))
    ax.text(0.99, 0.01, "Tracks: IBTrACS v04r01\nLand: Natural Earth 1:10m", transform=ax.transAxes, fontsize=5,
            color="0.4", ha="right", va="bottom")
    fig.text(0.012, 0.965, "A", fontsize=11, fontweight="bold", va="top")
    # inset: the Batanes islands
    ins = fig.add_axes([0.085, 0.60, 0.115, 0.27])
    _land(ins, lw=0.5)
    for nm_, (x, y, ha) in {"Itbayat": (121.84, 20.96, "center"), "Batan": (122.08, 20.47, "left"),
                            "Sabtang": (121.92, 20.20, "left")}.items():
        ins.text(x, y, nm_, fontsize=5.5, ha=ha, va="center", fontweight="bold" if nm_ == "Itbayat" else None)
    ins.plot(lon0, lat0, marker="*", color="black", ms=6, zorder=5)
    ins.set_xlim(121.55, 122.35)
    ins.set_ylim(20.15, 21.15)
    ins.set_aspect(1 / k)
    ins.set_xticks([])
    ins.set_yticks([])
    for s_ in ins.spines.values():
        s_.set_visible(True)
        s_.set_linewidth(0.6)
    ins.text(0.04, 0.96, "Batanes", transform=ins.transAxes, fontsize=6, style="italic", va="top", color="0.35")
    ax.add_patch(plt.Rectangle((121.55, 20.15), 0.8, 1.0, fill=False, ec="black", lw=0.6, zorder=8))

    # panel B: how AURORA sits on the island grid
    bx = fig.add_axes([0.54, 0.04, 0.45, 0.90])
    bx.set_xlim(0, 10)
    bx.set_ylim(-1.0, 10.6)
    bx.axis("off")

    def box(x, y, w, h, title, sub, c, fill="white", ls="-"):
        bx.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.15", fc=fill, ec=c, lw=1.1,
                                    ls=ls))
        bx.text(x + w / 2, y + h * (0.63 if sub else 0.5), title, ha="center", va="center", fontsize=6.8 if sub or "\n" in title else 5.6,
                fontweight="bold")
        if sub:
            bx.text(x + w / 2, y + h * 0.28, sub, ha="center", va="center", fontsize=5.8, color="0.25")

    def line(pts, c="0.35", ls="-", lw=0.9, head=True):
        pts = np.asarray(pts, float)
        bx.plot(pts[:, 0], pts[:, 1], color=c, ls=ls, lw=lw)
        if head:
            u = (pts[-1] - pts[-2]) / np.linalg.norm(pts[-1] - pts[-2])
            bx.annotate("", xy=pts[-1], xytext=pts[-1] - 0.05 * u,
                        arrowprops=dict(arrowstyle="-|>", color=c, lw=lw, mutation_scale=8, shrinkA=0, shrinkB=0))

    # AURORA control layer
    bx.add_patch(FancyBboxPatch((0.2, 7.4), 9.6, 2.5, boxstyle="round,pad=0.02,rounding_size=0.15", fc="#EAF3FA",
                                ec=OI["blue"], lw=1.2))
    bx.text(0.45, 9.55, "AURORA control layer (software)", fontsize=7, fontweight="bold", color=OI["blue"], va="center")
    # three equal columns; arrows centred in the gap between the step titles, measured after drawing
    cols = (("1  Forecast", "solar and demand,\n48 h ahead,\nP10 to P90"),
            ("2  Plan", "MPC, re-planned\nevery hour with\nweather and fuel"),
            ("3  Survival time", "CEST: hours the\ncritical load lasts\nif diesel stops"))
    t_y, s_y = 8.9, 8.05
    titles = [bx.text(0, t_y, ttl, ha="left", va="center", fontsize=6.4, fontweight="bold") for ttl, _ in cols]
    fig.canvas.draw()
    inv = bx.transData.inverted()
    wid = [np.diff(inv.transform(t_.get_window_extent())[:, 0])[0] for t_ in titles]
    left, right = 1.0, 9.0                                   # titles spread with equal gaps, group centred
    gap = (right - left - sum(wid)) / 2
    x_ = left
    for t_, w_, (_, sub) in zip(titles, wid, cols):
        t_.set_x(x_)
        bx.text(x_ + w_ / 2, s_y, sub, ha="center", va="center", fontsize=5.5, color="0.25", linespacing=1.2,
                multialignment="center")
        if t_ is not titles[-1]:
            xm = x_ + w_ + gap / 2
            line([(xm - 0.3 * gap, t_y), (xm + 0.3 * gap, t_y)], c=OI["blue"], lw=1.1)
        x_ += w_ + gap
    # power sources, bus, loads
    box(0.2, 5.0, 2.8, 1.5, "Solar PV", "300 kWp", OI["orange"])
    box(0.2, 3.0, 2.8, 1.5, "Battery", "375 kW / 1,500 kWh", OI["blue"])
    box(0.2, 1.0, 2.8, 1.5, "Diesel", "850 kW rated, 3 units", "black")
    box(4.0, 1.4, 1.6, 4.6, "Island\ngrid\n480 V", "", "0.35")
    box(6.4, 4.3, 3.0, 1.6, "Critical load", "clinic, water, telecoms", OI["vermillion"])
    box(6.4, 1.8, 3.0, 1.6, "Flexible load", "homes, shops", "0.45")
    for y_ in (5.75, 3.75, 1.75):
        line([(3.0, y_), (4.0, y_)])
    bx.annotate("", xy=(3.0, 3.75), xytext=(3.05, 3.75),
                arrowprops=dict(arrowstyle="-|>", color="0.35", lw=0.9, mutation_scale=8, shrinkA=0, shrinkB=0))
    line([(5.6, 5.1), (6.4, 5.1)])
    line([(5.6, 2.6), (6.4, 2.6)])
    # fuel by sea
    bx.add_patch(FancyBboxPatch((0.2, -0.85), 2.8, 1.05, boxstyle="round,pad=0.02,rounding_size=0.15", fc="white",
                                ec=OI["vermillion"], lw=1.0, ls="--"))
    bx.text(1.6, -0.32, "Fuel tank\nrefilled by sea", ha="center", va="center", fontsize=5.8, color=OI["vermillion"],
            linespacing=1.15)
    line([(1.6, 0.2), (1.6, 1.0)], c=OI["vermillion"])
    # control signals (dashed blue)
    cs = dict(c=OI["blue"], ls=(0, (2.5, 1.5)), lw=0.9)
    line([(3.5, 7.4), (3.5, 4.2), (3.0, 4.2)], **cs)
    line([(3.5, 4.2), (3.5, 2.2), (3.0, 2.2)], **cs)
    line([(9.65, 7.4), (9.65, 2.6), (9.4, 2.6)], **cs)
    bx.text(3.62, 7.25, "charge / discharge,\ngenerators on / off", fontsize=5.4, color=OI["blue"], va="top")
    bx.text(9.55, 7.25, "shed only\nif needed", fontsize=5.4, color=OI["blue"], va="top", ha="right")
    bx.text(6.6, -0.55, "AURORA size; diesel plant\nas reported by NPC", ha="center",
            fontsize=5.2, color="0.4", va="center")
    fig.text(0.535, 0.965, "B", fontsize=11, fontweight="bold", va="top")
    style.save(fig, FIG / "figa_site_system")
    pd.DataFrame(rows).to_csv(OUT / "figa_storms.csv", index=False)


# ---------------------------------------------------------------- (b) dispatch
def fig_b_dispatch():
    plt = _plt()
    job = "rec_mawar2023_d14"
    h = {c: hourly(job, c) for c in "ABC"}
    t0 = h["C"].index[0]
    fig, axes = plt.subplots(3, 1, figsize=(7.0, 5.4), sharex=True, gridspec_kw={"height_ratios": [1, 1, 0.8]})
    x = _days(h["C"].index, t0)
    due, arrive = 1.0, 15.0                       # tanker due 24 h after start, 14 days late
    for ax in axes:
        for xv in (due, arrive):
            ax.axvline(xv, color="0.5", lw=0.6, ls=":")
    ax = axes[0]
    for c in "ABC":
        tk = h[c]["tank_end"].where(x < arrive) / 1000
        ax.plot(x, tk, color=CTL[c]["color"], ls=CTL[c]["ls"], lw=1.1, label=CTL[c]["label"])
    ax.annotate("", xy=(arrive + 0.05, 6.9), xytext=(arrive + 0.05, 0.3),
                arrowprops=dict(arrowstyle="-|>", color="0.35", lw=0.8, mutation_scale=8))
    ax.text(arrive + 0.25, 3.6, "tanker arrives:\nrefilled to 60 kL\n(off scale)", fontsize=6, color="0.3", va="center")
    ax.text(due + 0.12, 6.55, "tanker due", fontsize=6, color="0.3")
    ax.set_ylabel("Fuel in tank (kL)")
    ax.set_ylim(0, 7)
    style.panel_label(ax, "A")
    ax = axes[1]
    for c in "BC":
        ax.plot(x, 100 * h[c]["soc_end"], color=CTL[c]["color"], ls=CTL[c]["ls"], lw=0.9)
    ax.axhline(30, color="0.5", lw=0.6, ls="--")
    ax.text(16.1, 33, "CEST reserve\n(30 %)", fontsize=6, color="0.3", va="bottom")
    ax.set_ylabel("Battery state of\ncharge (%)")
    ax.set_ylim(0, 100)
    style.panel_label(ax, "B")
    ax = axes[2]
    for i, c in enumerate("ABC"):
        out = h[c]["unserved_crit"].to_numpy() > 1e-3
        ax.fill_between(x, i, i + 0.75, where=out, step="post", color=CTL[c]["color"], lw=0)
        ax.text(x.max() + 0.2, i + 0.37, f"{int(out.sum())} h", va="center", fontsize=6.5)
    ax.set_yticks([0.37, 1.37, 2.37])
    ax.set_yticklabels(["A", "B", "C"])
    ax.set_ylim(-0.15, 2.9)
    ax.set_ylabel("Critical load\nlost (hours)")
    ax.set_xlabel("Days from 27 May 2023, 00:00 PHT (typhoon Mawar, tanker 14 days late)")
    ax.set_xlim(0, x.max())
    style.panel_label(ax, "C")
    h_, l_ = axes[0].get_legend_handles_labels()
    fig.legend(h_, l_, loc="upper center", ncol=3, fontsize=6.5, bbox_to_anchor=(0.5, 1.03))
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
    """Share of each day's hours with CEST of at least 24 h, B against C (Mawar, 14-day delay)."""
    plt = _plt()
    job = "rec_mawar2023_d14"
    rows = []
    for c in "BC":
        hh = hourly(job, c)
        day = np.floor(_days(hh.index, hh.index[0])).astype(int)
        g = pd.DataFrame({"day": day, "ok": np.minimum(hh["cest_h"], CAP_H) >= 24}).groupby("day")["ok"]
        n = g.size()
        for d_, v in (100 * g.mean()).items():
            if n[d_] == 24:
                rows.append(dict(controller=c, day=int(d_), pct_hours_cest_ge24=v))
    t = pd.DataFrame(rows)
    t.to_csv(OUT / "figd_cest_daily.csv", index=False)
    fig, ax = plt.subplots(figsize=(7.0, 2.5))
    w = 0.4
    for i, c in enumerate("BC"):
        g = t[t.controller == c]
        ax.bar(g.day + 0.5 + (i - 0.5) * w, g.pct_hours_cest_ge24, w, color="white" if c == "B" else CTL[c]["color"],
               edgecolor=CTL[c]["color"], hatch="////" if c == "B" else None, lw=0.7, label=CTL[c]["label"])
    for xv, lab in ((1.0, "tanker due"), (15.0, "tanker arrives")):
        ax.axvline(xv, color="0.5", lw=0.6, ls=":")
        ax.text(xv + 0.1, 104, lab, fontsize=6, color="0.3")
    mean_c = t[(t.controller == "C") & (t.day.between(1, 14))].pct_hours_cest_ge24.mean()
    mean_b = t[(t.controller == "B") & (t.day.between(1, 14))].pct_hours_cest_ge24.mean()
    ax.text(8.0, 117, f"days 1 to 14 (tanker late): AURORA {mean_c:.0f} % of hours, simple rule {mean_b:.0f} %",
            fontsize=6.5, ha="center")
    ax.set_xlim(0, t.day.max() + 1)
    ax.set_ylim(0, 124)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_xlabel("Day of the event (from 27 May 2023, typhoon Mawar, tanker 14 days late)")
    ax.set_ylabel("Hours with CEST \u2265 24 h (%)")
    ax.legend(loc="upper center", fontsize=6.5, ncol=2, bbox_to_anchor=(0.5, 1.25))
    fig.tight_layout()
    style.save(fig, FIG / "figd_cest_mawar14d")


# ---------------------------------------------------------------- (e) full-year diesel and CO2
def fig_e_year():
    plt = _plt()
    from ..twin import params
    co2 = params.from_site("inl").co2_kg_per_l          # kg CO2 per litre
    y = pd.read_csv(P4 / "year.csv")
    yp = pd.read_csv(P4 / "year_by_period.csv")
    fig, ax = plt.subplots(figsize=(4.6, 2.9))
    sizes = [("inl", "INL size\n300 kWp / 300 kWh"), (REC, "Recommended\n500 kWp / 1,000 kWh")]
    w = 0.26
    rows = []
    a_mean = yp[yp.controller == "A"]["diesel_l_per_yr"].mean() / 1e3
    for i, c in enumerate("ABC"):
        vals, lo, hi = [], [], []
        for sz, _ in sizes:
            g = yp[(yp.sizing == sz) & (yp.controller == c)]["diesel_l_per_yr"] / 1e3
            vals.append(g.mean()), lo.append(g.mean() - g.min()), hi.append(g.max() - g.mean())
            rows.append(dict(sizing=sz, controller=c, diesel_kl_mean=g.mean(), diesel_kl_min=g.min(), diesel_kl_max=g.max(),
                             co2_t_mean=g.mean() * co2))
        xs = np.arange(2) + (i - 1) * w
        ax.bar(xs, vals, w, yerr=[lo, hi], capsize=2, error_kw=dict(lw=0.6),
               color=CTL[c]["color"] if c != "B" else "white", edgecolor=CTL[c]["color"],
               hatch="////" if c == "B" else None, lw=0.8, label=CTL[c]["label"])
        if c != "A":
            for xx, vv, hh in zip(xs, vals, hi):
                ax.text(xx, vv + hh + 6, f"\u2212{100 * (1 - vv / a_mean):.0f} %", ha="center", fontsize=6)
    ax.set_xticks(range(2))
    ax.set_xticklabels([s_ for _, s_ in sizes], fontsize=6.5)
    ax.set_ylabel("Diesel (kL/yr)")
    ax.set_ylim(0, 420)
    sec = ax.secondary_yaxis("right", functions=(lambda v: v * co2, lambda v: v / co2))
    sec.set_ylabel("CO$_2$ (t/yr)")
    sec.spines["right"].set_visible(True)
    ax.legend(loc="upper center", ncol=3, fontsize=6, bbox_to_anchor=(0.5, 1.2), columnspacing=0.8, handlelength=1.6)
    fig.text(0.5, -0.04, "Mean of Nov 2024 to Oct 2025 and Nov 2025 to Oct 2026; error bars = range of the two years;\n"
             "percentages = diesel saved against diesel only", ha="center", fontsize=5.8, color="0.35")
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
            for xx, vv, top in zip(xs, v, g[f"{m}_hi"].to_numpy()):
                ax.text(xx, top + 1.5, f"+{vv:.0f} %", ha="center", fontsize=6)
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
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.8))
    pvs = [(300, OI["sky"], ":", "o"), (400, OI["green"], "-.", "s"), (500, OI["blue"], "-", "^"),
           (600, OI["black"], "--", "D")]
    for pv, c, ls, mk in pvs:
        g = sw[(sw.controller == "C") & (sw.pv_kwp == pv)].sort_values("bat_kwh")
        axes[0].plot(g.bat_kwh, np.minimum(g.cest_median_h, CAP_H), color=c, ls=ls, marker=mk, ms=3, lw=0.9,
                     label=f"AURORA, {pv} kWp")
        axes[1].plot(g.bat_kwh, g.crit_outage_h, color=c, ls=ls, marker=mk, ms=3, lw=0.9, label=f"AURORA, {pv} kWp")
    g = sw[(sw.controller == "B") & (sw.pv_kwp == 500)].sort_values("bat_kwh")
    axes[1].plot(g.bat_kwh, g.crit_outage_h, color=OI["orange"], ls="--", marker="x", ms=4, lw=1.1,
                 label="Simple rule, 500 kWp")
    axes[0].axhline(CAP_H, color="0.4", lw=0.6, ls=":")
    axes[0].text(20, CAP_H + 2, "72 h model cap", fontsize=6, color="0.3")
    axes[0].axhline(24, color="0.6", lw=0.6, ls="--")
    axes[0].text(20, 26, "target 24 h", fontsize=6, color="0.3")
    for ax in axes:
        ax.axvline(1000, color="0.6", lw=0.6, ls=":")
        ax.set_xlabel("Battery energy (kWh)")
    axes[0].annotate("recommended:\n500 kWp, 1,000 kWh", xy=(1000, CAP_H), xytext=(80, 48), fontsize=6,
                     arrowprops=dict(arrowstyle="->", lw=0.6))
    b1000 = int(g[g.bat_kwh == 1000].crit_outage_h.iloc[0])
    b2000 = int(g[g.bat_kwh == 2000].crit_outage_h.iloc[0])
    axes[1].annotate(f"simple rule needs 2,000 kWh\nto get down to {b2000} h\n(AURORA: 0 h at 1,000 kWh)",
                     xy=(2000, b2000), xytext=(1150, 34), fontsize=6, arrowprops=dict(arrowstyle="->", lw=0.6))
    axes[1].annotate(f"{b1000} h", xy=(1000, b1000), xytext=(1060, b1000 + 4), fontsize=6, color=OI["orange"])
    axes[0].set_ylabel("Median CEST (h)")
    axes[0].set_ylim(0, 82)
    axes[1].set_ylabel("Critical outage (h)")
    axes[1].set_ylim(0, 80)
    axes[0].legend(loc="lower right", fontsize=5.8)
    axes[1].legend(loc="upper right", fontsize=5.8)
    style.panel_label(axes[0], "A")
    style.panel_label(axes[1], "B")
    fig.text(0.5, -0.03, "Typhoon Mawar 2023, tanker 14 days late; battery power = min(kWh per hour, 375 kW)",
             ha="center", fontsize=6, color="0.35")
    fig.tight_layout()
    style.save(fig, FIG / "figg_sizing_sweep")


# ---------------------------------------------------------------- (h) hardware payback
def fig_h_payback():
    """20-year NPV of PV + battery (A to B) against installed cost, as a share of the NPC Sabtang bid price."""
    plt = _plt()
    from ..data.site import load_site
    from ..experiments import phase4 as P
    sv = load_site()["values"]
    v = lambda k_: sv[k_]["value"]  # noqa: E731
    om, n, rep_t = v("om_frac_of_capex_per_year_assumed"), int(v("ocon2019_project_life_yr")), int(v("ocon2019_battery_life_yr"))
    yr = pd.read_csv(P4 / "year.csv")
    a_l = yr[yr.controller == "A"]["diesel_l_per_yr"].mean()
    hw = pd.read_csv(P4 / "costs_hardware.csv")
    price = 113.0
    waccs = [(0.04, "-", OI["green"]), (0.06, "--", OI["blue"]), (v("ocon2019_wacc"), ":", OI["vermillion"])]
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.9), sharey=True)
    s_ = np.linspace(0, 1.4, 141)
    rows = []
    for ax, (sz, nm), lab in zip(axes, (("inl", "INL size, 300 kWp / 300 kWh"), (REC, "Recommended, 500 kWp / 1,000 kWh")), "AB"):
        r0 = hw[hw.sizing == sz].iloc[0]
        b_l = yr[(yr.sizing == sz) & (yr.controller == "B")]["diesel_l_per_yr"].iloc[0]
        sav = (a_l - b_l) * price
        cpv, cbat = P.capex_parts_php(r0.pv_kwp, r0.bat_kwh, r0.bat_kw, case="base")
        lpv, lbat = P.capex_parts_php(r0.pv_kwp, r0.bat_kwh, r0.bat_kw, case="low")
        cap = cpv + cbat
        for r, ls, c in waccs:
            af = sum(1 / (1 + r) ** t for t in range(1, n + 1))
            npv = (sav * af - s_ * (cap * (1 + om * af) + cbat / (1 + r) ** rep_t)) / 1e6
            be = sav * af / (cap * (1 + om * af) + cbat / (1 + r) ** rep_t)
            ax.plot(100 * s_, npv, color=c, ls=ls, lw=1.1, label=f"WACC {100 * r:.2f} %".replace(".00", ""))
            ax.plot(100 * be, 0, marker="o", color=c, ms=3.5, zorder=5)
            rows.append(dict(sizing=sz, wacc=r, diesel_php_per_l=price, breakeven_share_of_bid=be,
                             breakeven_capex_mphp=be * cap / 1e6, breakeven_php_per_kwp_all_in=be * cap / r0.pv_kwp))
        ax.axhline(0, color="black", lw=0.6)
        for xv, txt in ((100 * (lpv + lbat) / cap, "Ocon and Bertheau (2019)"), (100, "NPC Sabtang bid")):
            ax.axvline(xv, color="0.55", lw=0.6, ls=(0, (1, 1.5)))
            ax.text(xv + 1.5, 0.03, txt, transform=ax.get_xaxis_transform(), fontsize=5.8, ha="left", va="bottom",
                    color="0.3", rotation=90)
        be_lo = min(rr["breakeven_share_of_bid"] for rr in rows if rr["sizing"] == sz)
        be_hi = max(rr["breakeven_share_of_bid"] for rr in rows if rr["sizing"] == sz)
        ax.text(0.97, 0.93, f"break-even: {100 * be_lo:.0f} to {100 * be_hi:.0f} %\nof the bid price",
                transform=ax.transAxes, ha="right", va="top", fontsize=6.3)
        ax.set_xlim(0, 140)
        ax.set_xlabel("Installed cost (% of NPC Sabtang bid price)")
        ax.set_title(nm, fontsize=8, pad=6)
        style.panel_label(ax, lab)
    axes[0].set_ylabel("20-year NPV (M PHP)")
    axes[0].legend(loc="upper center", fontsize=6, bbox_to_anchor=(0.42, 1.0))
    fig.text(0.5, -0.04, "PV + battery against diesel only, diesel 113 PHP/L, O&M 2 % of capex a year, battery replaced "
             "in year 15, no salvage;\ndots = break-even installed cost", ha="center", fontsize=5.8, color="0.35")
    fig.tight_layout()
    style.save(fig, FIG / "figh_hardware_payback")
    pd.DataFrame(rows).to_csv(OUT / "figh_breakeven.csv", index=False)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    for f in (fig_a_site_system, fig_b_dispatch, fig_c_outage, fig_d_cest, fig_e_year, fig_f_skill, fig_g_sweep,
              fig_h_payback):
        f()
        print("done", f.__name__)


if __name__ == "__main__":
    main()
