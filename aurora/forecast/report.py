"""docs/validation_forecast.md and the three forecast figures."""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from aurora.data import paths
from aurora.plotting import style

from . import evaluate as E, quantile as Qm
from .backtest import EVAL_START
from .features import GHI_MODELS, ISSUE_HOUR_UTC, QUANTILES

OUT_MD = paths.DOCS_DIR / "validation_forecast.md"
FIG_SKILL = paths.FIG_DIR / "forecast_skill_lead"
FIG_REL = paths.FIG_DIR / "forecast_reliability"
FIG_TY = paths.FIG_DIR / "forecast_typhoon_week"
SEASONS = ["DJF", "MAM", "JJA", "SON"]


def f1(x):
    return "n/a" if x is None or not np.isfinite(x) else f"{x:.1f}"


def pct(x):
    return "n/a" if x is None or not np.isfinite(x) else f"{100 * x:+.1f} %"


def _table(t: pd.DataFrame, names: dict, cols) -> list[str]:
    head = "| Forecast | " + " | ".join(c for c, _ in cols) + " |"
    lines = [head, "|" + "---|" * (len(cols) + 1)]
    for k, nm in names.items():
        if k not in t.index:
            continue
        r = t.loc[k]
        lines.append(f"| {nm} | " + " | ".join(fmt(r.get(c, np.nan)) for c, fmt in cols) + " |")
    return lines


def _skill_ci(d, ref_fn, metric):
    """Skill of AURORA vs a reference with a 5-95 % daily block-bootstrap range."""
    def sk(g):
        yy = g["ghi_true"].to_numpy()
        a = E.ghi_quantiles(g)
        if metric == "RMSE":
            m = np.sqrt(np.mean((a[:, E.J50] - yy) ** 2))
            r = np.sqrt(np.mean((ref_fn(g) - yy) ** 2))
        else:
            m = np.mean(Qm.crps_quantiles(yy, a))
            r = np.mean(np.abs(ref_fn(g) - yy))
        return 1 - m / r

    point = sk(d)
    lo, hi = E.daily_block_bootstrap(d, sk, n_boot=200)
    return point, lo, hi


REFS = {"Raw NWP: ECMWF IFS": lambda g: g["ghi_nwp_ecmwf"].to_numpy(),
        "Raw NWP: GFS": lambda g: g["ghi_nwp_gfs"].to_numpy(),
        "Raw NWP: ICON": lambda g: g["ghi_nwp_icon"].to_numpy(),
        "Raw NWP: mean of 3": lambda g: g["ghi_nwp_mean"].to_numpy(),
        "Smart persistence": lambda g: (g["k_persist"] * g["ghi_clear"]).to_numpy()}


def typhoon_week(bt: pd.DataFrame):
    ev = pd.read_csv(paths.TYPHOON_EVENTS, parse_dates=["closest_time_utc"]) if paths.TYPHOON_EVENTS.exists() else None
    if ev is None:
        return None
    ev = ev[(ev["closest_time_utc"] >= EVAL_START) & (ev["closest_time_utc"] <= bt.index.max())]
    if ev.empty:
        return None
    e = ev.sort_values("closest_km").iloc[0]
    c = e["closest_time_utc"].tz_convert(paths.LOCAL_TZ).normalize()
    a = (c - pd.Timedelta(days=3)).tz_convert("UTC")
    return e, a, a + pd.Timedelta(days=7)


# ------------------------------------------------------------------ figures
def fig_skill(d: pd.DataFrame, stem=FIG_SKILL):
    style.apply()
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.7))
    refs = [("Raw NWP: ECMWF IFS", style.OKABE_ITO["blue"], "o", "-"),
            ("Raw NWP: mean of 3", style.OKABE_ITO["orange"], "s", "--"),
            ("Smart persistence", style.OKABE_ITO["purple"], "^", ":")]
    agg = d.assign(hr=d["lead_h"])
    for ax, metric, lab in ((axes[0], "RMSE", "A"), (axes[1], "CRPS", "B")):
        for name, colr, mk, ls in refs:
            xs, ys, los, his = [], [], [], []
            for h, g in agg.groupby("hr"):
                if len(g) < 100:
                    continue
                p, lo, hi = _skill_ci(g, REFS[name], metric)
                xs.append(h), ys.append(100 * p), los.append(100 * lo), his.append(100 * hi)
            xs, ys = np.array(xs), np.array(ys)
            err = np.vstack([ys - np.array(los), np.array(his) - ys])
            for seg in (xs <= 24, xs > 24):
                ax.errorbar(xs[seg], ys[seg], yerr=err[:, seg], color=colr, marker=mk, ms=2.5, lw=0.9,
                            ls=ls, elinewidth=0.6, capsize=0,
                            label=f"vs {name.replace('Raw NWP: ', '')}" if seg[0] else None)
        ax.axhline(0, color="black", lw=0.5)
        ax.set_xlabel("Lead time (h after 00:00 PHT issue)")
        ax.set_ylabel(f"{metric} skill of AURORA (%)")
        ax.set_xticks([0, 6, 12, 18, 24, 30, 36, 42, 48])
        style.panel_label(ax, lab)
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper center", ncol=3, fontsize=6.5, bbox_to_anchor=(0.5, 1.04))
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    style.save(fig, stem)


def fig_reliability(d: pd.DataFrame, stem=FIG_REL):
    style.apply()
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.8), gridspec_kw={"width_ratios": [1, 1.4]})
    ax = axes[0]
    ax.plot([0, 1], [0, 1], color="black", lw=0.6, ls=":", label="Perfect")
    for ld, colr, mk in ((1, style.OKABE_ITO["blue"], "o"), (2, style.OKABE_ITO["vermillion"], "s")):
        g = d[d["lead_day"] == ld]
        ax.plot(QUANTILES, E.reliability(g, "raw_"), color=colr, ls="--", marker=mk, mfc="white", ms=2.5,
                lw=0.8, label=f"Day {ld}, before conformal")
        ax.plot(QUANTILES, E.reliability(g), color=colr, ls="-", marker=mk, ms=2.5, lw=0.9,
                label=f"Day {ld}, calibrated")
    ax.set_xlabel("Nominal quantile level")
    ax.set_ylabel("Observed frequency below quantile")
    ax.set_xlim(0, 1), ax.set_ylim(0, 1)
    ax.legend(fontsize=6, loc="upper left")
    style.panel_label(ax, "A")
    ax = axes[1]
    groups = [(s, ld) for ld in (1, 2) for s in SEASONS] + [("TC", 1), ("TC", 2)]
    x = np.arange(len(groups))
    for off, prefix, colr, lab in ((-0.18, "raw_", style.OKABE_ITO["sky"], "Before conformal"),
                                   (0.18, "", style.OKABE_ITO["blue"], "Calibrated")):
        vals, lo, hi = [], [], []
        for s, ld in groups:
            g = d[(d["lead_day"] == ld) & ((d["season"] == s) if s != "TC" else d["tc500"])]
            inside = lambda gg: np.mean((gg["k_true"] >= gg[f"{prefix}q10"]) & (gg["k_true"] <= gg[f"{prefix}q90"]))
            v = inside(g)
            a, b = E.daily_block_bootstrap(g, inside, n_boot=200) if len(g) else (np.nan, np.nan)
            vals.append(v), lo.append(v - a), hi.append(b - v)
        ax.bar(x + off, vals, width=0.34, color=colr, label=lab, yerr=[lo, hi],
               error_kw=dict(elinewidth=0.6, capsize=0))
    ax.axhline(0.8, color="black", lw=0.6, ls="--")
    ax.set_xticks(x, [f"{s}\nday {ld}" for s, ld in groups], fontsize=6)
    ax.set_ylabel("PICP of the P10-P90 band")
    ax.set_ylim(0.5, 1.0)
    ax.legend(fontsize=6, loc="lower right", ncol=2)
    style.panel_label(ax, "B")
    fig.tight_layout()
    style.save(fig, stem)


def fig_typhoon(bt: pd.DataFrame, tw, stem=FIG_TY):
    style.apply()
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    e, a, b = tw
    d = bt[(bt.index > a) & (bt.index <= b) & (bt["lead_day"] == 1)].sort_index()
    idx = pd.date_range(a + pd.Timedelta(hours=1), b, freq="h")
    d = d.reindex(idx)
    gc = d["ghi_clear"].fillna(0)
    q = {c: (d[c] * gc).where(gc > 0, 0) for c in ("q10", "q50", "q90")}
    loc = idx.tz_convert(paths.LOCAL_TZ).tz_localize(None)
    fig, axes = plt.subplots(2, 1, figsize=(7.0, 3.8), sharex=True, gridspec_kw={"height_ratios": [2.2, 1]})
    ax = axes[0]
    ax.fill_between(loc, q["q10"], q["q90"], color=style.OKABE_ITO["sky"], alpha=0.45, lw=0,
                    label="AURORA P10-P90")
    ax.plot(loc, q["q50"], color=style.OKABE_ITO["blue"], lw=1.0, label="AURORA P50")
    ax.plot(loc, d["ghi_nwp_mean"].fillna(0), color=style.OKABE_ITO["orange"], lw=0.9, ls="--",
            label="Raw NWP mean")
    ax.plot(loc, d["ghi_true"], color="black", lw=0, marker="o", ms=1.6, label="Satellite reference")
    ax.set_ylabel("GHI (W/m²)")
    ax.legend(fontsize=6, ncol=4, loc="upper left", bbox_to_anchor=(0, 1.13))
    style.panel_label(ax, "A")
    ax = axes[1]
    fl = pd.read_parquet(paths.TYPHOON_HOURLY).reindex(idx)
    dist = fl["dist_km"].where(fl["storm_sid"] == e["sid"])
    ax.plot(loc, dist, color=style.OKABE_ITO["vermillion"], lw=1.0)
    ax.axhline(300, color="black", lw=0.5, ls=":")
    ax.axhline(500, color="black", lw=0.5, ls="--")
    ax.set_ylabel(f"{str(e['name']).title()}\ndistance (km)")
    ax.set_xlabel("Local time (PHT), lead day 1 forecasts")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    style.panel_label(ax, "B")
    fig.tight_layout()
    style.save(fig, stem)


# ------------------------------------------------------------------ report
def build(bt: pd.DataFrame, dm: pd.DataFrame, pv: dict | None = None, out_md=OUT_MD) -> dict:
    bt = E.add_typhoon_flags(bt)
    d = E.eval_sample(bt, EVAL_START)
    first, last = d.index.min(), d.index.max()
    nmonths = (last.year - first.year) * 12 + last.month - first.month + 1
    L, res = [], {}
    w = L.append
    w("# Forecast validation: Itbayat solar and demand")
    w("")
    w(f"Generated by `python -m aurora.forecast.build` on {dt.date.today():%Y-%m-%d}. "
      "Reads only `data/itbayat/raw_small/` and the Phase 1 outputs.")
    w("")
    by_ld = {ld: E.score_table(g) for ld, g in d.groupby("lead_day")}
    allt = E.score_table(d)
    res["by_ld"], res["all"] = by_ld, allt
    # verdict
    w("## Verdict")
    w("")
    checks = []
    for ld, t in by_ld.items():
        for ref in ("nwp_ecmwf", "nwp_gfs", "nwp_icon", "nwp_mean", "persist"):
            for metric in ("RMSE", "CRPS"):
                checks.append((ld, ref, metric, E.skill(t, metric, ref)))
    beaten = all(s > 0 for *_, s in checks)
    w(f"- Evaluation: rolling-origin backtest, monthly refit, {nmonths} test months "
      f"({first:%b %Y} to {last:%b %Y}), daylight hours, satellite reference.")
    w(f"- **AURORA beats every raw NWP model, their mean, and smart persistence on RMSE and CRPS at both "
      f"lead days: {'yes' if beaten else 'NO, see the skill table'}.**")
    for ld, t in by_ld.items():
        w(f"- Lead day {ld}: RMSE {f1(t.loc['aurora', 'RMSE'])} W/m² vs {f1(t.loc['nwp_ecmwf', 'RMSE'])} (ECMWF, "
          f"best raw model), {f1(t.loc['nwp_mean', 'RMSE'])} (NWP mean), {f1(t.loc['persist', 'RMSE'])} "
          f"(persistence). CRPS {f1(t.loc['aurora', 'CRPS'])} W/m² vs {f1(t.loc['nwp_ecmwf', 'CRPS'])}. "
          f"P10-P90 coverage {100 * t.loc['aurora', 'PICP80']:.1f} % (target 80 %).")
    losses = []
    for (lab, mask) in (("TC within 500 km", d["tc500"]), ("TC within 300 km", d["tc300"])):
        for ld in (1, 2):
            g = d[mask & (d["lead_day"] == ld)]
            if len(g) < 30:
                continue
            t = E.score_table(g)
            for ref in ("nwp_ecmwf", "nwp_mean", "persist"):
                for metric in ("RMSE", "CRPS"):
                    if E.skill(t, metric, ref) <= 0:
                        losses.append(f"{lab}, lead day {ld}: {metric} {f1(t.loc['aurora', metric])} vs "
                                      f"{f1(t.loc[ref, metric])} W/m² ({E.POINT_NAMES[ref]}, n = {len(g)})")
    for (s_, ld), g in d.groupby(["season", "lead_day"]):
        t = E.score_table(g)
        for ref in ("nwp_ecmwf", "nwp_mean", "persist"):
            for metric in ("RMSE", "CRPS"):
                if E.skill(t, metric, ref) <= 0:
                    losses.append(f"{s_}, lead day {ld}: {metric} vs {E.POINT_NAMES[ref]}")
    res["losses"] = losses
    if losses:
        w("- **Where AURORA does not win** (subsets; report honestly, revisit with more storm data):")
        for x in losses:
            w(f"  - {x}")
    else:
        w("- AURORA wins in every season subset and in typhoon hours.")
    w("")
    # setup
    w("## Set-up")
    w("")
    w(f"- **Issue time**: daily at {ISSUE_HOUR_UTC:02d}:00 UTC (00:00 PHT) for the next 48 h. Lead day 1 = "
      "the next local day (lead 1-24 h), lead day 2 = the day after (25-48 h).")
    w("- **NWP input**: Open-Meteo previous-runs archive, ECMWF IFS 0.25°, GFS, ICON (GHI, cloud, temperature, "
      "humidity, rain, pressure, wind, gusts) and JMA (same without GHI). Lead day 1 uses the run issued about "
      "one day before the target hour (`_d1`), lead day 2 the run two days before (`_d2`). Every input was "
      "therefore available at the issue time. An operator would have a run up to a day newer, so these "
      "scores are conservative.")
    w("- **Not used**: the low/mid/high cloud split (archived only at lead day 0); ensemble spread "
      "(ECMWF ENS / GEFS) is not in `raw_small/`, so the spread between the four models is the uncertainty "
      "feature. Adding the ensemble API is a follow-up.")
    w("- **Target**: clear-sky index k = GHI / GHI_clear (Ineichen, Linke turbidity climatology, hour-mean), "
      "daylight hours (GHI_clear ≥ 50 W/m²), converted back to GHI for scoring.")
    w("- **Truth**: Open-Meteo satellite radiation (a satellite retrieval at 0.05°, 3 km from the town). "
      "It observes the clouds over the island; ERA5 models them at 0.25° and NASA POWER is a 1° product. "
      "Phase 1 showed the satellite series agrees with the Tsai et al. (2020) annual GHI within 2.6 %. "
      "None of these is a measurement; scores against ERA5 are given as a cross-check below.")
    w("- **Model**: LightGBM quantile regression, one model per lead day and quantile level (19 levels, "
      "0.05-0.95, so CRPS can be computed), refit every month on all earlier data (expanding window, training "
      "truth ends 3 days before the test month). Crossing quantiles are sorted.")
    w("- **Calibration**: split conformal per quantile level, grouped by lead day and season, using the "
      "out-of-sample scores of the previous 365 days of the backtest. P50 is not shifted.")
    w(f"- **Sample**: hours where ECMWF, GFS and ICON all have GHI and persistence exists, so every forecast "
      f"is scored on the same hours (n = {len(d)} lead-day hours).")
    w("")
    # main table
    cols = [("MAE", f1), ("RMSE", f1), ("bias", f1), ("CRPS", f1), ("PICP80", lambda x: "" if not np.isfinite(x) else f"{100 * x:.1f} %"),
            ("width80", lambda x: "" if not np.isfinite(x) else f1(x)),
            ("pinball_P10", lambda x: "" if not np.isfinite(x) else f1(x)),
            ("pinball_P50", lambda x: "" if not np.isfinite(x) else f1(x)),
            ("pinball_P90", lambda x: "" if not np.isfinite(x) else f1(x))]
    names = {**E.POINT_NAMES, "aurora_raw": E.PROB_NAMES["aurora_raw"], "nwp_ens": E.PROB_NAMES["nwp_ens"]}
    for ld, t in by_ld.items():
        w(f"## Scores, lead day {ld} (W/m², daylight hours, n = {int(t.loc['aurora', 'n'])})")
        w("")
        w("Deterministic forecasts have CRPS = MAE. PICP80 = share of hours inside P10-P90; width80 = mean P90 - P10.")
        w("")
        L.extend(_table(t, names, cols))
        w("")
    # skill
    w("## Skill of AURORA (positive = better), with 5-95 % daily block-bootstrap ranges")
    w("")
    w("RMSE skill uses AURORA P50; CRPS skill uses the full AURORA distribution against the deterministic reference.")
    w("")
    w("| Reference | Lead day | RMSE skill | CRPS skill |")
    w("|---|---|---|---|")
    res["skill"] = {}
    for ld, g in d.groupby("lead_day"):
        for name, fn in REFS.items():
            r = _skill_ci(g, fn, "RMSE")
            c = _skill_ci(g, fn, "CRPS")
            res["skill"][(name, ld)] = (r, c)
            w(f"| {name} | {ld} | {pct(r[0])} ({pct(r[1])} to {pct(r[2])}) | {pct(c[0])} ({pct(c[1])} to {pct(c[2])}) |")
    w("")
    # season
    w("## By season")
    w("")
    w("| Season | Lead day | n | RMSE AURORA | RMSE ECMWF | RMSE NWP mean | RMSE persistence | CRPS AURORA | "
      "RMSE skill vs ECMWF | CRPS skill vs ECMWF | PICP80 |")
    w("|---|---|---|---|---|---|---|---|---|---|---|")
    for (s, ld), g in sorted(d.groupby(["season", "lead_day"]), key=lambda kv: (kv[0][1], SEASONS.index(kv[0][0]))):
        t = E.score_table(g)
        w(f"| {s} | {ld} | {len(g)} | {f1(t.loc['aurora', 'RMSE'])} | {f1(t.loc['nwp_ecmwf', 'RMSE'])} | "
          f"{f1(t.loc['nwp_mean', 'RMSE'])} | {f1(t.loc['persist', 'RMSE'])} | {f1(t.loc['aurora', 'CRPS'])} | "
          f"{pct(E.skill(t, 'RMSE', 'nwp_ecmwf'))} | {pct(E.skill(t, 'CRPS', 'nwp_ecmwf'))} | "
          f"{100 * t.loc['aurora', 'PICP80']:.1f} % |")
    w("")
    # typhoon
    w("## Typhoon hours vs normal hours")
    w("")
    w("Typhoon hours: an IBTrACS storm centre within 500 km (or 300 km) of Itbayat. The flags are used only "
      "to split the scores; the model sees storms only through the NWP pressure, pressure tendency, gust "
      "and wind features.")
    w("")
    w("| Hours | Lead day | n | RMSE AURORA | RMSE ECMWF | RMSE NWP mean | RMSE persistence | CRPS AURORA | "
      "CRPS ECMWF | PICP80 | width80 |")
    w("|---|---|---|---|---|---|---|---|---|---|---|")
    res["typhoon"] = {}
    for lab, mask in (("normal", ~d["tc500"]), ("TC within 500 km", d["tc500"]), ("TC within 300 km", d["tc300"])):
        for ld in (1, 2):
            g = d[mask & (d["lead_day"] == ld)]
            if len(g) < 30:
                w(f"| {lab} | {ld} | {len(g)} | too few hours | | | | | | | |")
                continue
            t = E.score_table(g)
            res["typhoon"][(lab, ld)] = t
            w(f"| {lab} | {ld} | {len(g)} | {f1(t.loc['aurora', 'RMSE'])} | {f1(t.loc['nwp_ecmwf', 'RMSE'])} | "
              f"{f1(t.loc['nwp_mean', 'RMSE'])} | {f1(t.loc['persist', 'RMSE'])} | {f1(t.loc['aurora', 'CRPS'])} | "
              f"{f1(t.loc['nwp_ecmwf', 'CRPS'])} | {100 * t.loc['aurora', 'PICP80']:.1f} % | {f1(t.loc['aurora', 'width80'])} |")
    w("")
    w("Typhoon samples are small (a few storms), so treat these numbers as indicative.")
    w("")
    # cross-check vs ERA5
    w("## Cross-check against ERA5")
    w("")
    de = d.dropna(subset=["ghi_era5"])
    w("Same forecasts, scored against ERA5 instead of the satellite product (the model was trained on the "
      "satellite target, so this favours the raw NWP, which shares ERA5's physics).")
    w("")
    w("| Lead day | RMSE AURORA | RMSE ECMWF | RMSE NWP mean | RMSE persistence (satellite k) |")
    w("|---|---|---|---|---|")
    for ld, g in de.groupby("lead_day"):
        y = g["ghi_era5"].to_numpy()
        r = lambda f: np.sqrt(np.mean((np.asarray(f) - y) ** 2))
        w(f"| {ld} | {f1(r(E.ghi_quantiles(g)[:, E.J50]))} | {f1(r(g['ghi_nwp_ecmwf']))} | "
          f"{f1(r(g['ghi_nwp_mean']))} | {f1(r(g['k_persist'] * g['ghi_clear']))} |")
    w("")
    # reduced regime
    w("## Reduced inputs (no NWP GHI, 2023)")
    w("")
    dr = bt[(bt["regime"] == "reduced") & bt["daylight"] & bt["k_true"].notna() & (bt.index < EVAL_START)
            & bt["k_persist"].notna()]
    w("Before Feb 2024 the archive has no NWP GHI at lead days 1-2, only JMA cloud, humidity, rain, pressure and "
      "wind. A reduced model (JMA plus persistence and sun geometry) covers that period, which holds the "
      "Jun 2023 Typhoon Betty case used in Phase 4. 2022 is predicted by a model trained on 2023 (out of sample, "
      "not causal in time; flagged `reduced_reverse`).")
    w("")
    w("| Lead day | n | RMSE reduced | RMSE persistence | RMSE climatology | CRPS reduced | CRPS climatology | PICP80 |")
    w("|---|---|---|---|---|---|---|---|")
    for ld, g in dr.groupby("lead_day"):
        y = g["ghi_true"].to_numpy()
        Qa, Qc = E.ghi_quantiles(g), E.ghi_quantiles(g, "clim_")
        r = lambda f: np.sqrt(np.mean((np.asarray(f) - y) ** 2))
        w(f"| {ld} | {len(g)} | {f1(r(Qa[:, E.J50]))} | {f1(r(g['k_persist'] * g['ghi_clear']))} | "
          f"{f1(r(g['k_clim'] * g['ghi_clear']))} | {f1(np.mean(Qm.crps_quantiles(y, Qa)))} | "
          f"{f1(np.mean(Qm.crps_quantiles(y, Qc)))} | "
          f"{100 * np.mean((y >= Qa[:, E.J10]) & (y <= Qa[:, E.J90])):.1f} % |")
    w("")
    # PV
    if pv:
        w("## PV power (300 kWp INL array, kW, daylight hours)")
        w("")
        w("GHI quantiles split into DNI/DHI with Erbs, then converted with the shared array model "
          "`aurora/data/pvmodel.py` (the one the twin uses: Hay-Davies, SAPM cell temperature with forecast air "
          "temperature and wind, PVWatts). Reference: the same chain applied to satellite GHI with ERA5 "
          "temperature and wind.")
        w("")
        w("| Lead day | MAE AURORA P50 | RMSE AURORA P50 | RMSE raw NWP mean | RMSE persistence | PICP80 |")
        w("|---|---|---|---|---|---|")
        for ld, r in pv.items():
            w(f"| {ld} | {f1(r['mae'])} | {f1(r['rmse'])} | {f1(r['rmse_nwp'])} | {f1(r['rmse_persist'])} | "
              f"{100 * r['picp']:.1f} % |")
        w("")
    # fallback
    w("## Communications-loss fallback")
    w("")
    w("When no NWP arrives the forecast uses climatology-conditioned persistence with bands widened by 25 % "
      "(`fallback = True` in the CSV). Its scores on the same hours:")
    w("")
    w("| Lead day | RMSE fallback | RMSE AURORA | CRPS fallback | CRPS AURORA | PICP80 fallback | width80 fallback |")
    w("|---|---|---|---|---|---|---|")
    for ld, t in by_ld.items():
        w(f"| {ld} | {f1(t.loc['fallback', 'RMSE'])} | {f1(t.loc['aurora', 'RMSE'])} | {f1(t.loc['fallback', 'CRPS'])} | "
          f"{f1(t.loc['aurora', 'CRPS'])} | {100 * t.loc['fallback', 'PICP80']:.1f} % | {f1(t.loc['fallback', 'width80'])} |")
    w("")
    w("The fallback is worse than AURORA, as expected, but its band is wider and still covers at least 80 %, "
      "so the dispatch layer sees the extra uncertainty.")
    w("")
    # demand
    w("## Demand forecast (SYNTHETIC load)")
    w("")
    w("**Trained and scored on the synthetic Phase 1 load.** These numbers show the model recovers the synthetic "
      "generator; they say nothing yet about real Itbayat demand. With plant logs "
      "(`python -m aurora.data.build_itbayat --load LOG.csv`) the same code retrains on real data.")
    w("")
    ds = E.demand_scores(dm, EVAL_START)
    res["demand"] = ds
    w("| Component | Lead day | Mean (kW) | MAE (kW) | MAE same hour last day (kW) | RMSE (kW) | bias (kW) | PICP80 | width80 (kW) |")
    w("|---|---|---|---|---|---|---|---|---|")
    for _, r in ds.iterrows():
        w(f"| {r['component']} | {r['lead_day']} | {f1(r['mean_kW'])} | {f1(r['MAE'])} | {f1(r.get('MAE_naive', np.nan))} | "
          f"{f1(r['RMSE'])} | {f1(r['bias'])} | {100 * r['PICP80']:.1f} % | {f1(r['width80'])} |")
    w("")
    w("The synthetic critical load is a fixed daily schedule (site.yaml `critical_profiles`), so it is forecast "
      "exactly and its band has zero width. Real critical loads vary; the same model then produces a real band.")
    w("")
    # figures
    w("## Figures")
    w("")
    fig_skill(d)
    fig_reliability(d)
    w(f"- `figures/{FIG_SKILL.name}.pdf`: RMSE and CRPS skill by lead time against ECMWF, the NWP mean and "
      "smart persistence (bars: 5-95 % daily block bootstrap).")
    w(f"- `figures/{FIG_REL.name}.pdf`: reliability diagram before and after conformal calibration, and "
      "P10-P90 coverage by season, lead day and typhoon hours.")
    tw = typhoon_week(bt)
    if tw is not None:
        fig_typhoon(bt, tw)
        e = tw[0]
        res["typhoon_week"] = tw
        w(f"- `figures/{FIG_TY.name}.pdf`: {str(e['name']).title()} ({e['sid']}), closest approach "
          f"{e['closest_km']:.0f} km on {e['closest_time_utc']:%d %b %Y}; lead day 1 bands vs the satellite "
          "reference.")
    w("")
    # limitations
    w("## Limitations")
    w("")
    w("- The reference is a satellite retrieval, not a pyranometer. No ground data exist for Itbayat.")
    w("- NWP archives with GHI start in Feb 2024, so the full model is trained on at most about 2.5 years; "
      "skill should grow as the archive grows.")
    w("- Lead day 1 uses runs about a day older than an operator would have, so operational skill should be "
      "a little higher; the comparison with raw NWP is fair because both use the same runs.")
    w("- Typhoon-hour statistics rest on a few storms.")
    w("- The demand model is trained on synthetic load.")
    w("")
    w("## References")
    w("")
    w("- Gneiting, T., Raftery, A. E. (2007). Strictly proper scoring rules, prediction, and estimation. "
      "J. Am. Stat. Assoc. 102(477), 359-378. doi:10.1198/016214506000001437")
    w("- Ineichen, P., Perez, R. (2002). A new airmass independent formulation for the Linke turbidity "
      "coefficient. Solar Energy 73(3), 151-157. doi:10.1016/S0038-092X(02)00045-2")
    w("- Lei, J., G'Sell, M., Rinaldo, A., Tibshirani, R. J., Wasserman, L. (2018). Distribution-free "
      "predictive inference for regression. J. Am. Stat. Assoc. 113(523), 1094-1111. "
      "doi:10.1080/01621459.2017.1307116")
    w("- Yang, D., Alessandrini, S., Antonanzas, J., et al. (2020). Verification of deterministic solar "
      "forecasts. Solar Energy 210, 20-37. doi:10.1016/j.solener.2020.04.019")
    w("- Anderson, K. S., Hansen, C. W., Holmgren, W. F., et al. (2023). pvlib python: 2023 project update. "
      "J. Open Source Softw. 8(92), 5994. doi:10.21105/joss.05994")
    w("- Knapp, K. R., et al. (2010). The International Best Track Archive for Climate Stewardship (IBTrACS). "
      "Bull. Am. Meteorol. Soc. 91, 363-376. doi:10.1175/2009BAMS2755.1")
    w("- Tsai, C.-T., et al. (2020). Energies 13(1), 8 (see data/itbayat/SOURCES.md).")
    out_md.write_text("\n".join(L) + "\n", encoding="utf-8")
    return res
