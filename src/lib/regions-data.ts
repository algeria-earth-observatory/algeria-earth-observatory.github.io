/**
 * Build-time access to administrative units and their published statistics.
 * Reads the files in public/ (boundaries + product JSON); never invents values —
 * a missing statistic is returned as null and shown as "not available".
 */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

export const BOUNDARY_VERSION = '2026-11-20';
const PUB = join(process.cwd(), 'public');
const read = (p: string) => JSON.parse(readFileSync(join(PUB, p), 'utf-8'));

export interface Trend { period: string; n: number; slope_mm_per_decade: number | null; ci95_low: number | null; ci95_high: number | null; mk_p: number | null; autocorrelation_corrected: boolean }
export interface PrecipStats { normal: number | null; years: number[]; annual: (number | null)[]; trend: Trend; support: string; effective_cells: number; last: { year: number; value: number | null; anomaly_pct: number | null }; driest: [number, number] | null; wettest: [number, number] | null }
export interface Wilaya { code: string; name: string; name_ar: string | null; name_en: string | null; iso: string | null; area_km2: number; n_communes: number; osm_relation: number; wikidata: string | null; precip: PrecipStats | null }
export interface Commune { code: string; name: string; name_ar: string | null; wilaya_code: string; wilaya_name: string; code_1984: string; area_km2: number; osm_relation: number; wikidata: string | null; precip: PrecipStats | null }

let cache: { national: PrecipStats | null; wilayas: Wilaya[]; communes: Commune[] } | null = null;

function precipFor(file: any, i: number): PrecipStats {
  const vals: (number | null)[] = file.annual[i];
  const normal = file.normal[i];
  const pairs = file.years.map((y: number, k: number) => [y, vals[k]]).filter(([, v]: any) => v !== null) as [number, number][];
  const lastY = file.years[file.years.length - 1];
  const lastV = vals[vals.length - 1];
  return {
    normal, years: file.years, annual: vals, trend: file.trend[i],
    support: file.units[i].support, effective_cells: file.units[i].effective_cells,
    last: { year: lastY, value: lastV, anomaly_pct: lastV !== null && normal ? Math.round((1000 * (lastV - normal)) / normal) / 10 : null },
    driest: pairs.length ? pairs.reduce((a, b) => (b[1] < a[1] ? b : a)) : null,
    wettest: pairs.length ? pairs.reduce((a, b) => (b[1] > a[1] ? b : a)) : null,
  };
}

export function loadRegions() {
  if (cache) return cache;
  const adm1 = read(`data/aeo/boundaries/${BOUNDARY_VERSION}/dza_adm1_wilayas.geojson`).features.map((f: any) => f.properties);
  const csv = readFileSync(join(PUB, `data/aeo/boundaries/${BOUNDARY_VERSION}/dza_admin_units.csv`), 'utf-8').trim().split(/\r?\n/);
  const head = csv[0].split(',');
  const rows = csv.slice(1).map((line) => {
    const out: string[] = []; let cur = '', q = false;
    for (const ch of line) { if (ch === '"') q = !q; else if (ch === ',' && !q) { out.push(cur); cur = ''; } else cur += ch; }
    out.push(cur);
    return Object.fromEntries(head.map((h, i) => [h, out[i]]));
  });
  let p0: any = null, p1: any = null, p2: any = null;
  try {
    const base = 'data/aeo/products/precipitation/v1.0.0/web';
    p0 = read(`${base}/annual_admin0.json`); p1 = read(`${base}/annual_admin1.json`); p2 = read(`${base}/annual_admin2.json`);
  } catch { /* product not built: pages show "not available" */ }
  const i1 = new Map<string, number>(p1?.units.map((u: any, i: number) => [u.code, i]) ?? []);
  const i2 = new Map<string, number>(p2?.units.map((u: any, i: number) => [u.code, i]) ?? []);
  const wilayas: Wilaya[] = adm1.map((w: any) => ({
    code: w.wilaya_code, name: w.name, name_ar: w.name_ar, name_en: w.name_en, iso: w.iso_3166_2,
    area_km2: w.area_km2, n_communes: w.n_communes, osm_relation: w.osm_relation, wikidata: w.wikidata,
    precip: i1.has(w.wilaya_code) ? precipFor(p1, i1.get(w.wilaya_code)!) : null,
  })).sort((a: Wilaya, b: Wilaya) => a.code.localeCompare(b.code));
  const communes: Commune[] = rows.map((r) => ({
    code: r.commune_code, name: r.name, name_ar: r.name_ar || null, wilaya_code: r.wilaya_code, wilaya_name: r.wilaya_name,
    code_1984: r.wilaya_code_1984, area_km2: Number(r.area_km2), osm_relation: Number(r.osm_relation), wikidata: r.wikidata || null,
    precip: i2.has(r.commune_code) ? precipFor(p2, i2.get(r.commune_code)!) : null,
  }));
  cache = { national: p0 ? precipFor(p0, 0) : null, wilayas, communes };
  return cache;
}

/** Legal origin of a wilaya code (see research/wilaya_geography.md). */
export function wilayaOrigin(code: string) {
  const n = Number(code);
  if (n <= 48) return 'One of the 48 wilayas of the 1984 territorial organisation (Loi n° 84-09).';
  if (n <= 58) return 'Created by Loi n° 19-12 (2019); name and chef-lieu fixed by Décret présidentiel n° 21-117 (2021).';
  return 'Created by Loi n° 26-06 of 4 April 2026 (JO n° 25); name and chef-lieu fixed by Décret présidentiel n° 26-206 (JO n° 40, 2026). Transfer of prerogatives from the mother wilaya is due by 31 December 2026.';
}

export const fmtNum = (v: number | null | undefined, d = 0) =>
  v === null || v === undefined ? '—' : v.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
export const fmtSigned = (v: number | null | undefined, d = 0) =>
  v === null || v === undefined ? '—' : `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d })}`;
export function trendText(t: Trend | null | undefined) {
  if (!t || t.slope_mm_per_decade === null || t.mk_p === null) return 'not available';
  const sig = t.mk_p < 0.05 ? 'significant (p < 0.05)' : `not significant (p = ${t.mk_p.toFixed(2)})`;
  return `${fmtSigned(t.slope_mm_per_decade, 1)} mm/decade (95 % CI ${fmtSigned(t.ci95_low, 1)} to ${fmtSigned(t.ci95_high, 1)}), ${sig}`;
}
