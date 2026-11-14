"""Slide versions of the key figures: few elements, large type, one annotated message each.

    python -m aurora.plotting.deck

Writes figures/deck/*.png (300 dpi) and .pdf. The journal versions stay in figures/final/.
Sizes are set for a 1920 x 1080 slide: text at 18 to 26 pt reads without zooming.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..data import paths
from . import style
from .phase5 import CTL, OI, P4, REC, hourly

OUT = paths.FIG_DIR / "deck"
INK, SOFT = "#14213D", "#4A5568"
COL = {"A": INK, "B": OI["orange"], "C": OI["blue"]}
NAME = {"A": "Diesel only", "B": "Simple rule", "C": "AURORA"}


def _plt():
    style.apply()
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 18, "axes.labelsize": 20, "xtick.labelsize": 18, "ytick.labelsize": 18,
                         "legend.fontsize": 18, "axes.linewidth": 1.2, "xtick.major.width": 1.2,
                         "ytick.major.width": 1.2, "xtick.major.size": 6, "ytick.major.size": 6,
                         "axes.edgecolor": INK, "text.color": INK, "axes.labelcolor": INK,
                         "xtick.color": INK, "ytick.color": INK})
    return plt


def _save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.png", dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight", facecolor="white")
    import matplotlib.pyplot as plt
    plt.close(fig)


# ---------------------------------------------------------------- impact: 14-day delay, three storms
def impact_bars():
    plt = _plt()
    d = pd.read_csv(P4 / "rec_storms.csv")
    d = d[d.delay_days == 14]
    storms = [("mawar2023", "Mawar 2023"), ("ragasa2025", "Ragasa 2025"), ("mekkhala2026", "Mekkhala 2026")]
    fig, ax = plt.subplots(figsize=(13, 5.2))
    w = 0.26
    for i, c in enumerate("ABC"):
        ys = [d[(d.storm == k) & (d.controller == c)]["crit_outage_h"].iloc[0] for k, _ in storms]
        xs = np.arange(3) + (i - 1) * w
        ax.bar(xs, ys, w * 0.92, color=COL[c], label=NAME[c])
        for x, y in zip(xs, ys):
            ax.text(x, y + 5, f"{y:.0f} h", ha="center", va="bottom", fontsize=20, fontweight="bold", color=COL[c])
    ax.set_xticks(range(3))
    ax.set_xticklabels([s for _, s in storms], fontsize=20)
    ax.set_ylabel("Hours the clinic is dark")
    ax.set_ylim(0, 260)
    ax.set_yticks([0, 100, 200])
    ax.legend(loc="upper center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 1.16), fontsize=20, handlelength=1.2)
    _save(fig, "impact_outage_14d")


# ---------------------------------------------------------------- replay: fuel tank and dark hours
def replay():
    plt = _plt()
    job = "rec_mawar2023_d14"
    h = {c: hourly(job, c) for c in "ABC"}
    t0 = h["C"].index[0]
    x = (h["C"].index - t0) / pd.Timedelta(days=1)
    arrive = 15.0
    fig, (ax, bx) = plt.subplots(2, 1, figsize=(12, 7.2), sharex=True, gridspec_kw={"height_ratios": [1.5, 1]})
    for c, ls in (("A", "-"), ("B", "--"), ("C", "-")):
        ax.plot(x, (h[c]["tank_end"] / 1000).where(x < arrive), color=COL[c], ls=ls, lw=3, label=NAME[c])
    ax.set_ylabel("Fuel left (kL)")
    ax.set_ylim(0, 6.8)
    ax.set_yticks([0, 2, 4, 6])
    ax.axvline(arrive, color="0.5", lw=1.2, ls=":")
    ax.text(arrive + 0.2, 3.4, "tanker\narrives", ha="left", va="center", fontsize=18, color=SOFT)
    ax.plot(5.9, 0, "o", ms=12, color=INK, zorder=6, clip_on=False)
    ax.text(6.3, 0.25, "diesel only\nruns dry: day 6", fontsize=19, va="bottom", ha="left", color=INK,
            fontweight="bold", linespacing=1.1)
    ax.legend(loc="upper right", frameon=False, bbox_to_anchor=(0.8, 1.02), fontsize=19, handlelength=1.6)
    for i, c in enumerate("ABC"):
        out = h[c]["unserved_crit"].to_numpy() > 1e-3
        bx.fill_between(x, i, i + 0.7, where=out, step="post", color=COL[c], lw=0)
        bx.text(x.max() + 0.3, i + 0.35, f"{int(out.sum())} h", va="center", fontsize=21, fontweight="bold", color=COL[c])
    bx.set_yticks([0.35, 1.35, 2.35])
    bx.set_yticklabels([NAME[c] for c in "ABC"], fontsize=19)
    bx.set_ylim(-0.15, 2.85)
    bx.set_title("Hours the clinic is dark", fontsize=20, loc="left", color=INK)
    bx.axvline(arrive, color="0.5", lw=1.2, ls=":")
    bx.set_xlabel("Days after typhoon Mawar cut the fuel route (27 May 2023)")
    bx.set_xlim(0, x.max())
    for s_ in ("left",):
        bx.spines[s_].set_visible(False)
    bx.tick_params(axis="y", length=0)
    fig.tight_layout()
    _save(fig, "replay_mawar_14d")


# ---------------------------------------------------------------- battery: AURORA vs a bigger battery
def battery():
    plt = _plt()
    sw = pd.read_csv(P4 / "sweep.csv")
    fig, ax = plt.subplots(figsize=(11, 5.4))
    for c, ls, mk in (("B", "--", "s"), ("C", "-", "o")):
        g = sw[(sw.controller == c) & (sw.pv_kwp == 500)].sort_values("bat_kwh")
        ax.plot(g.bat_kwh, g.crit_outage_h, color=COL[c], ls=ls, marker=mk, ms=9, lw=3, label=NAME[c])
    ax.set_xlabel("Battery size (kWh), with 500 kWp of solar")
    ax.set_ylabel("Hours the clinic is dark")
    ax.set_ylim(0, 80)
    ax.set_xticks([0, 500, 1000, 1500, 2000])
    ax.legend(frameon=False, loc="upper right", fontsize=20)
    ax.annotate("AURORA: 0 h\nat 1,000 kWh", xy=(1000, 0), xytext=(1030, 28), fontsize=20, fontweight="bold",
                color=OI["blue"], arrowprops=dict(arrowstyle="->", lw=2, color=OI["blue"]))
    ax.annotate("simple rule needs\n2,000 kWh for 1 h", xy=(2000, 1), xytext=(1450, 44), fontsize=20,
                fontweight="bold", color="#B37400", arrowprops=dict(arrowstyle="->", lw=2, color="#B37400"))
    _save(fig, "battery_vs_aurora")


# ---------------------------------------------------------------- economics: break-even price
def breakeven():
    plt = _plt()
    from ..data.site import load_site
    from ..experiments import phase4 as P
    sv = load_site()["values"]
    v = lambda k_: sv[k_]["value"]  # noqa: E731
    om, n, rep_t = v("om_frac_of_capex_per_year_assumed"), int(v("ocon2019_project_life_yr")), int(v("ocon2019_battery_life_yr"))
    yr = pd.read_csv(P4 / "year.csv")
    a_l = yr[yr.controller == "A"]["diesel_l_per_yr"].mean()
    b_l = yr[(yr.sizing == REC) & (yr.controller == "B")]["diesel_l_per_yr"].iloc[0]
    sav = (a_l - b_l) * 113.0
    cpv, cbat = P.capex_parts_php(500, 1000, 375, case="base")
    cap = cpv + cbat
    s_ = np.linspace(0, 1.3, 131)
    fig, ax = plt.subplots(figsize=(11, 5.4))
    for r, ls, c, lab in ((0.04, "-", OI["green"], "public finance, 4 %"), (v("ocon2019_wacc"), "--", OI["vermillion"],
                                                                             "commercial, 9.94 %")):
        af = sum(1 / (1 + r) ** t for t in range(1, n + 1))
        k = cap * (1 + om * af) + cbat / (1 + r) ** rep_t
        ax.plot(100 * s_, (sav * af - s_ * k) / 1e6, color=c, ls=ls, lw=3, label=lab)
        be = sav * af / k
        ax.plot(100 * be, 0, "o", color=c, ms=11, zorder=5)
        up = r < 0.05
        ax.text(100 * be + (3 if up else -3), 18 if up else -22, f"{100 * be:.0f} %", ha="left" if up else "right",
                va="bottom" if up else "top", fontsize=20, fontweight="bold", color=c)
    ax.axhline(0, color=INK, lw=1.2)
    ax.axvline(100, color="0.5", lw=1.2, ls=":")
    ax.text(98.5, -190, "NPC Sabtang\nbid price", fontsize=18, color=SOFT, va="bottom", ha="right")
    ax.text(3, 25, "pays back", fontsize=19, color=SOFT)
    ax.text(3, -45, "does not pay back", fontsize=19, color=SOFT)
    ax.set_xlim(0, 130)
    ax.set_ylim(-200, 290)
    ax.set_xlabel("Installed cost (% of NPC Sabtang bid price)")
    ax.set_ylabel("20-year value (M PHP)")
    ax.legend(frameon=False, loc="upper right", fontsize=19, bbox_to_anchor=(1.0, 0.9))
    _save(fig, "breakeven_price")


def main():
    for f in (impact_bars, replay, battery, breakeven):
        f()
        print("done", f.__name__)


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------- impact, model v2 (Phase 4b)
P4B = paths.ROOT / "results" / "phase4b"
COL4 = {"A": INK, "B": "#9AA5B1", "O": OI["orange"], "C": OI["blue"]}
NAME4 = {"A": "Diesel only (today)", "B": "Solar + battery,\nno plan", "O": "Solar + battery,\ncareful operator",
         "C": "Solar + battery,\nAURORA"}


def impact_v2(imp: dict | None = None):
    """One slide, one message: in a 14-day fuel crisis AURORA keeps the clinic on AND
    cuts homes for far fewer hours than rationing by hand. Mean of three real typhoons."""
    import json
    plt = _plt()
    imp = imp or json.loads((P4B / "impact.json").read_text(encoding="utf-8"))
    clinic, homes = imp["storm14_clinic_dark_h_mean"], imp["storm14_homes_cut_h_mean"]
    order = [c for c in ("A", "B", "O", "C") if c in clinic]
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.6), sharey=True, gridspec_kw={"wspace": 0.12})
    y = np.arange(len(order))[::-1]
    pos = dict(zip(order, y))

    def lab(v):
        v = round(v)
        return f"{v} h  ({v / 24:.0f} days)" if v >= 48 else f"{v} h"

    for ax, vals, title in ((axes[0], clinic, "Clinic, water, phones:\nhours without power"),
                            (axes[1], homes, "Homes:\nhours with power cut")):
        v = [vals[c] for c in order]
        ax.barh(y, v, height=0.62, color=[COL4[c] for c in order])
        top = max(max(v), 1)
        for yy, vv, c in zip(y, v, order):
            ax.text(vv + top * 0.02, yy, lab(vv), va="center", fontsize=22, fontweight="bold",
                    color=COL4[c] if c != "B" else SOFT)
        ax.set_xlim(0, top * 1.75)
        ax.set_title(title, fontsize=21, loc="left", color=INK, pad=12)
        ax.set_xticks([])
        ax.spines["bottom"].set_visible(False)
        ax.tick_params(axis="y", length=0)
    if "O" in homes and "C" in homes and homes["O"] > 0:
        cut = 100 * (1 - homes["C"] / homes["O"])
        top = max(max(homes[c] for c in order), 1)
        xb = max(homes["O"], homes["C"]) + top * 0.62
        yo, yc = pos["O"] - 0.3, pos["C"]               # start just under the operator's label
        axes[1].plot([xb, xb], [yo, yc], color=OI["blue"], lw=2.5, solid_capstyle="butt")
        for yy in (yo, yc):
            axes[1].plot([xb - top * 0.025, xb], [yy, yy], color=OI["blue"], lw=2.5)
        axes[1].text(xb + top * 0.03, (yo + yc) / 2, f"{cut:.0f} %\nfewer", va="center",
                     ha="left", fontsize=22, fontweight="bold", color=OI["blue"])
    axes[0].set_yticks(y)
    axes[0].set_yticklabels([NAME4[c] for c in order], fontsize=19)
    for lb, c in zip(axes[0].get_yticklabels(), order):
        lb.set_fontweight("bold" if c == "C" else "normal")
    axes[1].spines["left"].set_visible(False)
    _save(fig, "impact_v2_two_outcomes")
