---
title: Evapotranspiration and soil moisture (FAO WaPOR v3) — method
description: How AEO summarises FAO WaPOR v3 actual evapotranspiration, reference evapotranspiration and relative soil moisture by wilaya and commune, over all land and over stable cropland.
section: Scientific practice
order: 29
updated: 2026-11-22
---

This page documents product `aeo-dza-et-soil-moisture-wapor3`, version 1.0.0. The code is in [`scripts/pipelines/wapor/`](https://github.com/algeria-earth-observatory/algeria-earth-observatory.github.io/tree/main/scripts/pipelines/wapor).

## Data

FAO **WaPOR v3** (Water Productivity through Open access of Remotely sensed derived data; <https://data.apps.fao.org/wapor/>; CC BY 4.0) Level 1, global. The rasters are public Cloud Optimized GeoTIFFs and need no login.

| WaPOR layer | Content | Resolution |
|---|---|---|
| L1-AETI-M | Actual evapotranspiration and interception, mm/month | 300 m, monthly |
| L1-RET-M | Reference evapotranspiration (FAO-56 Penman–Monteith), mm/month | about 30 km, monthly |
| L1-RSM-D | Relative soil moisture of the root zone | 300 m, every 10 days (dekad) |

- **AETI:** WaPOR estimates it with a surface energy balance model (ETLook) from satellite land surface temperature, vegetation and weather data. It is a model estimate, not a measurement.
- **RET:** the atmospheric demand for water.
- **Relative soil moisture:** WaPOR derives it from land surface temperature. 0 means the wilting point and 100 field capacity.

**A note on units.** The WaPOR catalogue lists relative soil moisture in "%" with a scale factor of 0.001. After scaling, however, the values are fractions between 0 and 1: raw values run from 0 to 1,000. AEO multiplies by 100 to give percent.

## Computation

1. **Reading:** the 300 m layers are read from FAO's cloud files at their 1.17 km overview. FAO computes the overviews by averaging, so a unit mean from the overview equals the 300 m unit mean up to edge pixels. RET is read at its native resolution and resampled bilinearly to 1.17 km.
2. **Monthly soil moisture:** the mean of the month's dekads. At least 2 of 3 are required.
3. **Unit means:** area-weighted means by commune (coverage fractions), merged exactly into wilayas and Algeria. The national value equals the area-weighted mean of the wilayas; the build checks this every month.
4. **Stable cropland:** means weighted by each cell's [stable-cropland](/docs/method-stable-cropland/) area. They are left empty where a unit has less than 1,000 ha of stable cropland.
5. **Departures:** compared with the **2018–2025 mean of the same calendar month**: AETI in percent, soil moisture in percentage points. Eight years is too short for a climate normal, so departures flag an unusual month, not a drought class.

## How to read it

- **ET and rainfall:** in rain-fed cereal areas, ET rises from winter to an April–May peak and collapses after harvest. A spring ET well below the 2018–2025 mean on stable cropland points to poor crop growth, whether from drought or from land left unsown.
- **Irrigation:** on irrigated land, ET reflects irrigation as well as rainfall.
- **Soil moisture in the desert:** In the Sahara, with almost no vegetation, WaPOR relative soil moisture is not meaningful (values come from its surface-temperature method); read it for vegetated land and cropland.

## Limitations

- Model estimates (WaPOR ETLook), not measurements. AEO knows of no validation of WaPOR v3 specifically for Algeria.
- WaPOR relative soil moisture is not a microwave retrieval. It may disagree with SMAP or ESA CCI soil moisture.
- FAO can revise recent months. The product records the source file of each month.
- The record starts in 2018: long-term comparisons need other datasets (for example SPEI or ERA5-Land).
