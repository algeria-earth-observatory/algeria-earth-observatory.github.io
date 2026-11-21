---
title: "Tutorial (Python): calculating SPI for a wilaya"
description: Compute the Standardized Precipitation Index over 3 months for one wilaya from AEO monthly precipitation, with a gamma distribution fitted on 1991–2020, and reproduce the AEO SPI product.
section: Tutorials
order: 92
updated: 2026-11-21
---

## Scientific objective

The **Standardized Precipitation Index (SPI)** expresses how unusual the rainfall of the last k months is for that time of year. In this tutorial you compute SPI-3 for one wilaya:
- the precipitation is accumulated over 3 months;
- a gamma distribution is fitted per calendar month on 1991–2020;
- the fitted probabilities are converted to a standard-normal value.

You then check that you reproduce the published [AEO SPI product](/data/aeo-dza-spi-chirps3/).

## Data sources

- **AEO precipitation product** ([record](/data/aeo-dza-precipitation-chirps3/)). File: `aeo_precip_monthly_admin1_v1.0.0.parquet`. It holds the monthly area-mean precipitation of each wilaya from CHIRPS v3.0, 1981 onwards.
- **AEO SPI product**, used for the comparison. File: `aeo_spi_monthly_admin1_v1.0.0.parquet`.

Both files are about 0.1 MB.

## Dependencies

Python 3.10 or later, with `numpy`, `pandas`, `pyarrow` and `scipy`:

```bash
pip install numpy pandas pyarrow scipy
```

## Code

The script is [`scripts/tutorials/spi_wilaya.py`](https://github.com/algeria-earth-observatory/algeria-earth-observatory.github.io/blob/main/scripts/tutorials/spi_wilaya.py). Its core:

```python
acc = precip.rolling(3).sum()                      # 3-month totals
for each calendar month m:
    ref = acc[month == m and 1991 <= year <= 2020]
    q = share of ref equal to 0                    # probability of a dry accumulation
    a, b = gamma_lmoments(ref[ref > 0])            # shape, scale from L-moments
    H = q + (1 - q) * gamma.cdf(acc, a, scale=b)   # mixed distribution for zeros
    SPI = norm.ppf(H)                              # standard-normal value, clipped to ±3.09
```

Run it for Sétif (wilaya 19):

```bash
python spi_wilaya.py 19
```

## Output (run on 21 November 2026)

```text
Sétif (wilaya 19): 548 months; largest difference from the AEO product: 0.0005 (AEO values are rounded to 0.001)
Latest SPI-3 (2026-10): -2.43
Months with SPI-3 <= -1 since 2015: 44
```

The tutorial reproduces the product to its rounding. The same holds for Alger (16) and Oran (31). A test, `tests/python/test_spi.py`, compares the AEO code itself with the R package SPEI.

## Interpretation

- An SPI-3 of −2.43 means the three months up to October 2026 were extremely dry for that season. Such a value is expected less than once in a hundred years under 1991–2020 conditions.
- Read SPI with its timescale:
  - SPI-3 follows the agricultural season;
  - SPI-12 shows multi-year drought.
- About 16 % of months are expected at or below −1 in the reference period, so a count well above that, as here since 2015, indicates a drier recent climate.

## Limitations

- **Rainfall only.** SPI ignores evaporative demand; heat-driven drought is invisible. Compare with [SPEI](/docs/tutorial-spei-r/).
- **Area means.** The index is computed on the wilaya's average rainfall. Local drought inside a large wilaya can be stronger or weaker.
- **Arid areas.** Where the normal is below 100 mm per year, many calendar months have too few rainy values to fit, and SPI is unstable. See the [method](/docs/method-spi/).
- **Reference period.** Changing 1991–2020 changes every value.
