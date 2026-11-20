# Source audit

Status at **2026-11-19**. This document records which data products and services were checked while building the Algeria Earth Observatory catalog, which were incorporated, and which remain candidates. Every incorporated record also carries its own `verification` block (date checked, sources consulted, unconfirmed fields), shown on its dataset page and summarised at https://algeria-earth-observatory.github.io/sources/.

## Method

- Facts were taken only from official provider pages, user guides, data papers and DOI landing pages, fetched on the date above. URLs were tested with HTTP requests; DOIs were checked against the DOI handle API when publishers block automated requests.
- Fields that could not be confirmed were left empty and listed in `verification.unverified_fields` rather than guessed.
- External link health is re-checked weekly by `.github/workflows/link-check.yml` (`npm run check:links`).

## Candidate list from the project brief

| Theme | Candidate | Outcome | Record |
|---|---|---|---|
| Cropland | ESA WorldCereal | Incorporated (external) | `esa-worldcereal-2021` |
| Cropland | GLAD cropland products | Incorporated (external); **no data licence stated by provider** | `glad-global-cropland` |
| Cropland | GACED30 | Incorporated (external); identified as Global 30-m Annual Cropland Extent Dynamics (Liao et al. 2026, ESSD). Map year slider from AEO display tiles (2026-11-20); Algeria clip prepared for release `gaced30-dza-v1` | `gaced30` |
| Land cover | ESA WorldCover | Incorporated (external). Map layers 2020 and 2021 via Microsoft Planetary Computer tiles (Terrascope WMTS unreachable from the verification environment) | `esa-worldcover` |
| Satellite imagery | Sentinel-2 | Incorporated (external, Copernicus Data Space login) | `copernicus-sentinel-2-l2a` |
| Satellite imagery | Landsat | Incorporated (external, Collection 2 Level-2) | `usgs-landsat-c2-l2` |
| Vegetation | MODIS vegetation products | Incorporated (MOD13Q1 v061); map layer via NASA GIBS | `modis-mod13q1-v061` |
| Rainfall | CHIRPS | Incorporated (v2.0; v3 noted as successor) | `chirps-v2` |
| Climate | ERA5-Land | Incorporated (CDS login, CC BY 4.0) | `era5-land` |
| Drought | SPEIbase | Incorporated, with provider-reported PET bug flagged as an alert | `speibase` |
| Soil moisture | SMAP | Incorporated (SPL3SMP_E v6); map layer via NASA GIBS | `smap-soil-moisture` |
| Evapotranspiration | MODIS ET | Incorporated (MOD16A2GF v061) | `modis-mod16a2gf-v061` |
| Water | JRC Global Surface Water | Incorporated (v1.5 record; map tiles are v1.4, 1984–2021) | `jrc-global-surface-water` |
| Soil | SoilGrids | Incorporated (SoilGrids 2.0; no dataset DOI) | `soilgrids` |
| Elevation | Copernicus DEM | Incorporated (GLO-30) | `copernicus-dem-glo30` |
| Fire | NASA FIRMS | Incorporated; live map layer **not** added (API requires a private MAP_KEY) | `nasa-firms` |
| Population | WorldPop | Incorporated (Algeria-specific files offered by WorldPop) | `worldpop-dza` |

## Additional records

| Record | Reason |
|---|---|
| `aeo-dza-admin-boundaries` | AEO-derived 69-wilaya boundaries (OpenStreetMap snapshot), because no openly licensed boundary set reflected Loi n° 26-06 (2026). |
| `geoboundaries-dza` | Catalogued for reference (48 wilayas, 2017, ODbL). |
| `gpm-imerg`, `modis-mod11c3-v061`, `merra2-aerosol-diagnostics` | Back the IMERG, land-surface-temperature and dust map layers; verified from NASA CMR metadata. |
| `faostat-qcl` | National crop production, area and yield statistics. |
| `terraclimate`, `nex-gddp-cmip6` | Climate (historical and projections). |
| `hydrobasins` | River basins. **Not re-hosted**: HydroSHEDS v1 licence forbids redistribution as a stand-alone product. |
| `modis-mcd64a1-v061` | Burned area. |
| `ghsl-built-s`, `sentinel-5p-no2` | Human change and air pollution. |

## Map services

| Service | Checked | Use |
|---|---|---|
| NASA GIBS WMTS (EPSG:3857) | GetCapabilities parsed by `scripts/fetch_gibs_layers.py`; sample tiles HTTP 200 | NDVI, IMERG, LST, SMAP, MERRA-2 dust, VIIRS true colour, Blue Marble, ASTER relief |
| JRC GSW tiles (`tiles2021/occurrence`) | Sample tiles HTTP 200; colour ramp sampled | Surface water occurrence layer |
| OpenFreeMap styles (Positron, Liberty) | HTTP 200 | Basemaps |
| ESA WorldCover WMTS (Terrascope) | Connection reset (2026-11-19, 2026-11-20) | Not used; Planetary Computer mosaic tiles used instead (verified 2026-11-20) |

## Administrative geography

See `research/wilaya_geography.md`. Algeria has 69 wilayas under Loi n° 26-06 of 4 April 2026 (JO n° 25, 5 April 2026); wilayas 59–69 were named by Décret présidentiel n° 26-206 of 25 May 2026 (JO n° 40, 3 June 2026). geoBoundaries (gbOpen and gbHumanitarian), OCHA COD-AB and GADM 4.1 all represented 48 wilayas when checked. OpenStreetMap contained 69 admin_level 4 relations.

## Remaining candidates (not yet researched)

ESA CCI Land Cover, Copernicus Global Land Service products (NDVI, burnt area, water bodies), FAO WaPOR, GRACE/GRACE-FO terrestrial water storage, GRanD / GDW dams, CAMS reanalysis, VIIRS Black Marble night lights, Hansen Global Forest Change, Copernicus EMS flood activations, CHIRTS-daily temperature, SPI datasets.

---

# Detailed audit tables

## Audit: agriculture & land / imagery records

Checked: 2026-11-19. HTTP status from `curl -L`. Where usgs.gov or Zenodo blocked command-line requests, pages were read with a browser-style fetch instead.

| Dataset (id) | What was verified | Decision | Open questions |
|---|---|---|---|
| ESA WorldCereal 2021 (`esa-worldcereal-2021`) | Zenodo record 7875105 (v100, 2023-05-12, CC BY 4.0; concept DOI 10.5281/zenodo.7875104 via API). ESSD paper 10.5194/essd-15-5491-2023 (6 Dec 2023, abstract accuracies). GEE catalog (CC-BY-4.0, 0/100 classification). Portal esa-worldcereal.org, viewer vdm.*, download hub.* all 200. | Record created | No recommended dataset citation (built from Zenodo metadata). Value convention conflict (0/100 binary vs "0–100 fractional"). No newer global release found: site says "more products by end of 2026"; CEOS says a new set was expected in 2026. CRS EPSG code and bbox not stated. |
| GLAD global cropland 2003–2019 (`glad-global-cropland`) | glad.umd.edu/dataset/croplands (200): definition, 5 four-year epochs, 0.00025°, file list. Data directory and NE_2019.tif (200, image/tiff). Nature Food DOI 10.1038/s43016-021-00429-z (online 23 Dec 2021; vol 3, 2022), article CC BY 4.0, Table 3 accuracies. | Record created | **No data licence stated** by GLAD (only the article is CC BY 4.0). No dataset DOI or version. GEE app returned 405 to HEAD. |
| GACED30 (`gaced30`) | Confirmed as "Global 30-m Annual Cropland Extent Dynamics" (Zenodo title). Zenodo 10.5281/zenodo.18199675 (v1, 2026-01-09, CC BY 4.0, 25-band COG, 3° tiles, EPSG:4326, values 0/10/255). ESSD paper Liao et al. 2026, 10.5194/essd-18-7071-2026 (25 Sep 2026), abstract accuracies, cropland definition. | Record created | No recommended citation (built from Zenodo metadata). iEarth mirror (data-starcloud.pcl.ac.cn) unreachable. SDC30 input sensors not confirmed. No North Africa-specific accuracy. |
| ESA WorldCover 2020 v100 / 2021 v200 (`esa-worldcover`) | Zenodo API for 5571936 (v100, 2021-10-20) and 7254221 (v200, 2022-10-28), CC BY 4.0. PUM v2.0 (licence, attribution text, citations, classes, EPSG:4326, extent to 82.75°N). PVR v2.0: OA 76.7 ± 0.5%; PVR v1.1: OA 74.4 ± 0.1%. esa-worldcover.org, data-access and viewer: 200. | Record created | Continental OA table not transcribed (PDF layout ambiguous). worldcover2021.esa.int did not respond. Southern bbox limit not numeric. |
| Sentinel-2 MSI L2A (`copernicus-sentinel-2-l2a`) | CDSE Sentinel-2 docs, L2A baseline page, OData docs (download needs token), SentiWiki products page, ESA Collection-1 L2A page (citation, Sen2Cor 2.10), legal notice PDF (Reg. 1159/2013 wording), STAC collection (start 2015-06-27), DOI 10.5270/S2_-znk9xsj (Crossref). | Record created | No SPDX licence (Copernicus legal notice). Constellation status after 13 Mar 2026 not checked. No official accuracy figure consulted. Login needed to download. |
| Landsat C2 L2 (`usgs-landsat-c2-l2`) | USGS Level-2 page (LaSRC 1.5.0, LEDAPS 3.4.0, ST 1.3.0, scale factors, COG). DOIs P9OGBGM6 (L8-9), P9C7I13B (L7), P9IAXOVV (L4-5) resolve to EROS pages with 2024-revised citations. USGS copyrights page (public domain). AWS registry (requester pays). EarthExplorer 200. | Record created | usgs.gov returns 403 to curl (bot protection). CRS not confirmed from fetched pages. EarthExplorer download needs a free account; the AWS bucket is requester-pays. |
| MODIS MOD13Q1 v061 (`modis-mod13q1-v061`) | DOI 10.5067/MODIS/MOD13Q1.061 confirmed (DataCite: Didan 2021, LP DAAC). Earthdata catalog page (start 2000-02-18, layers, citation, "without restriction"). EOSDIS guidance (CC0). User Guide v3.10 (CV-MVC). Granule download redirects to Earthdata Login. | Record created | **Terra MODIS acquisitions end 1 Dec 2026** (catalog alert), with VIIRS VJ213A1 as the recommended successor. lpdaac.usgs.gov product URL now redirects to earthdata.nasa.gov. |
| FAOSTAT QCL (`faostat-qcl`) | FAOSTAT bulk index (DateUpdate 2025-12-31, CSV ZIP, bulk URL 200). FAO data catalog ISO record (1961–2024, units, sources, CC BY 4.0). FAO database terms of use (citation template). FAO brief Agricultural production statistics 2010–2024 (DOI 10.4060/cd8035en). | Record created | FAOSTAT web page is JavaScript-only (not text-readable). FAOSTAT API endpoints tried needed authorisation or failed (521). Flag code definitions not captured. |


## Audit – climate, drought and water records

Checked: 2026-11-19. Every URL listed below was fetched with curl or WebFetch on that date. Records are in `src/content/datasets/`.

| Dataset (id) | What was verified | Decision | Open questions |
|---|---|---|---|
| CHIRPS v2.0 (`chirps-v2`) | CHC page (200). README version history: v2.0 released 2015-02-12, v3.0 released 2025-01-14. Coverage 50°S–50°N. Public-domain waiver wording. Funk 2015 DOI 10.1038/sdata.2015.66 (Crossref). Global monthly NetCDF HEAD: 200, 7,769,103,244 B. CHIRPS v3: CC BY 4.0, DOI 10.15780/G2JQ0P, paper 10.1038/s41597-026-07096-4. | Record created | The CHC landing page links to `products/CHIRPS-2.0/`, which returns 404; the working path is `products/CHIRPS/v2.0/`. No dataset DOI for v2. The CC0 SPDX code is AEO's reading of the waiver text. v2 production ends after Dec 2026. Should AEO add a separate `chirps-v3` record? |
| ERA5-Land (`era5-land`) | CDS STAC API: licence CC-BY-4.0. DOIs: hourly 10.24381/cds.e2161bac, monthly 10.24381/cds.68d2bb30. Published 2019-07-12 / 2019-06-23. Citation and attribution text. ECMWF documentation: ERA5-Land-T runs about 5 days behind real time. Known issue with monthly accumulations Sep 2022–Feb 2024. ESSD DOI. | Record created | CDS account and licence acceptance are needed to download. Validation is summarised from the ESSD abstract only. |
| SPEIbase (`speibase`) | spei.csic.es: latest v2.11 (CRU TS 4.09, 1901–2024), licence ODbL 1.0. DataCite and DIGITAL.CSIC: latest registered DOI is v2.10 (10.20350/digitalCSIC/16497). v2.11 spei12.nc HEAD: 200, 380,954,035 B. Provider GitHub README: PET-conversion bug affects every release from v2.6 to v2.12.0, with the largest effect in arid regions. The fix landed in code v2.13.0 on 2026-11-07, and a corrected dataset is "to follow". | Record created (v2.11, doi null) | No DOI for v2.11. The site's per-version DIGITAL.CSIC links point one version too early. GEE states CC-BY 4.0 while the provider states ODbL. Watch for the corrected v2.13 data release. SPEIbase contains no SPI. |
| SMAP soil moisture (`smap-soil-moisture`) | NSIDC SPL3SMP_E v6: DOI 10.5067/M20OXIZHY3RJ, from 2015-03-31, 9 km EASE-Grid 2.0, HDF5, Earthdata Login required. User guide: ~5 cm depth, DCA baseline, quality flags, mountainous flag thresholds. SPL4SMGP v8: DOI 10.5067/T5RUATAQREF8. CMR dates and use constraints. | Record created (L3_E primary, L4 as companion) | No validation figure was extracted (assessment reports not read). NSIDC has posted a temporary forward-processing pause for 1–3 Dec 2026. |
| MODIS ET MOD16A2GF v061 (`modis-mod16a2gf-v061`) | LP DAAC page: DOI 10.5067/MODIS/MOD16A2GF.061, published 2021-03-15, citation. User Guide v6.1: fill values 32761–32767, with 32765 = barren/desert. Tower validation (MAE 0.31 kg/m²/day). CMR: latest granule ends 2025-12-31. NASA alert: Terra stops acquiring new data on 2026-12-01. | Record created | Most of the Sahara is fill, not zero ET. The record will stop growing after Terra's end. The Algeria tile range (h17–h19, v05–v07) is an AEO approximation. |
| JRC Global Surface Water (`jrc-global-surface-water`) | Download page and Users Guide v5: current version v1.5 (1984–2024), v1.4 deprecated. Licence: Copernicus, no restriction of use, attribution "Source: EC JRC/Google". Algeria tile `occurrence_0E_40N_v1_5_2024.tif` HEAD: 200 on Cloudferro (29,985,443 B, modified 2026-11-10) and on GCS (35,063,772 B, modified 2026-06-19). Validation figures for v1.0 from the FAQ. | Record created | No dataset DOI and no exact v1.5 release date. The two mirrors serve different files, and the GCS copy may predate the 10 Nov occurrence fix. GEE's public catalogue still lists only v1.4. The Collection 1/2 co-registration offset is unresolved. |
| TerraClimate (`terraclimate`) | Climatology Lab page: v1.1 released 15 Nov 2026 (CHELSA v2.1 + ERA5, 1/30°, 1950–present). THREDDS file metadata (DAS): licence CC BY 4.0, version v1.1, dated 2026-11-14, files for 1950–2025. ppt_2025 file HEAD: 200. Sci Data 2018 DOI. | Record created (v1.1) | The Zenodo DOI in the file metadata (10.5281/zenodo.23961197) returns 404. The v1.1 paper is not yet verifiable. The licence changed (GEE lists v1.0 as CC0). PDSI is absent from the v1.1 variable list. climate.northwestknowledge.net was unreachable. |
| NEX-GDDP-CMIP6 (`nex-gddp-cmip6`) | NCCS page and v2 Tech Note (May 2025): 0.25°, 60°S–90°N, 1950–2100, four SSPs, 35 GCMs, BCSD against GMFD. AWS registry: CC0 since Sept 2022, no-sign-request S3 access. DOI 10.7917/OFSG3345 resolves. v2.0 files present in S3. | Record created | The Tech Note still points to the CMIP6 Terms of Use and the per-file `cmip6_license` attribute, so reviewers should confirm before redistributing. The AWS text says "two of the four" SSPs, which conflicts with the Tech Note. |
| HydroBASINS v1c (`hydrobasins`) | Product page and the official Africa link `https://data.hydrosheds.org/file/hydrobasins/standard/hybas_af_lev01-12_v1c.zip` (also `hybas_lake_af_…`). TechDoc v1.c: citation, field definitions. HydroSHEDS TechDoc v1.4 Appendix A: custom WWF licence with no stand-alone redistribution and a required attribution. CC-BY 4.0 applies only to HydroSHEDS v2, whose HydroBASINS is a beta covering only the Americas. | Record created (download_url null) | HEAD and GET on the zip return 403 with a Cloudflare bot challenge, so the file and its size could not be confirmed and download_url is null. Per-level Africa URLs are not in the page HTML. bbox is unknown. Licence terms rule out re-hosting the data on AEO. |

## Cross-cutting notes
- NASA products (SMAP, MOD16) use the CC0 convention from the NASA ESDIS Data Use Guidance, consistent with existing AEO NASA records.
- Datasets that need a login: ERA5-Land (CDS account), SMAP and MOD16 (Earthdata Login), and all Google Earth Engine mirrors. Downloads with no login: CHIRPS, SPEIbase, JRC GSW, TerraClimate, NEX-GDDP-CMIP6 (AWS/THREDDS), and HydroBASINS (browser only).


## Audit: hazards, human-change and reference candidates (checked 2026-11-19)

| Dataset (record id) | What was verified (official sources, fetched) | Decision | Open questions |
|---|---|---|---|
| SoilGrids 2.0 (`soilgrids`) | ISRIC landing + docs (FAQ layers, access): 250 m, 6 depths 0-200 cm, properties/units/conversion factors, CC BY 4.0, Homolosine ESRI:54052, WebDAV listing (13 property folders incl. wrb), WCS/WMS at maps.isric.org; Poggio et al. 2021 DOI via Crossref; ISRIC accuracy statement (30-70% variance explained). All URLs HTTP 200. | Include (external, modeled). | No dataset DOI on ISRIC pages (paper DOI used); rolling release, no file date; REST API paused; FAQ water-content layers (wv*) not on WebDAV; bbox left null. |
| Copernicus DEM GLO-30 (`copernicus-dem-glo30`) | DOI 10.5270/ESA-c5d3d65 redirects to CDSE COP-DEM page (confirmed); specs, releases 2019_1-2024_1, accuracy specs; GLO-30 free licence Art. 6 notice copied from CDSE licence PDF; AWS registry + readme; Algiers tile COG read (EPSG:4326, 3600x3600); OpenTopography page 200. | Include (external). | Exact release dates (only month); completeness of all Algerian tiles not checked; OpenTopography DOI not captured. |
| NASA FIRMS (`nasa-firms`) | FIRMS page (acknowledgement text verbatim, disclaimer), archive page (coverage dates per sensor, ~5-month NRT->SP lag), API MAP_KEY page (5000 transactions/10 min), area API sources; CMR DOIs for MCD14DL C6.1 NRT and VIIRS S-NPP/NOAA-20/NOAA-21 375 m NRT (all resolve); Algeria yearly country CSVs (MODIS & VIIRS 2023) HTTP 200 with sizes; algorithm paper DOIs via Crossref. | Include (external, point). | No dataset validation statement; S-NPP archive listed as ending 2 Nov 2026 and Terra ending 1 Dec 2026 (sensor continuity); 'type' code meanings not re-read; country API endpoint "not available". |
| MODIS MCD64A1 v061 (`modis-mcd64a1-v061`) | Earthdata catalog page (lpdaac URL now 301 redirects there): DOI, layers, fill values, citation, Stage 3 validation; CMR (create date 2021-04-08, extent, latest granule Sep 2026); C6.1 user guide: validation numbers (commission 40.2%, omission 72.6%, bias -54.1%), cropland low-confidence, June 2001 degraded. | Include (external). | Terra end (1 Dec 2026) may affect production; catalog title includes "Direct Broadcast" while citation does not. |
| WorldPop Algeria (`worldpop-dza`) | REST API: Global2 R2025A (2015-2030, 100 m, constrained; DOI 10.5258/SOTON/WP00839, 2025-09-01), plus R2024B, 2020 constrained (WP00684) and 2000-2020 unconstrained (WP00645); licence.txt CC BY 4.0; release statement (methods, alpha status, UN WPP 2024 alignment); census-sources xlsx row DZA: single time point, RGPH 2008, admin 2, 1,540 units; HEAD of 3 GeoTIFFs (sizes recorded); 2025 file downloaded, header read (EPSG:4326, bbox, NoData -99999). | Include (external, modeled); download_url = 2025 R2025A file. | R2025A is "alpha" and may change; no per-country accuracy; ODbL clause for OSM/Microsoft-derived products noted on hub page. |
| GHSL GHS-BUILT-S R2023A (`ghsl-built-s`) | GHSL dataset JSON (product specs, epochs, resolutions, units/NoData), gallery JSON (citation, DOI, methodology paper); DOI via DataCite (issued 2023-04-25, abstract); Data Package 2023 PDF (terms of use 2011/833/EU, validation figures); JRC FTP files HEAD 200 with sizes. | Include (external), domain human-change. | JRC data catalogue page rejected automated request; bbox null; validation figures global only. |
| Sentinel-5P TROPOMI NO2 (`sentinel-5p-no2`) | CDSE S5P page (L2 since Apr 2018); ESA product page (resolution change 6 Aug 2019, v01/v02 citations + DOIs, PAL reprocessing); PRF v02.05.00 (DOI, qa_value>0.75, validation compliance, requirements table); PUM (units mol/m2, conversion factor, launch 13 Oct 2017, 13:30 overpass, DOAS); Sentinel data legal notice (attribution wording); GEE L3 page. | Include (external), domain hazards. | Exact first-data day; current processor version in Nov 2026; sentinel.esa.int domain timed out (used sentinels.copernicus.eu mirrors). |
| geoBoundaries DZA ADM0/ADM1 (`geoboundaries-dza`) | API gbOpen ADM0/ADM1/ADM2 and gbHumanitarian ADM0-2 (raw saved in `research/geoboundaries_dza.json`); gbAuthoritative 404; download URLs HTTP 200 with sizes; ADM1 simplified file: 48 features DZ-01..DZ-48; homepage citation guidance; Runfola et al. 2020 via Crossref. | Include as reference, labelled "48 wilayas (pre-2019, OSM 2017)". License is ODbL 1.0 (not the CC BY 4.0 on homepage). | Outdated vs law 19-12 (58) and law 26-06 (69); gbOpen ADM2 is not a commune layer. |
| Wilaya count (research) | JORADP PDFs: JO 78/2019 (law 19-12, 58 wilayas), JO 22/2021 (decree 21-117, names 49-58), JO 25/2026 (law 26-06, 69 wilayas, 1541 communes), JO 40/2026 (decree 26-206, names 59-69). HDX COD-AB DZA (48/1541, CC BY-IGO), GADM 4.1 (48, non-commercial). | See `research/wilaya_geography.md`. | OSM admin_level=4 count not checked (Overpass timeouts). The existing record `aeo-dza-admin-boundaries` says "2025 administrative reform"; legally it is law 26-06 of 4 April 2026. |

