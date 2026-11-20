"""Step 1 — retrieve CHIRPS v3.0 monthly precipitation for the Algeria window.

Source: CHIRPS v3.0 final monthly, global Cloud Optimized GeoTIFFs
  https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/global/cogs/chirps-v3.0.YYYY.MM.cog
  (Climate Hazards Center, UC Santa Barbara; data DOI 10.15780/G2JQ0P; CC BY 4.0)

Only the window 9.0°W–12.5°E, 18.5°N–37.5°N (430 x 380 cells of 0.05°) is read from each
file with HTTP range requests. Sea / outside-domain cells are -9999 in the source
(not declared as nodata in the files) and are stored as NaN.

Output: data-work/precip/raw/chirps3_YYYY.MM.npy (float32, mm/month) and
        data-work/precip/raw/index.json (file URL, Last-Modified, ETag, retrieval date)
Usage : python scripts/pipelines/precip/fetch_chirps3.py [--refresh]
"""
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data-work" / "precip" / "raw"
BASE = "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/global/cogs/"
# window in the source grid (origin 180°W, 60°N, 0.05° cells)
COL0, ROW0, NCOL, NROW = 3420, 450, 430, 380
WEST, NORTH, RES = -180 + COL0 * 0.05, 60 - ROW0 * 0.05, 0.05


def listing() -> list[str]:
    with urllib.request.urlopen(BASE, timeout=120) as r:
        html = r.read().decode()
    return sorted(set(re.findall(r"chirps-v3\.0\.(\d{4}\.\d{2})\.cog", html)))


def head(url: str) -> dict:
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=60) as r:
                return {"last_modified": r.headers.get("Last-Modified"), "etag": r.headers.get("ETag"),
                        "bytes": int(r.headers.get("Content-Length") or 0)}
        except OSError:
            time.sleep(30 * (attempt + 1))
    return {"last_modified": None, "etag": None, "bytes": None}


def fetch(month: str, refresh: bool) -> dict:
    url = f"{BASE}chirps-v3.0.{month}.cog"
    dest = RAW / f"chirps3_{month}.npy"
    meta = head(url)
    if dest.exists() and not refresh:
        return {"month": month, "url": url, **meta, "status": "cached"}
    for attempt in range(5):
        try:
            with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_MULTIRANGE="YES",
                              GDAL_HTTP_TIMEOUT="60", GDAL_HTTP_CONNECTTIMEOUT="20",
                              GDAL_HTTP_MAX_RETRY="3", GDAL_HTTP_RETRY_DELAY="5"):
                with rasterio.open(url) as src:
                    assert src.crs.to_epsg() == 4326 and abs(src.res[0] - RES) < 1e-6, (src.crs, src.res)
                    assert abs(src.bounds.left + 180) < 1e-6 and abs(src.bounds.top - 60) < 1e-6
                    a = src.read(1, window=Window(COL0, ROW0, NCOL, NROW)).astype("float32")
            a[a <= -9000] = np.nan
            if np.nanmin(a) < 0:
                raise ValueError(f"negative precipitation in {month}: {np.nanmin(a)}")
            np.save(dest, a)
            print(month, flush=True)
            return {"month": month, "url": url, **meta, "status": "downloaded"}
        except Exception as exc:  # network hiccups
            if attempt == 4:
                print(f"{month}: giving up for now ({exc})", flush=True)
                return {"month": month, "url": url, **meta, "status": "failed"}
            time.sleep(30 * (attempt + 1))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="re-download months already cached")
    args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    months = listing()
    print(f"{len(months)} monthly files on the server: {months[0]} .. {months[-1]}", flush=True)
    with ThreadPoolExecutor(2) as ex:
        log = list(ex.map(lambda m: fetch(m, args.refresh), months))
    index = {"source": BASE, "retrieved": date.today().isoformat(),
             "window": {"west": WEST, "north": NORTH, "res_deg": RES, "ncol": NCOL, "nrow": NROW},
             "files": log}
    (RAW / "index.json").write_text(json.dumps(index, indent=1))
    summary = {s: sum(1 for r in log if r["status"] == s) for s in ("downloaded", "cached", "failed")}
    print(summary)
    if summary["failed"]:
        raise SystemExit(f"{summary['failed']} months not retrieved; run again to resume")


if __name__ == "__main__":
    main()
