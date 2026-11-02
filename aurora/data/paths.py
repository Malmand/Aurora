"""Fixed locations used by the Phase 1 build."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE_DIR = ROOT / "data" / "itbayat"
RAW_DIR = SITE_DIR / "raw"            # download cache (git-ignored); raw_small/ holds the inputs
REF_DIR = SITE_DIR / "reference"      # values transcribed from papers / reports
SITE_YAML = SITE_DIR / "site.yaml"
SOURCES_MD = SITE_DIR / "SOURCES.md"
FIG_DIR = ROOT / "figures"
DOCS_DIR = ROOT / "docs"

# Site coordinates (Itbayat town centre); see site.yaml for the source.
LAT = 20.78
LON = 121.84
LOCAL_TZ = "Asia/Manila"  # PHT, UTC+8, no DST

# Inputs live in raw_small/ (aurora/data/rawio.py). Derived outputs:
TYPHOON_HOURLY = SITE_DIR / "typhoon_flags_hourly.parquet"
TYPHOON_EVENTS = SITE_DIR / "typhoon_events.csv"
LOAD_SYNTH = SITE_DIR / "load_synthetic_hourly.parquet"
LOAD_REAL = SITE_DIR / "load_hourly.parquet"
