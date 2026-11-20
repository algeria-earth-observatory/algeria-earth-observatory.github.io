---
title: Dataset quality and uncertainty
description: Observed, derived and modeled data; what accuracy statistics mean; and why satellite cropland maps of Algeria disagree.
section: Scientific practice
order: 60
updated: 2026-11-19
---

## Observed, derived, modeled

Every catalog record is labelled with its **data nature**:

- **Observed** — direct measurements or imagery, such as surface reflectance from Sentinel-2 or Landsat. Still subject to sensor calibration, atmospheric correction and cloud masking.
- **Derived** — produced by an algorithm from observations: land-cover and cropland classifications, vegetation indices, satellite–gauge precipitation blends, burned-area maps. Derived products have classification or retrieval errors and are **not ground truth**.
- **Modeled** — output of a physical or statistical model: reanalyses (ERA5-Land, MERRA-2), downscaled projections (NEX-GDDP-CMIP6), gridded population (WorldPop). Model values are estimates, not measurements, even where observations are assimilated.

The map explorer applies the same labels to each layer.

## Reading accuracy statements

A reported “overall accuracy of 80%” means that 80% of a validation sample was classified correctly. It does **not** tell you:

- how accurate the map is for a particular class (look for user's and producer's accuracy per class);
- how accurate it is in Algeria (global figures average over very different landscapes);
- whether area totals computed by counting map pixels are unbiased (they usually are not).

For area estimates, good practice is to combine the map with a probability sample of reference observations and report the estimated area with a confidence interval (Olofsson et al. 2014, *Remote Sensing of Environment* 148, 42–57, doi:10.1016/j.rse.2014.02.015).

When a record has no validation statement, the page says so. Absence of a reported figure is not evidence of poor or good quality.

## Cropland in Algeria: why maps disagree

Global cropland products often disagree strongly over Algeria. Common reasons:

- **Definitions differ.** Some products map land under cultivation in a given year or season (“active” or “temporary” crops); others map land used for cropping over multi-year periods, including fallow. Read each record's definition before comparing.
- **Fallow and rainfed cereals.** Cereal–fallow rotations and drought years leave cropland with little vegetation, which is spectrally similar to bare soil and degraded rangeland.
- **Steppe and rangeland.** Sparse natural vegetation on the High Plateaus can resemble poor crops.
- **Small fields and mixed systems** in the Tell, and irrigated **centre-pivot and oasis agriculture** in the Sahara, are under-represented in many training datasets.
- **Reference years differ**, and inter-annual rainfall variability changes what is cultivated.

Do not treat any single satellite-derived cropland map as ground truth, and do not compare products without harmonising definitions, reference periods and resolution.

## Precipitation and drought indices in arid regions

- Gauge density in the Algerian Sahara is very low, so satellite-gauge products rely mainly on satellite estimates there.
- Percent-of-normal anomalies and standardised indices become unstable where climatological precipitation is near zero; interpret SPI/SPEI values in hyper-arid areas with great care.
- SPEIbase: the provider has reported a unit-conversion error in potential evapotranspiration affecting releases v2.6–v2.12, with the largest effects in arid regions (see the [SPEIbase record](/data/speibase/)).
