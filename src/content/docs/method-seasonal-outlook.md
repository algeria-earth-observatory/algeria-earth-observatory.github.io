---
title: Seasonal rainfall outlook over stable cropland (experimental) — method and verification
description: How AEO tests the NMME seasonal forecasts against 31 years of observed rainfall over Algeria's stable cropland, how outlooks are calibrated, and why most outlooks are "equal chances".
section: Scientific practice
order: 28
updated: 2026-11-22
---

This page documents product `aeo-dza-seasonal-outlook-nmme`, version 0.1.0, status **experimental**. The code is in [`scripts/pipelines/outlook/`](https://github.com/algeria-earth-observatory/algeria-earth-observatory.github.io/tree/main/scripts/pipelines/outlook).

**This is a test, not an official forecast.** Official seasonal forecasts for Algeria are the responsibility of the Office National de la Météorologie.

## The question

Can a seasonal forecast say, one to six months ahead, whether rainfall over a wilaya's **stable cropland** will be below, near or above normal, and do so **better than climatology** (33 % / 33 % / 33 %)?

The answer is measured first. An outlook is shown only where the measured answer is yes.

## Data

- **Forecasts:** the NMME (North American Multi-Model Ensemble; Kirtman et al. 2014, doi:[10.1175/BAMS-D-12-00050.1](https://doi.org/10.1175/BAMS-D-12-00050.1)) multi-model ensemble mean of 3-month precipitation, on a 1° grid.
  - Source: the open files of NOAA's Climate Prediction Center (<https://ftp.cpc.ncep.noaa.gov/International/nmme/>), in CPT format.
  - **Hindcasts:** forecasts re-run for past years, 1991–2021, for 12 start months and 6 leads.
  - **Current forecast:** the latest issue.
  - Every file and its SHA-256 are listed in the product's PROVENANCE.json.
- **Observations:** CHIRPS v3.0 monthly precipitation, 0.05° (Funk et al. 2026).
- **Where:** the AEO [stable cropland](/docs/method-stable-cropland/) of each wilaya with at least 10,000 ha of it (45 wilayas), and all of Algeria's stable cropland.
  - Forecast cells are weighted by their stable-cropland area on the 1° grid, observations on the 0.05° grid.
  - The other 24 wilayas are not assessed: too little cropland for a 1° forecast.

## Calibration and verification

For each wilaya, start month and lead (3,036 combinations):

1. **Pairs:** x = forecast seasonal precipitation over the stable cropland; y = observed CHIRPS seasonal total over the same cropland, for each hindcast year.
2. **Leave one year out:** for each year, a linear regression y = a + b·x is fitted on the **other** years. If b ≤ 0 the forecast is not credible and the climatological forecast is used.
   - The predicted ŷ and the residual standard deviation s give tercile probabilities P(below) = Φ((q₁ − ŷ)/s) and P(above) = 1 − Φ((q₂ − ŷ)/s).
   - q₁ and q₂ are the other years' observed terciles.
   - The year being forecast never informs its own forecast.
3. **Scores against what happened:**
   - **RPSS**, the ranked probability skill score against equal chances (> 0 means better than climatology);
   - the **ROC area** for below-normal seasons (> 0.5 means it discriminates dry seasons);
   - Pearson **r** of forecast and observation, with a one-sided p-value.
4. **Local skill:** RPSS > 0, ROC area > 0.5 and p < 0.05.
5. **Field significance:** with 3,036 tests, about 5 % pass by chance. A start month and lead is usable only when at least **20 %** of the wilayas pass (four times the chance rate) and the lead is **three months or less**.

An outlook is published for a wilaya only if both rules hold. Everywhere else the published outlook is **equal chances**, and the uncalibrated model signal is given for transparency.

## Results of the verification

| Lead | Locally skilful |
|---|---|
| 1 month | 29 % |
| 2 months | 22 % |
| 3 months | 22 % |
| 4 months | 16 % |
| 5 months | 7 % |
| 6 months | 6 % |

- **Overall:** 17 % of the combinations are locally skilful, against about 5 % expected by chance. Skill falls with lead time; at 5–6 months it is no better than chance.
- **Start months with skill:** mainly forecasts started in **March, May, July, September and November**, one to three months ahead. The strongest is July for August–October: 87 % of wilayas pass.
- **Start months without skill:** forecasts started in **October, December and January** show almost none.
- **Algeria as a whole:** the RPSS of all stable cropland together is small (at most 0.29). National averages mix regions with different signals.

The full verification table (`aeo_outlook_verification_admin1`) gives the scores for every wilaya, start month and lead.

## Outlook issued on 1 November 2026

- **Published outlooks:** 15 wilayas pass both rules, all for **December 2026 – February 2027**: Annaba, Béjaïa, Biskra, Bordj Bou Arreridj, Bouira, Boumerdès, Constantine, El Tarf, Jijel, M'Sila, Médéa, Mila, Sétif, Skikda and Tizi Ouzou.
  - In all of them, **below-normal** rainfall over stable cropland is more likely than normal or above normal: 56–80 % chance of the lowest third of 1991–2021.
- **Everywhere else:** every other wilaya, and all later seasons, are **equal chances**.

Read this as: in past years, when the November NMME forecast looked like this one, winters in these wilayas were more often dry than not. It is not a prediction of a specific amount of rain.

## Limitations

- **Short record:** 31 years of hindcasts leave the skill estimates themselves uncertain. Some "skilful" combinations remain chance results even after the field rule.
- **Ensemble mean only:** the CPC files give the ensemble mean, not the members, so the spread of the forecast comes from the hindcast errors, not from the ensemble.
- **Coarse grid:** a 1° grid cannot separate the coastal Tell from the inland high plains within one cell.
- **Observations:** rainfall observations are CHIRPS v3.0, itself an estimate. Comparison with ONM stations has not been made.
- **Single source:** other systems (Copernicus C3S, IRI calibrated forecasts, ACMAD/PRESANORD regional outlooks) may perform differently and have not been tested here.
