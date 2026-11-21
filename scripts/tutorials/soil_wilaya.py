"""AEO tutorial: soil organic carbon of a wilaya from SoilGrids 2.0, checked against AEO.

Objective: read the SoilGrids 1 km soil organic carbon map (0–5 cm) for one wilaya directly
from ISRIC, compute its mean in the native equal-area projection, and compare it with the AEO
soil statistics table.

Requires: geopandas, rasterio, numpy, pandas, pyarrow
Network: reads about 1–2 MB from files.isric.org (only the window over the wilaya) and two
small files from the AEO website (or a local copy).

Usage:  python soil_wilaya.py [wilaya_code] [--local path/to/public]
"""
from __future__ import annotations

import argparse
import io
import os
import urllib.request
from pathlib import Path

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds

SITE = "https://algeria-earth-observatory.github.io"
WILAYAS = "/data/aeo/boundaries/2026-11-20/dza_adm1_wilayas.geojson"
STATS = "/data/aeo/products/soil/v1.0.0/tables/aeo_soil_stats_admin1_v1.0.0.parquet"
SOC = "/vsicurl/https://files.isric.org/soilgrids/latest/data_aggregated/1000m/soc/soc_0-5cm_mean_1000.tif"


def fetch(path: str, local: Path | None) -> bytes:
    if local:
        return (local / path.lstrip("/")).read_bytes()
    with urllib.request.urlopen(SITE + path, timeout=120) as r:
        return r.read()


def main(code: str = "19", local: Path | None = None) -> dict:
    w = gpd.read_file(io.BytesIO(fetch(WILAYAS, local)))
    w = w[w.wilaya_code == code]
    with rasterio.open(SOC) as ds:
        wi = w.to_crs(ds.crs)                                   # SoilGrids: Interrupted Goode Homolosine (equal-area)
        win = from_bounds(*wi.total_bounds, ds.transform).round_offsets().round_lengths()
        a = ds.read(1, window=win).astype(float)
        inside = geometry_mask(wi.geometry, out_shape=a.shape, transform=ds.window_transform(win), invert=True)
        a[a == ds.nodata] = np.nan
    vals = a[inside] / 10.0                                     # dg/kg -> g/kg (ISRIC conversion factor 10)
    mean = float(np.nanmean(vals))                              # equal-area pixels: plain mean = area-weighted mean
    aeo = pd.read_parquet(io.BytesIO(fetch(STATS, local)))
    row = aeo[(aeo.unit_code == code) & (aeo.property == "soc") & (aeo.depth == "0-5cm")].iloc[0]
    print(f"{w.name.iloc[0]} (wilaya {code}): {inside.sum()} pixels of 1 km²")
    print(f"Soil organic carbon 0–5 cm, mean of predictions: {mean:.2f} g/kg (AEO table: {row['mean']:.2f} g/kg)")
    print(f"Average pixel 5–95 % prediction range (AEO table): {row.q05_mean:.2f}–{row.q95_mean:.2f} g/kg")
    return {"mean": mean, "aeo": float(row["mean"]), "pixels": int(inside.sum())}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("wilaya", nargs="?", default="19")
    ap.add_argument("--local", type=Path, default=None, help="local copy of the site's public/ folder")
    a = ap.parse_args()
    main(a.wilaya, a.local)
