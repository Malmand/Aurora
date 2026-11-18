"""Figures for the full GSC deck (problem, idea, what's new, plan, extras), slide-sized.

    python -m aurora.plotting.deck_full            # all figures
    python -m aurora.plotting.deck_full map storms # some of them

Writes figures/deck/*.png (300 dpi) and .pdf. Every number comes from committed data:
site.yaml, typhoon_events.csv, IBTrACS tracks, the synthetic (NPC-calibrated) load,
the forecast backtest and results/phase4b. News-reported power hours are typed in
below with their source, as evidence of events only.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from ..data import paths
from ..data.site import load_site
from .deck import INK, SOFT, COL4, NAME4, STY4, _plt, _save
from .phase5 import OI, _km_circle, _land

P4B = paths.ROOT / "results" / "phase4b"
LAT0, LON0 = paths.LAT, paths.LON
K = np.cos(np.radians(LAT0))
LANDC = "#E4E2DC"


def _hav(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(np.radians, (lon1, lat1, lon2, lat2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * np.arcsin(np.sqrt(a))


def _land2(ax, lw=0.6, fc=LANDC):
    import json
    from matplotlib.patches import Polygon
    from .phase5 import BASEMAP
    g = json.loads(BASEMAP.read_text(encoding="utf-8"))["features"][0]["geometry"]
    polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    for poly in polys:
        ax.add_patch(Polygon(np.asarray(poly[0]), closed=True, fc=fc, ec="0.45", lw=lw, zorder=1))


def _label(ax, letter, x=-0.02, y=1.03):
    ax.text(x, y, letter, transform=ax.transAxes, fontsize=26, fontweight="bold", va="bottom", ha="right")


# ---------------------------------------------------------------- 1. map: where Itbayat is and how fuel gets there
BOLINAO = (119.90, 16.39)
MANILA = (120.98, 14.60)
BASCO = (121.97, 20.45)
ROUTE = np.array([BOLINAO, (119.72, 17.4), (120.2, 18.6), (120.9, 19.35), (121.6, 19.95), BASCO, (LON0, LAT0)])


def map_overview():
    plt = _plt()
    fig = plt.figure(figsize=(17, 8.2))
    ax = fig.add_axes([0.05, 0.08, 0.46, 0.86])
    _land2(ax)
    ax.set_facecolor("white")
    ax.plot(ROUTE[:, 0], ROUTE[:, 1], color=OI["vermillion"], lw=2.6, ls=(0, (4, 2)), zorder=4)
    seg = _hav(ROUTE[:-1, 0], ROUTE[:-1, 1], ROUTE[1:, 0], ROUTE[1:, 1]).sum()
    ax.plot(*BOLINAO, marker="D", color=OI["vermillion"], ms=11, zorder=6)
    ax.text(BOLINAO[0] - 0.25, BOLINAO[1] - 0.05, "Bolinao\nfuel tanker port", fontsize=17, ha="right", va="center",
            color=OI["vermillion"], zorder=6)
    ax.text(118.2, 18.6, f"about {round(seg, -1):.0f} km\nby sea (schematic)", fontsize=17, ha="center",
            color=OI["vermillion"], zorder=6)
    ax.plot(*MANILA, marker="s", color=INK, ms=9, zorder=6)
    ax.text(MANILA[0] + 0.3, MANILA[1], "Manila", fontsize=17, va="center", zorder=6)
    ax.plot(LON0, LAT0, marker="*", color="black", ms=24, mec="white", mew=1, zorder=7)
    ax.text(LON0 + 0.75, LAT0 + 0.1, "Itbayat", fontsize=22, fontweight="bold", va="center", zorder=7)
    for txt, (x, y) in {"LUZON": (121.6, 16.6), "TAIWAN": (121.0, 23.6)}.items():
        ax.text(x, y, txt, fontsize=18, color="0.4", ha="center", style="italic", zorder=2)
    ax.text(117.0, 21.6, "South China Sea", fontsize=16, color="0.5", ha="center", style="italic")
    ax.text(125.6, 17.0, "Philippine Sea", fontsize=16, color="0.5", ha="center", style="italic")
    ax.text(121.4, 19.9 - 0.95, "Luzon Strait", fontsize=15, color="0.5", ha="center", style="italic")
    ax.add_patch(plt.Rectangle((121.55, 20.15), 0.8, 1.0, fill=False, ec="black", lw=1.6, zorder=8))
    ax.set_xlim(115.5, 127.5)
    ax.set_ylim(13.8, 25.2)
    ax.set_aspect(1 / K)
    ax.set_xlabel("Longitude (°E)")
    ax.set_ylabel("Latitude (°N)")
    _label(ax, "A")
    # B: Batanes
    bx = fig.add_axes([0.56, 0.08, 0.42, 0.86])
    _land2(bx, lw=1.0)
    bx.set_facecolor("white")
    bx.plot(LON0, LAT0, marker="*", color="black", ms=28, mec="white", mew=1, zorder=7)
    bx.text(LON0 + 0.06, LAT0 + 0.075, "Itbayat", fontsize=22, fontweight="bold", zorder=7)
    bx.text(LON0 + 0.06, LAT0 - 0.005, "3,128 people · 1,009 homes\ndiesel plant, 850 kW rated", fontsize=15,
            va="top", zorder=7, color=SOFT)
    bx.plot(*BASCO, marker="o", color=INK, ms=11, zorder=7)
    bx.text(BASCO[0] + 0.05, BASCO[1] + 0.01, "Basco, Batan\nprovincial capital", fontsize=15, va="center", zorder=7)
    bx.text(121.84, 20.27, "Sabtang", fontsize=15, ha="right", zorder=7, color=SOFT)
    d = _hav(LON0, LAT0, *BASCO)
    bx.annotate("", xy=(BASCO[0] - 0.02, BASCO[1] + 0.03), xytext=(LON0 + 0.02, LAT0 - 0.04),
                arrowprops=dict(arrowstyle="<->", color=OI["vermillion"], lw=2, ls="--"), zorder=6)
    bx.text(121.73, 20.60, f"{d:.0f} km of open sea:\nfuel and food by boat", fontsize=16, color=OI["vermillion"],
            ha="center", va="center", zorder=6)
    # scale bar 20 km
    x0, y0 = 122.05, 20.2
    bx.plot([x0, x0 + 20 / (111.2 * K)], [y0, y0], color="black", lw=3)
    bx.text(x0 + 10 / (111.2 * K), y0 + 0.02, "20 km", ha="center", fontsize=15)
    bx.set_xlim(121.55, 122.35)
    bx.set_ylim(20.15, 21.15)
    bx.set_aspect(1 / K)
    bx.set_xlabel("Longitude (°E)")
    bx.set_ylabel("Latitude (°N)")
    _label(bx, "B")
    fig.text(0.05, -0.03, "Land: Natural Earth 1:10m. Fuel route drawn by hand; distance along the drawn route.", fontsize=12, color="0.4", ha="left")
    _save(fig, "map_overview")
    return seg, d


# ---------------------------------------------------------------- 2. typhoon exposure
def storms_exposure():
    plt = _plt()
    ev = pd.read_csv(paths.TYPHOON_EVENTS, parse_dates=["closest_time_utc"])
    tr = pd.read_parquet(paths.SITE_DIR / "raw_small" / "ibtracs_wp_tracks.parquet")
    yrs = (ev["closest_time_utc"].max() - pd.Timestamp("2015-01-01", tz="UTC")).days / 365.25
    fig = plt.figure(figsize=(17, 7.6))
    ax = fig.add_axes([0.05, 0.1, 0.42, 0.85])
    _land2(ax, lw=0.4)
    for sid in ev["sid"]:
        t = tr[tr["SID"] == sid].sort_index()
        ax.plot(t["LON"], t["LAT"], color=OI["blue"], lw=0.9, alpha=0.45, zorder=3)
    for r_km, ls in ((300, ":"), (500, "--")):
        x, y = _km_circle(LON0, LAT0, r_km)
        ax.plot(x, y, color="black", lw=1.4, ls=ls, zorder=4)
        ax.text(LON0, LAT0 - r_km / 111.2 - 0.05, f"{r_km} km", ha="center", va="top", fontsize=15, zorder=6,
                bbox=dict(fc="white", ec="none", pad=1))
    ax.plot(LON0, LAT0, marker="*", color="black", ms=22, mec="white", mew=1, zorder=7)
    ax.text(LON0 + 0.4, LAT0 + 0.35, "Itbayat", fontsize=19, fontweight="bold", zorder=7,
            bbox=dict(fc="white", ec="none", pad=1, alpha=0.8))
    ax.set_xlim(115.5, 128.5)
    ax.set_ylim(14.0, 27.0)
    ax.set_aspect(1 / K)
    ax.set_xlabel("Longitude (°E)")
    ax.set_ylabel("Latitude (°N)")
    ax.text(0.02, 0.02, f"{len(ev)} storm tracks, 2015 to 2026", transform=ax.transAxes, fontsize=16, color=OI["blue"],
            bbox=dict(fc="white", ec="none", pad=2))
    _label(ax, "A")
    bx = fig.add_axes([0.58, 0.16, 0.40, 0.74])
    m = ev["closest_time_utc"].dt.tz_convert(paths.LOCAL_TZ).dt.month
    n = m.value_counts().reindex(range(1, 13), fill_value=0) / yrs
    close = ev["closest_km"] <= 300
    n3 = m[close].value_counts().reindex(range(1, 13), fill_value=0) / yrs
    x = np.arange(1, 13)
    bx.bar(x, n, 0.75, color=OI["sky"], label="within 500 km")
    bx.bar(x, n3, 0.75, color=OI["blue"], label="within 300 km")
    bx.set_xticks(x, list("JFMAMJJASOND"))
    bx.set_ylabel("Storms per year passing near Itbayat")
    bx.set_xlabel("Month")
    bx.legend(frameon=False, loc="upper left")
    bx.text(0.02, 0.70, f"{len(ev) / yrs:.1f} storms a year\nwithin 500 km;\n{close.sum() / yrs:.1f} within 300 km",
            transform=bx.transAxes, fontsize=19, fontweight="bold", color=INK, va="top")
    _label(bx, "B", x=-0.1)
    fig.text(0.98, 0.005, f"IBTrACS v04r01 (Knapp et al. 2010), storm centres within 500 km, Jan 2015 to Oct 2026 "
             f"({yrs:.1f} years).", fontsize=12, color="0.4", ha="right")
    _save(fig, "storms_exposure")
    return len(ev) / yrs, close.sum() / yrs


# ---------------------------------------------------------------- 3. hours of power during past fuel crises
CRISES = [  # (label, hours of power per day, where, source) — news, evidence of events only
    ("Normal service", 24, "Itbayat", "NPC 2025 (24 h service)"),
    ("Sep 2022\nport congestion, storm", 16, "Batanes", "Manila Bulletin, 3 Sep 2022"),
    ("Jun 2023\ntyphoon Betty (Mawar)", 16, "Batanes", "Rappler, 29 May 2023 (8 h rotational cuts)"),
    ("Sep 2009\nfuel ship in dry dock", 6, "Itbayat", "Philstar, 15 Sep 2009"),
    ("Aug 2011\nrough seas, late fuel", 6, "Itbayat", "Philstar, 27 Aug 2011"),
]


def crisis_hours():
    plt = _plt()
    fig, ax = plt.subplots(figsize=(13, 6.4))
    y = np.arange(len(CRISES))[::-1]
    for yi, (lab, h, where, _) in zip(y, CRISES):
        c = OI["sky"] if h == 24 else (OI["orange"] if where == "Batanes" else OI["vermillion"])
        ax.barh(yi, h, 0.62, color=c, hatch="//" if where == "Batanes" else None, edgecolor="white")
        ax.text(h + 0.4, yi, f"{h} h  ({where})", va="center", fontsize=19, fontweight="bold", color=INK)
    ax.set_yticks(y, [c[0] for c in CRISES], fontsize=17)
    ax.set_xlim(0, 32)
    ax.set_xticks([0, 6, 12, 18, 24])
    ax.set_xlabel("Hours of electricity per day (h)")
    ax.axvline(24, color=SOFT, lw=1, ls=":")
    fig.text(0.99, 0.0, "News reports, evidence of events only: Philstar 2009, 2011; Manila Bulletin 2022; Rappler 2023. "
             "Hatched: whole province.", fontsize=12, color="0.4", ha="right")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    _save(fig, "crisis_hours")


# ---------------------------------------------------------------- 4. what the island uses in a day (synthetic)
def load_day():
    plt = _plt()
    d = pd.read_parquet(paths.LOAD_SYNTH)
    loc = d.index.tz_convert(paths.LOCAL_TZ)
    sel = d[(loc.month.isin([5, 6, 7])) & (loc.year >= 2023)]
    h = sel.groupby(sel.index.tz_convert(paths.LOCAL_TZ).hour).mean()
    parts = [("crit_clinic_kW", "Clinic", OI["vermillion"]), ("crit_water_kW", "Water pumps", OI["blue"]),
             ("crit_telecom_kW", "Phones", OI["purple"]), ("crit_cold_storage_kW", "Cold storage", OI["green"]),
             ("crit_municipal_kW", "Town hall", OI["yellow"]), ("flex_kW", "Homes and shops", "#C9CED6")]
    fig, ax = plt.subplots(figsize=(13, 6.4))
    x = np.arange(24)
    base = np.zeros(24)
    for col, lab, c in parts:
        ax.fill_between(x, base, base + h[col].to_numpy(), step="mid", color=c, lw=0, label=lab)
        base = base + h[col].to_numpy()
    crit = h["critical_kW"].to_numpy()
    ax.plot(x, crit, color=INK, lw=2, drawstyle="steps-mid")
    ax.set_xlim(-0.5, 23.5)
    ax.set_xticks([0, 6, 12, 18, 23], ["00:00", "06:00", "12:00", "18:00", "23:00"])
    ax.set_ylim(0, base.max() * 1.15)
    ax.set_ylabel("Demand (kW)")
    ax.set_xlabel("Hour of day, May to July (local time)")
    ax.legend(frameon=False, ncol=3, loc="upper left", fontsize=16)
    share = crit.sum() / base.sum()
    ax.text(3, crit.max() + 8, f"must stay on: {crit.mean():.0f} kW,\n{share * 100:.0f} % of the energy",
            fontsize=18, fontweight="bold", color=INK)
    fig.text(0.99, 0.0, "SYNTHETIC hourly demand, calibrated to NPC's annual peak and energy for Itbayat (2019 to 2023). "
             "Mean of 2023 to 2026.", fontsize=12, color="0.4", ha="right")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    _save(fig, "load_day")
    return crit.mean(), share


# ---------------------------------------------------------------- 5. demand growth (NPC)
def demand_growth():
    plt = _plt()
    npc = load_site()["npc_itbayat_dpp"]
    t = pd.DataFrame({k: npc[k] for k in ("years", "kind", "peak_kw", "dependable_kw")})
    fig, ax = plt.subplots(figsize=(13, 6.4))
    x = np.arange(len(t))
    hist = (t["kind"] == "hist").to_numpy()
    ax.bar(x[hist], t["peak_kw"][hist], 0.62, color=OI["blue"], label="Peak demand, NPC records")
    ax.bar(x[~hist], t["peak_kw"][~hist], 0.62, color="white", edgecolor=OI["blue"], hatch="//", lw=1.2,
           label="Peak demand, NPC forecast")
    ax.plot(x, t["dependable_kw"], color=INK, lw=2.2, ls="--", marker="o", ms=7, label="Dependable diesel capacity")
    for xi, v in zip(x, t["peak_kw"]):
        ax.text(xi, v + 10, f"{v}", ha="center", fontsize=15, color=OI["blue"])
    ax.set_xticks(x, [str(v) for v in t["years"]])
    ax.set_ylabel("Power (kW)")
    ax.set_ylim(0, 900)
    ax.legend(frameon=False, loc="upper left", fontsize=16)
    g = t["peak_kw"][4] / t["peak_kw"][0] - 1
    ax.text(-0.3, 300, f"+{g * 100:.0f} % in four years", fontsize=20, fontweight="bold", color=OI["blue"])
    fig.text(0.99, 0.0, "NPC Missionary Electrification Plan 2025 to 2029, Annex R (Itbayat diesel power plant).",
             fontsize=12, color="0.4", ha="right")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    _save(fig, "demand_growth")
    return g


# ---------------------------------------------------------------- 6. how long the tank lasts
def tank_days():
    plt = _plt()
    y = pd.read_csv(P4B / "year.csv").set_index("controller")
    site = load_site()
    full = site["values"]["fuel_storage_l_assumed"]["value"] if "values" in site else 52000
    fig, ax = plt.subplots(figsize=(13, 6.4))
    tank = np.linspace(0, 60000, 61)
    for c, lab in (("A", "Diesel only (today)"), ("C", "With 300 kWp solar, 1,500 kWh battery")):
        per_day = y.loc[c, "diesel_l_per_yr"] / 365
        ax.plot(tank / 1000, tank / per_day, color=COL4[c], lw=3, ls=STY4[c][0], label=f"{lab}: {per_day:.0f} L a day")
    per_a = y.loc["A", "diesel_l_per_yr"] / 365
    for v, txt in ((full, "full tank\n(assumed)"), (6000, "low tank at\nstorm start")):
        ax.axvline(v / 1000, color=SOFT, lw=1, ls=":")
        xx, yy = (v / 1000 + 0.8, 34) if v < 20000 else (v / 1000 - 0.8, 16)
        ax.text(xx, yy, f"{txt}\n{v / per_a:.0f} days today", fontsize=16, color=INK, ha="left" if v < 20000 else "right")
    ax.set_xlabel("Fuel in the tank when the boat stops coming (1,000 L)")
    ax.set_ylabel("Days until the tank is empty (d)")
    ax.set_xlim(0, 60)
    ax.set_ylim(0, 110)
    ax.legend(frameon=False, loc="upper left", fontsize=16)
    fig.text(0.99, 0.0, "Average daily use from the year simulation; tank size and level are ASSUMPTIONS "
             "(INL 2025: about 2 months of fuel on hand).", fontsize=12, color="0.4", ha="right")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    _save(fig, "tank_days")


# ---------------------------------------------------------------- 7. forecast accuracy
RMSE = {  # docs/validation_forecast.md, daylight hours, satellite reference, Nov 2024 to Oct 2026
    "Yesterday's sun\n(persistence)": (150.0, 174.3), "GFS (USA)": (151.3, 162.3), "ICON (Germany)": (118.7, 126.7),
    "Mean of 3 models": (95.2, 103.8), "ECMWF (Europe)": (90.8, 101.3), "AURORA": (80.6, 92.6)}


def forecast_rmse():
    plt = _plt()
    fig, ax = plt.subplots(figsize=(13, 6.4))
    labs = list(RMSE)
    y = np.arange(len(labs))
    w = 0.38
    for i, (ld, c, hatch) in enumerate(((0, OI["blue"], None), (1, OI["sky"], "//"))):
        v = [RMSE[k][ld] for k in labs]
        cols = [c if k == "AURORA" else ("#9AA5B1" if ld == 0 else "#CDD3DA") for k in labs]
        ax.barh(y + (0.5 - i) * w, v, w * 0.92, color=cols, hatch=hatch, edgecolor="white",
                label=f"{'tomorrow' if ld == 0 else 'day after'}")
        for yi, vi in zip(y + (0.5 - i) * w, v):
            ax.text(vi + 2, yi, f"{vi:.0f}", va="center", fontsize=15)
    ax.set_yticks(y, labs, fontsize=17)
    ax.set_xlabel("Error in sunshine forecast, RMSE (W/m²)")
    ax.set_xlim(0, 200)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(fc="#9AA5B1", label="tomorrow (lead day 1)"),
                       Patch(fc="#CDD3DA", hatch="//", ec="white", label="day after (lead day 2)")],
              frameon=False, loc="center right", fontsize=16)
    ax.text(107, 5.0, "11 % lower than ECMWF", fontsize=18, fontweight="bold", color=OI["blue"], va="center")
    fig.text(0.99, 0.0, "Rolling backtest, 24 months (Nov 2024 to Oct 2026), daylight hours, satellite reference. "
             "Open-Meteo archived forecasts.", fontsize=12, color="0.4", ha="right")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    _save(fig, "forecast_rmse")


def forecast_week(start="2025-07-15", end="2025-07-22"):
    plt = _plt()
    b = pd.read_parquet(paths.SITE_DIR / "forecast" / "backtest_solar.parquet")
    b = b[(b["lead_day"] == 1) & (b["calibrated"])]
    b.index = b.index.tz_convert(paths.LOCAL_TZ)
    b = b.loc[start:end].sort_index()
    fig, ax = plt.subplots(figsize=(13, 6.0))
    ax.fill_between(b.index, b["ghi_p10"], b["ghi_p90"], color=OI["sky"], alpha=0.45, lw=0, label="AURORA range (P10 to P90)")
    ax.plot(b.index, b["ghi_p50"], color=OI["blue"], lw=2.2, label="AURORA (P50)")
    ax.plot(b.index, b["ghi_nwp_mean"], color=OI["orange"], lw=1.8, ls="--", label="Weather models, raw mean")
    ax.plot(b.index, b["ghi_ref"], ls="none", marker="o", ms=4.5, color=INK, label="Satellite (truth)")
    ax.set_ylabel("Sunshine, GHI (W/m²)")
    ax.set_ylim(0, 1250)
    import matplotlib.dates as mdates
    ax.xaxis.set_major_locator(mdates.DayLocator(tz=b.index.tz))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b", tz=b.index.tz))
    ax.legend(frameon=False, ncol=2, loc="upper right", fontsize=15)
    fig.text(0.99, 0.0, "Forecast issued the day before (lead day 1). July 2025, typhoon Wipha passing Batanes.",
             fontsize=12, color="0.4", ha="right")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    _save(fig, "forecast_week")


# ---------------------------------------------------------------- 8. Survival Clock during Mawar
def _h(job, c):
    d = pd.read_csv(P4B / "hourly" / f"{job}_{c}.csv.gz", index_col=0, parse_dates=True)
    return d


def survival_clock(job="rec_mawar2023_pv300_bat1500_d14"):
    plt = _plt()
    fig, (ax, bx) = plt.subplots(2, 1, figsize=(13, 8.2), sharex=True, gridspec_kw=dict(height_ratios=[1.3, 1]))
    t0 = None
    for c in ("B", "O", "C"):
        d = _h(job, c)
        if t0 is None:
            t0 = d.index[0]
        x = (d.index - t0) / pd.Timedelta(days=1)
        dd = d["cest_h"].clip(upper=72).groupby(np.floor(x)).mean()
        ax.plot(dd.index + 0.5, dd.to_numpy(), color=COL4[c], lw=2.4, ls=STY4[c][0], marker=STY4[c][1], ms=8,
                label=NAME4[c])
        bx.plot(x, d["tank_end"] / 1000, color=COL4[c], lw=2.2, ls=STY4[c][0])
    d = _h(job, "A")
    bx.plot((d.index - t0) / pd.Timedelta(days=1), d["tank_end"] / 1000, color=COL4["A"], lw=2.2, ls=STY4["A"][0],
            label=NAME4["A"])
    ax.axhline(24, color=SOFT, lw=1, ls=":")
    ax.text(17.9, 25.5, "one day in hand", ha="right", fontsize=15, color=SOFT)
    ax.set_ylabel("Survival Clock,\ndaily mean (h)")
    ax.set_ylim(0, 78)
    ax.legend(frameon=False, ncol=3, loc="upper left", fontsize=16, bbox_to_anchor=(0, 1.16))
    bx.set_ylabel("Fuel left (1,000 L)")
    bx.set_xlabel("Days since 27 May 2023 (typhoon Mawar, tanker 14 days late)")
    bx.legend(frameon=False, loc="upper center", fontsize=16)
    bx.set_xlim(0, 18)
    bx.set_ylim(0, 7)
    bx.annotate("tanker arrives\n(tank refilled)", xy=(15.1, 6.9), xytext=(15.5, 4.2), fontsize=15,
                arrowprops=dict(arrowstyle="->", color=INK))
    _label(ax, "A", x=-0.06)
    _label(bx, "B", x=-0.06)
    fig.text(0.99, 0.0, "Survival Clock: hours the clinic, water and phones last on battery and pessimistic sun if diesel "
             "stopped now (capped at 72 h).", fontsize=12, color="0.4", ha="right")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    _save(fig, "survival_clock")


# ---------------------------------------------------------------- 9. one day of AURORA's plan
def dispatch_day(job="rec_mawar2023_pv300_bat1500_d14", day0=2, ndays=3):
    plt = _plt()
    d = _h(job, "C")
    t0 = d.index[0]
    d = d[(d.index >= t0 + pd.Timedelta(days=day0)) & (d.index < t0 + pd.Timedelta(days=day0 + ndays))]
    x = (d.index - t0) / pd.Timedelta(days=1)
    fig, (ax, bx) = plt.subplots(2, 1, figsize=(13, 8.0), sharex=True, gridspec_kw=dict(height_ratios=[1.5, 1]))
    parts = [("pv_used", "Solar", OI["yellow"]), ("discharge", "Battery", OI["blue"]), ("diesel", "Diesel", INK)]
    base = np.zeros(len(d))
    for col, lab, c in parts:
        v = d[col].clip(lower=0).to_numpy()
        ax.fill_between(x, base, base + v, step="post", color=c, lw=0, label=lab, alpha=0.9)
        base = base + v
    served = d["crit"] + d["flex"] - d["shed"]
    ax.step(x, d["crit"], where="post", color=OI["vermillion"], lw=2.4, label="Clinic, water, phones")
    ax.step(x, d["crit"] + d["flex"], where="post", color=SOFT, lw=1.6, ls="--", label="All demand")
    ax.set_ylabel("Power (kW)")
    ax.legend(frameon=False, ncol=3, loc="upper left", fontsize=15, bbox_to_anchor=(0, 1.22))
    bx.step(x, d["soc_end"] * 100, where="post", color=OI["blue"], lw=2.2, label="Battery charge")
    bx.set_ylabel("Battery (%)")
    bx.set_ylim(0, 100)
    sh = d["shed"] > 0
    if sh.any():
        for xi in x[sh.to_numpy()]:
            bx.axvspan(xi, xi + 1 / 24, color=OI["orange"], alpha=0.35, lw=0)
        bx.text(0.99, 0.9, "orange: a block of homes cut", transform=bx.transAxes, ha="right", fontsize=15,
                color=OI["orange"])
    bx.set_xlabel("Days since 27 May 2023 (typhoon Mawar, tanker 14 days late)")
    _label(ax, "A", x=-0.06)
    _label(bx, "B", x=-0.06)
    fig.tight_layout()
    _save(fig, "dispatch_day")
    return served


# ---------------------------------------------------------------- 10. the twin matches NPC's records
def twin_check():
    plt = _plt()
    from .calibration import annual
    npc = load_site()["npc_itbayat_dpp"]
    t = pd.DataFrame({k: npc[k] for k in ("years", "kind", "peak_kw", "gross_gen_mwh")}).set_index("years")
    new = annual(pd.read_parquet(paths.LOAD_SYNTH))
    yrs = [y for y in t.index if y in new.index and t.loc[y, "kind"] == "hist"]
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.6))
    for ax, col, mcol, ylab, L in ((axes[0], "gross_gen_mwh", "mwh", "Energy per year (MWh)", "A"),
                                   (axes[1], "peak_kw", "peak", "Peak demand (kW)", "B")):
        x = np.arange(len(yrs))
        ax.bar(x, t.loc[yrs, col], 0.6, color=OI["sky"], label="NPC records")
        ax.plot(x, new.loc[yrs, mcol], color=INK, lw=2.2, marker="o", ms=9, label="Digital twin")
        ax.set_xticks(x, [str(y) for y in yrs])
        ax.set_ylabel(ylab)
        ax.set_ylim(0, None)
        err = (new.loc[yrs, mcol] / t.loc[yrs, col] - 1).abs().max() * 100
        ax.text(0.03, 0.93, f"within {err:.0f} % every year", transform=ax.transAxes, fontsize=17, fontweight="bold",
                va="top")
        _label(ax, L, x=-0.1)
    axes[1].legend(frameon=False, loc="lower right", fontsize=16)
    fig.text(0.99, 0.0, "NPC MEP 2025 to 2029, Annex R. The hourly shape is SYNTHETIC; its yearly totals are matched to NPC.",
             fontsize=12, color="0.4", ha="right")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    _save(fig, "twin_check")


# ---------------------------------------------------------------- 11. sizing map
def sizing_map():
    plt = _plt()
    s = pd.read_csv(P4B / "sweep.csv")
    s = s[s["controller"] == "C"]
    g = s.groupby(["pv_kwp", "bat_kwh"])[["flex_shed_h", "crit_outage_h"]].mean().reset_index()
    pv = sorted(g["pv_kwp"].unique())
    bat = sorted(g["bat_kwh"].unique())
    M = g.pivot(index="pv_kwp", columns="bat_kwh", values="flex_shed_h").loc[pv, bat].to_numpy()
    Cc = g.pivot(index="pv_kwp", columns="bat_kwh", values="crit_outage_h").loc[pv, bat].to_numpy()
    fig, ax = plt.subplots(figsize=(13, 6.2))
    im = ax.imshow(M, cmap="viridis_r", aspect="auto", origin="lower")
    for i in range(len(pv)):
        for j in range(len(bat)):
            txt = f"{M[i, j]:.0f} h" + ("" if Cc[i, j] < 0.5 else f"\nclinic {Cc[i, j]:.0f} h")
            ax.text(j, i, txt, ha="center", va="center", fontsize=15,
                    color="white" if M[i, j] > np.nanmax(M) * 0.45 else INK)
    i0, j0 = pv.index(300.0), bat.index(1500.0)
    ax.add_patch(plt.Rectangle((j0 - 0.5, i0 - 0.5), 1, 1, fill=False, ec=OI["vermillion"], lw=4))
    ax.set_xticks(range(len(bat)), [f"{b:,.0f}" for b in bat])
    ax.set_yticks(range(len(pv)), [f"{p:.0f}" for p in pv])
    ax.set_xlabel("Battery energy (kWh)")
    ax.set_ylabel("Solar (kWp)")
    cb = fig.colorbar(im, ax=ax, pad=0.02)
    cb.set_label("Hours homes are cut (h)")
    fig.text(0.99, 0.0, "AURORA, mean of three typhoons, tanker 14 days late. Battery power = min(kWh per hour, 375 kW). "
             "Red box: chosen size.", fontsize=12, color="0.4", ha="right")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    _save(fig, "sizing_map")
    return g


FIGS = {"map": map_overview, "storms": storms_exposure, "crisis": crisis_hours, "load": load_day,
        "growth": demand_growth, "tank": tank_days, "fc": forecast_rmse, "fcweek": forecast_week,
        "clock": survival_clock, "dispatch": dispatch_day, "twin": twin_check, "sizing": sizing_map}

if __name__ == "__main__":
    for k in (sys.argv[1:] or FIGS):
        r = FIGS[k]()
        if r is not None and not isinstance(r, (pd.DataFrame, pd.Series)):
            print(k, r)
