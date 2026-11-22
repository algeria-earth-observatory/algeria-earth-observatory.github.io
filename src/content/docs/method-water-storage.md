---
title: Terrestrial water storage (downscaled GRACE) — method
description: How AEO summarises the 0.25° downscaled GRACE/GRACE-FO water storage anomalies of Li & Kusche (2026) for Algeria and its wilayas, what GRACE can and cannot resolve, and how trends are computed.
section: Scientific practice
order: 27
updated: 2026-11-22
---

This page documents product `aeo-dza-water-storage-grace`, version 1.0.0. The code is in [`scripts/pipelines/grace/`](https://github.com/algeria-earth-observatory/algeria-earth-observatory.github.io/tree/main/scripts/pipelines/grace).

## What it measures

The GRACE (2002–2017) and GRACE-FO (2018–) satellites measure changes in the Earth's gravity field. Over land, these are mostly changes in **total water storage**:
- soil moisture;
- groundwater;
- surface water (lakes, reservoirs);
- snow.

The product gives the anomaly in centimetres of water: the change in water stored, spread evenly over the area.

**It is not groundwater.** Separating groundwater needs models of the other components, which adds large uncertainty.

## Data

- **Downscaled storage:** Li, F. (2025), *Global high-resolution (0.25°) total water storage anomaly dataset derived by reproducing GRACE data*, version 2, Zenodo, doi:[10.5281/zenodo.17265162](https://doi.org/10.5281/zenodo.17265162), CC BY 4.0.
  - Method in Li & Kusche (2026), *Geophysical Research Letters* 53, e2025GL119881, doi:[10.1029/2025GL119881](https://doi.org/10.1029/2025GL119881).
  - Downscaled from the NASA JPL RL06 mascon solution with a machine-learning (LSTM) model driven by ERA5. The authors report that it reproduces the original GRACE signal closely (average correlation 0.98 across 1° land cells).
  - The file holds the storage anomaly and a downscaling uncertainty, monthly from April 2002 to March 2025, with missing months.
  - Missing months include the gap of almost a year between the two missions and isolated months of both missions.
- **Download check:** AEO checked the downloaded file against its Zenodo checksum (MD5 7d51f349bf74543d3bcd73e504502073).
- **Boundaries and cropland:** AEO boundaries of 2026-11-20, and the [stable-cropland mask](/docs/method-stable-cropland/).

Other downscaled GRACE products exist and are listed in the [catalog](/data/?q=GRACE):
- NASA GLDAS-2.2 and GRACE-DA-DM (data assimilation, Earthdata login);
- GFZ deep-learning TWSA (0.5°);
- SYSU TWSA v1.0 (0.5°).

AEO chose Li & Kusche because it is openly downloadable, finer (0.25°), recent (to 2025) and designed to keep the GRACE trends.

## Resolution: what GRACE resolves

GRACE resolves about **300 km**. The JPL solution uses 3° equal-area mascons of about 96,000 km² at 30° N. The 0.25° detail of the downscaled product comes from the model and its ERA5 inputs, constrained to match GRACE at large scale.

Only **9 of the 69 wilayas** are at least one mascon in area. The others are flagged: their value is mostly spatial detail added by the downscaling, not resolved by the satellites. Communes are not published.

## Computation

1. **Unit means:** area-weighted means of the 0.25° cells over each wilaya and Algeria (commune coverage fractions, merged exactly).
2. **Baseline:** the anomaly is re-referenced by AEO to each unit's **2004–2009** mean. Values are therefore changes relative to 2004–2009.
3. **Uncertainty:** the unit mean of the cell uncertainties. This assumes fully correlated errors, so it is an upper bound for the uncertainty of the unit mean.
4. **Trend:**
   - Slope: Theil–Sen over all available months, in cm per year, with its 95 % interval.
   - Significance: Mann–Kendall test on the deseasonalised series (each calendar month's mean removed).
5. **Stable cropland:** means weighted by each cell's stable-cropland area. They are left empty below 10,000 ha.
6. **Coastal gaps:** Tipaza has no value: the source treats its coastal 0.25° cells as ocean.

## Results (Algeria)

- **National trend:** water storage in Algeria declined by **0.25 cm per year** (95 % interval 0.23–0.26) between 2002 and 2025. The trend is significant (Mann–Kendall p < 0.0001).
- **Strongest regional decline:** about −1.2 to −1.3 cm per year in the north-east wilayas (El Tarf, Souk Ahras, Tébessa, Guelma). These are much smaller than a mascon, so this pattern rests on the downscaling.

## Limitations

- Total storage only; not groundwater, and not reservoir storage.
- Large-scale signal: values for small wilayas are model-dependent.
- The 2017–2018 gap and other missing months are left empty, never interpolated.
- The product ends in March 2025. It is a research dataset, not an operational service, and may not be updated.
