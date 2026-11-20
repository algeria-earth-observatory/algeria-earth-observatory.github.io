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
import type { DomainId } from '../lib/domains';

type GibsId = keyof typeof gibs.layers;

export interface Legend {
  kind: 'image' | 'gradient' | 'line' | 'none';
  url?: string;
  stops?: string[];
  labels?: [string, string];
  caption?: string;
}

export interface MapLayer {
  id: string;
  title: string;
  summary: string;
  domain: DomainId | 'reference';
  type: 'raster' | 'geojson';
  dataset: string | null;
  nature: 'observed' | 'derived' | 'modeled' | 'reference';
  /** Raster tile URL template ({z}/{x}/{y}; {time} replaced at runtime). */
  tiles?: string;
  /** GeoJSON URL (site-relative). */
  data?: string;
  minzoom?: number;
  maxzoom: number;
  time?: { periods: string[]; default: string | null; step: 'day' | '16-day' | 'month' | 'year' };
  opacity: number;
  attribution: string;
  legend: Legend;
  caveat?: string;
  defaultOn?: boolean;
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

export const BOUNDARY_VERSION = '2026-11-19';
const BDIR = `/data/aeo/boundaries/${BOUNDARY_VERSION}`;

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
];

export const BASEMAPS = [
  {
    id: 'light',
    title: 'Light (OpenStreetMap)',
    style: 'https://tiles.openfreemap.org/styles/positron',
    attribution: '<a href="https://openfreemap.org" target="_blank" rel="noopener">OpenFreeMap</a> © <a href="https://www.openmaptiles.org/" target="_blank" rel="noopener">OpenMapTiles</a> Data from <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>',
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
