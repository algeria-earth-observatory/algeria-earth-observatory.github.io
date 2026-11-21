---
title: Algeria Standardized Precipitation Index SPI (CHIRPS v3.0) — method
description: How AEO computes SPI-1, 3, 6 and 12 for Algeria, its wilayas and communes from CHIRPS v3.0, how zero-rainfall months are handled, how it was checked against the R reference implementation, and where it should not be used.
section: Scientific practice
order: 22
updated: 2026-11-21
---

This page documents product `aeo-dza-spi-chirps3`, version 1.0.0. The code is in [`scripts/pipelines/spi/`](https://github.com/algeria-earth-observatory/algeria-earth-observatory.github.io/tree/main/scripts/pipelines/spi) and [`scripts/pipelines/aeo/spi.py`](https://github.com/algeria-earth-observatory/algeria-earth-observatory.github.io/blob/main/scripts/pipelines/aeo/spi.py).

## What SPI measures

The **Standardized Precipitation Index** expresses precipitation accumulated over k months as a standard-normal value. Negative values are drier than usual for that time of year, positive values wetter. The WMO recommends it for meteorological drought (Hayes et al. 2011, doi:10.1175/2010BAMS3103.1).

SPI uses precipitation only. It does not see evaporative demand. For the water balance, use [SPEI](/docs/method-spei/).

## Data

The input is the published [AEO precipitation product](/data/aeo-dza-precipitation-chirps3/): monthly area-weighted mean precipitation of each unit, from **CHIRPS v3.0** (Funk et al. 2026, doi:10.1038/s41597-026-07096-4) at 0.05°.

SPI is computed on the **unit-mean series**: the spatial mean is taken first. A wilaya's SPI is the index of its average rainfall, not the average of cell indices.

## Computation

1. **Accumulation:** monthly precipitation is summed over k = 1, 3, 6 and 12 months. The first k − 1 months have no value. A missing month makes the accumulation missing.
2. **Reference:** for each calendar month, the accumulations of **1991–2020** form the reference sample. Let q be the share of zero accumulations in it.
3. **Gamma fit:** a two-parameter gamma distribution G is fitted to the positive reference accumulations.
   - The fit uses unbiased probability-weighted moments (L-moments; Hosking 1990, doi:10.1111/j.2517-6161.1990.tb01775.x).
   - The shape comes from Hosking's rational approximation (`pelgam`), as in the R package SPEI.
4. **Zero rainfall:** the cumulative probability is H(x) = q + (1 − q)·G(x), so H(0) = q.
5. **Index:** SPI = Φ⁻¹(H(x)). Values beyond ±3.09 (p < 0.001 or > 0.999) are clipped.
6. **Not computed:** if fewer than 10 of the 30 reference accumulations of a calendar month are positive, that calendar month has no SPI. The same applies if the L-moments are invalid.

## Validation

- **Reference implementation:** `tests/python/test_spi.py` compares AEO with **R SPEI 1.8.1** `spi()` (Gamma, `ub-pwm`, reference 1991–2020). The comparison uses six wilaya series, from Alger to Adrar, at all four timescales.
  - The values agree to 10⁻⁶ wherever the reference sample of a calendar month has no zero accumulations.
  - *Difference from R SPEI 1.8.1:* that version computes the zero probability, but the line that applies it is overwritten. A zero accumulation therefore gets G(0) = 0 and an SPI of −∞. AEO applies the mixed distribution above instead.
- **Standardisation:** over 1991–2020, SPI-3 has a mean within ±0.03 of 0 and a standard deviation of 0.93–1.04 in every non-arid wilaya and commune. The values are recorded in `PROVENANCE.json`.
- **Not yet done:** no comparison with station-based SPI from the Office National de la Météorologie has been made.

## Arid units

**Flag:** units whose 1991–2020 normal is below 100 mm per year are flagged `arid`. That is 11 wilayas and 93 communes.

**Why it matters:** there, most months have no rain and the gamma fit rests on few values. When q is large, the lowest possible SPI is Φ⁻¹(q), so even a completely dry month is not "extreme". Do not compare SPI values between arid and humid units.

## Files

| File | Content |
|---|---|
| `aeo_spi_monthly_{admin0,admin1}_v1.0.0.csv` / `.parquet` | Monthly precipitation and SPI-1/3/6/12 for every unit |
| `aeo_spi_monthly_admin2_v1.0.0.parquet` | The same for 1,541 communes (also split by wilaya for the download assistant) |
| `aeo_spi_summary_{level}_v1.0.0.csv` | Latest month and the share of months with SPI-12 ≤ −1 over the last ten years |

Every file is listed with its size and SHA-256 in the [manifest](/data/aeo/products/spi/v1.0.0/manifest.json).

## References

- Guttman, N.B. (1999). Accepting the Standardized Precipitation Index: a calculation algorithm. *JAWRA* 35(2), 311–322. doi:10.1111/j.1752-1688.1999.tb03592.x
- Stagge, J.H. et al. (2015). Candidate distributions for climatological drought indices (SPI and SPEI). *International Journal of Climatology* 35, 4027–4040. doi:10.1002/joc.4267
- McKee, T.B., Doesken, N.J. & Kleist, J. (1993). The relationship of drought frequency and duration to time scales. *8th Conference on Applied Climatology*, Anaheim, 179–184 (conference paper; no DOI).
- Full bibliography: [Publications & References](/science/publications/).
