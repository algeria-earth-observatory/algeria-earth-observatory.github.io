/**
 * Shared MapLibre logic for the AEO map explorer and the homepage preview.
 *
 * The explorer state (basemap, active overlays, opacity, dates) is the single
 * source of truth: switching basemap rebuilds the whole style from it, while
 * per-layer changes are applied to the live map.
 */
import maplibregl, { type StyleSpecification, type LayerSpecification, type Map as MLMap } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { MAP_LAYERS, BASEMAPS, ALGERIA_BOUNDS, type MapLayer } from '../data/map-layers';

export { MAP_LAYERS, BASEMAPS, ALGERIA_BOUNDS };
export type BasemapId = (typeof BASEMAPS)[number]['id'];

const GLYPHS = 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf';
const LABEL_FONT = ['Noto Sans Regular'];

export interface LayerState { on: boolean; opacity: number; time: string | null }
export interface MapState { basemap: BasemapId; layers: Record<string, LayerState> }

// ---------------------------------------------------------------- time axis
function addStep(d: Date, step: string) {
  const n = new Date(d);
  if (step === 'P1D') n.setUTCDate(n.getUTCDate() + 1);
  else if (step === 'P16D') n.setUTCDate(n.getUTCDate() + 16);
  else if (step === 'P8D') n.setUTCDate(n.getUTCDate() + 8);
  else if (step === 'P1M') n.setUTCMonth(n.getUTCMonth() + 1);
  else if (step === 'P1Y') n.setUTCFullYear(n.getUTCFullYear() + 1);
  else n.setUTCDate(n.getUTCDate() + 1);
  return n;
}
const iso = (d: Date) => d.toISOString().slice(0, 10);
const cache = new Map<string, string[]>();
/** Expand GIBS "start/end/period" strings into the sorted list of valid dates. */
export function availableDates(layer: MapLayer): string[] {
  if (!layer.time) return [];
  if (cache.has(layer.id)) return cache.get(layer.id)!;
  const out: string[] = [];
  for (const p of layer.time.periods) {
    const [s, e, step] = p.split('/');
    let d = new Date(`${s}T00:00:00Z`);
    const end = new Date(`${e}T00:00:00Z`);
    let guard = 0;
    while (d <= end && guard++ < 20000) { out.push(iso(d)); d = addStep(d, step); }
  }
  const sorted = [...new Set(out)].sort();
  cache.set(layer.id, sorted);
  return sorted;
}
/** Latest available date on or before `wanted` (or the earliest one). */
export function snapDate(layer: MapLayer, wanted: string): string | null {
  const ds = availableDates(layer);
  if (!ds.length) return null;
  let lo = 0, hi = ds.length - 1, best = 0;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (ds[mid] <= wanted) { best = mid; lo = mid + 1; } else hi = mid - 1;
  }
  return ds[wanted < ds[0] ? 0 : best];
}
export function stepDate(layer: MapLayer, current: string, dir: 1 | -1): string {
  const ds = availableDates(layer);
  const i = ds.indexOf(current);
  return ds[Math.min(ds.length - 1, Math.max(0, (i < 0 ? ds.length - 1 : i) + dir))];
}
export const defaultDate = (l: MapLayer) => (l.time ? l.time.default ?? availableDates(l).at(-1) ?? null : null);
const searchIds = new Map<string, string>();
const tileUrl = (l: MapLayer, time: string | null) =>
  (l.tiles ?? '').replace('{time}', time ?? '').replace('{search}', searchIds.get(l.id) ?? l.mosaic?.fallback ?? '');

const pending = new Map<string, Promise<void>>();
/** Register a Planetary Computer mosaic search for the layer (once per page load). */
export function resolveMosaic(l: MapLayer): Promise<void> {
  if (!l.mosaic) return Promise.resolve();
  if (!pending.has(l.id)) {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), 8000);
    pending.set(l.id, fetch(l.mosaic.register, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(l.mosaic.body), signal: ctl.signal,
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((j: { searchid?: string } | null) => { if (j?.searchid) searchIds.set(l.id, j.searchid); })
      .catch(() => {})
      .finally(() => clearTimeout(timer)));
  }
  return pending.get(l.id)!;
}
/** Point a live raster source at its current tile URL (after a mosaic was resolved). */
export function refreshTiles(map: MLMap, l: MapLayer, time: string | null) {
  const src = map.getSource(`aeo-${l.id}`) as maplibregl.RasterTileSource | undefined;
  if (src && 'setTiles' in src) src.setTiles([tileUrl(l, time)]);
}

// ---------------------------------------------------------------- style
const styleCache = new Map<string, StyleSpecification>();
async function baseStyle(id: BasemapId): Promise<StyleSpecification> {
  const b = BASEMAPS.find((x) => x.id === id) ?? BASEMAPS[0];
  if (styleCache.has(b.id)) return structuredClone(styleCache.get(b.id)!);
  let s: StyleSpecification;
  if ('style' in b) {
    const res = await fetch(b.style);
    s = (await res.json()) as StyleSpecification;
  } else {
    s = {
      version: 8,
      glyphs: GLYPHS,
      sources: { 'base-raster': { type: 'raster', tiles: [b.raster], tileSize: 256, maxzoom: b.maxzoom, attribution: b.attribution } },
      layers: [
        { id: 'base-bg', type: 'background', paint: { 'background-color': '#0e2a3e' } },
        { id: 'base-raster', type: 'raster', source: 'base-raster' },
      ],
    };
  }
  styleCache.set(b.id, s);
  return structuredClone(s);
}

let wilayaData: GeoJSON.FeatureCollection | null = null;
export async function loadWilayas(): Promise<GeoJSON.FeatureCollection> {
  if (wilayaData) return wilayaData;
  const l = MAP_LAYERS.find((x) => x.id === 'wilayas')!;
  wilayaData = (await (await fetch(l.data!)).json()) as GeoJSON.FeatureCollection;
  return wilayaData;
}

export async function buildStyle(state: MapState): Promise<StyleSpecification> {
  const s = await baseStyle(state.basemap);
  s.glyphs = s.glyphs ?? GLYPHS;
  const firstSymbol = s.layers.findIndex((l) => l.type === 'symbol');
  const below: LayerSpecification[] = [];
  const above: LayerSpecification[] = [];
  const dark = state.basemap === 'satellite';

  for (const l of MAP_LAYERS) {
    const st = state.layers[l.id];
    const vis = st?.on ? 'visible' : 'none';
    if (l.type === 'raster') {
      s.sources[`aeo-${l.id}`] = {
        type: 'raster', tiles: [tileUrl(l, st?.time ?? defaultDate(l))], tileSize: 256,
        ...(l.minzoom ? { minzoom: l.minzoom } : {}),
        maxzoom: l.maxzoom, attribution: l.attribution,
      };
      below.push({ id: `aeo-${l.id}`, type: 'raster', source: `aeo-${l.id}`, layout: { visibility: vis }, paint: { 'raster-opacity': st?.opacity ?? l.opacity, 'raster-fade-duration': 0 } });
    }
  }
  // Wilaya boundaries (vector) always sit on top of raster overlays.
  const w = MAP_LAYERS.find((x) => x.id === 'wilayas')!;
  const wst = state.layers.wilayas;
  const wvis = wst?.on ? 'visible' : 'none';
  s.sources['aeo-wilayas'] = { type: 'geojson', data: await loadWilayas(), promoteId: 'wilaya_code', attribution: w.attribution };
  const line = dark ? '#F7F9FA' : '#143B56';
  above.push(
    { id: 'aeo-wilayas-fill', type: 'fill', source: 'aeo-wilayas', layout: { visibility: wvis },
      paint: { 'fill-color': '#176BBA', 'fill-opacity': ['case', ['boolean', ['feature-state', 'selected'], false], 0.18, ['boolean', ['feature-state', 'hover'], false], 0.08, 0] } },
    { id: 'aeo-wilayas-line', type: 'line', source: 'aeo-wilayas', layout: { visibility: wvis, 'line-join': 'round' },
      paint: { 'line-color': line, 'line-width': ['interpolate', ['linear'], ['zoom'], 4, 0.6, 8, 1.4], 'line-opacity': (wst?.opacity ?? 1) * 0.8 } },
    { id: 'aeo-wilayas-selected', type: 'line', source: 'aeo-wilayas', layout: { visibility: wvis },
      paint: { 'line-color': '#176BBA', 'line-width': ['case', ['boolean', ['feature-state', 'selected'], false], 3, 0] } },
    { id: 'aeo-wilayas-label', type: 'symbol', source: 'aeo-wilayas', minzoom: 5.2,
      layout: { visibility: wvis, 'text-field': ['get', 'name'], 'text-font': LABEL_FONT, 'text-size': 11.5, 'text-max-width': 8 },
      paint: { 'text-color': dark ? '#F7F9FA' : '#143B56', 'text-halo-color': dark ? '#0E2A3E' : '#FFFFFF', 'text-halo-width': 1.4 } },
  );
  const at = firstSymbol < 0 ? s.layers.length : firstSymbol;
  s.layers = [...s.layers.slice(0, at), ...below, ...s.layers.slice(at), ...above];
  return s;
}

// ---------------------------------------------------------------- live updates
export function setLayerVisible(map: MLMap, id: string, on: boolean) {
  const ids = id === 'wilayas' ? ['aeo-wilayas-fill', 'aeo-wilayas-line', 'aeo-wilayas-selected', 'aeo-wilayas-label'] : [`aeo-${id}`];
  for (const lid of ids) if (map.getLayer(lid)) map.setLayoutProperty(lid, 'visibility', on ? 'visible' : 'none');
}
export function setLayerOpacity(map: MLMap, id: string, v: number) {
  if (id === 'wilayas') { if (map.getLayer('aeo-wilayas-line')) map.setPaintProperty('aeo-wilayas-line', 'line-opacity', v * 0.8); return; }
  if (map.getLayer(`aeo-${id}`)) map.setPaintProperty(`aeo-${id}`, 'raster-opacity', v);
}
export function setLayerTime(map: MLMap, layer: MapLayer, time: string) {
  const src = map.getSource(`aeo-${layer.id}`) as maplibregl.RasterTileSource | undefined;
  if (src && 'setTiles' in src) src.setTiles([tileUrl(layer, time)]);
}

export function bboxOf(f: GeoJSON.Feature): [number, number, number, number] {
  let w = 180, s = 90, e = -180, n = -90;
  const visit = (c: unknown): void => {
    if (Array.isArray(c) && typeof c[0] === 'number') {
      const [x, y] = c as number[];
      if (x < w) w = x; if (x > e) e = x; if (y < s) s = y; if (y > n) n = y;
    } else if (Array.isArray(c)) c.forEach(visit);
  };
  visit((f.geometry as GeoJSON.Polygon | GeoJSON.MultiPolygon).coordinates);
  return [w, s, e, n];
}

export function escapeHtml(s: unknown) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!);
}

export function wilayaPopupHtml(p: Record<string, unknown>) {
  return `<div class="aeo-pop">
    <p class="aeo-pop-k">Wilaya ${escapeHtml(p.wilaya_code)}</p>
    <p class="aeo-pop-t">${escapeHtml(p.name)}</p>
    ${p.name_ar ? `<p class="aeo-pop-ar" lang="ar" dir="rtl">${escapeHtml(p.name_ar)}</p>` : ''}
    <dl>
      <dt>ISO 3166-2</dt><dd>${p.iso_3166_2 ? escapeHtml(p.iso_3166_2) : '<span title="Not tagged in OSM">—</span>'}</dd>
      <dt>Area (computed)</dt><dd>${Number(p.area_km2).toLocaleString('en-US')} km²</dd>
      <dt>Source</dt><dd><a href="https://www.openstreetmap.org/relation/${escapeHtml(p.osm_relation)}" target="_blank" rel="noopener">OSM relation ${escapeHtml(p.osm_relation)}</a></dd>
      <dt>Snapshot</dt><dd>${escapeHtml(p.snapshot)}</dd>
    </dl>
    <p class="aeo-pop-n">Simplified display geometry. <a href="/data/aeo-dza-admin-boundaries/">Boundary dataset</a></p>
  </div>`;
}

export function createMap(container: HTMLElement, style: StyleSpecification, opts: Partial<maplibregl.MapOptions> = {}) {
  return new maplibregl.Map({
    container,
    style,
    bounds: ALGERIA_BOUNDS,
    fitBoundsOptions: { padding: 24 },
    maxZoom: 13,
    attributionControl: { compact: window.matchMedia('(max-width: 640px)').matches },
    ...opts,
  });
}

export { maplibregl };
