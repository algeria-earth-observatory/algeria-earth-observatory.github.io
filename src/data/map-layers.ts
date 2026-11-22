/**
 * Map explorer layer registry.
 *
 * Every overlay links to a catalog record (`dataset`) so the map never shows
 * data whose provenance is not documented. Raster overlays are visualisation
 * tiles rendered by the provider — they are not the analysis-ready data, and
 * pixel colours must not be read as measured values.
 *
 * GIBS templates/time dimensions come from src/data/gibs-layers.json, which
 * scripts/fetch_gibs_layers.py regenerates from the live GetCapabilities.
 */
import gibs from './gibs-layers.json';
import precipMap from '../../public/data/aeo/products/precipitation/v1.0.0/map/map.json';
import speiMap from '../../public/data/aeo/products/spei/v1.0.0/map/map.json';
import spiMap from '../../public/data/aeo/products/spi/v1.0.0/map/map.json';
import spiManifest from '../../public/data/aeo/products/spi/v1.0.0/manifest.json';
// Soil overlays exist only once scripts/pipelines/soil/build_soil.py has run.
const soilMapFiles = import.meta.glob('../../public/data/aeo/products/soil/v1.0.0/map/map.json', { eager: true, import: 'default' });
const soilMap = (Object.values(soilMapFiles)[0] ?? null) as null | {
  coordinates: [number, number][];
  layers: Record<string, { breaks: number[]; colors: string[]; units: string; label: string; depth: string }>;
};
import type { DomainId } from '../lib/domains';

type GibsId = keyof typeof gibs.layers;

export interface Legend {
  kind: 'image' | 'gradient' | 'line' | 'classes' | 'none';
  url?: string;
  stops?: string[];
  labels?: [string, string];
  /** Categorical legend entries (kind 'classes'). */
  classes?: { color: string; label: string }[];
  caption?: string;
}

export interface MapLayer {
  id: string;
  title: string;
  summary: string;
  domain: DomainId | 'reference';
  type: 'raster' | 'geojson' | 'image' | 'choropleth';
  /** Choropleth by wilaya from a published AEO table (type 'choropleth'): web JSON with months, units, values[key][scale]. */
  choropleth?: { url: string; key: string; scale: string; breaks: number[]; colors: string[]; flag: string; flagColor: string };
  /** Image overlay (type 'image'): URL template with {year}, {month} or {variant}, Web Mercator image corners. */
  image?: { url: string; coordinates: [number, number][] };
  dataset: string | null;
  nature: 'observed' | 'derived' | 'modeled' | 'reference';
  /** Raster tile URL template ({z}/{x}/{y}; {time} replaced at runtime). */
  tiles?: string;
  /** GeoJSON URL (site-relative). */
  data?: string;
  minzoom?: number;
  maxzoom: number;
  time?: { periods: string[]; default: string | null; step: 'day' | '16-day' | 'month' | 'year' };
  /** Non-temporal variants of one indicator (e.g. soil depth intervals), substituted for {variant}. */
  variants?: { label: string; options: { id: string; label: string }[]; default: string; note?: string };
  opacity: number;
  attribution: string;
  legend: Legend;
  caveat?: string;
  defaultOn?: boolean;
  /** Provider answers HTTP 404 for tiles with no data (e.g. sea); do not report these as errors. */
  emptyTiles404?: boolean;
  /** Map view (MapLibre hash "zoom/lat/lng") used when the layer is opened from a dataset page. */
  focusView?: string;
  /**
   * Planetary Computer mosaic: the browser registers `body` at `register` when the layer
   * is first shown and substitutes the returned search id for `{search}` in `tiles`
   * (search ids expire after about 24 h, so they cannot be stored in a static site).
   * `fallback` is used if registration fails.
   */
  mosaic?: { register: string; body: unknown; fallback: string };
}

// ESA WorldCover, served as mosaic tiles by Microsoft Planetary Computer (STAC
// collection `esa-worldcover`). The ESA Terrascope WMTS could not be reached from
// the verification environment; Planetary Computer was verified on 2026-11-20
// (tiles render from zoom 6; CORS open; colormap = official WorldCover palette).
const PC_DATA = 'https://planetarycomputer.microsoft.com/api/data/v1';
const WORLDCOVER_CLASSES = [
  { color: '#006400', label: 'Tree cover' },
  { color: '#ffbb22', label: 'Shrubland' },
  { color: '#ffff4c', label: 'Grassland' },
  { color: '#f096ff', label: 'Cropland' },
  { color: '#fa0000', label: 'Built-up' },
  { color: '#b4b4b4', label: 'Bare / sparse vegetation' },
  { color: '#f0f0f0', label: 'Snow and ice' },
  { color: '#0064c8', label: 'Permanent water bodies' },
  { color: '#0096a0', label: 'Herbaceous wetland' },
  { color: '#00cf75', label: 'Mangroves' },
  { color: '#fae6a0', label: 'Moss and lichen' },
];
function worldcover({ id, year, version, hash }: { id: string; year: 2020 | 2021; version: string; hash: string }): MapLayer {
  return {
    id,
    title: `Land cover ${year} (ESA WorldCover ${version}), 10 m`,
    summary: `ESA WorldCover ${year} ${version}: 11 land-cover classes at 10 m from Sentinel-1 and Sentinel-2. Tiles rendered by Microsoft Planetary Computer from the ESA files.`,
    domain: 'land-ecosystems',
    type: 'raster',
    dataset: 'esa-worldcover',
    nature: 'derived',
    tiles: `${PC_DATA}/mosaic/{search}/tiles/WebMercatorQuad/{z}/{x}/{y}@1x?collection=esa-worldcover&assets=map&colormap_name=esa-worldcover&format=png`,
    minzoom: 6,
    maxzoom: 13,
    opacity: 0.85,
    attribution: `© ESA WorldCover project ${year} / Contains modified Copernicus Sentinel data (${year}) processed by ESA WorldCover consortium · tiles: <a href="https://planetarycomputer.microsoft.com/dataset/esa-worldcover" target="_blank" rel="noopener">Microsoft Planetary Computer</a>`,
    legend: { kind: 'classes', classes: WORLDCOVER_CLASSES, caption: 'Land-cover class' },
    caveat: 'At national scale the map is a coarse overview; zoom in for 10 m detail. Olive groves, date palms and fallow are often not mapped as cropland, so “Cropland” understates agricultural land in Algeria. Global overall accuracy (validation reports): 76.7% for 2021, 74.4% for 2020. 2020 and 2021 used different algorithms; differences between the two maps are not reliable change.',
    emptyTiles404: true,
    focusView: '8/36.55/2.95',
    mosaic: {
      register: `${PC_DATA}/mosaic/register`,
      fallback: hash,
      body: {
        collections: ['esa-worldcover'],
        'filter-lang': 'cql2-json',
        filter: { op: 'anyinteracts', args: [{ property: 'datetime' }, { interval: [`${year}-01-01T00:00:00Z`, `${year}-12-31T23:59:59Z`] }] },
      },
    },
  };
}

const g = (id: GibsId) => gibs.layers[id] as {
  template: string; max_zoom: number; time_default: string | null; time_periods: string[];
  legend_url: string | null; tile_matrix_set: string;
};

/** Convert a GIBS WMTS REST template to a MapLibre {z}/{x}/{y} template. */
function gibsTiles(id: GibsId) {
  const l = g(id);
  return l.template
    .replace('{TileMatrixSet}', l.tile_matrix_set)
    .replace('{TileMatrix}', '{z}')
    .replace('{TileRow}', '{y}')
    .replace('{TileCol}', '{x}')
    .replace('{Time}', '{time}');
}
function gibsTime(id: GibsId, step: NonNullable<MapLayer['time']>['step']) {
  const l = g(id);
  return { periods: l.time_periods, default: l.time_default, step };
}

const GIBS_ATTR =
  '<a href="https://earthdata.nasa.gov/gibs" target="_blank" rel="noopener">NASA EOSDIS GIBS</a>';

export const BOUNDARY_VERSION = '2026-11-20';
const BDIR = `/data/aeo/boundaries/${BOUNDARY_VERSION}`;
/** World minus Algeria: drawn over every overlay so that only Algeria is shown. */
export const OUTSIDE_MASK = `${BDIR}/dza_outside_mask.geojson`;

// ---------------------------------------------------------------- water, cropland and climate products
// Each product's map.json exists only once its pipeline has run; layers are added only then.
const one = (files: Record<string, unknown>) => (Object.values(files)[0] ?? null) as any;
const etMap = one(import.meta.glob('../../public/data/aeo/products/et-soil-moisture/v1.0.0/map/map.json', { eager: true, import: 'default' }));
const twsMap = one(import.meta.glob('../../public/data/aeo/products/water-storage/v1.0.0/map/map.json', { eager: true, import: 'default' }));
const cropMap = one(import.meta.glob('../../public/data/aeo/products/stable-cropland/v1.0.0/map/map.json', { eager: true, import: 'default' }));
const cmipMap = one(import.meta.glob('../../public/data/aeo/products/climate-projections/v1.0.0/map/map.json', { eager: true, import: 'default' }));
const outlookMap = one(import.meta.glob('../../public/data/aeo/products/seasonal-outlook/v0.1.0/web/choropleth.json', { eager: true, import: 'default' }));

export const classLabels = (breaks: number[], colors: string[], fmt: (v: number) => string = String) =>
  colors.map((c, i) => ({ color: c, label: i === 0 ? `< ${fmt(breaks[0])}` : i === breaks.length ? `≥ ${fmt(breaks[i - 1])}` : `${fmt(breaks[i - 1])} to ${fmt(breaks[i])}` }));
const monthly = (months: string[]) => ({ periods: [`${months[0]}-01/${months[months.length - 1]}-01/P1M`], default: `${months[months.length - 1]}-01`, step: 'month' as const });
const signedFmt = (v: number) => (v > 0 ? `+${v}` : String(v).replace('-', '−'));

export const MAP_LAYERS: MapLayer[] = [
  {
    id: 'wilayas',
    title: 'Wilaya boundaries (69)',
    summary: `Administrative boundaries of Algeria’s 69 wilayas from an OpenStreetMap snapshot (${BOUNDARY_VERSION}). Click a wilaya to inspect it.`,
    domain: 'reference',
    type: 'geojson',
    dataset: 'aeo-dza-admin-boundaries',
    nature: 'reference',
    data: `${BDIR}/dza_adm1_wilayas_display.geojson`,
    maxzoom: 22,
    opacity: 1,
    attribution: '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap contributors</a> (ODbL) · AEO processing',
    legend: { kind: 'line', caption: 'Wilaya boundary (community-mapped; not a legal delineation)' },
    caveat: 'Simplified for display. Community-mapped boundaries; not an official legal or cadastral delineation.',
    defaultOn: true,
  },
  {
    id: 'communes',
    title: 'Commune boundaries (1,541)',
    summary: `Algeria's 1,541 communes (OpenStreetMap snapshot ${BOUNDARY_VERSION}), nested in the 69 wilayas. Click a commune for its codes and profile.`,
    domain: 'reference',
    type: 'geojson',
    dataset: 'aeo-dza-admin-boundaries',
    nature: 'reference',
    data: `${BDIR}/dza_adm2_communes_display.geojson`,
    maxzoom: 22,
    opacity: 1,
    attribution: '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap contributors</a> (ODbL) · AEO processing',
    legend: { kind: 'line', caption: 'Commune boundary (community-mapped)' },
    caveat: 'Simplified for display (about 1.5 MB, loaded when switched on). Not an official delineation.',
  },
  {
    id: 'spei-3',
    title: 'Drought index SPEI-3 (AEO, TerraClimate), monthly',
    summary: 'Seasonal (3-month) water balance anomaly. Standardised Precipitation–Evapotranspiration Index from the AEO SPEI product (TerraClimate P and PET, 1/30°, calibrated on 1991–2020). Use the month slider.',
    domain: 'climate-drought',
    type: 'image',
    dataset: 'aeo-dza-spei-terraclimate',
    nature: 'derived',
    image: { url: '/data/aeo/products/spei/v1.0.0/map/spei3_{month}.png', coordinates: speiMap.coordinates as [number, number][] },
    maxzoom: 22,
    time: { periods: [`${speiMap.months[0]}-01/${speiMap.months[speiMap.months.length - 1]}-01/P1M`], default: `${speiMap.months[speiMap.months.length - 1]}-01`, step: 'month' },
    opacity: 0.85,
    attribution: 'SPEI: AEO from TerraClimate (Abatzoglou et al. 2018, CC0)',
    legend: { kind: 'classes', caption: 'SPEI-3 (standard deviations); sand = hyper-arid, not shown', classes: [...speiMap.colors.map((c: string, i: number) => ({ color: c, label: speiMap.labels[i] })), { color: speiMap.hyper_arid.color, label: 'hyper-arid (normal P < 50 mm)' }] },
    caveat: 'Hyper-arid cells (normal precipitation below 50 mm/year) are shown in sand: there SPEI only reflects evaporative demand. Display resampled to 4.5 km; use the GeoTIFF or statistics for analysis.',
  },
  {
    id: 'spei-12',
    title: 'Drought index SPEI-12 (AEO, TerraClimate), monthly',
    summary: 'Annual (12-month) water balance anomaly. Standardised Precipitation–Evapotranspiration Index from the AEO SPEI product (TerraClimate P and PET, 1/30°, calibrated on 1991–2020). Use the month slider.',
    domain: 'climate-drought',
    type: 'image',
    dataset: 'aeo-dza-spei-terraclimate',
    nature: 'derived',
    image: { url: '/data/aeo/products/spei/v1.0.0/map/spei12_{month}.png', coordinates: speiMap.coordinates as [number, number][] },
    maxzoom: 22,
    time: { periods: [`${speiMap.months[0]}-01/${speiMap.months[speiMap.months.length - 1]}-01/P1M`], default: `${speiMap.months[speiMap.months.length - 1]}-01`, step: 'month' },
    opacity: 0.85,
    attribution: 'SPEI: AEO from TerraClimate (Abatzoglou et al. 2018, CC0)',
    legend: { kind: 'classes', caption: 'SPEI-12 (standard deviations); sand = hyper-arid, not shown', classes: [...speiMap.colors.map((c: string, i: number) => ({ color: c, label: speiMap.labels[i] })), { color: speiMap.hyper_arid.color, label: 'hyper-arid (normal P < 50 mm)' }] },
    caveat: 'Hyper-arid cells (normal precipitation below 50 mm/year) are shown in sand: there SPEI only reflects evaporative demand. Display resampled to 4.5 km; use the GeoTIFF or statistics for analysis.',
  },
  ...(['3', '12'] as const).map((k): MapLayer => ({
    id: `spi-${k}`,
    title: `Precipitation index SPI-${k} (AEO, CHIRPS v3.0), monthly, by wilaya`,
    summary: `${k}-month rainfall anomaly as a standard-normal index, for each wilaya, from the AEO SPI product (CHIRPS v3.0 unit means, gamma fit on 1991–2020). Coloured by wilaya: values are wilaya statistics, not a grid.`,
    domain: 'climate-drought',
    type: 'choropleth',
    dataset: 'aeo-dza-spi-chirps3',
    nature: 'derived',
    choropleth: { url: '/data/aeo/products/spi/v1.0.0/web/admin1.json', key: 'spi', scale: k, breaks: spiMap.breaks, colors: spiMap.colors, flag: 'arid', flagColor: spiMap.arid.color },
    maxzoom: 22,
    time: { periods: [`1991-01-01/${spiManifest.temporal_coverage.monthly[1]}-01/P1M`], default: `${spiManifest.temporal_coverage.monthly[1]}-01`, step: 'month' },
    opacity: 0.85,
    attribution: 'SPI: AEO from CHIRPS v3.0 (Climate Hazards Center, UCSB; CC BY 4.0)',
    legend: { kind: 'classes', caption: `SPI-${k} (standard deviations), by wilaya`, classes: [...spiMap.colors.map((c: string, i: number) => ({ color: c, label: spiMap.labels[i] })), { color: spiMap.arid.color, label: 'arid wilaya: SPI unstable' }] },
    caveat: 'One value per wilaya (area-mean rainfall). In arid wilayas (normal below 100 mm/year) SPI is unstable and shown in sand.',
  })),
  {
    id: 'precip-annual',
    title: 'Annual precipitation (AEO, CHIRPS v3.0)',
    summary: 'Calendar-year precipitation totals for Algeria from the AEO precipitation product (CHIRPS v3.0, 0.05° ≈ 5.5 km). Use the year slider.',
    domain: 'climate-drought',
    type: 'image',
    dataset: 'aeo-dza-precipitation-chirps3',
    nature: 'derived',
    image: { url: '/data/aeo/products/precipitation/v1.0.0/map/annual_{year}.png', coordinates: precipMap.coordinates as [number, number][] },
    maxzoom: 22,
    time: { periods: [`${precipMap.years[0]}-01-01/${precipMap.years[precipMap.years.length - 1]}-01-01/P1Y`], default: `${precipMap.years[precipMap.years.length - 1]}-01-01`, step: 'year' },
    opacity: 0.85,
    attribution: 'Precipitation: CHIRPS v3.0 (UCSB Climate Hazards Center, CC BY 4.0) · AEO processing',
    legend: { kind: 'classes', caption: 'mm per year', classes: precipMap.annual.colors.map((c: string, i: number) => ({ color: c, label: i === 0 ? `< ${precipMap.annual.breaks[0]}` : i === precipMap.annual.breaks.length ? `≥ ${precipMap.annual.breaks[i - 1]}` : `${precipMap.annual.breaks[i - 1]}–${precipMap.annual.breaks[i]}` })) },
    caveat: 'Satellite–gauge estimate at about 5.5 km; few gauges in the Sahara. Display pixels are resampled to 5 km; use the GeoTIFF for analysis.',
  },
  {
    id: 'precip-anomaly',
    title: 'Precipitation anomaly vs 1991–2020 (AEO)',
    summary: 'Calendar-year precipitation as a percentage departure from the 1991–2020 normal, from the AEO precipitation product (CHIRPS v3.0).',
    domain: 'climate-drought',
    type: 'image',
    dataset: 'aeo-dza-precipitation-chirps3',
    nature: 'derived',
    image: { url: '/data/aeo/products/precipitation/v1.0.0/map/anomaly_{year}.png', coordinates: precipMap.coordinates as [number, number][] },
    maxzoom: 22,
    time: { periods: [`${precipMap.years[0]}-01-01/${precipMap.years[precipMap.years.length - 1]}-01-01/P1Y`], default: `${precipMap.years[precipMap.years.length - 1]}-01-01`, step: 'year' },
    opacity: 0.85,
    attribution: 'Precipitation: CHIRPS v3.0 (UCSB Climate Hazards Center, CC BY 4.0) · AEO processing',
    legend: { kind: 'classes', caption: '% of the 1991–2020 normal (brown drier, teal wetter · ColorBrewer BrBG)', classes: precipMap.anomaly.colors.map((c: string, i: number) => ({ color: c, label: i === 0 ? `< ${precipMap.anomaly.breaks[0]}` : i === precipMap.anomaly.breaks.length ? `≥ +${precipMap.anomaly.breaks[i - 1]}` : `${precipMap.anomaly.breaks[i - 1]} to ${precipMap.anomaly.breaks[i]}` })) },
    caveat: 'Relative anomalies are large and unstable where the normal is very low (most of the Sahara); not computed where the normal is below 1 mm.',
  },
  {
    id: 'gaced30-cropland',
    title: 'Cropland extent by year (GACED30), 2000–2024',
    summary: 'GACED30 annual 30 m cropland extent for Algeria, one map per year from 2000 to 2024. Use the year slider; cropland mapped in other years is shown in light sand to reveal expansion, fallow and abandonment.',
    domain: 'agriculture',
    type: 'raster',
    dataset: 'gaced30',
    nature: 'derived',
    tiles: 'aeo-gaced:///data/aeo/gaced30/v1/gaced30_dza_2000_2024.pmtiles/{z}/{x}/{y}?t={time}',
    minzoom: 4,
    maxzoom: 11,
    time: { periods: ['2000-01-01/2024-01-01/P1Y'], default: '2024-01-01', step: 'year' },
    opacity: 0.9,
    attribution: 'Cropland: <a href="https://doi.org/10.5281/zenodo.18199675" target="_blank" rel="noopener">GACED30 v1</a> (CC BY 4.0) · display tiles: AEO',
    legend: {
      kind: 'classes',
      // Colours must match ON / OTHER in src/scripts/gaced-protocol.ts.
      classes: [
        { color: '#c85200', label: 'Cropland in the selected year' },
        { color: '#d6be96', label: 'Cropland in another year only' },
      ],
      caption: 'GACED30 cropland / non-cropland',
    },
    caveat: 'AEO display tiles, about 60 m at the finest zoom: each pixel shows the majority GACED30 class, so small or scattered fields can disappear when zoomed out. Year-to-year changes include classification noise, especially fallow versus bare land in drylands. In 2003–2006 large patches (15–35 km) between Ghardaïa and Ouargla are mapped as cropland in the source data only for those years; they are probably classification artefacts. Use the 30 m files for analysis.',
    focusView: '8/35.9/1.2',
  },
  {
    id: 'ndvi-16day',
    title: 'Vegetation index (NDVI), 16-day',
    summary: 'MODIS Terra NDVI 16-day composite (MOD13Q1 family) — vegetation greenness for crop and rangeland condition.',
    domain: 'agriculture',
    type: 'raster',
    dataset: 'modis-mod13q1-v061',
    nature: 'derived',
    tiles: gibsTiles('MODIS_Terra_L3_NDVI_16Day'),
    maxzoom: g('MODIS_Terra_L3_NDVI_16Day').max_zoom,
    time: gibsTime('MODIS_Terra_L3_NDVI_16Day', '16-day'),
    opacity: 0.85,
    attribution: `MODIS Terra NDVI · ${GIBS_ATTR}`,
    legend: { kind: 'image', url: g('MODIS_Terra_L3_NDVI_16Day').legend_url ?? undefined, caption: 'NDVI (unitless)' },
    caveat: 'Visualisation tiles. Sparse dryland vegetation gives low NDVI even on cultivated land; bright soils affect values.',
  },
  {
    id: 'imerg-daily',
    title: 'Precipitation rate (IMERG), daily',
    summary: 'NASA GPM IMERG satellite precipitation estimate, daily visualisation.',
    domain: 'climate-drought',
    type: 'raster',
    dataset: 'gpm-imerg',
    nature: 'derived',
    tiles: gibsTiles('IMERG_Precipitation_Rate'),
    maxzoom: g('IMERG_Precipitation_Rate').max_zoom,
    time: gibsTime('IMERG_Precipitation_Rate', 'day'),
    opacity: 0.8,
    attribution: `GPM IMERG · ${GIBS_ATTR}`,
    legend: { kind: 'image', url: g('IMERG_Precipitation_Rate').legend_url ?? undefined, caption: 'Precipitation rate' },
    caveat: 'Satellite estimate; light and orographic rainfall over the Tell and Atlas is uncertain.',
  },
  {
    id: 'lst-monthly-day',
    title: 'Land surface temperature (day), monthly',
    summary: 'MODIS Terra daytime land surface temperature, monthly composite.',
    domain: 'climate-drought',
    type: 'raster',
    dataset: 'modis-mod11c3-v061',
    nature: 'derived',
    tiles: gibsTiles('MODIS_Terra_L3_Land_Surface_Temp_Monthly_Day'),
    maxzoom: g('MODIS_Terra_L3_Land_Surface_Temp_Monthly_Day').max_zoom,
    time: gibsTime('MODIS_Terra_L3_Land_Surface_Temp_Monthly_Day', 'month'),
    opacity: 0.8,
    attribution: `MODIS Terra LST · ${GIBS_ATTR}`,
    legend: { kind: 'image', url: g('MODIS_Terra_L3_Land_Surface_Temp_Monthly_Day').legend_url ?? undefined, caption: 'Land surface temperature' },
    caveat: 'Land surface (skin) temperature is not air temperature.',
  },
  {
    id: 'smap-soil-moisture',
    title: 'Surface soil moisture (SMAP L3 Enhanced), daily',
    summary: 'SMAP Enhanced Level-3 radiometer surface soil moisture (top ~5 cm), 9 km (GIBS “Day” overpass layer).',
    domain: 'climate-drought',
    type: 'raster',
    dataset: 'smap-soil-moisture',
    nature: 'derived',
    tiles: gibsTiles('SMAP_L3_Passive_Enhanced_Day_Soil_Moisture'),
    maxzoom: g('SMAP_L3_Passive_Enhanced_Day_Soil_Moisture').max_zoom,
    time: gibsTime('SMAP_L3_Passive_Enhanced_Day_Soil_Moisture', 'day'),
    opacity: 0.85,
    attribution: `SMAP L3 Enhanced · ${GIBS_ATTR}`,
    legend: { kind: 'image', url: g('SMAP_L3_Passive_Enhanced_Day_Soil_Moisture').legend_url ?? undefined, caption: 'Volumetric soil moisture' },
    caveat: 'Daily swaths leave gaps between orbits; retrievals are flagged over steep terrain. Very dry desert soils sit near the retrieval lower bound.',
  },
  worldcover({
    id: 'worldcover-2021', year: 2021, version: 'v200', hash: '940d56fc80d1d9dc292442a5ab8bcfee',
  }),
  worldcover({
    id: 'worldcover-2020', year: 2020, version: 'v100', hash: '6b387e3254d00636ef84e72ea3a6f639',
  }),
  {
    id: 'gsw-occurrence',
    title: 'Surface water occurrence, 1984–2021',
    summary: 'JRC Global Surface Water: how often each 30 m pixel was observed as water by Landsat.',
    domain: 'water',
    type: 'raster',
    dataset: 'jrc-global-surface-water',
    nature: 'derived',
    tiles: 'https://storage.googleapis.com/global-surface-water/tiles2021/occurrence/{z}/{x}/{y}.png',
    maxzoom: 13,
    opacity: 1,
    attribution: 'Source: EC JRC/Google — <a href="https://global-surface-water.appspot.com/" target="_blank" rel="noopener">Global Surface Water</a> (v1.4 tiles, 1984–2021)',
    legend: { kind: 'gradient', stops: ['#fc0002', '#7f007f', '#0200fc'], labels: ['rarely water', 'permanent water'], caption: 'Water occurrence (% of valid observations)' },
    caveat: 'Small or ephemeral wadis and sebkhas may be missed or intermittently classified.',
  },
  {
    id: 'merra2-dust',
    title: 'Dust surface concentration (MERRA-2), monthly',
    summary: 'NASA MERRA-2 reanalysis dust surface mass concentration, monthly mean.',
    domain: 'hazards',
    type: 'raster',
    dataset: 'merra2-aerosol-diagnostics',
    nature: 'modeled',
    tiles: gibsTiles('MERRA2_Dust_Surface_Mass_Concentration_Monthly'),
    maxzoom: g('MERRA2_Dust_Surface_Mass_Concentration_Monthly').max_zoom,
    time: gibsTime('MERRA2_Dust_Surface_Mass_Concentration_Monthly', 'month'),
    opacity: 0.75,
    attribution: `NASA GMAO MERRA-2 · ${GIBS_ATTR}`,
    legend: { kind: 'image', url: g('MERRA2_Dust_Surface_Mass_Concentration_Monthly').legend_url ?? undefined, caption: 'Dust surface mass concentration' },
    caveat: 'Reanalysis at ~0.5° × 0.625°; not station-measured air quality.',
  },
  {
    id: 'viirs-truecolor',
    title: 'Daily satellite image (VIIRS true colour)',
    summary: 'Suomi NPP VIIRS corrected-reflectance true-colour image for a chosen day — useful for clouds, dust events and burn scars.',
    domain: 'reference',
    type: 'raster',
    dataset: null,
    nature: 'observed',
    tiles: gibsTiles('VIIRS_SNPP_CorrectedReflectance_TrueColor'),
    maxzoom: g('VIIRS_SNPP_CorrectedReflectance_TrueColor').max_zoom,
    time: gibsTime('VIIRS_SNPP_CorrectedReflectance_TrueColor', 'day'),
    opacity: 1,
    attribution: `VIIRS (Suomi NPP) · ${GIBS_ATTR}`,
    legend: { kind: 'none', caption: 'True-colour imagery' },
    caveat: 'Swath gaps and clouds occur on individual days.',
  },
  ...soilLayers(),
  ...waterClimateLayers(),
];

function waterClimateLayers(): MapLayer[] {
  const out: MapLayer[] = [];
  if (etMap) {
    const S = '/data/aeo/products/et-soil-moisture/v1.0.0/map';
    out.push({
      id: 'et-aeti',
      title: 'Actual evapotranspiration (WaPOR v3), monthly',
      summary: 'Water evaporated from soil and transpired by plants (FAO WaPOR v3, 300 m), monthly, 2018 to the latest month. Statistics by wilaya and commune, for all land and for stable cropland only.',
      domain: 'water', type: 'image', dataset: 'aeo-dza-et-soil-moisture-wapor3', nature: 'modeled',
      image: { url: `${S}/aeti_{month}.png`, coordinates: etMap.coordinates }, maxzoom: 22, time: monthly(etMap.months), opacity: 0.85,
      attribution: 'Evapotranspiration: <a href="https://data.apps.fao.org/wapor/" target="_blank" rel="noopener">FAO WaPOR v3</a> (CC BY 4.0) · AEO processing',
      legend: { kind: 'classes', caption: 'mm per month · palette ColorBrewer GnBu (WaPOR colour family)', classes: classLabels(etMap.aeti.breaks, etMap.aeti.colors) },
      caveat: 'Modelled from satellite data (surface energy balance), not measured. Shown at 2.5 km; statistics use the 1.2 km average of the 300 m maps. Recent months can be revised by FAO.',
    }, {
      id: 'sm-rsm',
      title: 'Relative soil moisture (WaPOR v3), monthly',
      summary: 'Root-zone soil moisture relative to its range (0 = wilting point, 100 = field capacity), FAO WaPOR v3, monthly mean of the 10-day maps, 2018 to the latest month.',
      domain: 'climate-drought', type: 'image', dataset: 'aeo-dza-et-soil-moisture-wapor3', nature: 'modeled',
      image: { url: `${S}/rsm_{month}.png`, coordinates: etMap.coordinates }, maxzoom: 22, time: monthly(etMap.months), opacity: 0.85,
      attribution: 'Soil moisture: <a href="https://data.apps.fao.org/wapor/" target="_blank" rel="noopener">FAO WaPOR v3</a> (CC BY 4.0) · AEO processing',
      legend: { kind: 'classes', caption: '% of the available range · palette ColorBrewer BrBG (brown dry, teal wet)', classes: classLabels(etMap.rsm.breaks, etMap.rsm.colors) },
      caveat: 'Derived by WaPOR from land surface temperature, not a microwave retrieval or field measurement. In the Sahara, with almost no vegetation, WaPOR relative soil moisture is not meaningful (values come from its surface-temperature method); read it for vegetated land and cropland.',
    });
  }
  if (cropMap) {
    out.push({
      id: 'stable-cropland',
      title: 'Stable cropland 2000–2024 (from GACED30)',
      summary: 'Share of land that GACED30 maps as cropland in at least 20 of the 25 years 2000–2024. AEO uses it as a mask: agricultural statistics and the seasonal outlook are computed over this land only.',
      domain: 'agriculture', type: 'image', dataset: 'aeo-dza-stable-cropland-gaced30', nature: 'derived',
      image: { url: '/data/aeo/products/stable-cropland/v1.0.0/map/stable_share.png', coordinates: cropMap.coordinates }, maxzoom: 22, opacity: 0.9,
      attribution: 'Cropland: <a href="https://doi.org/10.5281/zenodo.18199675" target="_blank" rel="noopener">GACED30 v1</a> (CC BY 4.0) · stable-cropland mask: AEO',
      legend: { kind: 'classes', caption: `${cropMap.units} (cells under 1 % not shown) · palette ColorBrewer YlOrBr`, classes: classLabels(cropMap.breaks, cropMap.colors).map((c, i) => (i === 0 ? { ...c, label: `1 to ${cropMap.breaks[0]}` } : c)) },
      caveat: 'Derived from a global 30 m classification without published accuracy for Algeria. Active fallow counts as cropland. Shown at about 1.2 km.',
      focusView: '6.5/35.6/3.5',
    });
  }
  if (twsMap) {
    const S = '/data/aeo/products/water-storage/v1.0.0/map';
    out.push({
      id: 'tws-grace',
      title: 'Water storage anomaly (downscaled GRACE), monthly',
      summary: 'Change in all water stored on and below the land surface (soil, groundwater, surface water), in cm of water, relative to 2004–2009. Downscaled GRACE/GRACE-FO (Li & Kusche 2026), 0.25°, 2002–2025.',
      domain: 'water', type: 'image', dataset: 'aeo-dza-water-storage-grace', nature: 'modeled',
      image: { url: `${S}/tws_{month}.png`, coordinates: twsMap.coordinates }, maxzoom: 22, time: monthly(twsMap.months), opacity: 0.8,
      attribution: 'Water storage: Li & Kusche (2026), <a href="https://doi.org/10.5281/zenodo.17265162" target="_blank" rel="noopener">Zenodo</a> (CC BY 4.0), from NASA JPL GRACE/GRACE-FO mascons · AEO processing',
      legend: { kind: 'classes', caption: 'cm of water vs 2004–2009 · red loss, blue gain (ColorBrewer RdBu, as the Copernicus Global Drought Observatory)', classes: classLabels(twsMap.tws.breaks, twsMap.tws.colors, signedFmt) },
      caveat: 'GRACE resolves about 300 km; the 0.25° detail comes from a downscaling model. Total storage, not groundwater alone. Some months are missing, including the 2017–2018 gap between missions.',
    });
  }
  if (cmipMap) {
    const S = '/data/aeo/products/climate-projections/v1.0.0/map';
    const SC: Record<string, string> = { ssp245: 'SSP2-4.5 (intermediate)', ssp585: 'SSP5-8.5 (very high)' };
    const options = cmipMap.scenarios.flatMap((s: string) => cmipMap.periods.map((p: string) => ({ id: `${s}_${p}`, label: `${SC[s]}, ${p.replace('-', '–')}` })));
    const lc = (t: string) => (/^(November|March)/.test(t) ? t : t[0].toLowerCase() + t.slice(1));
    for (const [ind, m] of Object.entries<any>(cmipMap.layers)) {
      out.push({
        id: `cmip6-${ind}`,
        title: `Projected change: ${lc(m.label)} (CMIP6)`,
        summary: `Change in ${lc(m.label)} from 1985–2014, median of 8 CMIP6 models (NASA NEX-GDDP-CMIP6, 0.25°). Choose the scenario and period; the inspector gives the model range for each wilaya and for its stable cropland.`,
        domain: 'hazards', type: 'image', dataset: 'aeo-dza-climate-projections-nexgddp', nature: 'modeled',
        image: { url: `${S}/${ind}_{variant}.png`, coordinates: cmipMap.coordinates }, maxzoom: 22,
        variants: { label: 'Scenario and period', options, default: 'ssp245_2041-2070', note: 'Projections: 30-year averages compared with 1985–2014.' }, opacity: 0.8,
        attribution: 'Projections: <a href="https://www.nccs.nasa.gov/services/data-collections/land-based-products/nex-gddp-cmip6" target="_blank" rel="noopener">NASA NEX-GDDP-CMIP6</a> · AEO processing',
        legend: { kind: 'classes', caption: `${m.units}, 8-model median · palette ColorBrewer ${m.units.includes('%') ? 'BrBG' : 'OrRd'}`, classes: classLabels(m.breaks, m.colors, m.units.includes('%') ? signedFmt : String) },
        caveat: 'Projections, not forecasts: they describe 30-year climates under an emissions scenario. Downscaled and bias-corrected to 0.25° (≈ 25 km); local detail is limited. Always read the median with the model range. For precipitation, cells with almost no rain in 1985–2014 (under 1 mm) have no % change and are left uncoloured.',
      });
    }
  }
  if (outlookMap) {
    out.push({
      id: 'outlook-nmme',
      title: 'Seasonal rainfall outlook over stable cropland (experimental)',
      summary: `Chance of below- or above-normal 3-month rainfall over each wilaya's stable cropland, from the NMME forecast issued ${outlookMap.issued}, recalibrated against CHIRPS 1991–2021. Shown only where past forecasts beat climatology; grey = no usable skill, equal chances.`,
      domain: 'climate-drought', type: 'choropleth', dataset: 'aeo-dza-seasonal-outlook-nmme', nature: 'modeled',
      choropleth: { url: '/data/aeo/products/seasonal-outlook/v0.1.0/web/choropleth.json', key: 'v', scale: outlookMap.targets[0], breaks: outlookMap.breaks, colors: outlookMap.colors, flag: 'none', flagColor: '#c9ced3' },
      variants: { label: 'Target season', options: outlookMap.targets.map((t: string) => ({ id: t, label: outlookMap.labels[t] })), default: outlookMap.targets[0], note: `Forecast issued ${outlookMap.issued}.` },
      maxzoom: 22, opacity: 0.8,
      attribution: 'Forecast: NMME (NOAA CPC) · observations: CHIRPS v3.0 · calibration and verification: AEO (experimental)',
      legend: { kind: 'classes', caption: 'tercile probability; grey = not skilful (equal chances) or too little cropland', classes: outlookMap.colors.map((c: string, i: number) => ({ color: c, label: outlookMap.class_labels[i] })) },
      caveat: 'Experimental test. Seasonal rainfall forecasts for North Africa have low skill; read every probability together with its verification on the Drought page.',
    });
  }
  return out;
}

/** SoilGrids 2.0 properties summarised by AEO: one indicator per property, depth as a variant. */
function soilLayers(): MapLayer[] {
  if (!soilMap) return [];
  const SOIL_SITE = '/data/aeo/products/soil/v1.0.0/map';
  const props: Record<string, string> = {};
  for (const [id, m] of Object.entries(soilMap.layers)) props[id.split('_')[0]] = m.label;
  const DEPTH_LABEL: Record<string, string> = { '0-5cm': '0–5 cm', '5-15cm': '5–15 cm', '15-30cm': '15–30 cm', '0-30cm': '0–30 cm' };
  return Object.entries(props).map(([prop, label]) => {
    const ids = Object.keys(soilMap.layers).filter((k) => k.startsWith(`${prop}_`));
    const first = soilMap.layers[ids[0]];
    return {
      id: `soil-${prop}`,
      title: `${label} (SoilGrids 2.0)`,
      summary: `${label} predicted by ISRIC SoilGrids 2.0 (machine-learning model, 250 m, shown at 1 km), summarised by AEO for Algeria. Model predictions, not field measurements. Choose the depth interval.`,
      domain: 'soil' as DomainId,
      type: 'image' as const,
      dataset: 'aeo-dza-soil-soilgrids',
      nature: 'modeled' as const,
      image: { url: `${SOIL_SITE}/${prop}_{variant}.png`, coordinates: soilMap.coordinates },
      maxzoom: 22,
      variants: { label: 'Depth', options: ids.map((k) => ({ id: k.slice(prop.length + 1), label: DEPTH_LABEL[k.slice(prop.length + 1)] ?? k })), default: ids[0].slice(prop.length + 1), note: 'Static map: SoilGrids predictions have no time dimension.' },
      opacity: 0.85,
      attribution: 'Soil: ISRIC SoilGrids 2.0 (Poggio et al. 2021, CC BY 4.0) · AEO processing',
      legend: { kind: 'classes' as const, caption: `${first.units}; classes from Algerian pixel quantiles`, classes: first.colors.map((c, i) => ({ color: c, label: i === 0 ? `< ${first.breaks[0]}` : i === first.breaks.length ? `≥ ${first.breaks[i - 1]}` : `${first.breaks[i - 1]}–${first.breaks[i]}` })) },
      caveat: 'Model predictions with large uncertainty in Algeria, where few soil profiles were available to the model. Display resampled to 2 km; statistics use the 1 km grid.',
    };
  });
}

/** Legend classes of a soil layer for one depth (the classes differ by depth). */
export function soilLegend(id: string, variant: string) {
  const m = soilMap?.layers[`${id.replace(/^soil-/, '')}_${variant}`];
  if (!m) return null;
  return { caption: `${m.units}; classes from Algerian pixel quantiles`, classes: m.colors.map((c, i) => ({ color: c, label: i === 0 ? `< ${m.breaks[0]}` : i === m.breaks.length ? `≥ ${m.breaks[i - 1]}` : `${m.breaks[i - 1]}–${m.breaks[i]}` })) };
}

export const BASEMAPS = [
  {
    id: 'light',
    title: 'Light with relief',
    style: 'https://tiles.openfreemap.org/styles/positron',
    relief: gibsTiles('ASTER_GDEM_Greyscale_Shaded_Relief'),
    attribution: '<a href="https://openfreemap.org" target="_blank" rel="noopener">OpenFreeMap</a> © <a href="https://www.openmaptiles.org/" target="_blank" rel="noopener">OpenMapTiles</a> Data from <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> · relief: ASTER GDEM (NASA/METI) via ' + GIBS_ATTR,
  },
  {
    id: 'streets',
    title: 'Detailed (OpenStreetMap)',
    style: 'https://tiles.openfreemap.org/styles/liberty',
    attribution: '<a href="https://openfreemap.org" target="_blank" rel="noopener">OpenFreeMap</a> © <a href="https://www.openmaptiles.org/" target="_blank" rel="noopener">OpenMapTiles</a> Data from <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>',
  },
  {
    id: 'satellite',
    title: 'Satellite composite (Blue Marble)',
    raster: gibsTiles('BlueMarble_NextGeneration'),
    maxzoom: g('BlueMarble_NextGeneration').max_zoom,
    attribution: `NASA Blue Marble: Next Generation · ${GIBS_ATTR}`,
  },
  {
    id: 'relief',
    title: 'Shaded relief (ASTER GDEM)',
    raster: gibsTiles('ASTER_GDEM_Greyscale_Shaded_Relief'),
    maxzoom: g('ASTER_GDEM_Greyscale_Shaded_Relief').max_zoom,
    attribution: `ASTER GDEM (NASA/METI) · ${GIBS_ATTR}`,
  },
] as const;

/** Initial view framing all of Algeria. */
export const ALGERIA_BOUNDS: [number, number, number, number] = [-8.7, 18.9, 12.0, 37.2];
