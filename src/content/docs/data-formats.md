---
title: Data formats
description: The file formats you will meet in the catalog — GeoTIFF/COG, NetCDF, HDF, GeoJSON, CSV — and which tools open them.
section: Getting started
order: 20
updated: 2026-11-19
---

## Raster formats

**GeoTIFF** stores a georeferenced grid (one or more bands) with its coordinate reference system (CRS), pixel size and nodata value in the file header. A **Cloud Optimized GeoTIFF (COG)** is a GeoTIFF organised in internal tiles with overviews, so software can read only the part it needs over HTTP. ESA WorldCover, WorldCereal and many AEO-relevant products are distributed as COGs.

**NetCDF** (`.nc`, `.nc4`) holds multi-dimensional arrays — typically time × latitude × longitude — with self-describing variables, units and attributes following the CF conventions. Climate products such as ERA5-Land, TerraClimate, SPEIbase and NEX-GDDP-CMIP6 use NetCDF.

**HDF / HDF-EOS** (`.hdf`, `.h5`) is used by NASA's MODIS, SMAP and VIIRS products. Files contain several datasets (“subdatasets”), often with scale factors and quality-assessment layers that must be applied before analysis.

**GRIB** is a meteorological format used by ECMWF (ERA5). The CDS can usually deliver NetCDF instead.

## Vector formats

**GeoJSON** is a plain-text JSON format for points, lines and polygons. By specification its coordinates are WGS 84 longitude/latitude. AEO boundary files are GeoJSON.

**GeoPackage** (`.gpkg`) is a single-file SQLite database for vector (and raster) data; it is the recommended replacement for shapefiles.

**Shapefile** (`.shp` with `.shx`, `.dbf`, `.prj`) is still common; keep all sidecar files together and note its 10-character field-name limit.

## Tabular formats

**CSV** is used for statistics such as FAOSTAT. Always check the units column, the flag/status columns and whether values are national totals or sub-national.

## Which tool opens what

| Format | QGIS | Python | R |
|---|---|---|---|
| GeoTIFF / COG | drag and drop | `rasterio`, `rioxarray` | `terra::rast()` |
| NetCDF | drag and drop (choose variable) | `xarray` | `terra::rast()`, `ncdf4` |
| HDF4/HDF5 | via GDAL subdatasets | `rasterio`, `h5py`, `xarray` | `terra::rast()` (subdatasets) |
| GeoJSON / GeoPackage | drag and drop | `geopandas` | `terra::vect()`, `sf::st_read()` |
| CSV | Add delimited text layer | `pandas` | `read.csv()` |

All of these tools rely on the open-source GDAL library for reading geospatial formats.
