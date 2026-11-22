"""Fetch NASA NEX-GDDP-CMIP6 daily tasmax and pr over Algeria (server-side subset, no login).

Source: NASA NCCS THREDDS NetCDF Subset Service, https://ds.nccs.nasa.gov/thredds/ (AMES/NEX/GDDP-CMIP6),
0.25° bias-corrected, statistically downscaled CMIP6 (Thrasher et al. 2022, doi:10.1038/s41597-022-01393-4).
For each model, the newest file version per year is used (e.g. _v2.0 over _v1.1 or unversioned).

Models (8, first realisation with historical, SSP2-4.5 and SSP5-8.5), periods:
  historical 1985–2014; ssp245 and ssp585 2041–2070 and 2071–2100.

Output: data-work/cmip6/<model>/<scenario>/<var>_<year>.nc and data-work/cmip6/files.json
Usage:  python scripts/pipelines/cmip6/fetch_nex_gddp.py [--workers 4]
"""
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data-work" / "cmip6"
CAT = "https://ds.nccs.nasa.gov/thredds/catalog/AMES/NEX/GDDP-CMIP6/{m}/{s}/{r}/{v}/catalog.html"
NCSS = "https://ds.nccs.nasa.gov/thredds/ncss/grid/AMES/NEX/GDDP-CMIP6/{m}/{s}/{r}/{v}/{f}"
Q = "?var={v}&north=37.25&west=-8.75&east=12.0&south=18.9&horizStride=1&time_start={y}-01-01T00:00:00Z&time_end={y}-12-31T23:59:59Z&accept=netcdf4"
MODELS = {"ACCESS-CM2": "r1i1p1f1", "EC-Earth3": "r1i1p1f1", "GFDL-ESM4": "r1i1p1f1", "IPSL-CM6A-LR": "r1i1p1f1",
          "MIROC6": "r1i1p1f1", "MPI-ESM1-2-HR": "r1i1p1f1", "MRI-ESM2-0": "r1i1p1f1", "NorESM2-LM": "r1i1p1f1"}
PERIODS = {"historical": [range(1985, 2015)], "ssp245": [range(2041, 2071), range(2071, 2101)],
           "ssp585": [range(2041, 2071), range(2071, 2101)]}
VARS = ["tasmax", "pr"]
UA = {"User-Agent": "aeo-pipeline"}


def get(url: str, timeout: int = 600) -> bytes:
    for i in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except Exception:  # noqa: BLE001 — retry transient server errors
            if i == 4:
                raise
            time.sleep(10 * (i + 1))
    raise RuntimeError(url)


def version_key(name: str) -> tuple:
    m = re.search(r"_v(\d+)\.(\d+)\.nc$", name)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def files_for(m: str, s: str, v: str) -> dict[int, str]:
    html = get(CAT.format(m=m, s=s, r=MODELS[m], v=v), 120).decode("utf-8", "ignore")
    names = set(re.findall(rf"({v}_day_{re.escape(m)}_{s}_{MODELS[m]}_g[a-z0-9]+_(\d{{4}})(?:_v\d+\.\d+)?\.nc)", html))
    best: dict[int, str] = {}
    for n, y in names:
        y = int(y)
        if y not in best or version_key(n) > version_key(best[y]):
            best[y] = n
    return best


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    jobs, log = [], {}
    for m in MODELS:
        for s, ranges in PERIODS.items():
            for v in VARS:
                avail = files_for(m, s, v)
                for rg in ranges:
                    for y in rg:
                        if y not in avail:
                            raise SystemExit(f"missing {m} {s} {v} {y}")
                        jobs.append((m, s, v, y, avail[y]))
    print("requests", len(jobs), flush=True)

    def run(j):
        m, s, v, y, f = j
        dst = OUT / m / s / f"{v}_{y}.nc"
        if not (dst.exists() and dst.stat().st_size > 100_000):
            dst.parent.mkdir(parents=True, exist_ok=True)
            b = get(NCSS.format(m=m, s=s, r=MODELS[m], v=v, f=f) + Q.format(v=v, y=y))
            tmp = dst.with_suffix(".part")
            tmp.write_bytes(b)
            tmp.replace(dst)
        return f"{m}/{s}/{v}_{y}", f

    done = 0
    with ThreadPoolExecutor(a.workers) as ex:
        for k, f in ex.map(run, jobs):
            log[k] = f
            done += 1
            if done % 50 == 0:
                print(done, "/", len(jobs), flush=True)
    (OUT / "files.json").write_text(json.dumps(log, indent=1), encoding="utf-8")
    print("done", len(log))


if __name__ == "__main__":
    main()
