---
title: Algeria soil properties (SoilGrids 2.0) — method
description: How AEO summarises SoilGrids 2.0 soil property predictions (organic carbon, texture, pH, bulk density, CEC, nitrogen, coarse fragments, carbon stock) for Algeria, its wilayas and communes, with depth intervals, units and prediction uncertainty.
section: Scientific practice
order: 23
updated: 2026-11-21
---

This page documents product `aeo-dza-soil-soilgrids`, version 1.0.0. The code is [`scripts/pipelines/soil/build_soil.py`](https://github.com/algeria-earth-observatory/algeria-earth-observatory.github.io/blob/main/scripts/pipelines/soil/build_soil.py).

## What the data are — and are not

**SoilGrids 2.0** (Poggio et al. 2021, doi:10.5194/soil-7-217-2021) is produced by ISRIC — World Soil Information.
- It predicts soil properties at 250 m with machine-learning models.
- The models are trained on soil profiles (WoSIS) and environmental covariates.
- They are **model predictions, not field measurements**.
- In Algeria few profiles were available to the model: the live WoSIS service lists only 10 soil profiles for Algeria (4 from 1971–72, 6 undated, none in the Sahara; queried 2026-11-21; see the [WoSIS record](/data/wosis-soil-profiles/)). The prediction uncertainty is therefore large, and AEO publishes it next to every value.

AEO does not change the predictions. It averages them over administrative units and reports their uncertainty.

## Properties, depths and units

Values are converted from the integer mapped units with ISRIC's conversion factors (SoilGrids FAQ):

| Property | Code | Depths | Units |
|---|---|---|---|
| Soil organic carbon (concentration in the fine earth) | `soc` | 0–5, 5–15, 15–30 cm | g/kg |
| pH in water | `phh2o` | 0–5, 5–15, 15–30 cm | pH |
| Clay, sand, silt fractions | `clay`, `sand`, `silt` | 0–5, 5–15, 15–30 cm | % (g/100 g) |
| Bulk density of the fine earth | `bdod` | 0–5, 5–15, 15–30 cm | kg/dm³ |
| Cation exchange capacity at pH 7 | `cec` | 0–5, 5–15, 15–30 cm | cmol(c)/kg |
| Total nitrogen | `nitrogen` | 0–5, 5–15, 15–30 cm | g/kg |
| Coarse fragments (volume) | `cfvo` | 0–5, 5–15, 15–30 cm | vol % |
| Organic carbon stock | `ocs` | 0–30 cm | t/ha |

**Concentration is not stock.**
- Soil organic carbon *concentration* (g/kg) cannot be turned into a *stock* without bulk density, coarse fragments and layer thickness.
- AEO does not make that conversion. The stock reported here is ISRIC's own `ocs` product, which ISRIC computed with those terms.

## Computation

1. **Source maps:**
   - the 1 km aggregated mean predictions (`data_aggregated/1000m`);
   - the 250 m 5 % and 95 % quantile maps (`Q0.05`, `Q0.95`), averaged in 4 × 4 blocks onto the same 1 km grid. The 250 m grid nests exactly in the 1 km grid; this is checked.
2. **Projection:** everything is computed in SoilGrids' **Interrupted Goode Homolosine** projection.
   - It is equal-area, so every 1 km pixel has the same area.
   - The unweighted mean of the pixels whose centre falls in a unit is therefore its area-weighted mean.
   - AEO boundaries are projected to Homolosine; the rasters are not resampled.
3. **Statistics per unit, property and depth:**
   - `mean`: mean of the predicted means;
   - `q05_mean`, `q95_mean`: unit averages of the pixel 5 % and 95 % quantiles. They show pixel-level prediction uncertainty; they are *not* a confidence interval of the unit mean;
   - `pixels_1km`, `valid_pct`: number of pixels and share with a prediction. SoilGrids leaves water bodies and some built-up areas without a prediction;
   - `total_stock_Mt` (stock only): sum over predicted pixels of t/ha × 100 ha.
4. **Small communes:** a commune without any pixel centre gets the pixel at its centroid and is flagged `centroid pixel only`. Communes with fewer than 10 predicted pixels are flagged `limited`.

## Quality checks

The checks are recorded in `PROVENANCE.json`:
- for every layer, the national mean equals the pixel-weighted mean of the 69 wilaya means (within 2 %, boundary-pixel effects);
- the 5 % quantile never exceeds the 95 % quantile;
- pH stays within physical bounds.

`tests/python/test_soil_product.py` checks the published tables. The [Learn with AEO tutorial](/docs/tutorial-soil/) recomputes one wilaya directly from the ISRIC file.

## Limitations

- **Uncertainty:** model predictions with wide prediction intervals, especially in the Sahara and on stony or saline soils that are poorly represented in the training data.
- **Texture:** in SoilGrids 2.0 the clay, sand and silt means sum to 100 % (checked: 100.0 % for every wilaya and depth). Texture classes are not derived here.
- **Salinity and water-holding capacity:** not included. SoilGrids 2.0 has no salinity layer, and its water-retention layers were not processed. See the [Data catalog](/data/?domain=soil) for other soil datasets.
- **No rasters redistributed:** AEO does not redistribute SoilGrids rasters. Download them from [ISRIC](https://files.isric.org/soilgrids/latest/) (CC BY 4.0).
