---
title: Subsetting data to Algeria
description: Clip global rasters and NetCDF time series to Algeria or to a wilaya with Python, R or QGIS, and document what you did.
section: Working with data
order: 50
updated: 2026-11-19
---

Most catalog records are global products. Before analysis you will usually (1) cut a bounding box, then (2) mask with a boundary polygon. Do the cheap step first: reading a bounding box reduces the data volume by orders of magnitude.

## Boundary to use

Use a documented, versioned boundary and cite it. The [AEO boundary dataset](/data/aeo-dza-admin-boundaries/) provides the national outline (`dza_adm0.geojson`) and 69 wilayas (`dza_adm1_wilayas.geojson`), version 2026-11-19. Use the full-detail files for analysis; the “display” files are simplified.

## GeoTIFF — Python (rasterio)

```python
import geopandas as gpd, rasterio
from rasterio.mask import mask

dz = gpd.read_file("dza_adm0.geojson")
with rasterio.open("global_product.tif") as src:
    dz = dz.to_crs(src.crs)
    out, transform = mask(src, dz.geometry, crop=True)   # pixels outside Algeria -> nodata
    meta = src.meta | {"height": out.shape[1], "width": out.shape[2], "transform": transform}
with rasterio.open("algeria_product.tif", "w", **meta) as dst:
    dst.write(out)
```

## GeoTIFF — R (terra)

```r
library(terra)
r  <- rast("global_product.tif")
dz <- project(vect("dza_adm0.geojson"), crs(r))
r_dz <- mask(crop(r, dz), dz)
writeRaster(r_dz, "algeria_product.tif", overwrite = TRUE)
```

## NetCDF time series — Python (xarray)

Climate files are ordered latitude/longitude grids. Check the coordinate names and whether latitude is ascending or descending before slicing:

```python
import xarray as xr
ds = xr.open_dataset("chirps-v2.0.monthly.nc")       # dims: time, latitude, longitude
lat = slice(18.9, 37.2) if ds.latitude[0] < ds.latitude[-1] else slice(37.2, 18.9)
dz = ds.sel(longitude=slice(-8.7, 12.0), latitude=lat)
dz.to_netcdf("chirps_monthly_algeria_bbox.nc")
```

Some products (for example ERA5-Land as delivered by the CDS) use longitudes 0–360 in older files; convert with `ds.assign_coords(longitude=((ds.longitude + 180) % 360) - 180).sortby("longitude")` before slicing.

## QGIS

1. Load the raster and `dza_adm0.geojson`.
2. *Raster → Extraction → Clip Raster by Mask Layer*.
3. Select the boundary as mask, tick *Match the extent of the clipped raster to the extent of the mask layer*, and set the nodata value.

## Document the subset

When you publish results based on a subset, record:

- the input dataset, its **version** and DOI;
- the boundary file and its version (for AEO: `aeo-dza-admin-boundaries`, version 2026-11-19);
- whether pixels were kept by centre point (`all_touched=False`, the default) or any touch;
- any reprojection and resampling method.

AEO applies the same rules to its own derived products: every Algeria-specific derivative documents its clipping boundary, processing steps, input version, output version and code.
