"""Tropical cyclone proximity flags for Itbayat from IBTrACS v04r01 (West Pacific).

Source: Knapp et al. (2010), Bull. Amer. Meteor. Soc. 91, 363-376,
doi:10.1175/2009BAMS2755.1; data: NOAA NCEI IBTrACS v04r01.

Track fixes (3-hourly, some 6-hourly) are interpolated linearly to hourly
positions. For each UTC hour we keep the nearest active storm and flag hours
with a storm centre within 300 km and 500 km of the site.
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from . import paths
from .http import download

IBTRACS_URL = ("https://www.ncei.noaa.gov/data/international-best-track-archive-for-"
               "climate-stewardship-ibtracs/v04r01/access/csv/ibtracs.WP.list.v04r01.csv")
RADII_KM = (300, 500)
R_EARTH_KM = 6371.0


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dlmb = np.radians(np.asarray(lon2) - np.asarray(lon1))
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * R_EARTH_KM * np.arcsin(np.sqrt(a))


def read_ibtracs(path, since: int = 2014) -> pd.DataFrame:
    cols = ["SID", "SEASON", "NAME", "ISO_TIME", "LAT", "LON",
            "WMO_WIND", "WMO_PRES", "USA_WIND", "USA_PRES", "TOKYO_WIND", "TOKYO_PRES"]
    df = pd.read_csv(path, usecols=cols, skiprows=[1], keep_default_na=False,
                     na_values=[" ", ""], low_memory=False)
    df["SEASON"] = pd.to_numeric(df["SEASON"], errors="coerce")
    df = df[df["SEASON"] >= since].copy()
    df["time"] = pd.to_datetime(df["ISO_TIME"], utc=True)
    for c in cols[4:]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    # best available intensity: JMA (RSMC Tokyo, 10-min wind) then WMO then USA (1-min)
    df["wind_kt"] = df["TOKYO_WIND"].fillna(df["WMO_WIND"]).fillna(df["USA_WIND"])
    df["pres_hpa"] = df["TOKYO_PRES"].fillna(df["WMO_PRES"]).fillna(df["USA_PRES"])
    return df[["SID", "NAME", "time", "LAT", "LON", "wind_kt", "pres_hpa"]]


def to_hourly(tracks: pd.DataFrame) -> pd.DataFrame:
    """Interpolate each storm's fixes to whole UTC hours."""
    out = []
    for sid, g in tracks.groupby("SID", sort=False):
        g = g.drop_duplicates("time").set_index("time").sort_index()
        if len(g) < 2:
            continue
        lon = np.degrees(np.unwrap(np.radians(g["LON"].to_numpy())))
        g = g.assign(LON=lon)
        idx = pd.date_range(g.index[0].ceil("h"), g.index[-1].floor("h"), freq="h")
        num = g[["LAT", "LON", "wind_kt", "pres_hpa"]]
        h = num.reindex(num.index.union(idx)).interpolate(method="time", limit_area="inside").reindex(idx)
        h["LON"] = (h["LON"] + 180) % 360 - 180
        h["SID"], h["NAME"] = sid, g["NAME"].iloc[0]
        out.append(h)
    hourly = pd.concat(out)
    hourly.index.name = "time"
    return hourly.reset_index()


def site_flags(hourly_tracks: pd.DataFrame, index: pd.DatetimeIndex,
               lat=paths.LAT, lon=paths.LON) -> pd.DataFrame:
    t = hourly_tracks.copy()
    t["dist_km"] = haversine_km(lat, lon, t["LAT"], t["LON"])
    near = t.sort_values("dist_km").drop_duplicates("time").set_index("time").sort_index()
    f = pd.DataFrame(index=index)
    f.index.name = "time"
    f = f.join(near[["SID", "NAME", "dist_km", "wind_kt", "pres_hpa"]])
    f = f.rename(columns={"SID": "storm_sid", "NAME": "storm_name",
                          "wind_kt": "storm_wind_kt", "pres_hpa": "storm_pres_hpa"})
    for r in RADII_KM:
        f[f"tc_within_{r}km"] = (f["dist_km"] <= r).fillna(False).astype(bool)
    return f


def events(hourly_tracks: pd.DataFrame, lat=paths.LAT, lon=paths.LON,
           radius_km: float = 500) -> pd.DataFrame:
    t = hourly_tracks.copy()
    t["dist_km"] = haversine_km(lat, lon, t["LAT"], t["LON"])
    rows = []
    for sid, g in t[t["dist_km"] <= radius_km].groupby("SID"):
        g = g.sort_values("time")
        ca = g.loc[g["dist_km"].idxmin()]
        rows.append({
            "sid": sid, "name": g["NAME"].iloc[0],
            "first_within_500km_utc": g["time"].min(),
            "last_within_500km_utc": g["time"].max(),
            "hours_within_500km": len(g),
            "hours_within_300km": int((g["dist_km"] <= 300).sum()),
            "closest_km": round(float(ca["dist_km"]), 1),
            "closest_time_utc": ca["time"],
            "max_wind_kt_within_500km": g["wind_kt"].max(),
            "min_pres_hpa_within_500km": g["pres_hpa"].min(),
        })
    return pd.DataFrame(rows).sort_values("first_within_500km_utc").reset_index(drop=True)


def build(index: pd.DatetimeIndex | None = None, since: int = 2015):
    raw = download(IBTRACS_URL, paths.RAW_DIR / "ibtracs.WP.list.v04r01.csv")
    tracks = read_ibtracs(raw, since=since - 1)
    hourly = to_hourly(tracks)
    if index is None:
        index = pd.date_range(pd.Timestamp(f"{since}-01-01", tz="UTC"), hourly["time"].max().floor("D"),
                              freq="h")
    flags = site_flags(hourly, index)
    flags.attrs.update(source="IBTrACS v04r01 WP (Knapp et al. 2010, doi:10.1175/2009BAMS2755.1)",
                       url=IBTRACS_URL)
    ev = events(hourly)
    ev = ev[ev["last_within_500km_utc"] >= pd.Timestamp(f"{since}-01-01", tz="UTC")]
    flags.to_parquet(paths.TYPHOON_HOURLY)
    ev.to_csv(paths.TYPHOON_EVENTS, index=False)
    return flags, ev


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--since", type=int, default=2015)
    a = ap.parse_args(argv)
    flags, ev = build(since=a.since)
    print(f"{len(ev)} storms within 500 km since {a.since}; "
          f"{int(flags['tc_within_300km'].sum())} h within 300 km, "
          f"{int(flags['tc_within_500km'].sum())} h within 500 km")
    print(ev.to_string())


if __name__ == "__main__":
    main()
