# raw_small: downloaded inputs (Phases 1-2)

Written only by `python scripts/download_itbayat.py` (run on a machine with its own network quota). The pipeline reads these files and never downloads. Zstd-compressed parquet, UTC index `time`, schema in `aurora/data/rawio.py`. `MANIFEST.json` gives source, URL, period, rows and sha256 for each file.

| File | Content |
|---|---|
| `era5_hourly.parquet` | ERA5 hourly, 2015 to present (Open-Meteo or Copernicus CDS) |
| `satellite_radiation_hourly.parquet` | Open-Meteo satellite radiation (GHI, DNI, DHI) |
| `nasa_power_hourly.parquet` | NASA POWER hourly, relabelled to hour-ending |
| `previous_runs_{ecmwf,gfs,icon,jma}.parquet` | Archived NWP forecasts, columns `<var>_d0/_d1/_d2` |
| `ibtracs_wp_tracks.parquet` | IBTrACS v04r01 West Pacific track fixes, seasons 2014 onwards |

None of these is a measurement.
