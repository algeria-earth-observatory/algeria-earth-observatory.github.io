---
title: Geospatial reproducibility and harmonisation
description: Record versions, CRS and resampling; harmonise grids and calendars; and publish code with derived data.
section: Scientific practice
order: 70
updated: 2026-11-19
---

## A minimal provenance record

For every dataset in an analysis, keep:

| Item | Example |
|---|---|
| Dataset and version | CHIRPS v2.0, global annual GeoTIFF |
| Identifier | DOI or the exact download URL |
| Access date | 2026-11-19 |
| Spatial subset | AEO boundaries v2026-11-19, `dza_adm0.geojson` |
| Processing | reprojection, resampling method, masks, units conversion |
| Code | repository URL and commit hash |
| Checksum | SHA-256 of the input file (optional but useful) |

AEO dataset pages give you the first three items; AEO-distributed files also provide checksums and processing code.

## Harmonising datasets

Combining products of different origin requires explicit choices:

- **Grid:** choose a target grid (often the coarsest input) and aggregate finer data with an averaging method rather than resampling coarse data to a fine grid.
- **CRS:** keep the native CRS for zonal statistics where possible; reproject vectors, not rasters.
- **Time:** align calendars (dekads, pentads, 8-day and 16-day composites do not coincide with months). For agriculture in northern Algeria, the cereal season typically spans autumn sowing to late-spring/early-summer harvest, so annual statistics on a calendar-year basis can split a season.
- **Units:** check units (mm/day vs mm/month, kelvin vs °C, scale factors) and document conversions.
- **Definitions:** cropland, forest and water definitions differ between products; harmonise or report them.

## Environments and code

- Pin software versions (`environment.yml`, `renv.lock`, `requirements.txt`).
- Script every step from download to figure; avoid manual GIS edits that cannot be repeated, or document them.
- Publish code alongside derived data; AEO requires this for every derived product it distributes.

## Versions change results

Providers reprocess archives (MODIS Collection 6.0 → 6.1, IMERG V06 → V07, CHIRPS v2 → v3, WorldCover v100 → v200). Values can change between versions, and missions end (Terra MODIS acquisitions stop on 1 December 2026). State the version you used and avoid mixing versions within a time series unless the provider documents continuity.
