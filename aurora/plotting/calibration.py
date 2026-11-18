"""Load calibration check: SYNTHETIC load before and after calibration vs NPC's
annual figures for Itbayat DPP (MEP 2025-2029 Annex R).

    python -m aurora.plotting.calibration [OLD_LOAD.parquet]

OLD_LOAD is the uncalibrated series (optional; e.g. from git show 36f42bc:...).
Writes figures/load_calibration_npc.pdf|png.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from aurora.data import paths
from aurora.data.site import load_site

from . import style
from .style import OKABE_ITO as C, plt

OUT = paths.ROOT / "figures" / "load_calibration_npc"


def annual(df: pd.DataFrame) -> pd.DataFrame:
    loc = df.index.tz_convert(paths.LOCAL_TZ)
    g = df["total_kW"].groupby(loc.year)
    n = g.size()
    full = n >= 24 * 360
    return pd.DataFrame({"mwh": g.sum()[full] / 1000, "peak": g.max()[full]})


def main(old_path: str | None = None):
    style.apply()
    npc = load_site()["npc_itbayat_dpp"]
    t = pd.DataFrame({k: npc[k] for k in ("years", "kind", "peak_kw", "gross_gen_mwh")}).set_index("years")
    new = annual(pd.read_parquet(paths.LOAD_SYNTH))
    old = annual(pd.read_parquet(old_path)) if old_path else None
    yrs = [y for y in t.index if y in new.index]
    t = t.loc[yrs]

    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.6))
    for ax, col, mcol, ylab in ((axes[0], "gross_gen_mwh", "mwh", "Annual energy (MWh)"),
                                (axes[1], "peak_kw", "peak", "Annual peak demand (kW)")):
        x = np.arange(len(yrs))
        hist = (t["kind"] == "hist").to_numpy()
        ax.bar(x[hist], t[col][hist], 0.6, color=C["sky"], label="NPC, historical")
        ax.bar(x[~hist], t[col][~hist], 0.6, color="white", edgecolor=C["sky"], hatch="////", lw=0.6,
               label="NPC, forecast")
        if old is not None:
            o = old.reindex(yrs)[mcol]
            ax.plot(x, o, ls="--", marker="s", ms=3.5, color=C["vermillion"], label="Model before calibration")
        ax.plot(x, new.loc[yrs, mcol], ls="-", marker="o", ms=3.5, color=C["black"], label="Model, calibrated")
        ax.set_xticks(x, [str(y) for y in yrs])
        ax.set_ylabel(ylab)
        ax.set_xlabel("Year")
        ax.set_ylim(0, None)
    h, lab = axes[0].get_legend_handles_labels()
    style.panel_label(axes[0], "A")
    style.panel_label(axes[1], "B")
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    fig.legend(h, lab, loc="lower center", ncol=4, fontsize=7, bbox_to_anchor=(0.5, 0.0))
    style.save(fig, OUT)
    print("wrote", OUT.with_suffix(".png").relative_to(paths.ROOT))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
