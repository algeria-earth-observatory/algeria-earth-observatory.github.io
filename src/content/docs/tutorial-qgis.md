---
title: "Tutorial (QGIS): wilayas, surface water and zonal statistics"
description: Load the AEO wilaya layer, add the JRC Global Surface Water tiles as a backdrop, and compute zonal statistics from a GeoTIFF — no programming.
section: Tutorials
order: 92
updated: 2026-11-19
---

Written for QGIS 3.x (long-term release). Menu names may differ slightly between versions.

## 1. Load the wilaya boundaries

1. Download `dza_adm1_wilayas.geojson` from the [boundary dataset page](/data/aeo-dza-admin-boundaries/).
2. Drag the file onto the QGIS map canvas. The layer has 69 features in EPSG:4326.
3. Right-click the layer → *Properties → Symbology*: choose *Simple fill*, set fill to transparent and stroke to a dark colour.
4. *Labels* tab → *Single labels* → value `name`.

## 2. Add a backdrop of surface water (XYZ tiles)

1. In the *Browser* panel, right-click *XYZ Tiles* → *New Connection*.
2. Name: `JRC Global Surface Water occurrence (v1.4)`.
3. URL: `https://storage.googleapis.com/global-surface-water/tiles2021/occurrence/{z}/{x}/{y}.png`
4. Max zoom level: 13. Save, then double-click the connection to add it.
5. Add the attribution “Source: EC JRC/Google” to any map you export.

These tiles are a visualisation (red = rarely water, blue = permanent water). For analysis, download the GeoTIFF tiles from the [dataset source](/data/jrc-global-surface-water/).

## 3. Zonal statistics from a GeoTIFF

1. Download a GeoTIFF, for example the CHIRPS annual total `chirps-v2.0.2024.tif` (see the [Python tutorial](/docs/tutorial-python/) for the URL).
2. Load it. In *Properties → Transparency*, confirm the nodata value is -9999.
3. *Processing Toolbox* → search **Zonal statistics** (*Raster analysis*).
4. Input layer: the wilayas; Raster layer: the GeoTIFF; Statistics: *Mean* and *Count*; output prefix `p24_`.
5. Run. Open the attribute table of the output layer to see `p24_mean` for each wilaya.

QGIS counts the cells whose centre falls in the polygon, consistent with the Python and R tutorials.

## 4. Export

- *Right-click layer → Export → Save Features As…* to write a GeoPackage or CSV.
- When exporting a map (*Project → New Print Layout*), include data sources and licences in the layout text: CHIRPS (CC0 per the provider), boundaries © OpenStreetMap contributors (ODbL).
