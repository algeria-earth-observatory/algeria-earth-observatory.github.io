"""AEO tutorial: mean annual CHIRPS precipitation per wilaya (Python).

Requires: geopandas, rasterio, numpy (e.g. `conda install -c conda-forge geopandas rasterio`).
Downloads ~58 MB (CHIRPS v2.0 global annual total for 2024) and the AEO wilaya layer.
"""
import urllib.request
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.mask import mask

CHIRPS_URL = "https://data.chc.ucsb.edu/products/CHIRPS/v2.0/global_annual/tifs/chirps-v2.0.2024.tif"
WILAYAS_URL = (
    "https://algeria-earth-observatory.github.io/data/aeo/boundaries/2026-11-19/dza_adm1_wilayas.geojson"
)


def fetch(url: str, dest: Path) -> Path:
    if not dest.exists():
        print(f"downloading {url}")
        urllib.request.urlretrieve(url, dest)
    return dest


def main(workdir: Path = Path("aeo_tutorial"), wilayas_path: Path | None = None) -> gpd.GeoDataFrame:
    workdir.mkdir(exist_ok=True)
    tif = fetch(CHIRPS_URL, workdir / "chirps-v2.0.2024.tif")
    wil = gpd.read_file(wilayas_path or fetch(WILAYAS_URL, workdir / "dza_adm1_wilayas.geojson"))

    rows = []
    with rasterio.open(tif) as src:
        # Always bring vectors into the raster's CRS before overlaying.
        wil = wil.to_crs(src.crs)
        for _, w in wil.iterrows():
            # filled=False returns a masked array: pixels outside the polygon
            # and nodata pixels (-9999 in CHIRPS) are masked.
            data, _ = mask(src, [w.geometry], crop=True, filled=False)
            vals = data[0].compressed()
            rows.append({
                "wilaya_code": w.wilaya_code,
                "name": w["name"],
                "n_pixels": vals.size,
                "precip_mm_2024": float(np.mean(vals)) if vals.size else np.nan,
            })
    out = wil[["wilaya_code", "geometry"]].merge(gpd.pd.DataFrame(rows), on="wilaya_code")
    out.drop(columns="geometry").to_csv(workdir / "wilaya_precip_2024.csv", index=False)
    print(out.drop(columns="geometry").sort_values("precip_mm_2024", ascending=False).head(10).to_string(index=False))
    return out


if __name__ == "__main__":
    main()
