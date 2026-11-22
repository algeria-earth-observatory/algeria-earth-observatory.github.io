---
title: Reservoir monitor (Landsat water area) — method
description: How AEO follows the water surface of Algeria's main reservoirs month by month from Digital Earth Africa Waterbodies and Global Dam Watch, and why this is not an official filling rate.
section: Scientific practice
order: 30
updated: 2026-11-22
---

This page documents product `aeo-dza-reservoirs-deafrica`, version 1.0.0. The code is in [`scripts/pipelines/reservoirs/`](https://github.com/algeria-earth-observatory/algeria-earth-observatory.github.io/tree/main/scripts/pipelines/reservoirs).

## Data

- **Global Dam Watch (GDW) v1.0** (figshare, doi:[10.6084/m9.figshare.25988293](https://doi.org/10.6084/m9.figshare.25988293), CC BY 4.0).
  - Content: dams and reservoir polygons, with names, river, construction year and capacity.
  - Coverage: Algeria has 88 GDW reservoirs; 65 are 0.5 km² or larger. Some capacities are reported, the others modelled by GDW from area.
  - Re-hosting: the GDW authors ask that their database not be re-hosted in whole, so AEO publishes only dam points and derived values.
  - Attribution: *This product incorporates data from the GDW database © Global Dam Watch (2024).*
- **Digital Earth Africa Waterbodies** (<https://www.digitalearthafrica.org/en_za/waterbodies-continental-service/>, CC BY 4.0).
  - Content: waterbody polygons and, for each Landsat scene since 1984, the wet, dry and unobserved area of each waterbody.
  - Updates: weekly.

## Computation

1. **Reservoirs:** GDW reservoirs in Algeria of at least 0.5 km².
2. **Matching:** every DE Africa waterbody whose interior point lies inside the GDW reservoir polygon buffered by 500 m. DE Africa splits large reservoirs into several polygons; Beni Haroun has 22.
3. **Valid scenes:** for each scene date, wet and observed areas are summed over the reservoir's polygons. A scene counts only when at least **85 %** of the reservoir was observed (cloud-free), DE Africa's own rule. Other scenes are dropped, never filled.
4. **Monthly value:** the median wet area of the month's valid scenes, from the year after the dam's construction year when GDW gives it.
5. **Reference:** the largest monthly wet area observed since 1984. "% of observed maximum" = this month's area ÷ that maximum.

## How to read it

- **Not a filling rate.** It is a ratio of **surface areas**, not volumes, and not the official filling rate published by the Agence Nationale des Barrages et Transferts (ANBT). A reservoir at 50 % of its maximum area usually holds much less than 50 % of its volume, because reservoirs are deeper near the dam.
- **Months without data:** a month without a value had no scene with 85 % of the reservoir visible.

## Check

At Beni Haroun, Sentinel-2 images of November 2026 classified with the MNDWI water index gave 25–32 km² of water. That matches the DE Africa Landsat series (29.0 km² on 16 October 2026) and the GDW outline (36 km²).

## Limitations

- **Small waters:** Landsat (30 m) misses narrow arms and small reservoirs. Turbid, very shallow or vegetated water can be misclassified. Terrain shadow in Kabylie and the Aurès can be mistaken for water.
- **Saharan reservoirs:** these, such as Djorf Torba, are rarely observed well enough to give a monthly value.
- **Missing dams:** dams built after the GDW compilation (2024) are missing.
- **Volumes:** these need area–storage curves (for example GRDL, Hao et al. 2024), a possible next step.
