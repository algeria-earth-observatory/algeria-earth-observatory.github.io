---
title: "Tutorial (R): calculating SPEI for a wilaya"
description: Recompute SPEI-12 for one wilaya with the R package SPEI from the published AEO water balance (TerraClimate P − PET) and compare it with the AEO SPEI product.
section: Tutorials
order: 93
updated: 2026-11-21
---

## Scientific objective

The **Standardized Precipitation–Evapotranspiration Index (SPEI)** standardises the climatic water balance D = P − PET. It responds to missing rain and to higher evaporative demand.

In this tutorial you fit the log-logistic distribution on 1991–2020 with the reference implementation, the R package **SPEI** (Beguería & Vicente-Serrano), and check the values published by AEO.

## Data sources

**AEO SPEI product** ([record](/data/aeo-dza-spei-terraclimate/)). File: `aeo_spei_monthly_admin1_v1.0.0.csv`, about 3.4 MB. For every wilaya and month from 1961 it gives:
- precipitation `p_mm`;
- reference evapotranspiration `pet_mm`;
- the water balance `d_mm`;
- SPEI at 1, 3, 6 and 12 months.

These are area means of TerraClimate (Abatzoglou et al. 2018).

## Dependencies

R 4.x with the SPEI package:

```r
install.packages("SPEI")
```

## Code

The script is [`scripts/tutorials/spei_wilaya.R`](https://github.com/algeria-earth-observatory/algeria-earth-observatory.github.io/blob/main/scripts/tutorials/spei_wilaya.R):

```r
balance <- ts(w$d_mm, start = c(w$year[1], w$month[1]), frequency = 12)
fit <- SPEI::spei(balance, 12, distribution = "log-Logistic", fit = "ub-pwm",
                  ref.start = c(1991, 1), ref.end = c(2020, 12))
```

Run it for Sétif:

```bash
Rscript spei_wilaya.R 19
```

## Output (run on 21 November 2026, R 4.6.2, SPEI 1.8.1)

```text
Wilaya 19: 762 months compared; largest difference from the AEO product: 0.0027
Latest SPEI-12 (2025-12): -0.36
Months with SPEI-12 <= -1 since 2015: 68
```

The small differences come from rounding: the published water balance `d_mm` has one decimal, while AEO computed SPEI from the unrounded values. On unrounded synthetic series the AEO code matches R to 2 × 10⁻¹³ (see the [method](/docs/method-spei/)).

## Interpretation

- **The latest value.** SPEI-12 of −0.36 in December 2025 is in the normal range (−1 to 1). Nationally, SPEI-12 was lowest in 2020–2024; plot `w$spei_12` to see how Sétif followed that drought.
- **Frequency of dry months.** The count of months at or below −1 since 2015 (68 of 132) is far above the roughly 16 % expected under 1991–2020 conditions.

## Limitations

- **Interpolated data.** TerraClimate is an interpolated climate product with few stations in Algeria, especially in the south.
- **Hyper-arid areas.** In hyper-arid wilayas SPEI mostly reflects evaporative demand (heat), not rainfall.
- **Area means.** Wilaya means hide differences between the Tell and the steppe within one wilaya.
