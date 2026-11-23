"""Fetch FAO WaPOR v3 Level-1 rasters over Algeria (open Cloud Optimized GeoTIFFs, no login).

Mapsets (WaPOR v3, global, https://data.apps.fao.org/wapor/):
  L1-AETI-M  actual evapotranspiration and interception, monthly, 300 m, mm/month (scale 0.1)
  L1-RET-M   reference evapotranspiration (FAO-56), monthly, ~30 km, mm/month (scale 0.1)
  L1-RSM-D   relative soil moisture, dekadal, 300 m, % (scale 0.1) — root-zone, from the WaPOR
             surface energy balance (LST-based), not a microwave retrieval

The rasters are read with HTTP range requests from the COG overview whose pixel is about
1.2 km (overview level 1 for the 300 m layers, 0.0117°); the overviews are AVERAGE-resampled
by FAO, so a unit mean computed from them equals the unit mean at 300 m up to edge pixels.
RET is read at its native resolution.

Output: data-work/wapor/<mapset>/<code>.tif (Algeria window, int16, same nodata and scale)
        data-work/wapor/catalog.json (raster list with dates and source URLs)

Usage:  python scripts/pipelines/wapor/fetch_wapor.py [--workers 4]
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import rasterio
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data-work" / "wapor"
API = "https://data.apps.fao.org/gismgr/api/v2/catalog/workspaces/WAPOR-3/mapsets/{m}/rasters?size=100"
BBOX = (-8.75, 18.9, 12.0, 37.25)  # Algeria with margin (W, S, E, N)
MAPSETS = {"L1-AETI-M": 1, "L1-RET-M": None, "L1-RSM-D": 1}  # overview level (None = native)
UA = {"User-Agent": "aeo-pipeline"}
ENV = dict(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
           GDAL_HTTP_USERAGENT="aeo-pipeline", GDAL_HTTP_MAX_RETRY="5", GDAL_HTTP_RETRY_DELAY="3")


def list_rasters(mapset: str) -> list[dict]:
    """All rasters of a mapset; the API returns at most 100 items per page."""
    items, page = [], 0
    while True:
        url = API.format(m=mapset) + f"&page={page}"
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
            resp = json.load(r)["response"]
        items += resp["items"]
        if not resp.get("hasNext"):
            break
        page += 1
    out = []
    for it in items:
        mem = it["dimensions"][0]["member"]
        out.append({"code": it["code"], "start": mem["startDate"], "end": mem["endDate"], "url": it["downloadUrl"],
                    "scale": it["scale"], "unit": it["measureUnit"]})
    return sorted(out, key=lambda x: x["start"])


def fetch(mapset: str, item: dict, level: int | None) -> str:
    dst = OUT / mapset / f"{item['code']}.tif"
    if dst.exists() and dst.stat().st_size > 0:
        return "cached"
    kw = {} if level is None else {"overview_level": level}
    with rasterio.Env(**ENV):
        with rasterio.open("/vsicurl/" + item["url"], **kw) as src:
            win = from_bounds(*BBOX, src.transform).round_offsets().round_lengths()
            a = src.read(1, window=win)
            prof = {"driver": "GTiff", "dtype": a.dtype, "count": 1, "height": a.shape[0], "width": a.shape[1],
                    "crs": src.crs, "transform": src.window_transform(win), "nodata": src.nodata,
                    "compress": "deflate", "predictor": 2, "tiled": True}
    tmp = dst.with_suffix(".part")
    with rasterio.open(tmp, "w", **prof) as d:
        d.write(a, 1)
        d.update_tags(source_url=item["url"], scale=str(item["scale"]), unit=item["unit"], start=item["start"], end=item["end"])
    tmp.replace(dst)
    return "ok"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--mapsets", nargs="*", default=list(MAPSETS))
    a = ap.parse_args()
    catalog = {}
    for m in a.mapsets:
        (OUT / m).mkdir(parents=True, exist_ok=True)
        items = list_rasters(m)
        catalog[m] = items
        print(m, len(items), items[0]["start"], "→", items[-1]["end"], flush=True)
        with ThreadPoolExecutor(a.workers) as ex:
            res = list(ex.map(lambda it: (it["code"], fetch(m, it, MAPSETS[m])), items))
        bad = [c for c, s in res if s not in ("ok", "cached")]
        print("  done", sum(s == "ok" for _, s in res), "new,", sum(s == "cached" for _, s in res), "cached", flush=True)
        if bad:
            sys.exit(f"failed: {bad}")
    (OUT / "catalog.json").write_text(json.dumps(catalog, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
