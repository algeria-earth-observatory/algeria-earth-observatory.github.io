"""Step 1 — retrieve TerraClimate monthly precipitation (ppt) and reference
evapotranspiration (pet) for the Algeria window, 1961 to the latest complete year.

Source: TerraClimate (Abatzoglou et al. 2018, Scientific Data 5, 170191,
doi:10.1038/sdata.2017.191), University of Idaho / Climatology Lab; CC0 public domain.
Yearly global NetCDF files are read over OPeNDAP and subset to 9.0°W–12.5°E,
18.5°N–37.5°N (1/30° grid). pet is Penman–Monteith reference evapotranspiration (ASCE).

Output: data-work/spei/raw/tc_<var>_<year>.npy (float32, mm/month, NaN = sea) + index.json
Usage : python scripts/pipelines/spei/fetch_terraclimate.py [first_year] [last_year]
"""
from __future__ import annotations

import json
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np
import xarray as xr

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data-work" / "spei" / "raw"
BASE = "http://thredds.northwestknowledge.net:8080/thredds/dodsC/TERRACLIMATE_ALL/data/TerraClimate_{var}_{year}.nc"
BOX = dict(lat=slice(37.5, 18.5), lon=slice(-9.0, 12.5))


def fetch(var: str, year: int) -> dict:
    dest = RAW / f"tc_{var}_{year}.npy"
    url = BASE.format(var=var, year=year)
    if dest.exists():
        return {"var": var, "year": year, "url": url, "status": "cached"}
    for attempt in range(5):
        try:
            with xr.open_dataset(url) as ds:
                da = ds[var].sel(**BOX).load()
            a = da.values.astype("float32")
            assert a.shape[0] == 12, a.shape
            if np.nanmin(a) < 0:
                raise ValueError(f"negative {var} in {year}")
            np.save(dest, a)
            if not (RAW / "grid.json").exists():
                (RAW / "grid.json").write_text(json.dumps({"lat": da.lat.values.tolist(), "lon": da.lon.values.tolist()}))
            return {"var": var, "year": year, "url": url, "status": "downloaded"}
        except Exception as exc:
            if attempt == 4:
                raise
            print(f"retry {var} {year}: {exc}", flush=True)
            time.sleep(20 * (attempt + 1))


def main():
    y0 = int(sys.argv[1]) if len(sys.argv) > 1 else 1961
    y1 = int(sys.argv[2]) if len(sys.argv) > 2 else date.today().year - 1
    RAW.mkdir(parents=True, exist_ok=True)
    log = []
    for year in range(y0, y1 + 1):
        for var in ("ppt", "pet"):
            log.append(fetch(var, year))
        print(year, flush=True)
    (RAW / "index.json").write_text(json.dumps({"retrieved": date.today().isoformat(), "base": BASE, "box": "9W-12.5E, 18.5N-37.5N", "files": log}, indent=1))


if __name__ == "__main__":
    main()
