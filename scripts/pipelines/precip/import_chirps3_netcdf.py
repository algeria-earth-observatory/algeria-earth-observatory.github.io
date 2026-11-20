"""Step 1 (alternative) — import CHIRPS v3.0 monthly from the official yearly NetCDF files.

Use when the CHC data server is unreachable but a local copy of the official files
exists: chirps-v3.0.YYYY.monthly.nc from
  https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/global/netcdf/by_year/
(global, 0.05°, latitude ascending from 59.975°S, longitude from 179.975°W; variable
"precip", mm/month). The same Algeria window as fetch_chirps3.py is extracted
(9.0°W–12.5°E, 18.5°N–37.5°N, north-up) and written to the same raw cache, so
build_precip.py runs unchanged. Each source file's SHA-256, size and the
"data_created" attribute are recorded in index.json.

Usage: python scripts/pipelines/precip/import_chirps3_netcdf.py <folder with *.monthly.nc>
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import xarray as xr

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data-work" / "precip" / "raw"
WEST, EAST, SOUTH, NORTH = -9.0, 12.5, 18.5, 37.5


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def main(src: Path) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    files = sorted(src.glob("chirps-v3.0.*.monthly.nc"))
    if not files:
        raise SystemExit(f"no chirps-v3.0.*.monthly.nc in {src}")
    log, sources = [], []
    for f in files:
        with xr.open_dataset(f) as ds:
            assert ds.attrs.get("version") == "Version 3.0", (f, ds.attrs.get("version"))
            lat, lon = ds.latitude.values, ds.longitude.values
            assert abs(float(np.median(np.diff(lat))) - 0.05) < 1e-4 and abs(float(np.median(np.diff(lon))) - 0.05) < 1e-4
            sub = ds.precip.sel(latitude=slice(SOUTH, NORTH), longitude=slice(WEST, EAST))
            assert sub.sizes["latitude"] == 380 and sub.sizes["longitude"] == 430, sub.sizes
            assert abs(float(sub.latitude.max()) - (NORTH - 0.025)) < 1e-3 and abs(float(sub.longitude.min()) - (WEST + 0.025)) < 1e-3
            for t in range(sub.sizes["time"]):
                a = sub.isel(time=t).values[::-1].astype("float32")  # north-up
                a[(a <= -9000) | ~np.isfinite(a)] = np.nan
                if np.nanmin(a) < 0:
                    raise ValueError(f"negative precipitation in {f.name} t={t}")
                month = str(sub.time.values[t])[:7].replace("-", ".")
                np.save(RAW / f"chirps3_{month}.npy", a)
                log.append({"month": month, "url": f"local:{f.name}", "last_modified": None, "etag": None, "bytes": None, "status": "cached"})
            sources.append({"file": f.name, "bytes": f.stat().st_size, "sha256": sha256(f), "data_created": ds.attrs.get("data_created"),
                            "months": [str(sub.time.values[0])[:7], str(sub.time.values[-1])[:7]]})
        print(f.name, flush=True)
    index = {"source": "Official CHIRPS v3.0 monthly yearly NetCDF files (CHC), local copy; original location "
                       "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/global/netcdf/by_year/",
             "retrieved": date.today().isoformat(), "window": {"west": WEST, "north": NORTH, "res_deg": 0.05, "ncol": 430, "nrow": 380},
             "source_files": sources, "files": log}
    (RAW / "index.json").write_text(json.dumps(index, indent=1))
    print(f"{len(log)} months imported: {log[0]['month']} .. {log[-1]['month']}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
