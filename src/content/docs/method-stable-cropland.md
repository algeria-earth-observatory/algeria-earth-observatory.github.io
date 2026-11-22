---
title: Stable cropland mask (GACED30, 2000–2024) — method
description: How AEO derives a stable-cropland mask for Algeria from 25 annual 30 m GACED30 maps, how areas are computed, and how the mask is used to restrict other products to agricultural land.
section: Scientific practice
order: 26
updated: 2026-11-22
---

This page documents product `aeo-dza-stable-cropland-gaced30`, version 1.0.0. The code is in [`scripts/pipelines/cropland/`](https://github.com/algeria-earth-observatory/algeria-earth-observatory.github.io/tree/main/scripts/pipelines/cropland).

## Why a stable-cropland mask

Drought, evapotranspiration, soil moisture or climate change averaged over a whole wilaya mixes cropland with rangeland, forest, towns and desert. Agricultural questions need values over the land that is actually farmed.

A single-year cropland map would follow the noise and the fallow cycle of that year. AEO therefore uses land that is mapped as cropland **in almost every year**.

## Data

- **Cropland maps:** GACED30 v1, *Global 30-m Annual Cropland Extent Dynamics*, 2000–2024 (doi:[10.5281/zenodo.18199675](https://doi.org/10.5281/zenodo.18199675); paper doi:[10.5194/essd-18-7071-2026](https://doi.org/10.5194/essd-18-7071-2026); CC BY 4.0).
  - Format: one 30 m cropland / non-cropland map per year.
  - AEO's [Algeria clip of GACED30](/data/gaced30/) is used unchanged.
- **Boundaries:** AEO boundaries of 2026-11-20 (69 wilayas, 1,541 communes).

## Definition

A 30 m pixel is **stable cropland** when GACED30 maps it as cropland in **at least 20 of the 25 years** (80 %).

- **Fallow:** GACED30 counts active fallow as cropland, so cereal–fallow rotations stay in the class.
- **Short-lived detections:** pixels mapped as cropland only in a few years are excluded. This includes the patches between Ghardaïa and Ouargla that the source maps only in 2003–2006, probably classification artefacts.
- **Other definitions:** the number of cropland years (0–25) is kept for every commune, so another threshold can be applied without reprocessing (table `aeo_cropland_years_histogram_admin2`).

## Areas

- **Pixel areas:** every pixel's true area is computed on the authalic sphere (radius 6,371,007.2 m) from its latitude. A 30 m pixel at 36° N is about 15 % smaller than at the equator. Pixel counts are never used as areas.
- **Communes:** a pixel belongs to the commune that contains its centre.
- **Wilayas and Algeria:** sums of their communes.
- **Boundary gaps:** 3,281 ha (0.001 %) of land inside Algeria falls outside any commune polygon. These are slivers between polygons; they are reported, not reassigned.

| Algeria, 2000–2024 | Area |
|---|---|
| Land mapped by GACED30 | 231.3 Mha |
| Cropland in any year | 12.98 Mha |
| Cropland in most years (13 or more) | 8.35 Mha |
| **Stable cropland (20 or more)** | **6.40 Mha** |
| Cropland in all 25 years | 4.80 Mha |

The "most years" area (8.35 Mha) is close to Algeria's commonly cited utilised agricultural area, about 8.5 Mha. That is a plausibility check, not a validation: the definitions differ.

## How other products use the mask

For each product grid, the stable-cropland area of every cell is accumulated from the 30 m pixels:
- CHIRPS 0.05°;
- WaPOR 1.17 km;
- NEX-GDDP-CMIP6 0.25°;
- downscaled GRACE 0.25°;
- NMME 1°.

A "stable cropland" value of a wilaya is then the mean of the product over its cells, weighted by each cell's **stable-cropland area** (not by its total area). Cells without stable cropland do not count.

Products leave the value empty where a unit has too little stable cropland:
- ET and soil moisture: less than 1,000 ha;
- climate projections and the seasonal outlook: less than 10,000 ha.

The per-cell grids are published as `aeo_stable_cropland_grids_v1.0.0.npz`, so every cropland statistic can be reproduced.

## Limitations

- **Accuracy:** GACED30 is a global classification. Its authors report confusion between active fallow and bare land and larger errors in semi-arid regions. No accuracy assessment specific to Algeria is published, and AEO has not made one.
- **What stable cropland is not:** it is not the cultivated area of a given year. Land sown one year in two may fall below the threshold.
- **Changes over time:** cropland that appeared after about 2005 (for example new irrigated perimeters in the Sahara) can have fewer than 20 cropland years and is then excluded. The histogram table shows these pixels.
- **Display:** the map shows the share of each 1.2 km cell that is stable cropland. Cells under 1 % are not drawn.
