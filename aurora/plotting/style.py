"""Journal figure style from CLAUDE.md: L-frame, outward ticks, no grid, Okabe-Ito."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OKABE_ITO = {
    "black": "#000000", "orange": "#E69F00", "sky": "#56B4E9", "green": "#009E73",
    "yellow": "#F0E442", "blue": "#0072B2", "vermillion": "#D55E00", "purple": "#CC79A7",
}


def apply():
    plt.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "font.size": 7, "axes.labelsize": 8, "axes.titlesize": 8,
        "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7,
        "axes.linewidth": 0.75, "axes.edgecolor": "black",
        "axes.spines.top": False, "axes.spines.right": False, "axes.grid": False,
        "xtick.direction": "out", "ytick.direction": "out",
        "xtick.major.width": 0.75, "ytick.major.width": 0.75,
        "xtick.minor.visible": False, "ytick.minor.visible": False,
        "legend.frameon": False, "lines.linewidth": 1.0,
        "pdf.fonttype": 42, "savefig.dpi": 300, "savefig.bbox": "tight",
    })


def panel_label(ax, letter: str):
    ax.text(-0.14, 1.04, letter, transform=ax.transAxes, fontsize=11,
            fontweight="bold", va="bottom", ha="left")


def save(fig, stem):
    """Save PDF plus 300 dpi PNG."""
    stem.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(stem.with_suffix(".pdf"))
    fig.savefig(stem.with_suffix(".png"), dpi=300)
    plt.close(fig)
