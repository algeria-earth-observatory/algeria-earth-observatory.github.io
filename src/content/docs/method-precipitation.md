---
title: Algeria precipitation (CHIRPS v3.0) — method
description: How AEO builds its Algeria precipitation product from CHIRPS v3.0 — retrieval, quality control, annual totals, 1991–2020 normals, anomalies, zonal statistics for wilayas and communes, and trend tests.
section: Scientific practice
order: 20
updated: 2026-11-20
---

This page documents product `aeo-dza-precipitation-chirps3`, version 1.0.0. The code is in [`scripts/pipelines/precip/`](https://github.com/algeria-earth-observatory/algeria-earth-observatory.github.io/tree/main/scripts/pipelines/precip). The shared statistics are in [`scripts/pipelines/aeo/stats.py`](https://github.com/algeria-earth-observatory/algeria-earth-observatory.github.io/blob/main/scripts/pipelines/aeo/stats.py), and the browser copy is `src/lib/trend.js`.

## Source

**CHIRPS v3.0** (Climate Hazards Center InfraRed Precipitation with Stations, version 3) is produced by the Climate Hazards Center, University of California, Santa Barbara.
- **Content:** monthly precipitation in millimetres on a 0.05° grid (about 5.5 km), from January 1981 to near-real time. It blends satellite infrared estimates, a station-based climatology and station observations.
- **Version used:** the *final* monthly version, which the provider updates after quality control around the third week of the following month.
- **Data DOI:** 10.15780/G2JQ0P. **Paper:** Funk et al. (2026), *Scientific Data* 13, 718, doi:10.1038/s41597-026-07096-4.
- **Licence:** CC BY 4.0.

Version 3.0 replaced version 2.0 in 2025. v2.0 production ends after December 2026. Version 3.0 corrects gauge observations for undercatch, so it is generally wetter than v2.0. **Do not mix the two versions in one series.**

## Processing steps

1. **Retrieval.** For each month, only the window 9.0°W–12.5°E, 18.5°N–37.5°N (430 × 380 cells) is read from the provider's global Cloud Optimized GeoTIFF, using HTTP range requests. The file's Last-Modified date is recorded, because the provider can revise final data. Sea and out-of-domain cells (−9999 in the source, not declared as no-data) are set to missing.
2. **Quality control.** The pipeline stops if a month is missing or a value is negative. It records the maximum value and checks that the valid-cell mask is the same in every month. The results are in `PROVENANCE.json`.
3. **Annual totals.** The calendar-year total is the sum of the 12 monthly values. Only complete years are published, so the current year appears in the monthly data only.
4. **Normals and anomalies.**
   - The reference period is **1991–2020**, the current WMO standard normal.
   - Anomaly (mm) = value − normal.
   - Relative anomaly (%) = 100 × (value − normal) / normal. It is not computed where the normal is below 1 mm, as in parts of the central Sahara.
   - Monthly anomalies use the 1991–2020 mean of the same calendar month.
5. **Zonal statistics.**
   - The value for an administrative unit is the **area-weighted mean depth** (mm) over the unit.
   - Each CHIRPS cell is weighted by the fraction of it inside the unit, times its geodesic area on the WGS84 authalic sphere.
   - Fractions are computed by rasterising boundaries on a grid 10 × 10 times finer (cell centres).
   - Communes smaller than one sub-cell use the cell containing a representative point.
   - Cells with no data are excluded, and the remaining weights are renormalised. The valid-area percentage is reported for every value.
   - Wilaya and national weights are the union of their communes' weights, so the levels nest exactly. The national mean equals the area-weighted mean of the 69 wilaya means. This is checked at every build.
6. **Trends** (precomputed for the full period; recomputed in the browser for any selected period):
   - **Theil–Sen slope:** the median of all pairwise slopes, with Sen's 95 % confidence interval (Gilbert 1987).
   - **Mann–Kendall test:** two-sided, with tie correction, on at least 8 values.
   - **Autocorrelation:** if the lag-1 autocorrelation of the detrended series is significant at 5 % (|r₁| > 1.96/√n), the variance of S is multiplied by 1 + 2 Σ (1 − k/n) r₁ᵏ (Yue & Wang 2004).
   - **Reporting:** a trend is called significant only when p < 0.05.
   - **Missing years** are skipped and never interpolated.
7. **Exports.** Files are listed in `manifest.json` with size and SHA-256. The build stops if any file does not match.
   - **Rasters:** Cloud Optimized GeoTIFFs for Algeria and for each wilaya, in EPSG:4326, with cells outside the unit set to −9999.
   - **Tables:** CSV and Parquet, at national, wilaya and commune level.
   - **Website:** compact JSON files, plus Web Mercator PNG images for the maps (display only).

## Seasons and periods in Analyze

[Analyze](/analyze/) sums the published monthly unit means:
- **Agricultural year:** September of the previous year to August.
- **Seasons:** autumn SON, winter DJF (December of the previous year), spring MAM, summer JJA.
- **Single months.**

Because a weighted mean is linear, the sum of monthly means equals the unit mean of the seasonal total. The only difference is rounding (values are published to 0.1 mm). Normals for these periods use key years 1991–2020.

## What commune values mean

At 0.05°, one CHIRPS cell covers about 28–31 km² in northern Algeria. Many communes in the Tell are smaller than that or cover only a few cells. AEO publishes commune statistics with a **support** class, based on the effective number of cells (the sum of the cell fractions inside the commune):

| Support | Effective cells | Meaning |
|---|---|---|
| adequate | ≥ 4 | The mean summarises several independent cells. |
| limited | 1–4 | The value is close to that of one or two cells. |
| very limited | < 1 | The commune is smaller than a cell; the value describes the surrounding cell. |

A commune value is a description of the commune area at the resolution of the source. It is **not** a local measurement, and it cannot resolve differences between neighbouring small communes. Spatial subsets (GeoTIFF) are published for Algeria and for each wilaya, but not for communes.

## Quality checks (automated)

Run by `tests/python/test_precip_product.py` on the published files, and by the build:
- national coverage of the grid and of the commune weights;
- CRS, resolution and no-data value of every GeoTIFF;
- complete annual and monthly series;
- units and plausible value ranges;
- national mean equals the area-weighted mean of wilaya means;
- annual totals equal the sum of the monthly values;
- every manifest file exists with the recorded size and SHA-256.

## Known limitations

- **Satellite–gauge estimate.** There are few gauges in the Sahara and in the high plateaus. Short, intense convective events and orographic rainfall in the Tell and Atlas are uncertain. Snow is not separated from rain.
- **Dry-region anomalies.** Relative anomalies are very unstable where the normal is tens of millimetres or less. Read them as "a few millimetres more or less", not as a large percentage change.
- **National means** are dominated by the large, dry southern wilayas. The national mean is not representative of the agricultural north.
- **Trends** over about 45 years are sensitive to the period chosen and to multi-year drought sequences. Changes in the station network used by CHIRPS can also affect them. A non-significant result does not show there is no change.
- **Boundaries** come from OpenStreetMap (AEO version 2026-11-20). See [boundary method](/docs/boundaries/).

## How to cite

> Algeria Earth Observatory (2026). Algeria Precipitation (CHIRPS v3.0), version 1.0.0. https://algeria-earth-observatory.github.io/data/aeo-dza-precipitation-chirps3/ — derived from: Climate Hazards Center (2025), CHIRPS v3.0, doi:10.15780/G2JQ0P, and Funk et al. (2026), doi:10.1038/s41597-026-07096-4.

## References

- Funk, C. et al. (2026). The Climate Hazards Center Infrared Precipitation with Stations, Version 3. *Scientific Data* 13, 718. doi:10.1038/s41597-026-07096-4
- Gilbert, R. O. (1987). *Statistical Methods for Environmental Pollution Monitoring.* Van Nostrand Reinhold.
- Sen, P. K. (1968). Estimates of the regression coefficient based on Kendall's tau. *JASA* 63, 1379–1389.
- Yue, S. & Wang, C. (2004). The Mann–Kendall test modified by effective sample size to detect trend in serially correlated hydrological series. *Water Resources Management* 18, 201–218.
