---
title: Algeria drought index SPEI (TerraClimate) — method
description: How AEO computes the Standardised Precipitation–Evapotranspiration Index (SPEI-1, 3, 6, 12) for Algeria, its wilayas and communes from TerraClimate, how it was validated against the R reference implementation, and where it should not be used.
section: Scientific practice
order: 21
updated: 2026-11-20
---

This page documents product `aeo-dza-spei-terraclimate`, version 1.0.0. The code is in [`scripts/pipelines/spei/`](https://github.com/algeria-earth-observatory/algeria-earth-observatory.github.io/tree/main/scripts/pipelines/spei) and [`scripts/pipelines/aeo/spei.py`](https://github.com/algeria-earth-observatory/algeria-earth-observatory.github.io/blob/main/scripts/pipelines/aeo/spei.py).

## Why SPEI, and why AEO computes it

The **SPEI** (Vicente-Serrano et al. 2010) standardises the climatic water balance: precipitation minus reference evapotranspiration (P − PET). It responds to both missing rain and higher evaporative demand, which matters in a warming, semi-arid country.

The widely used global dataset **SPEIbase** has a documented evapotranspiration error in versions 2.6–2.12, largest in arid regions (see the [SPEIbase record](/data/speibase/)). AEO therefore computes SPEI itself from a single, consistent source.

## Data

**TerraClimate** (Abatzoglou et al. 2018, *Scientific Data* 5, 170191, doi:10.1038/sdata.2017.191) provides monthly precipitation and Penman–Monteith reference evapotranspiration (ASCE). It is a 1/30° grid (about 3.7 km), released as CC0 public domain.

AEO reads the yearly files from 1961 onwards over OPeNDAP, for the window 9°W–12.5°E and 18.5–37.5°N. TerraClimate combines a high-resolution climatology with reanalysis anomalies, so it is an *interpolated climate product*. In Algeria it rests on few stations, especially in the south.

## Computation

1. **Water balance:** D = P − PET for each month, in each cell and for each administrative unit.
2. **Unit values:** P and PET are averaged over the unit with the same nested commune weights as the precipitation product (cell fraction × geodesic area). Then D_unit = P_unit − PET_unit, and SPEI is computed on D_unit. A unit's SPEI is therefore the index of its average water balance, not the average of cell indices.
3. **Accumulation:** D is summed over k = 1, 3, 6 and 12 months. The first k − 1 months have no value.
4. **Distribution:**
   - For each calendar month, a three-parameter log-logistic distribution is fitted to the accumulated values of **1991–2020**. The fit uses unbiased probability-weighted moments (L-moments) in Hosking's generalised-logistic form, as in the R package SPEI (fit `ub-pwm`).
   - SPEI = Φ⁻¹(F(x)).
   - Values beyond ±3.09 (p < 0.001 or > 0.999) are clipped.
5. **Grid maps:** SPEI-3 and SPEI-12 are computed for every cell in the same way and drawn as monthly map layers from 1991.

## Validation

- **Reference implementation:** on synthetic water-balance series, the AEO code reproduces the **R package SPEI 1.8.1** (log-logistic, ub-pwm, `ref.start`/`ref.end`) to 2 × 10⁻¹³ at every timescale. The only differences are values beyond ±3.09, which R does not clip. The script is in `tests/validation/spei_vs_r/`.
- **Product tests:** for every wilaya and timescale, SPEI over 1991–2020 has a mean within ±0.1 of 0 and a standard deviation between 0.85 and 1.1.
- **Table checks:** tables are complete, d = P − PET, and checksums match.
- **Plausibility:** national SPEI-12 is most negative in 2020–2024, consistent with the multi-year Maghreb drought of those years. This is not an independent validation. No comparison with Algerian station-based indices has been made yet.

## Reading SPEI

| SPEI | Class (McKee et al. 1993) |
|---|---|
| ≤ −2 | extremely dry |
| −2 to −1.5 | severely dry |
| −1.5 to −1 | moderately dry |
| −1 to 1 | near normal |
| 1 to 1.5 | moderately wet |
| 1.5 to 2 | very wet |
| ≥ 2 | extremely wet |

In the 1991–2020 reference, about 16 % of months fall at or below −1 by construction.

Choose the timescale for the question being asked:
- **SPEI-3** at the end of winter and spring for rainfed cereals;
- **SPEI-6** over the agricultural year;
- **SPEI-12** for annual and multi-year drought.

## Limitations

- **Hyper-arid areas.** Where normal precipitation is below 100 mm/year, P is near zero most months and SPEI reflects **evaporative demand only** (heat), not water-supply drought. This covers 16 wilayas and 121 communes, mostly in the Sahara. They are flagged, and cells below 50 mm/year are shown in sand on maps.
- **Warming signal.** With a fixed 1991–2020 calibration and rising PET, recent years tend towards drier values and early decades towards wetter ones. Several 1960s–1970s years reach the +3.09 cap. This is intended: SPEI is "sensitive to global warming" by design. Do not read it as rainfall change alone.
- **National value.** The national SPEI is dominated by the Saharan wilayas. Use wilaya or commune series for the agricultural north.
- **Communes.** Commune values summarise a few ≈3.7 km cells of an interpolated product. They describe the commune area, not a local observation.
- **Product differences.** SPEI from TerraClimate will differ from SPEI computed from other precipitation or PET products, for example CHIRPS or ERA5-Land. Do not mix sources in one analysis.

## How to cite

> Algeria Earth Observatory (2026). Algeria Drought Index SPEI (TerraClimate), version 1.0.0. https://algeria-earth-observatory.github.io/data/aeo-dza-spei-terraclimate/ — from Abatzoglou et al. (2018), doi:10.1038/sdata.2017.191; method Vicente-Serrano et al. (2010), doi:10.1175/2009JCLI2909.1.

## References

- Abatzoglou, J.T., Dobrowski, S.Z., Parks, S.A. & Hegewisch, K.C. (2018). TerraClimate, a high-resolution global dataset of monthly climate and climatic water balance from 1958–2015. *Scientific Data* 5, 170191.
- Beguería, S., Vicente-Serrano, S.M., Reig, F. & Latorre, B. (2014). Standardized precipitation evapotranspiration index (SPEI) revisited. *International Journal of Climatology* 34, 3001–3023.
- Hosking, J.R.M. (1986). The theory of probability weighted moments. IBM Research Report RC12210.
- McKee, T.B., Doesken, N.J. & Kleist, J. (1993). The relationship of drought frequency and duration to time scales. *8th Conference on Applied Climatology*, 179–184.
- Vicente-Serrano, S.M., Beguería, S. & López-Moreno, J.I. (2010). A multiscalar drought index sensitive to global warming: the SPEI. *Journal of Climate* 23, 1696–1718.
