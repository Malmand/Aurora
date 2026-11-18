"""Every figure of the GSC deck, drawn at the exact size it takes on the slide.

    python -m aurora.plotting.slides            # all figures
    python -m aurora.plotting.slides map storms # some of them

Each figure is SIZE_PX wide and tall on a 1920 x 1080 slide. The figure is built at
100 px per inch, so a 16 pt label is 22 px on the slide, close to the 24 to 26 px body
text. Saved as PDF plus 300 dpi PNG in figures/slides/. One message per figure; sources
go in the slide footer, not in the figure.

Every number is read from committed data: site.yaml, typhoon_events.csv, the IBTrACS
tracks, the synthetic (NPC-calibrated) load, the forecast backtest, results/phase4b.
News-reported hours (crisis_hours) are typed in with their source, as evidence of events.
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from ..data import paths
from ..data.site import load_site

OUT = paths.ROOT / "figures" / "slides"
P4B = paths.ROOT / "results" / "phase4b"
BASEMAP = paths.ROOT / "data" / "basemap" / "luzon_strait_land.geojson"
LAT0, LON0 = paths.LAT, paths.LON
K = np.cos(np.radians(LAT0))

INK, SOFT, MUTE = "#14213D", "#4A5568", "#8A93A0"
BLUE, SKY, ORANGE, VERM, GREEN, YELLOW, PURPLE = "#0072B2", "#56B4E9", "#E69F00", "#D55E00", "#009E73", "#F0E442", "#CC79A7"
GREY = "#A7B0BC"
SEA, LAND, COAST = "#EAF2F8", "#F3EFE6", "#8C8577"
COL = {"A": INK, "B": GREY, "O": ORANGE, "C": BLUE}
NAME = {"A": "Diesel only (today)", "B": "Solar + battery, no plan", "O": "Careful operator", "C": "AURORA"}
LS = {"A": "-", "B": ":", "O": "--", "C": "-"}
MK = {"A": "o", "B": "^", "O": "s", "C": "D"}
KEYS = ["A", "B", "O", "C"]

SIDE = (1120, 570)      # figure next to a column of big numbers
WIDE = (1664, 570)      # figure across the slide


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.family": "Inter", "font.size": 16, "axes.labelsize": 17, "xtick.labelsize": 16, "ytick.labelsize": 16,
        "legend.fontsize": 16, "axes.linewidth": 1.0, "axes.edgecolor": INK, "axes.labelcolor": INK,
        "text.color": INK, "xtick.color": INK, "ytick.color": INK, "xtick.direction": "out", "ytick.direction": "out",
        "xtick.major.size": 6, "ytick.major.size": 6, "xtick.major.width": 1.0, "ytick.major.width": 1.0,
        "xtick.minor.visible": False, "ytick.minor.visible": False,
        "axes.spines.top": False, "axes.spines.right": False, "axes.grid": False,
        "legend.frameon": False, "legend.handlelength": 2.4, "axes.labelpad": 8,
        "figure.dpi": 100, "savefig.dpi": 300, "pdf.fonttype": 42, "mathtext.default": "regular",
    })
    return plt


def _fig(size, **kw):
    plt = _plt()
    return plt.subplots(figsize=(size[0] / 100, size[1] / 100), **kw)


def _save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(OUT / f"{name}.{ext}", facecolor="white")
    import matplotlib.pyplot as plt
    plt.close(fig)


def _panel(ax, letter, x=-0.02, y=1.02):
    ax.text(x, y, letter, transform=ax.transAxes, fontsize=21, fontweight="bold", ha="right", va="bottom")


def _hav(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(np.radians, (lon1, lat1, lon2, lat2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * np.arcsin(np.sqrt(a))


def _circle(r_km, n=240):
    th = np.linspace(0, 2 * np.pi, n)
    return LON0 + r_km / (111.2 * K) * np.cos(th), LAT0 + r_km / 111.2 * np.sin(th)


def _land(ax, lw=0.7):
    from matplotlib.patches import Polygon
    g = json.loads(BASEMAP.read_text(encoding="utf-8"))["features"][0]["geometry"]
    polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    for poly in polys:
        ax.add_patch(Polygon(np.asarray(poly[0]), closed=True, fc=LAND, ec=COAST, lw=lw, zorder=1))


def _map_axes(ax, xlim, ylim, ticks=True):
    ax.set_facecolor(SEA)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect(1 / K)
    for s in ("top", "right"):
        ax.spines[s].set_visible(True)
    for s in ax.spines.values():
        s.set_color(INK)
        s.set_linewidth(1.0)
    if ticks:
        ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0f}°E" if float(v).is_integer() else f"{v:.1f}°E")
        ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}°N" if float(v).is_integer() else f"{v:.1f}°N")
    else:
        ax.set_xticks([])
        ax.set_yticks([])


def _halo(t, w=4, c="white"):
    import matplotlib.patheffects as pe
    t.set_path_effects([pe.withStroke(linewidth=w, foreground=c)])
    return t


BOLINAO, MANILA, BASCO = (119.90, 16.39), (120.98, 14.60), (121.97, 20.45)
ROUTE = np.array([BOLINAO, (119.72, 17.4), (120.2, 18.6), (120.9, 19.35), (121.6, 19.95), BASCO, (LON0, LAT0)])
STORMS = {"mawar2023": ("MAWAR", 2023, "Mawar 2023", ORANGE, "--"), "ragasa2025": ("RAGASA", 2025, "Ragasa 2025", BLUE, "-"),
          "mekkhala2026": ("MEKKHALA", 2026, "Mekkhala 2026", PURPLE, "-.")}


def _tracks():
    ev = pd.read_csv(paths.TYPHOON_EVENTS, parse_dates=["closest_time_utc"])
    tr = pd.read_parquet(paths.SITE_DIR / "raw_small" / "ibtracs_wp_tracks.parquet")
    return ev, tr


# ======================================================================= maps
def cover_map(size=(760, 818)):
    """Cover: Itbayat, the three replayed typhoons and the fuel route."""
    fig, ax = _fig(size)
    fig.subplots_adjust(0.02, 0.02, 0.98, 0.98)
    _land(ax)
    ev, tr = _tracks()
    for key, (nm, yr, lab, c, ls) in STORMS.items():
        e = ev[(ev["name"] == nm) & (ev["closest_time_utc"].dt.year == yr)].iloc[0]
        t = tr[tr["SID"] == e["sid"]].sort_index()
        ax.plot(t["LON"], t["LAT"], color=c, lw=3.2, ls=ls, zorder=4)
    for r_km in (300, 500):
        x, y = _circle(r_km)
        ax.plot(x, y, color=INK, lw=1.0, ls=":", zorder=3, alpha=0.6)
    ax.plot(ROUTE[:, 0], ROUTE[:, 1], color=VERM, lw=3, ls=(0, (2, 1.5)), zorder=5)
    ax.plot(*BOLINAO, marker="o", color=VERM, ms=11, mec="white", mew=1.5, zorder=6)
    ax.plot(LON0, LAT0, marker="*", color=INK, ms=30, mec="white", mew=1.5, zorder=7)
    _halo(ax.text(LON0 + 0.35, LAT0 + 0.25, "Itbayat", fontsize=26, fontweight="bold", zorder=8))
    _halo(ax.text(BOLINAO[0] + 0.25, BOLINAO[1] - 0.45, "fuel tanker\nport, Bolinao", fontsize=17, color=VERM, zorder=8))
    _halo(ax.text(118.15, 18.9, "fuel route", fontsize=17, color=VERM, zorder=8))
    for (x, y, ha), key in (((116.9, 20.15, "left"), "ragasa2025"), ((125.0, 23.4, "right"), "mekkhala2026"),
                            ((126.8, 19.0, "right"), "mawar2023")):
        nm, yr, lab, c, ls = STORMS[key]
        _halo(ax.text(x, y, lab, fontsize=18, fontweight="bold", color=c, ha=ha, zorder=8))
    for txt, (x, y) in {"LUZON": (121.3, 16.9), "TAIWAN": (121.0, 23.7)}.items():
        ax.text(x, y, txt, fontsize=17, color=SOFT, ha="center", style="italic", zorder=2)
    _halo(ax.text(LON0, LAT0 + 500 / 111.2 - 0.45, "500 km", fontsize=15, color=SOFT, ha="center", zorder=8))
    _map_axes(ax, (116.5, 127.0), (15.6, 25.4), ticks=False)
    _save(fig, "cover_map")


def map_where(size=SIDE):
    """A: the region and the fuel route. B: the Batanes islands."""
    plt = _plt()
    fig = plt.figure(figsize=(size[0] / 100, size[1] / 100))
    ax = fig.add_axes([0.075, 0.08, 0.53, 0.84])
    _land(ax)
    ax.plot(ROUTE[:, 0], ROUTE[:, 1], color=VERM, lw=3, ls=(0, (2, 1.5)), zorder=4)
    seg = _hav(ROUTE[:-1, 0], ROUTE[:-1, 1], ROUTE[1:, 0], ROUTE[1:, 1]).sum()
    ax.plot(*BOLINAO, marker="o", color=VERM, ms=11, mec="white", mew=1.5, zorder=6)
    _halo(ax.text(BOLINAO[0] - 0.3, BOLINAO[1], "Bolinao\nfuel port", fontsize=17, ha="right", va="center", color=VERM, zorder=6))
    _halo(ax.text(118.9, 18.75, f"≈ {round(seg, -1):.0f} km\nby sea", fontsize=18, fontweight="bold", ha="center", color=VERM, zorder=6))
    ax.plot(*MANILA, marker="s", color=INK, ms=9, mec="white", zorder=6)
    _halo(ax.text(MANILA[0] + 0.3, MANILA[1], "Manila", fontsize=16, va="center", zorder=6))
    ax.plot(LON0, LAT0, marker="*", color=INK, ms=26, mec="white", mew=1.5, zorder=7)
    _halo(ax.text(LON0 + 0.5, LAT0 + 0.05, "Itbayat", fontsize=21, fontweight="bold", va="center", zorder=7))
    for txt, (x, y) in {"LUZON": (121.5, 16.7), "TAIWAN": (121.0, 23.65)}.items():
        ax.text(x, y, txt, fontsize=16, color=SOFT, ha="center", style="italic", zorder=2)
    ax.text(125.4, 17.3, "Philippine\nSea", fontsize=15, color=MUTE, ha="center", style="italic")
    ax.text(117.3, 21.6, "South\nChina Sea", fontsize=15, color=MUTE, ha="center", style="italic")
    ax.add_patch(plt.Rectangle((121.62, 20.18), 0.62, 0.86, fill=False, ec=INK, lw=1.6, zorder=8))
    _map_axes(ax, (116.0, 127.5), (14.0, 25.0))
    ax.set_xticks([118, 122, 126])
    ax.set_yticks([16, 20, 24])
    _panel(ax, "A")
    bx = fig.add_axes([0.665, 0.08, 0.33, 0.84])
    _land(bx, lw=1.1)
    bx.plot(LON0, LAT0, marker="*", color=INK, ms=30, mec="white", mew=1.5, zorder=7)
    _halo(bx.text(LON0 + 0.045, LAT0 + 0.055, "Itbayat", fontsize=22, fontweight="bold", zorder=7))
    _halo(bx.text(LON0 + 0.045, LAT0 + 0.005, "3,128 people\n1 diesel plant", fontsize=16, va="top", color=SOFT, zorder=7))
    bx.plot(*BASCO, marker="o", color=INK, ms=11, mec="white", mew=1.5, zorder=7)
    _halo(bx.text(BASCO[0] + 0.035, BASCO[1] + 0.02, "Basco\ncapital", fontsize=16, va="center", zorder=7))
    _halo(bx.text(121.86, 20.30, "Sabtang", fontsize=15, ha="right", color=SOFT, zorder=7))
    d = _hav(LON0, LAT0, *BASCO)
    bx.annotate("", xy=(BASCO[0] - 0.015, BASCO[1] + 0.03), xytext=(LON0 + 0.015, LAT0 - 0.035),
                arrowprops=dict(arrowstyle="<|-|>", color=VERM, lw=2.2, mutation_scale=18), zorder=6)
    _halo(bx.text(121.735, 20.6, f"{d:.0f} km\nopen sea", fontsize=18, fontweight="bold", color=VERM, ha="center",
                  va="center", zorder=6))
    x0, y0 = 122.03, 20.23
    bx.plot([x0, x0 + 10 / (111.2 * K)], [y0, y0], color=INK, lw=3.5, solid_capstyle="butt", zorder=8)
    bx.text(x0 + 5 / (111.2 * K), y0 + 0.018, "10 km", ha="center", fontsize=15, zorder=8)
    _map_axes(bx, (121.62, 122.24), (20.18, 21.04))
    bx.set_xticks([121.7, 121.9, 122.1])
    bx.set_yticks([20.3, 20.6, 20.9])
    _panel(bx, "B")
    _save(fig, "map_where")
    return round(seg), round(d)


def storms(size=SIDE):
    """A: every storm track within 500 km since 2015. B: storms per year by month."""
    plt = _plt()
    ev, tr = _tracks()
    yrs = (ev["closest_time_utc"].max() - pd.Timestamp("2015-01-01", tz="UTC")).days / 365.25
    fig = plt.figure(figsize=(size[0] / 100, size[1] / 100))
    ax = fig.add_axes([0.075, 0.08, 0.44, 0.84])
    _land(ax, lw=0.5)
    for sid in ev["sid"]:
        t = tr[tr["SID"] == sid].sort_index()
        ax.plot(t["LON"], t["LAT"], color=BLUE, lw=1.1, alpha=0.4, zorder=3)
    for r_km, ls in ((300, "--"), (500, "-")):
        x, y = _circle(r_km)
        ax.plot(x, y, color=INK, lw=1.6, ls=ls, zorder=4)
        _halo(ax.text(LON0 + r_km / (111.2 * K) * 0.71 + 0.1, LAT0 - r_km / 111.2 * 0.71 - 0.1, f"{r_km} km",
                      fontsize=15, fontweight="bold", zorder=6))
    ax.plot(LON0, LAT0, marker="*", color=INK, ms=22, mec="white", mew=1.5, zorder=7)
    _map_axes(ax, (115.0, 128.7), (13.5, 28.0))
    ax.set_xticks([116, 122, 128])
    ax.set_yticks([15, 20, 25])
    _panel(ax, "A")
    bx = fig.add_axes([0.62, 0.17, 0.37, 0.75])
    m = ev["closest_time_utc"].dt.tz_convert(paths.LOCAL_TZ).dt.month
    n5 = m.value_counts().reindex(range(1, 13), fill_value=0) / yrs
    n3 = m[ev["closest_km"] <= 300].value_counts().reindex(range(1, 13), fill_value=0) / yrs
    x = np.arange(1, 13)
    bx.bar(x, n5, 0.78, color=SKY, label="within 500 km")
    bx.bar(x, n3, 0.78, color=BLUE, label="within 300 km")
    bx.set_xticks(x, list("JFMAMJJASOND"), fontsize=15)
    bx.set_ylabel("Storms per year")
    bx.set_xlabel("Month")
    bx.set_ylim(0, 1.45)
    bx.legend(loc="upper left", fontsize=15, handlelength=1.2)
    _panel(bx, "B", x=-0.12)
    _save(fig, "storms")
    return len(ev) / yrs, (ev["closest_km"] <= 300).sum() / yrs


# ======================================================================= problem charts
CRISES = [  # (label, hours of power per day, where) — news reports, evidence of events only
    ("Normal service", 24, "Itbayat"),
    ("Sep 2022 · port congestion, storm", 16, "Batanes"),
    ("Jun 2023 · typhoon Betty (Mawar)", 16, "Batanes"),
    ("Sep 2009 · fuel ship in dry dock", 6, "Itbayat"),
    ("Aug 2011 · rough seas, late fuel", 6, "Itbayat"),
]


def crisis_hours(size=SIDE):
    fig, ax = _fig(size)
    fig.subplots_adjust(0.36, 0.15, 0.97, 0.97)
    y = np.arange(len(CRISES))[::-1]
    for yi, (lab, h, where) in zip(y, CRISES):
        c = SKY if h == 24 else (ORANGE if where == "Batanes" else VERM)
        ax.barh(yi, h, 0.66, color=c, hatch="//" if where == "Batanes" else None, edgecolor="white", lw=0)
        ax.text(h + 0.5, yi, f"{h} h", va="center", fontsize=20, fontweight="bold")
        ax.text(h + 3.9, yi, where, va="center", fontsize=15, color=SOFT)
    ax.set_yticks(y, [c[0] for c in CRISES], fontsize=16)
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(0, 31)
    ax.set_xticks([0, 6, 12, 18, 24])
    ax.set_xlabel("Hours of electricity per day (h)")
    _save(fig, "crisis_hours")


def demand_growth(size=SIDE):
    npc = load_site()["npc_itbayat_dpp"]
    t = pd.DataFrame({k: npc[k] for k in ("years", "kind", "peak_kw", "dependable_kw")})
    fig, ax = _fig(size)
    fig.subplots_adjust(0.09, 0.1, 0.99, 0.96)
    x = np.arange(len(t))
    hist = (t["kind"] == "hist").to_numpy()
    ax.bar(x[hist], t["peak_kw"][hist], 0.66, color=BLUE, label="Peak demand, NPC records")
    ax.bar(x[~hist], t["peak_kw"][~hist], 0.66, color="white", edgecolor=BLUE, hatch="//", lw=1.4,
           label="Peak demand, NPC forecast")
    ax.plot(x, t["dependable_kw"], color=INK, lw=2.2, ls="--", marker="o", ms=7, label="Dependable diesel capacity")
    for xi, v, hh in zip(x, t["peak_kw"], hist):
        ax.text(xi, v + 12, f"{v}", ha="center", fontsize=15, color=BLUE, fontweight="bold" if hh else "normal")
    ax.set_xticks(x, [f"'{str(v)[2:]}" for v in t["years"]])
    ax.set_ylabel("Power (kW)")
    ax.set_ylim(0, 1060)
    ax.legend(loc="upper left", fontsize=15, ncol=1)
    g = t["peak_kw"][4] / t["peak_kw"][0] - 1
    ax.annotate(f"+{g * 100:.0f} % in four years", xy=(4.3, 285), xytext=(4.9, 590), fontsize=19, fontweight="bold",
                color=BLUE, arrowprops=dict(arrowstyle="->", color=BLUE, lw=1.8))
    _save(fig, "demand_growth")


def load_day(size=SIDE):
    d = pd.read_parquet(paths.LOAD_SYNTH)
    loc = d.index.tz_convert(paths.LOCAL_TZ)
    sel = d[(loc.month.isin([5, 6, 7])) & (loc.year >= 2023)]
    h = sel.groupby(sel.index.tz_convert(paths.LOCAL_TZ).hour).mean()
    parts = [("crit_clinic_kW", "Clinic", VERM), ("crit_water_kW", "Water pumps", BLUE), ("crit_telecom_kW", "Phones", PURPLE),
             ("crit_cold_storage_kW", "Cold storage", GREEN), ("crit_municipal_kW", "Town hall", YELLOW),
             ("flex_kW", "Homes and shops", "#D5DAE1")]
    fig, ax = _fig(size)
    fig.subplots_adjust(0.09, 0.15, 0.96, 0.97)
    x = np.arange(25)
    base = np.zeros(25)
    for col, lab, c in parts:
        v = np.r_[h[col].to_numpy(), h[col].to_numpy()[:1]]
        ax.fill_between(x, base, base + v, step="post", color=c, lw=0, label=lab)
        base = base + v
    crit = np.r_[h["critical_kW"].to_numpy(), h["critical_kW"].to_numpy()[:1]]
    ax.step(x, crit, where="post", color=INK, lw=2.2)
    ax.set_xlim(0, 24)
    ax.set_xticks([0, 6, 12, 18, 24], ["00:00", "06:00", "12:00", "18:00", "24:00"])
    ax.set_ylim(0, 330)
    ax.set_ylabel("Demand (kW)")
    ax.set_xlabel("Hour of the day, May to July")
    ax.legend(ncol=3, loc="upper left", fontsize=15, handlelength=1.2, columnspacing=1.2)
    share = h["critical_kW"].sum() / h["total_kW"].sum()
    _halo(ax.text(0.5, 88, f"must stay on: {h['critical_kW'].mean():.0f} kW, {share * 100:.0f} % of the energy",
                  fontsize=17, fontweight="bold"), w=5)
    _save(fig, "load_day")
    return h["critical_kW"].mean(), share


def tank_days(size=SIDE):
    y = pd.read_csv(P4B / "year.csv").set_index("controller")
    full = load_site()["values"]["fuel_storage_l_assumed"]["value"]
    fig, ax = _fig(size)
    fig.subplots_adjust(0.09, 0.14, 0.97, 0.96)
    tank = np.linspace(0, 56000, 57)
    per = {c: y.loc[c, "diesel_l_per_yr"] / 365 for c in ("A", "C")}
    for c, lab in (("A", f"Diesel only (today): {per['A']:.0f} L a day"),
                   ("C", f"With solar and battery: {per['C']:.0f} L a day")):
        ax.plot(tank / 1000, tank / per[c], color=COL[c], lw=3.2, ls=LS[c], label=lab)
    for v, txt in ((6000, "low tank"), (full, "full tank")):
        ax.plot([v / 1000] * 2, [0, v / per["A"]], color=SOFT, lw=1.2, ls=":")
        ax.plot(v / 1000, v / per["A"], "o", color=INK, ms=10, zorder=5)
        _halo(ax.text(v / 1000 + (1.0 if v < 20000 else -1.5), 30 if v < 20000 else 32,
                      f"{txt}:\n{v / per['A']:.0f} days", fontsize=18, fontweight="bold", ha="left" if v < 20000 else "right"))
    ax.set_xlabel("Fuel in the tank when the boat stops (1,000 L)")
    ax.set_ylabel("Days until empty (d)")
    ax.set_xlim(0, 56)
    ax.set_ylim(0, 100)
    ax.legend(loc="upper left", fontsize=16)
    _save(fig, "tank_days")


# ======================================================================= idea
def system_diagram(size=(740, 792)):
    """How AURORA sits on the island grid: software layer above the existing plant."""
    from matplotlib.patches import FancyBboxPatch
    fig, ax = _fig(size)
    fig.subplots_adjust(0, 0, 1, 1)
    ax.set_xlim(0, 7.4)
    ax.set_ylim(0, 7.92)
    ax.axis("off")

    def box(x, y, w, h, title, sub, c, fill="white", ls="-", tc=INK):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.14", fc=fill, ec=c, lw=2.4, ls=ls))
        ax.text(x + w / 2, y + h / 2 + (0.17 if sub else 0), title, ha="center", va="center", fontsize=19, fontweight="bold", color=tc)
        if sub:
            ax.text(x + w / 2, y + h / 2 - 0.22, sub, ha="center", va="center", fontsize=15, color=SOFT if tc == INK else tc)

    def arrow(p, q, c=SOFT, ls="-", lw=2.0):
        ax.annotate("", xy=q, xytext=p, arrowprops=dict(arrowstyle="-|>", color=c, lw=lw, ls=ls, mutation_scale=18))

    # AURORA layer
    ax.add_patch(FancyBboxPatch((0.2, 5.55), 7.0, 2.15, boxstyle="round,pad=0,rounding_size=0.18", fc="#E6F1F9", ec=BLUE, lw=2.6))
    ax.text(0.45, 7.35, "AURORA  (software)", fontsize=20, fontweight="bold", color=BLUE, va="center")
    for i, (t, s) in enumerate((("Forecast", "sun, demand,\nthe boat"), ("Plan", "48 h, every\nhour"), ("Clock", "hours the\nclinic lasts"))):
        x = 0.45 + i * 2.27
        ax.add_patch(FancyBboxPatch((x, 5.75), 1.95, 1.3, boxstyle="round,pad=0,rounding_size=0.12", fc="white", ec=BLUE, lw=1.6))
        ax.text(x + 0.975, 6.73, f"{i + 1}  {t}", ha="center", va="center", fontsize=18, fontweight="bold", color=INK)
        ax.text(x + 0.975, 6.2, s, ha="center", va="center", fontsize=14.5, color=SOFT, linespacing=1.15)
        if i < 2:
            arrow((x + 1.97, 6.4), (x + 2.25, 6.4), c=BLUE)
    # plant
    box(0.2, 3.85, 2.3, 1.05, "Solar", "300 kWp", ORANGE)
    box(0.2, 2.55, 2.3, 1.05, "Battery", "1,500 kWh", BLUE)
    box(0.2, 1.25, 2.3, 1.05, "Diesel", "3 units, 850 kW", INK)
    box(0.2, 0.05, 2.3, 0.85, "Fuel tank", "", VERM, ls="--", tc=VERM)
    arrow((1.35, 0.92), (1.35, 1.23), c=VERM)
    ax.add_patch(FancyBboxPatch((3.05, 1.25), 1.15, 3.65, boxstyle="round,pad=0,rounding_size=0.14", fc="white", ec=SOFT, lw=2.4))
    ax.text(3.625, 3.08, "Grid\n480 V", ha="center", va="center", fontsize=18, fontweight="bold", linespacing=1.2)
    for yy in (4.37, 3.07, 1.77):
        arrow((2.52, yy), (3.03, yy))
    box(4.75, 3.45, 2.45, 1.45, "Must stay on", "clinic, water,\nphones", VERM)
    box(4.75, 1.25, 2.45, 1.45, "Homes, shops", "cut in blocks\nonly if needed", GREY)
    arrow((4.22, 4.17), (4.73, 4.17))
    arrow((4.22, 1.97), (4.73, 1.97))
    # control links
    ax.plot([2.75, 2.75], [5.53, 1.77], color=BLUE, lw=2, ls=(0, (3, 2)))
    for yy in (3.07, 1.77):
        arrow((2.75, yy + 0.0), (2.53, yy), c=BLUE, lw=1.8)
    ax.plot([7.32, 7.32], [5.53, 1.97], color=BLUE, lw=2, ls=(0, (3, 2)))
    arrow((7.33, 1.97), (7.22, 1.97), c=BLUE, lw=1.8)
    _halo(ax.text(2.85, 5.3, "sets battery, generators", fontsize=14, color=BLUE, va="center"))
    _halo(ax.text(7.22, 3.07, "cuts homes only\nif fuel runs short", fontsize=14, color=BLUE, va="center", ha="right"))
    _save(fig, "system_diagram")


def survival_clock(size=SIDE, job="rec_mawar2023_pv300_bat1500_d14"):
    plt = _plt()
    fig, (ax, bx) = plt.subplots(2, 1, figsize=(size[0] / 100, size[1] / 100), sharex=True,
                                 gridspec_kw=dict(height_ratios=[1.35, 1], hspace=0.18))
    fig.subplots_adjust(0.1, 0.15, 0.98, 0.9)
    t0 = None
    for c in ("A", "B", "O", "C"):
        d = pd.read_csv(P4B / "hourly" / f"{job}_{c}.csv.gz", index_col=0, parse_dates=True)
        t0 = d.index[0] if t0 is None else t0
        x = (d.index - t0) / pd.Timedelta(days=1)
        if c != "A":
            dd = d["cest_h"].clip(upper=72).groupby(np.floor(x)).mean()
            ax.plot(dd.index + 0.5, dd.to_numpy(), color=COL[c], lw=2.8, ls=LS[c], marker=MK[c], ms=8, label=NAME[c])
        bx.plot(x, d["tank_end"] / 1000, color=COL[c], lw=2.6, ls=LS[c], label=NAME[c] if c == "A" else None)
    ax.axhline(24, color=SOFT, lw=1, ls=":")
    _halo(ax.text(0.2, 26, "one day in hand", fontsize=14, color=SOFT))
    ax.set_ylabel("Survival Clock (h)")
    ax.set_ylim(0, 80)
    ax.set_yticks([0, 24, 48, 72])
    ax.legend(ncol=3, loc="lower left", bbox_to_anchor=(0, 1.0), fontsize=15)
    bx.set_ylabel("Fuel (1,000 L)")
    bx.set_ylim(0, 6.8)
    bx.set_yticks([0, 3, 6])
    bx.set_xlim(0, 18)
    bx.set_xlabel("Days since 27 May 2023 (typhoon Mawar, boat 14 days late)")
    bx.annotate("boat\narrives", xy=(15.05, 6.4), xytext=(15.7, 2.6), fontsize=15, arrowprops=dict(arrowstyle="->", color=INK))
    bx.legend(loc="upper center", fontsize=14, bbox_to_anchor=(0.6, 1.0))
    _panel(ax, "A", x=-0.06)
    _panel(bx, "B", x=-0.06)
    _save(fig, "survival_clock")


# ======================================================================= what's new
def replay(size=(1000, 600), job="rec_mawar2023_pv300_bat1500_d14"):
    plt = _plt()
    h = {c: pd.read_csv(P4B / "hourly" / f"{job}_{c}.csv.gz", index_col=0, parse_dates=True) for c in KEYS}
    x = (h["C"].index - h["C"].index[0]) / pd.Timedelta(days=1)
    arrive = 15.0
    fig, (ax, bx) = plt.subplots(2, 1, figsize=(size[0] / 100, size[1] / 100), sharex=True,
                                 gridspec_kw={"height_ratios": [1.1, 1.25], "hspace": 0.32})
    fig.subplots_adjust(0.25, 0.14, 0.84, 0.93)
    for c in KEYS:
        ax.plot(x, (h[c]["tank_end"] / 1000).where(x < arrive), color=COL[c], ls=LS[c], lw=3, label=NAME[c])
    ax.set_ylabel("Fuel (1,000 L)")
    ax.set_ylim(0, 6.6)
    ax.set_yticks([0, 3, 6])
    ax.axvline(arrive, color=MUTE, lw=1.2, ls=":")
    ax.legend(loc="upper right", ncol=1, fontsize=13, handlelength=2.0, bbox_to_anchor=(1.22, 1.05))
    for i, c in enumerate(KEYS[::-1]):
        d = h[c]
        crit = d["unserved_crit"].to_numpy() > 1e-3
        cut = (d["shed"].to_numpy() > 1e-3) & ~crit
        bx.fill_between(x, i, i + 0.72, where=cut, step="post", color="#A9C4E2", lw=0)
        bx.fill_between(x, i, i + 0.72, where=crit, step="post", color=VERM, lw=0)
        bx.text(18.6, i + 0.36, f"clinic {int(crit.sum())} h\nhomes {int((crit | cut).sum())} h", va="center",
                fontsize=14, fontweight="bold", color=VERM if crit.sum() else INK, linespacing=1.1)
    bx.set_yticks([i + 0.36 for i in range(4)], [NAME[c] for c in KEYS[::-1]], fontsize=15)
    bx.set_ylim(-0.15, 3.9)
    bx.axvline(arrive, color=MUTE, lw=1.2, ls=":")
    bx.set_xlabel("Days after Mawar cut the fuel route (27 May 2023)")
    bx.set_xlim(0, 18)
    bx.set_xticks([0, 3, 6, 9, 12, 15, 18])
    bx.spines["left"].set_visible(False)
    bx.tick_params(axis="y", length=0)
    from matplotlib.patches import Patch
    bx.legend(handles=[Patch(color=VERM, label="clinic dark"), Patch(color="#A9C4E2", label="homes cut")],
              loc="lower right", bbox_to_anchor=(1.0, 0.98), ncol=2, fontsize=14, handlelength=1.2)
    _panel(ax, "A", x=-0.3)
    _panel(bx, "B", x=-0.3)
    _save(fig, "replay")


RMSE = {"Yesterday's sun": (150.0, 174.3), "GFS (USA)": (151.3, 162.3), "ICON (Germany)": (118.7, 126.7),
        "Mean of 3 models": (95.2, 103.8), "ECMWF (Europe)": (90.8, 101.3), "AURORA": (80.6, 92.6)}


def forecast_rmse(size=SIDE):
    """docs/validation_forecast.md: RMSE, daylight hours, satellite reference, Nov 2024 to Oct 2026."""
    fig, ax = _fig(size)
    fig.subplots_adjust(0.22, 0.14, 0.97, 0.97)
    labs = list(RMSE)
    y = np.arange(len(labs))
    w = 0.4
    for i, (ld, hatch) in enumerate(((0, None), (1, "//"))):
        v = [RMSE[k][ld] for k in labs]
        cols = [(BLUE if ld == 0 else SKY) if k == "AURORA" else (GREY if ld == 0 else "#D3D8DF") for k in labs]
        ax.barh(y + (0.5 - i) * w, v, w * 0.9, color=cols, hatch=hatch, edgecolor="white", lw=0)
        for yi, vi, k in zip(y + (0.5 - i) * w, v, labs):
            ax.text(vi + 2, yi, f"{vi:.0f}", va="center", fontsize=15, fontweight="bold" if k == "AURORA" else "normal",
                    color=BLUE if k == "AURORA" else INK)
    ax.set_yticks(y, labs, fontsize=16)
    for lb in ax.get_yticklabels():
        if lb.get_text() == "AURORA":
            lb.set_fontweight("bold")
            lb.set_color(BLUE)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("Forecast error, RMSE (W/m²)")
    ax.set_xlim(0, 190)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(fc=GREY, label="tomorrow"), Patch(fc="#D3D8DF", hatch="//", ec="white", label="day after")],
              loc="center right", fontsize=16, bbox_to_anchor=(1.0, 0.62))
    _save(fig, "forecast_rmse")


def forecast_week(size=WIDE, start="2025-07-15", end="2025-07-22"):
    import matplotlib.dates as mdates
    b = pd.read_parquet(paths.SITE_DIR / "forecast" / "backtest_solar.parquet")
    b = b[(b["lead_day"] == 1) & (b["calibrated"])]
    b.index = b.index.tz_convert(paths.LOCAL_TZ)
    b = b.loc[start:end].sort_index()
    fig, ax = _fig(size)
    fig.subplots_adjust(0.07, 0.12, 0.99, 0.88)
    ax.fill_between(b.index, b["ghi_p10"], b["ghi_p90"], color=SKY, alpha=0.45, lw=0, label="AURORA range (P10 to P90)")
    ax.plot(b.index, b["ghi_p50"], color=BLUE, lw=2.6, label="AURORA forecast")
    ax.plot(b.index, b["ghi_nwp_mean"], color=ORANGE, lw=2.0, ls="--", label="Weather models, raw")
    ax.plot(b.index, b["ghi_ref"], ls="none", marker="o", ms=5.5, color=INK, label="Satellite (truth)")
    ax.set_ylabel("Sunshine (W/m²)")
    ax.set_ylim(0, 1050)
    ax.xaxis.set_major_locator(mdates.DayLocator(tz=b.index.tz))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b", tz=b.index.tz))
    ax.legend(ncol=4, loc="lower left", bbox_to_anchor=(0, 1.0), fontsize=16)
    t = pd.Timestamp("2025-07-18 18:00", tz=b.index.tz)
    _halo(ax.text(t, 990, "typhoon Wipha passes 134 km away", ha="center", fontsize=17, fontweight="bold", color=BLUE))
    _save(fig, "forecast_week")


# ======================================================================= plan
def twin_check(size=WIDE):
    plt = _plt()
    from .calibration import annual
    npc = load_site()["npc_itbayat_dpp"]
    t = pd.DataFrame({k: npc[k] for k in ("years", "kind", "peak_kw", "gross_gen_mwh")}).set_index("years")
    new = annual(pd.read_parquet(paths.LOAD_SYNTH))
    yrs = [y for y in t.index if y in new.index and t.loc[y, "kind"] == "hist"]
    fig, axes = plt.subplots(1, 2, figsize=(size[0] / 100, size[1] / 100))
    fig.subplots_adjust(0.07, 0.1, 0.99, 0.86, wspace=0.22)
    for ax, col, mcol, ylab, L in ((axes[0], "gross_gen_mwh", "mwh", "Energy per year (MWh)", "A"),
                                   (axes[1], "peak_kw", "peak", "Peak demand (kW)", "B")):
        x = np.arange(len(yrs))
        ax.bar(x, t.loc[yrs, col], 0.62, color=SKY, label="NPC records")
        ax.plot(x, new.loc[yrs, mcol], color=INK, lw=2.4, marker="o", ms=10, label="Digital twin")
        ax.set_xticks(x, [str(y) for y in yrs])
        ax.set_ylabel(ylab)
        ax.set_ylim(0, t.loc[yrs, col].max() * 1.32)
        err = (new.loc[yrs, mcol] / t.loc[yrs, col] - 1).abs().max() * 100
        ax.text(0.02, 0.97, f"within {err:.0f} % every year", transform=ax.transAxes, fontsize=19, fontweight="bold",
                va="top", color=BLUE)
        _panel(ax, L, x=-0.1)
    h_, l_ = axes[1].get_legend_handles_labels()
    fig.legend(h_, l_, loc="upper center", fontsize=17, ncol=2, bbox_to_anchor=(0.5, 1.0))
    _save(fig, "twin_check")


# ======================================================================= impact
def _rec(delay=14):
    r = pd.read_csv(P4B / "storms_rec.csv")
    return r[r.delay_days == delay]


def _bars(ax, labels, series, ylabel, ymax=None, fs=15):
    n = len(series)
    w = 0.8 / n
    x = np.arange(len(labels))
    top = max(max(v) for v in series.values())
    for i, (k, v) in enumerate(series.items()):
        xs = x + (i - (n - 1) / 2) * w
        ax.bar(xs, v, width=w * 0.9, color=COL[k], label=NAME[k], edgecolor="white", lw=0)
        for xx, vv in zip(xs, v):
            ax.text(xx, vv + top * 0.02, f"{vv:.0f}", ha="center", va="bottom", fontsize=fs,
                    fontweight="bold" if k == "C" else "normal", color=BLUE if k == "C" else INK)
    ax.set_xticks(x, labels)
    ax.tick_params(axis="x", length=0)
    ax.set_ylabel(ylabel)
    ax.set_ylim(0, ymax or top * 1.18)


def impact(size=(1120, 420)):
    plt = _plt()
    imp = json.loads((P4B / "impact.json").read_text(encoding="utf-8"))
    clinic, homes = imp["storm14_clinic_dark_h_mean"], imp["storm14_homes_cut_h_mean"]
    fig, axes = plt.subplots(1, 2, figsize=(size[0] / 100, size[1] / 100), sharey=True)
    fig.subplots_adjust(0.24, 0.04, 0.98, 0.84, wspace=0.08)
    y = np.arange(4)[::-1]
    lab = lambda v: f"{round(v)} h" + (f"  ({round(v) / 24:.0f} days)" if v >= 48 else "")  # noqa: E731
    for ax, vals, title in ((axes[0], clinic, "Clinic, water, phones dark"), (axes[1], homes, "Homes cut off")):
        v = [vals[c] for c in KEYS]
        ax.barh(y, v, 0.64, color=[COL[c] for c in KEYS])
        for yy, vv, c in zip(y, v, KEYS):
            ax.text(vv + 6, yy, lab(vv), va="center", fontsize=18, fontweight="bold", color=BLUE if c == "C" else INK)
        ax.set_xlim(0, 650)
        ax.set_title(title, fontsize=19, fontweight="bold", loc="left", pad=10)
        ax.set_xticks([])
        ax.spines["bottom"].set_visible(False)
        ax.tick_params(axis="y", length=0)
    axes[0].set_yticks(y, [NAME[c] for c in KEYS], fontsize=16)
    for lb in axes[0].get_yticklabels():
        if lb.get_text() == "AURORA":
            lb.set_fontweight("bold")
            lb.set_color(BLUE)
    axes[1].spines["left"].set_visible(False)
    cut = 100 * (1 - homes["C"] / homes["O"])
    xb = 520
    axes[1].plot([xb, xb + 8, xb + 8, xb], [0.72, 0.72, 0, 0], color=BLUE, lw=2)
    axes[1].text(xb + 14, 0.36, f"−{cut:.0f} %", fontsize=20, fontweight="bold", color=BLUE, va="center")
    axes[1].set_xlim(0, 650)
    _save(fig, "impact")


def delay(size=SIDE):
    plt = _plt()
    r = pd.read_csv(P4B / "storms_rec.csv")
    g = r.groupby(["delay_days", "controller"])[["crit_outage_h", "flex_shed_h"]].mean()
    fig, axs = plt.subplots(1, 2, figsize=(size[0] / 100, size[1] / 100), sharey=True)
    fig.subplots_adjust(0.085, 0.14, 0.99, 0.78, wspace=0.12)
    for ax, col, ttl, L in ((axs[0], "crit_outage_h", "Clinic, water, phones dark", "A"),
                            (axs[1], "flex_shed_h", "Homes cut off", "B")):
        for k in KEYS:
            yv = [g.loc[(d, k), col] for d in (3, 7, 14)]
            ax.plot([3, 7, 14], yv, color=COL[k], ls=LS[k], marker=MK[k], ms=10, lw=3, label=NAME[k],
                    zorder=5 if k == "C" else 3)
        ax.set_xticks([3, 7, 14])
        ax.set_xlabel("Boat late by (days)")
        ax.set_ylim(-8, 270)
        ax.set_title(ttl, fontsize=17, fontweight="bold", loc="left")
        _panel(ax, L, x=-0.03, y=1.0)
    axs[0].set_ylabel("Hours (h)")
    h, l = axs[0].get_legend_handles_labels()
    fig.legend(h, l, ncol=4, loc="upper center", fontsize=15, bbox_to_anchor=(0.53, 1.0), columnspacing=1.2)
    _save(fig, "delay")


def homes_energy(size=SIDE):
    r = _rec(14)
    fig, ax = _fig(size)
    fig.subplots_adjust(0.1, 0.17, 0.98, 0.96)
    for i, k in enumerate(KEYS):
        v = 100 - r[r.controller == k]["flex_shed_pct"].to_numpy()
        m = v.mean()
        ax.bar(i, m, width=0.62, color=COL[k])
        ax.errorbar(i, m, yerr=[[m - v.min()], [v.max() - m]], color=INK, capsize=8, lw=1.8)
        ax.text(i, v.max() + 3, f"{m:.0f} %", ha="center", fontsize=21, fontweight="bold", color=BLUE if k == "C" else INK)
    ax.set_xticks(range(4), ["Diesel only\n(today)", "Solar + battery\nno plan", "Careful\noperator", "AURORA"])
    ax.tick_params(axis="x", length=0)
    ax.set_ylabel("Homes' usual energy delivered (%)")
    ax.set_ylim(0, 112)
    ax.text(1, 22, "but clinic\ndark 75 h", ha="center", fontsize=16, fontweight="bold", color="white")
    _save(fig, "homes_energy")


def normal_year(size=SIDE):
    y = pd.read_csv(P4B / "year.csv").set_index("controller")
    vals = [y.loc[k, "diesel_l_per_yr"] / 1000 for k in ("A", "B", "C")]
    co2 = [y.loc[k, "co2_t_per_yr"] for k in ("A", "B", "C")]
    fig, ax = _fig(size)
    fig.subplots_adjust(0.1, 0.17, 0.98, 0.96)
    cols = [INK, GREY, BLUE]
    for i, (v, c, col) in enumerate(zip(vals, co2, cols)):
        ax.bar(i, v, width=0.58, color=col)
        ax.text(i, v + 8, f"{v:.0f} kL", ha="center", va="bottom", fontsize=21, fontweight="bold", color=BLUE if i == 2 else INK)
        ax.text(i, v / 2, f"{c:.0f} t\nCO₂", ha="center", va="center", fontsize=16, color="white" if i != 1 else INK)
    ax.set_xticks(range(3), ["Diesel only\n(today)", "Solar + battery\nsimple rule", "Solar + battery\nwith AURORA"])
    ax.tick_params(axis="x", length=0)
    ax.set_ylabel("Diesel per year (1,000 L)")
    ax.set_ylim(0, 420)
    ax.annotate("", (2.45, vals[2]), (2.45, vals[0]), arrowprops=dict(arrowstyle="<|-|>", color=BLUE, lw=2.2, mutation_scale=16))
    ax.text(2.53, (vals[0] + vals[2]) / 2, f"−{vals[0] - vals[2]:.0f} kL\n(−{100 * (1 - vals[2] / vals[0]):.0f} %)",
            va="center", fontsize=19, fontweight="bold", color=BLUE)
    ax.set_xlim(-0.5, 3.15)
    _save(fig, "normal_year")


def stress(size=SIDE):
    s = pd.read_csv(P4B / "stress.csv").groupby(["stress", "controller"])["crit_outage_h"].mean()
    n = _rec(14).groupby("controller")["crit_outage_h"].mean()
    cases = [("Normal", None), ("One\ngenerator", "gen_fail"), ("Solar\nhalved", "pv_damage"),
             ("No\ninternet", "comms_down"), ("Shared\nfeeder", "clinic_shared")]
    series = {k: [n[k] if c is None else s[(c, k)] for _, c in cases] for k in ("B", "O", "C")}
    fig, ax = _fig(size)
    fig.subplots_adjust(0.1, 0.17, 0.99, 0.88)
    _bars(ax, [c for c, _ in cases], series, "Clinic, water, phones dark (h)", ymax=138)
    ax.legend(ncol=3, loc="lower left", bbox_to_anchor=(0, 1.0), fontsize=16)
    ax.axvspan(3.5, 4.5, color=VERM, alpha=0.08, lw=0)
    _save(fig, "stress")


def npc_size(size=SIDE):
    plt = _plt()
    npc = pd.read_csv(P4B / "storms_npc.csv")
    npc = npc[npc.delay_days == 14].groupby("controller")[["crit_outage_h", "flex_shed_h"]].mean()
    big = _rec(14).groupby("controller")[["crit_outage_h", "flex_shed_h"]].mean()
    fig, axs = plt.subplots(1, 2, figsize=(size[0] / 100, size[1] / 100), sharey=True)
    fig.subplots_adjust(0.085, 0.16, 0.99, 0.8, wspace=0.1)
    for ax, col, ttl, L in ((axs[0], "crit_outage_h", "Clinic, water, phones dark", "A"),
                            (axs[1], "flex_shed_h", "Homes cut off", "B")):
        series = {k: [npc.loc[k, col], big.loc[k, col]] for k in KEYS}
        _bars(ax, ["NPC plan\n120 kWh", "Our size\n1,500 kWh"], series, "Hours (h)" if L == "A" else "", ymax=360, fs=14)
        ax.set_title(ttl, fontsize=17, fontweight="bold", loc="left")
        _panel(ax, L, x=-0.03, y=1.0)
    h, l = axs[0].get_legend_handles_labels()
    fig.legend(h, l, ncol=4, loc="upper center", fontsize=15, bbox_to_anchor=(0.53, 1.0), columnspacing=1.2)
    _save(fig, "npc_size")


# ======================================================================= growth and extras
def growth(size=SIDE):
    s = pd.read_csv(P4B / "sweep.csv")
    s = s[(s.delay_days == 14) & (s.bat_kwh == 1500)]
    g = s.groupby(["pv_kwp", "controller"])["flex_shed_h"].mean().unstack()
    fig, ax = _fig(size)
    fig.subplots_adjust(0.1, 0.15, 0.97, 0.96)
    for c in ("O", "C"):
        ax.plot(g.index, g[c], color=COL[c], ls=LS[c], marker=MK[c], ms=11, lw=3.2, label=NAME[c])
    for x_ in g.index:
        o, c_ = g.loc[x_, "O"], g.loc[x_, "C"]
        ax.plot([x_, x_], [c_ + 6, o - 6], color=BLUE, lw=1, ls=":")
        _halo(ax.text(x_ + 7, (o + c_) / 2, f"−{100 * (1 - c_ / o):.0f} %", fontsize=19, fontweight="bold", color=BLUE, va="center"))
    ax.set_xlabel("Solar size (kWp), battery 1,500 kWh")
    ax.set_ylabel("Hours homes are cut off (h)")
    ax.set_xticks([300, 400, 500, 600])
    ax.set_ylim(0, 270)
    ax.set_xlim(280, 650)
    ax.legend(loc="upper right", fontsize=17)
    _save(fig, "growth")


def breakeven(size=(1000, 520)):
    from ..experiments import phase4 as P
    sv = load_site()["values"]
    v = lambda k_: sv[k_]["value"]  # noqa: E731
    om, n, rep_t = v("om_frac_of_capex_per_year_assumed"), int(v("ocon2019_project_life_yr")), int(v("ocon2019_battery_life_yr"))
    yr = pd.read_csv(P4B / "year.csv")
    a_l = yr[yr.controller == "A"]["diesel_l_per_yr"].mean()
    c_l = yr[yr.controller == "C"]["diesel_l_per_yr"].iloc[0]
    cpv, cbat = P.capex_parts_php(300, 1500, 375, case="base")
    cap = cpv + cbat
    s_ = np.linspace(0, 1.3, 131)
    fig, ax = _fig(size)
    fig.subplots_adjust(0.12, 0.15, 0.97, 0.96)
    out = {}
    for r, ls, col, lab in ((0.04, "-", BLUE, "public finance, 4 %"), (v("ocon2019_wacc"), "--", ORANGE, "commercial, 9.94 %")):
        af = sum(1 / (1 + r) ** t for t in range(1, n + 1))
        k = cap * (1 + om * af) + cbat / (1 + r) ** rep_t
        sav = (a_l - c_l) * 113.0
        be = sav * af / k
        out[lab] = be
        ax.plot(100 * s_, (sav * af - s_ * k) / 1e6, color=col, ls=ls, lw=3.2, label=lab)
        ax.plot(100 * be, 0, "o", color=col, ms=12, zorder=5, mec="white", mew=1.5)
        _halo(ax.text(100 * be + (2 if r < 0.05 else -2), 9, f"{100 * be:.0f} %", fontsize=20, fontweight="bold", color=col,
                      ha="left" if r < 0.05 else "right", va="bottom"))
    ax.axhline(0, color=INK, lw=1.2)
    ax.axvline(100, color=MUTE, lw=1.4, ls=":")
    ax.text(98.5, -160, "Sabtang\nbudget", ha="right", fontsize=16, color=SOFT)
    ax.text(88, 30, "pays back", fontsize=17, color=GREEN, fontweight="bold")
    ax.text(3, -70, "does not pay back", fontsize=17, color=VERM, fontweight="bold")
    ax.legend(loc="upper right", fontsize=16)
    ax.set_xlim(0, 130)
    ax.set_xlabel("Installed cost (% of NPC's Sabtang budget)")
    ax.set_ylabel("20-year net value (M PHP)")
    _save(fig, "breakeven")
    return out


def sizing(size=SIDE):
    s = pd.read_csv(P4B / "sweep.csv")
    s = s[s["controller"] == "C"]
    g = s.groupby(["pv_kwp", "bat_kwh"])[["flex_shed_h", "crit_outage_h"]].mean().reset_index()
    pv, bat = sorted(g["pv_kwp"].unique()), sorted(g["bat_kwh"].unique())
    M = g.pivot(index="pv_kwp", columns="bat_kwh", values="flex_shed_h").loc[pv, bat].to_numpy()
    fig, ax = _fig(size)
    fig.subplots_adjust(0.11, 0.15, 0.93, 0.96)
    im = ax.imshow(M, cmap="viridis_r", aspect="auto", origin="lower", vmin=0, vmax=170)
    for i in range(len(pv)):
        for j in range(len(bat)):
            ax.text(j, i, f"{M[i, j]:.0f} h", ha="center", va="center", fontsize=17,
                    fontweight="bold" if (pv[i], bat[j]) == (300.0, 1500.0) else "normal",
                    color="white" if M[i, j] > 75 else INK)
    i0, j0 = pv.index(300.0), bat.index(1500.0)
    ax.add_patch(__import__("matplotlib").patches.Rectangle((j0 - 0.5, i0 - 0.5), 1, 1, fill=False, ec=VERM, lw=4))
    ax.set_xticks(range(len(bat)), [f"{b:,.0f}" for b in bat])
    ax.set_yticks(range(len(pv)), [f"{p:.0f}" for p in pv])
    ax.tick_params(length=0)
    for s_ in ax.spines.values():
        s_.set_visible(False)
    ax.set_xlabel("Battery (kWh)")
    ax.set_ylabel("Solar (kWp)")
    cb = fig.colorbar(im, ax=ax, pad=0.02, fraction=0.04)
    cb.set_label("Hours homes are cut off (h)")
    cb.outline.set_visible(False)
    _save(fig, "sizing")


FIGS = {"cover": cover_map, "map": map_where, "storms": storms, "crisis": crisis_hours, "growthd": demand_growth,
        "load": load_day, "tank": tank_days, "system": system_diagram, "clock": survival_clock, "replay": replay,
        "fc": forecast_rmse, "fcweek": forecast_week, "twin": twin_check, "impact": impact, "delay": delay,
        "homes": homes_energy, "year": normal_year, "stress": stress, "npc": npc_size, "growth": growth,
        "breakeven": breakeven, "sizing": sizing}

if __name__ == "__main__":
    for k in (sys.argv[1:] or FIGS):
        r = FIGS[k]()
        if r is not None:
            print(k, r)
