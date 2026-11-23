# Implementation report — water, cropland and climate (2026-11-22)

Branch `water-climate`. This round added evapotranspiration, soil moisture, water storage, reservoirs, a verified seasonal outlook restricted to stable cropland, climate-hazard projections, documented map palettes, terrain-shaded maps and a monthly automatic update.

## New AEO products

| Product | Source | Coverage | Key result |
|---|---|---|---|
| **Stable cropland** (`aeo-dza-stable-cropland-gaced30`) | GACED30 v1, 30 m, 2000–2024 | Algeria, 69 wilayas, 1,541 communes | Stable cropland (cropland in ≥ 20 of 25 years): **6.40 Mha**. Cropland in any year: 12.98 Mha. In most years: 8.35 Mha. |
| **Evapotranspiration and soil moisture** (`aeo-dza-et-soil-moisture-wapor3`) | FAO WaPOR v3 L1 (open COGs) | monthly 2018-01 → 2026-10; all land and stable cropland | Departures from the 2018–2025 mean |
| **Water storage** (`aeo-dza-water-storage-grace`) | Downscaled GRACE/GRACE-FO (Li & Kusche 2026, 0.25°) | monthly 2002-04 → 2025-03; Algeria and wilayas | Algeria **−0.25 cm/yr** (95 % −0.26 to −0.23), Mann–Kendall p < 0.0001 |
| **Reservoir monitor** (`aeo-dza-reservoirs-deafrica`) | DE Africa Waterbodies (Landsat) + Global Dam Watch | 63 of 65 reservoirs ≥ 0.5 km², 1984 → Nov 2026 | Median reservoir at 68 % of its largest observed area; 20 below half |
| **Seasonal outlook, experimental** (`aeo-dza-seasonal-outlook-nmme`) | NMME (NOAA CPC) + CHIRPS v3.0, over stable cropland | 45 wilayas; hindcasts 1991–2021; issue 2026-11-01 | 17 % of 3,036 combinations skilful (5 % expected by chance). Published: 15 wilayas, Dec 2026 – Feb 2027, all leaning below normal (56–80 %). |
| **Climate projections** (`aeo-dza-climate-projections-nexgddp`) | NASA NEX-GDDP-CMIP6, 8 models, SSP2-4.5 / SSP5-8.5 | Algeria and wilayas, all land and stable cropland | Cropland Nov–Apr rain −18 % (2041–70, SSP2-4.5), 8/8 models |

Every product has:
- a manifest with SHA-256 checksums;
- PROVENANCE.json;
- CSV and Parquet tables;
- a catalog record;
- a method page;
- regional statistics in the Explore inspector, with CSV download.

### Climate projections (8-model median, lowest to highest model)

| | SSP2-4.5, 2041–2070 | SSP5-8.5, 2071–2100 |
|---|---|---|
| Mean daily maximum temperature, Algeria | +2.2 °C (+1.8 to +2.8) | +5.4 °C (+4.3 to +6.5) |
| Days above 40 °C, Algeria | +40 (+29 to +45) | +82 (+68 to +92) |
| November–April rainfall, stable cropland | −18 % (−21 to −9), 8/8 models | −37 % (−53 to −20), 8/8 models |
| Longest dry spell, stable cropland | +9 days | +22 days |

- **Rainfall on cropland:** in each of the 46 wilayas with at least 10,000 ha of stable cropland, at least 7 of 8 models project a drier cereal season.
- **Rainfall nationally:** the range of annual precipitation change for Algeria crosses zero.

### Choices that matter

- **Stable cropland mask.** It is built from GACED30, a public dataset. The user's own research cropland mask was **not** used, because that research is unpublished.
- **Seasonal outlook rules.** An outlook is published only where the forecast passes leave-one-year-out verification (RPSS > 0, ROC > 0.5, p < 0.05) **and** field significance: at least 20 % of wilayas for that start month and lead, and a lead of 3 months or less. Everywhere else the outlook is "equal chances". Without the field rule, about 5 % of the 3,036 combinations would pass by chance.
- **Units fix.** The WaPOR catalogue labels relative soil moisture "%" with scale 0.001, but the scaled values are fractions. AEO converts them to percent. A test fails if the values look like fractions.
- **Reservoirs.** Values are **surface areas**, not volumes. They are never presented as ANBT filling rates. GDW polygons are not redistributed, at the GDW authors' request.
- **Water storage.** GRACE resolves about 300 km, and only 9 wilayas are large enough. Other wilayas are flagged, and communes are not published.

## External records (8 new, all verified)

1. NMME seasonal forecasts.
2. NASA GLDAS-2.2 CLSM GRACE-DA.
3. GRACE-DA-DM Global v3.
4. Li & Kusche downscaled GRACE.
5. GFZ Uz et al. downscaled TWSA.
6. SYSU TWSA v1.0.
7. DE Africa Waterbodies.
8. JRC ASAP warnings.

For each:
- every DOI was checked against doi.org, Crossref or DataCite;
- links were fetched;
- unconfirmed fields are listed in `verification.unverified_fields`.

The catalog now holds 74 records.

## Site

- **Navigation:** Explore | Data | Drought | **Water** | **Climate** | Science | Contribute | About.
- **Homepage:** an **"Algeria now"** strip with the latest value of each monitoring product and the month it describes:
  - SPI-3;
  - soil moisture on cropland;
  - reservoirs;
  - seasonal outlook;
  - GRACE trend.
- **Explore:** new layers:
  - ET;
  - soil moisture;
  - stable cropland;
  - water storage;
  - CMIP6 changes (5 indicators × 4 scenario-periods);
  - seasonal outlook (choropleth, grey where not skilful).

  The inspector gives values for all land and for stable cropland, the model range for projections, and the verification scores for the outlook. A ▶ button animates the last 24 months of monthly layers.
- **Drought:** a "Cropland conditions" section (WaPOR on stable cropland), the verified outlook table, and a start-month × lead skill grid.
- **Water:**
  - a reservoir map and table with 36-month sparklines;
  - the national GRACE series and trends;
  - ET on cropland compared with all land.
- **Climate:** indicator, scenario/period and area choices; a national summary; and a table of all wilayas with the median, model range and agreement.
- **Palettes now follow documented sources:**
  - SPEI/SPI: ColorBrewer RdBu-7, as documented by the Copernicus Global Drought Observatory;
  - precipitation: YlGnBu;
  - precipitation anomaly: BrBG;
  - ET: GnBu, the WaPOR colour family;
  - soil moisture: BrBG;
  - water storage: RdBu;
  - warming: OrRd;
  - stable cropland: YlOrBr;
  - reservoirs: Blues.

  931 existing overlay images were recoloured by exact class swap; no class changed.
- **Terrain shading:** faint ASTER GDEM relief is drawn above the data overlays, so mountains read through the colours.

## "Live" updates

`.github/workflows/update-monthly.yml` runs on the 14th of each month, or by hand. It rebuilds:
- precipitation and SPI (CHIRPS v3.0);
- WaPOR ET and soil moisture;
- the reservoir monitor;
- the NMME outlook.

Calibration uses the saved CHIRPS cropland series; a test confirmed that this gives results identical to a full rebuild.

The workflow then:
1. regenerates the catalog records and checksums;
2. runs every test and the site build;
3. commits to `main` only if all pass;
4. starts the deployment, which runs the browser tests again.

It takes effect only once this branch is merged. It has not yet run on GitHub.

## Tests

- **Python:**
  - `tests/python/test_water_climate_products.py`: manifest checksums;
  - cropland nesting and grid totals;
  - WaPOR ranges and the cropland threshold;
  - GRACE trend intervals and the resolution flag;
  - the outlook publication rule;
  - reservoirs: area only, nothing before dam construction, points only;
  - projections: ensemble ordering, every model warms, SSP5-8.5 above SSP2-4.5.
- **Playwright (`tests/e2e/water-climate.spec.ts`):** Explore values equal the files; the outlook shows equal chances where there is no skill; the Drought table equals the published outlooks; the Water table equals the product and never says "filling rate"; the Climate summary equals the file; the "Algeria now" cards are dated.
- **Accessibility:** axe now covers `/water/` and `/climate/`.

## Proposed additions (from a survey of comparable platforms)

Ranked. Platforms surveyed:
- Digital Earth Africa;
- Copernicus EDO/GDO;
- JRC ASAP and OSS GuetCrop;
- GEOGLAM Crop Monitor;
- UCSB CHC (EWX);
- World Bank CCKP;
- Copernicus Climate Atlas;
- FAO WaPOR;
- NASA Worldview;
- Climate Reanalyzer;
- ACMAD/PRESANORD;
- IRI.

1. **JRC ASAP crop warnings mirror.** Dekadal warnings for Algeria since 2001 (48 old wilayas), open; needs a 48→69 crosswalk.
2. **15-day rainfall outlook (CHIRPS-GEFS).** Open and daily; AEO would score it against CHIRPS before showing it.
3. **Season-to-date rainfall chart.** Cumulative rainfall since 1 September against the 1991–2020 percentile bands, per wilaya (Climate Reanalyzer style).
4. **Reservoir volumes.** From GRDL area–storage curves (47 of 50 GRanD dams covered). Compare the summed storage with ANBT's published national filling rates.
5. **Embeddable widgets and a static JSON API.** One file per wilaya and indicator, carrying source, date and licence.
6. **Wildfire hotspots in summer.** NASA FIRMS, with a free key stored as a secret, gas flares masked.
7. **Indicator factsheets.** One page each (EDO style): method, latency, strengths, weaknesses.
8. **Monthly drought note.** Archive plus RSS or e-mail digest, quoting sources and avoiding impact claims.
9. **Swipe and compare** two dates in Explore.

## Not done / limits

- **Seasonal outlook:** a single system (NMME ensemble mean, CPC CPT files). C3S needs a CDS account. Not compared with ONM stations.
- **Soil moisture before 2018:** none. ESA CCI (1978–2024, open) could give a long baseline; not yet processed.
- **Climate exposure:** population and assets exposed to the projected hazards are not computed. "Risk" also needs vulnerability data, which AEO does not have.
- **French and Arabic:** the new pages are not yet translated.
- **Manual screen-reader testing:** still pending.
