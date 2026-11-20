---
title: Working with GeoTIFF files
description: Inspect a GeoTIFF's CRS, resolution and nodata value, read a window over Algeria, and avoid common resampling mistakes.
section: Working with data
order: 30
updated: 2026-11-19
---

## Inspect before you analyse

Every GeoTIFF carries metadata you should read first: CRS, pixel size, extent, data type, nodata value and band descriptions.

Command line (GDAL):

```bash
gdalinfo chirps-v2.0.2024.tif
```

Python:

```python
import rasterio
with rasterio.open("chirps-v2.0.2024.tif") as src:
    print(src.crs, src.res, src.bounds, src.nodata, src.dtypes, src.count)
```

R:

```r
library(terra)
r <- rast("chirps-v2.0.2024.tif")
r            # prints CRS, resolution, extent and value range
```

## Read only the Algeria window

Global rasters are large. Read just the bounding box of Algeria (approximately 8.7°W–12.0°E, 18.9°N–37.2°N):

```python
import rasterio
from rasterio.windows import from_bounds
with rasterio.open("chirps-v2.0.2024.tif") as src:
    win = from_bounds(-8.7, 18.9, 12.0, 37.2, transform=src.transform)
    arr = src.read(1, window=win, masked=True)   # masked=True applies nodata
```

```r
r_dz <- crop(r, ext(-8.7, 12.0, 18.9, 37.2))
```

A bounding box is not the national boundary. To exclude neighbouring countries, mask with the [AEO boundaries](/data/aeo-dza-admin-boundaries/) (see [Subsetting data to Algeria](/docs/subsetting-algeria/)).

## Nodata, scale factors and quality flags

- **Nodata:** CHIRPS uses -9999; many MODIS products use fill values such as -3000 and 32767. Never average fill values.
- **Scale factors:** MODIS NDVI is stored as integers with a 0.0001 scale factor; MODIS LST uses 0.02 to convert to kelvin. Check the user guide linked from each dataset page.
- **Quality layers:** products such as MOD13Q1 include pixel reliability layers. Filter cloudy or low-quality pixels before computing statistics.

## Resampling and reprojection

- Use **nearest neighbour** for categorical rasters (land cover, cropland masks) — bilinear interpolation invents classes that do not exist.
- Use **bilinear/average** for continuous variables (temperature, precipitation), and prefer **average** when aggregating to a coarser grid.
- Reproject vectors to the raster CRS rather than the reverse whenever you only need zonal statistics: it avoids resampling the data.
- For area calculations use an equal-area projection; degrees are not a unit of area.
