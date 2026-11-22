---
title: Climate hazard projections (NEX-GDDP-CMIP6) — method
description: How AEO computes projected changes in heat, rainfall and dry spells for Algeria and its wilayas, over all land and over stable cropland, from 8 bias-corrected CMIP6 models, and how to read the model range.
section: Scientific practice
order: 31
updated: 2026-11-22
---

This page documents product `aeo-dza-climate-projections-nexgddp`, version 1.0.0. The code is in [`scripts/pipelines/cmip6/`](https://github.com/algeria-earth-observatory/algeria-earth-observatory.github.io/tree/main/scripts/pipelines/cmip6).

## Projections, not forecasts

A projection describes the climate of a 30-year period under an assumed path of greenhouse-gas emissions. It does not say what any particular year will be like. AEO uses two scenarios:

- **SSP2-4.5:** intermediate emissions;
- **SSP5-8.5:** very high emissions.

They are compared over two periods, **2041–2070** and **2071–2100**, each against **1985–2014**.

## Data

- **Climate models:** NASA **NEX-GDDP-CMIP6** (Thrasher et al. 2022, *Scientific Data* 9, 262, doi:[10.1038/s41597-022-01393-4](https://doi.org/10.1038/s41597-022-01393-4)).
  - Content: daily CMIP6 model output, bias-corrected and statistically downscaled to 0.25° against the GMFD observational dataset.
  - Variables used: daily maximum temperature (`tasmax`) and precipitation (`pr`).
  - Access: subset to Algeria on NASA's NCCS THREDDS server. For each year, the newest file version is used; the list is in PROVENANCE.json.
- **Models (8):** ACCESS-CM2, EC-Earth3, GFDL-ESM4, IPSL-CM6A-LR, MIROC6, MPI-ESM1-2-HR, MRI-ESM2-0 and NorESM2-LM, the first realisation of each. They span low-, middle- and high-sensitivity models. They are not the whole CMIP6 ensemble.
- **Areas:** the AEO [stable-cropland mask](/docs/method-stable-cropland/) and boundaries.

## Indicators

Computed for every model, year and 0.25° cell:

| Indicator | Definition |
|---|---|
| Mean daily maximum temperature | annual mean of Tmax (°C) |
| Days above 35 °C / 40 °C | days per year with Tmax above the threshold |
| Days above 32 °C in March–May | spring hot days, during flowering and grain filling of rain-fed cereals |
| Annual precipitation | mm per year |
| November–April precipitation | the cereal season (season ending in the calendar year) |
| Longest dry spell | longest run of days with less than 1 mm |

Thresholds of 32, 35 and 40 °C are simple indicators of heat. They are not crop-specific damage thresholds.

## Computation

1. **Period means:** each indicator is averaged over each 30-year period, for each model and cell.
2. **Unit values:** area-weighted means over each wilaya and Algeria. The **stable cropland** versions weight each cell by its stable-cropland area; they are left empty where a wilaya has less than 10,000 ha of stable cropland.
3. **Change:** each model's future value minus its **own** 1985–2014 value. Temperatures and days are absolute changes; precipitation is a percentage. Comparing each model with itself removes most of its remaining bias.
4. **Ensemble summary:** median, lowest and highest model, and the number of models (of 8) that agree with the median on the sign of the change.

## How to read it

- **Start with the median:** it is the best single estimate from these models.
- **Then read the range:** when it crosses zero (for rainfall), the models disagree on the direction of change.
- **Agreement:** "8 of 8 models agree" is a much stronger statement than "5 of 8".
- **Size of the range:** it reflects model disagreement only. It does not include downscaling error, other scenarios or other models.

## Results (8-model median, with the lowest and highest model)

| | SSP2-4.5, 2041–2070 | SSP5-8.5, 2071–2100 |
|---|---|---|
| Mean daily maximum temperature, Algeria | +2.2 °C (+1.8 to +2.8) | +5.4 °C (+4.3 to +6.5) |
| Days above 40 °C, Algeria | +40 days (+29 to +45) | +82 days (+68 to +92) |
| Annual precipitation, Algeria | −6 % (−24 to 0) | −24 % (−40 to +26) |
| November–April precipitation, stable cropland | **−18 % (−21 to −9), 8 of 8 models** | **−37 % (−53 to −20), 8 of 8 models** |
| Longest dry spell, stable cropland | +9 days (+3 to +21) | +22 days (+11 to +37) |
| Days above 32 °C in March–May, stable cropland | +2.4 days (baseline 0.9) | +10.6 days |

- **Warming:** every model warms every wilaya.
- **Rainfall on cropland:** where the cereals grow, all 8 models agree that the November–April season becomes drier. In each of the 46 wilayas with at least 10,000 ha of stable cropland, at least 7 of 8 models agree.
- **Rainfall nationally:** for Algeria as a whole, dominated by the Sahara, the range of annual precipitation change crosses zero.

## Limitations

- **Resolution:** 0.25° statistical downscaling does not represent the relief of the Tell Atlas or of the Aurès in detail. Coastal and mountain wilayas are the least reliable.
- **Bias correction:** it is made against a global observational dataset with few Algerian stations, especially in the south.
- **Rainfall:** projections of North African rainfall differ strongly between models.
- **Ensemble size:** 8 models out of the more than 30 in NEX-GDDP-CMIP6.
