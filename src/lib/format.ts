import type { Dataset } from '../content.config';

export const STATUS: Record<Dataset['status'], { label: string; help: string; cls: string }> = {
  available: {
    label: 'Available',
    help: 'Distributed by AEO with a direct download, version and checksum.',
    cls: 'bg-[#e3f4ee] text-[#0b5d45] border-[#9fd6c2]',
  },
  external: {
    label: 'External source',
    help: 'Held by the original provider. AEO documents it and links to the source; it does not host the files.',
    cls: 'bg-[#e8f1fa] text-[#124f87] border-[#a9c9ea]',
  },
  experimental: {
    label: 'Experimental',
    help: 'An AEO product released for testing. Files are real, but the method may change and validation is incomplete.',
    cls: 'bg-[#fdf1e4] text-[#8a4b0f] border-[#f0c99a]',
  },
  'under-validation': {
    label: 'Under validation',
    help: 'An AEO product whose method is fixed and whose validation is in progress.',
    cls: 'bg-[#f1ecfa] text-[#4c3a87] border-[#cbbfec]',
  },
  'in-preparation': {
    label: 'Planned',
    help: 'A planned AEO product. No data are released until scientific review is complete.',
    cls: 'bg-sand-100 text-[#6b5228] border-sand',
  },
  archived: {
    label: 'Deprecated',
    help: 'Kept for reference; superseded or no longer maintained.',
    cls: 'bg-[#eef0f2] text-[#4a5a66] border-[#cfd6dc]',
  },
};

export const NATURE: Record<NonNullable<Dataset['data_nature']>, { label: string; help: string }> = {
  observed: { label: 'Observed', help: 'Direct measurements or imagery (e.g. surface reflectance, gauge records).' },
  derived: { label: 'Derived', help: 'Produced by an algorithm from observations (e.g. classifications, indices, satellite–gauge blends). Not ground truth.' },
  modeled: { label: 'Modeled', help: 'Model output: reanalysis, statistical estimates, simulations or projections. Not direct observation.' },
};

export const COVERAGE: Record<string, string> = {
  global: 'Global',
  continental: 'Continental',
  regional: 'Regional',
  algeria: 'Algeria',
};

export const SUBSET: Record<string, string> = {
  extract: 'Algeria must be extracted by the user',
  'country-file': 'Provider offers an Algeria file',
  native: 'Algeria-specific product',
};

export const DATA_TYPE: Record<string, string> = {
  raster: 'Raster',
  vector: 'Vector',
  tabular: 'Tabular',
  imagery: 'Satellite imagery',
  point: 'Point records',
};

export const ORIGIN: Record<Dataset['origin'], string> = {
  external: 'External dataset',
  'aeo-derived': 'AEO-derived (from external sources)',
  'aeo-original': 'AEO original product',
};

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
export function fmtDate(iso?: string | null): string {
  if (!iso) return '—';
  const [y, m, d] = iso.split('-').map(Number);
  return `${d} ${MONTHS[m - 1]} ${y}`;
}

export function period(d: Dataset): string {
  const t = d.temporal_extent;
  if (!t) return '—';
  const s = t.start ? t.start.slice(0, 4) : '?';
  const e = t.ongoing ? 'present' : t.end ? t.end.slice(0, 4) : '?';
  if (s === e) return s;
  return `${s}–${e}`;
}

/** Resolution class used by the catalog filter. */
export function resolutionBucket(d: Dataset): string {
  const m = d.resolution?.spatial_m;
  if (m == null) return 'n/a';
  if (m <= 30) return '≤ 30 m';
  if (m <= 1000) return '30 m – 1 km';
  if (m <= 10000) return '1 – 10 km';
  return '> 10 km';
}
export const RES_BUCKETS = ['≤ 30 m', '30 m – 1 km', '1 – 10 km', '> 10 km', 'n/a'];

/** Period class used by the catalog filter (a record can belong to several). */
export function periodBuckets(d: Dataset): string[] {
  const t = d.temporal_extent;
  if (!t?.start) return [];
  const s = Number(t.start.slice(0, 4));
  const e = t.ongoing || !t.end ? new Date().getFullYear() : Number(t.end.slice(0, 4));
  const out: string[] = [];
  if (s < 2000) out.push('Before 2000');
  if (s <= 2015 && e >= 2000) out.push('2000–2015');
  if (e >= 2016) out.push('2016 onward');
  if (t.ongoing) out.push('Ongoing updates');
  return out;
}
export const PERIOD_BUCKETS = ['Before 2000', '2000–2015', '2016 onward', 'Ongoing updates'];

/** Normalised format families used by the catalog filter. */
export function formatFamilies(d: Dataset): string[] {
  const fam = new Set<string>();
  for (const f of d.format) {
    const s = f.toLowerCase();
    if (s.includes('tif')) fam.add('GeoTIFF');
    if (s.includes('netcdf') || s.includes('nc4') || s.includes('.nc')) fam.add('NetCDF');
    if (s.includes('hdf')) fam.add('HDF');
    if (s.includes('geojson')) fam.add('GeoJSON');
    if (s.includes('shapefile') || s.includes('shp')) fam.add('Shapefile');
    if (s.includes('geopackage') || s.includes('gpkg')) fam.add('GeoPackage');
    if (s.includes('csv')) fam.add('CSV');
    if (s.includes('grib')) fam.add('GRIB');
    if (s.includes('zarr')) fam.add('Zarr');
    if (s.includes('jp2') || s.includes('safe')) fam.add('SAFE / JP2');
    if (s.includes('vrt')) fam.add('VRT');
  }
  if (fam.size === 0 && d.format.length) fam.add('Other');
  return [...fam];
}

export function accessMode(d: Dataset): 'direct' | 'external' | 'none' {
  if (d.status === 'in-preparation') return 'none';
  if (d.access.some((a) => a.kind === 'download') || d.download_url) return 'direct';
  return 'external';
}

export function doiUrl(doi?: string | null) {
  return doi ? `https://doi.org/${doi}` : null;
}

export function humanBytes(n?: number | null): string | null {
  if (!n) return null;
  const u = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0;
  let v = n;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(v >= 10 || i === 0 ? 0 : 1)} ${u[i]}`;
}

export function hostOf(u: string) {
  try { return new URL(u).hostname.replace(/^www\./, ''); } catch { return u; }
}
