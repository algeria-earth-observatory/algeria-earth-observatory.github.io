# Implementation report — scientific gateway (2026-11-21)

Branch `science-gateway`. This report lists what was built in response to the brief "Scientific Observatory, Open Data Infrastructure and Accessible Environmental Atlas", how it was checked, and what scientific work remains.

## Completed

### Navigation and pages
- **Navigation:** Explore | Data | Drought | Science | Contribute | About.
- **Redirects:** `/analyze/` now redirects (with its query string) to `/drought/`, and `/data/sources/` redirects to the external section of `/data/`.
- **Homepage, in the brief's order:**
  1. identity and mission, with **Explore Algeria** and **Browse Data**;
  2. a large interactive map of Algeria on a light basemap, with a non-map wilaya selector and a table of values;
  3. the five environmental domains, each with links to a map and its datasets;
  4. data discovery, with counts computed from the catalog;
  5. science and methods;
  6. community.
- **About:** the brief's mission statement, and a project-status section stating that AEO is not an official observatory, a consortium or a forecasting authority.

### Explore (the central experience)
- **Map:** light basemap (OpenFreeMap Positron with faint ASTER GDEM relief); the dark basemap is removed. The outside-Algeria mask is limestone, not black.
- **Overlay colours:** the 930 precipitation and SPEI images were recoloured class by class for light maps (exact colour swap, no class changed). Hyper-arid SPEI cells now have a hatch pattern, so they don't rely on colour alone.
- **Layout:** three areas — data selection on the left (place search, domain, one indicator at a time, period or depth), the map, and the **RegionInspector** beside the map once a place is selected. On mobile they stack: place, map, statistics.
- **Selecting a place:** click a wilaya or search it (accent-insensitive, codes, Arabic names). With "show communes" on, click a commune. The selection is kept when the indicator or period changes, and is in the URL.
- **RegionInspector** (`src/scripts/region-inspector.ts`), one component for every domain:
  - **Output:** region, indicator, value with units and period, comparison (normal, anomaly, trend or drought frequency; prediction range for soil), a chart with a table equivalent, source and resolution, **Download CSV** (the shared regional-extraction code), and links to the method and the Drought page.
  - **Indicators without AEO statistics** show "Available from external source — regional statistics not yet processed by AEO.", a link to the source, and no number.
  - **Aggregations differ by variable:**
    - precipitation: area-weighted mean of the 0.05° cells;
    - SPI and SPEI: index of the area-mean series;
    - soil: equal-area mean of the predictions, with the prediction range. A concentration is never presented as a stock.

### New Algeria-ready products
- **SPI-1/3/6/12 from CHIRPS v3.0** (`aeo-dza-spi-chirps3`, for Algeria, 69 wilayas and 1,541 communes, 1981-01 to 2026-10):
  - Method: gamma fitted with unbiased PWMs, the mixed distribution H = q + (1 − q)G for zeros, reference period 1991–2020.
  - Validated against **R SPEI 1.8.1** to 10⁻⁶ where the methods coincide.
  - A defect in R SPEI 1.8.1 was found and documented: `spi()` does not apply the probability of zero rainfall.
  - Shown as a wilaya choropleth in Explore, and as a variable in the Drought workspace.
- **Soil properties from SoilGrids 2.0** (`aeo-dza-soil-soilgrids`):
  - Content: SOC, pH, clay, sand, silt, bulk density, CEC, nitrogen and coarse fragments at 0–5, 5–15 and 15–30 cm, plus the 0–30 cm organic carbon stock.
  - Computed in the equal-area Homolosine projection, with unit-averaged 5 % and 95 % quantiles and ISRIC conversion factors.
  - No rasters redistributed; the ISRIC files are linked.

### Drought
- **Latest conditions:** from SPEI (to 2025-12) and the more recent rainfall-only SPI (to 2026-10), plus the five wilayas with the lowest SPEI-12.
- **Workspace:** SPEI, SPI or precipitation, by country, wilaya or commune.
- **Drought outlook:** marked *experimental, not yet published*, with the conditions for publication (hindcast verification).

### Data catalog
- **Three categories:**
  - **Available through AEO** (Explore | Download | Methods);
  - **Available from external sources** (Visit source | Documentation | Publication; never a Download button);
  - **Under development**.
- **Soil domain:** "Soil & Land Properties" is now a primary domain.
- **External records:** 21 new verified records, so the catalog now holds 61 records (49 external).
  - Soil (8): FAO GSOCmap, HWSD v2.2, WoSIS profiles, OpenLandMap-soildb, iSDAsoil, FAO GSOCseq, FAO DSMW, JRC Soil Atlas of Africa.
  - Climate, water, vegetation and agriculture (13): ERA5, C3S seasonal forecasts, CRU TS, GLEAM, ESA CCI Soil Moisture, GRACE mascons, AQUASTAT, Global Dam Watch, Hansen Global Forest Change, MODIS GPP/NPP, FAO WaPOR, Copernicus NDVI 300 m, GGCMI crop calendar.
  - Every URL was fetched, every DOI was checked as registered (doi.org) and against Crossref or DataCite, and Algeria coverage was checked by reading the data where possible.
  - Licence conflicts between official sources are recorded with the most restrictive reading, for example GSOCseq.
  - The live WoSIS service lists only 10 soil profiles for Algeria; this is now cited in the soil method.
- **Algerian institutions:** 6 institutions (ONM, ASAL, ONS, MADRP, DGF, CRSTRA), each with what is openly available ("publications only", "on request" or "no public data found"). ANRH, ANBT and INSID were left out because their sites could not be reached or verified. No partnership is implied.

### Science
- **Overview:** methods, data guides, and a table of the ten open-science standards for each product. It shows "partial" or "not yet" where true (reproducible environment, quantitative uncertainty, software DOI).
- **Publications & References:** 28 references with metadata from **Crossref**.
  - Each DOI is checked as registered (doi.org handle API) and against the expected title, first author and year.
  - The check caught one wrong DOI (Guttman 1999), which was corrected.
  - Copy citation and BibTeX are generated from the verified metadata.
  - "AEO Research" is empty and says so.
- **Learn with AEO:** SPI (Python), SPEI (R), SoilGrids soil organic carbon (Python), plus the existing rainfall tutorials. Each lists objective, data, code, dependencies, the outputs actually obtained, interpretation and limitations.
  - The SPI and SPEI tutorials run in the test suite. The soil tutorial runs when network tests are enabled.
  - Agricultural drought exposure is listed as planned.

## Tests (all passing on the branch)
- **Python (93 passed, 1 network test skipped); build validates all 61 records and 276 regional partitions:**
  - SPI against R;
  - soil product QA (checksums, completeness, ranges, quantile order, national vs wilaya, stock totals);
  - regional partitions;
  - tutorials;
  - existing statistics, SPEI and precipitation tests.
- **JavaScript (56):** download resolution and extraction against the published files, including SPI partitions and soil.
- **Playwright (70 at desktop and mobile widths):**
  - the nine tests of the brief: bright homepage map; click Sétif → inspector beside the map with "Wilaya 19"; real precipitation statistics and chart; changing the indicator keeps the place; external SoilGrids source link works; DOI resolves to SoilGrids 2.0 (doi.org + Crossref); inspector CSV has the right wilaya, years, units and source; keyboard and mobile; honest message for NDVI;
  - the regional download journeys;
  - axe-core (WCAG 2.2 AA rules) on 15 pages at two widths;
  - no horizontal scrolling on mobile.

## Remaining scientific work (not done)
1. **French and Arabic.** The structure is ready (EN/FR/AR markers), but no translated pages are published. Accurate scientific translation needs a reviewed workflow. Machine-translated pages were deliberately not published.
2. **Drought outlook.** Seasonal forecasts (e.g. C3S/SEAS5) need hindcast verification for Algeria (reliability, RPSS) before any probability is shown.
3. **SPEI with ERA5-Land PET.** AEO's SPEI uses TerraClimate Penman–Monteith PET, which is justified and documented. A version on ERA5-Land, and a comparison of the two, remain to be done.
4. **Validation against stations.** None of the climate indices has been compared with Algerian station data (ONM); that needs data access.
5. **Agricultural drought exposure.** This needs a validated cropland mask for Algeria first.
6. **Soil.** Not yet done:
   - salinity and water-holding properties;
   - texture classes;
   - comparison with WoSIS profile measurements in Algeria;
   - SoilGrids uncertainty propagated to unit means (current ranges are pixel-level).
7. **Commune-level map layers.** Only SPI has a choropleth, and only by wilaya; commune choropleths and gridded SPI are not published.
8. **Reproducible environment.** Python environments are pinned only through requirements files. A lock file or container and a software DOI (e.g. a Zenodo release) are still missing.
9. **Manual accessibility testing.** Screen-reader testing (NVDA, VoiceOver) of Explore and the inspector has not been done.
