---
title: "Tutorial (Python): rainfall per wilaya"
description: Compute mean annual CHIRPS precipitation for each of the 69 wilayas with geopandas and rasterio.
section: Tutorials
order: 90
updated: 2026-11-19
---

This tutorial combines an external global dataset ([CHIRPS v2.0](/data/chirps-v2/)) with the [AEO wilaya boundaries](/data/aeo-dza-admin-boundaries/) to compute the mean 2024 precipitation total per wilaya. The script was run end-to-end by AEO on 19 November 2026 and produced the same results as the [R version](/docs/tutorial-r/) to within 0.0001 mm.

## Requirements

```bash
conda create -n aeo -c conda-forge python=3.12 geopandas rasterio
conda activate aeo
```

The script downloads about 58 MB.

## Script

```python
import urllib.request
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.mask import mask

CHIRPS_URL = "https://data.chc.ucsb.edu/products/CHIRPS/v2.0/global_annual/tifs/chirps-v2.0.2024.tif"
WILAYAS_URL = "https://algeria-earth-observatory.github.io/data/aeo/boundaries/2026-11-19/dza_adm1_wilayas.geojson"

work = Path("aeo_tutorial"); work.mkdir(exist_ok=True)
tif = work / "chirps-v2.0.2024.tif"
gj = work / "dza_adm1_wilayas.geojson"
for url, dest in [(CHIRPS_URL, tif), (WILAYAS_URL, gj)]:
    if not dest.exists():
        urllib.request.urlretrieve(url, dest)

wil = gpd.read_file(gj)
rows = []
with rasterio.open(tif) as src:
    wil = wil.to_crs(src.crs)                       # match the raster CRS
    for _, w in wil.iterrows():
        data, _ = mask(src, [w.geometry], crop=True, filled=False)
        vals = data[0].compressed()                 # drops outside-polygon and nodata (-9999) pixels
        rows.append({"wilaya_code": w.wilaya_code, "name": w["name"],
                     "n_pixels": vals.size,
                     "precip_mm_2024": float(np.mean(vals)) if vals.size else np.nan})

res = pd.DataFrame(rows)
res.to_csv(work / "wilaya_precip_2024.csv", index=False)
print(res.sort_values("precip_mm_2024", ascending=False).head(10).to_string(index=False))
```

## What the result means — and does not

- Values are means of 0.05° CHIRPS cells whose **centres** fall inside each wilaya (`all_touched=False`). The smallest wilaya, Alger, contains 29 cells.
- CHIRPS is a satellite–gauge blend; over the Sahara it relies mainly on satellite estimates (see the record's limitations).
- One year is not a climatology. For drought analysis, compare against a long baseline from the same product and version.

## Going further

- Repeat for several years from the `global_annual/tifs/` folder of the CHIRPS archive and compute anomalies.
- Replace CHIRPS with another GeoTIFF from the catalog; always check its nodata value and scale factor first ([Working with GeoTIFF files](/docs/geotiff/)).
