/**
 * Client-side access to the AEO precipitation product (CHIRPS v3.0) — the JSON files
 * written by scripts/pipelines/precip/build_precip.py. No values are generated here:
 * aggregates are sums of the published monthly unit means.
 */
import { theilSen, mannKendall } from './trend.js';

export const PRECIP = {
  id: 'aeo-dza-precipitation-chirps3',
  version: '1.0.0',
  base: '/data/aeo/products/precipitation/v1.0.0',
  datasetPage: '/data/aeo-dza-precipitation-chirps3/',
  methodPage: '/docs/method-precipitation/',
};

export type Level = 'admin0' | 'admin1' | 'admin2';
export interface Unit { code: string; name: string; name_ar: string | null; parent: string | null; support: string; effective_cells: number }
export interface AnnualFile {
  product: string; version: string; level: Level; boundary_version: string; years: number[]; baseline: [number, number];
  units: Unit[]; annual: (number | null)[][]; normal: (number | null)[];
  trend: { period: string; n: number; slope_mm_per_decade: number | null; ci95_low: number | null; ci95_high: number | null; mk_p: number | null; mk_tau: number | null; autocorrelation_corrected: boolean }[];
}
export interface MonthlyFile { product: string; version: string; level: Level; months: string[]; units: string[]; monthly: (number | null)[][]; normal_monthly: (number | null)[][] }

const cache = new Map<string, Promise<unknown>>();
function getJson<T>(url: string): Promise<T> {
  if (!cache.has(url)) cache.set(url, fetch(url).then((r) => { if (!r.ok) throw new Error(`${r.status} ${url}`); return r.json(); }));
  return cache.get(url) as Promise<T>;
}
export const loadAnnual = (level: Level) => getJson<AnnualFile>(`${PRECIP.base}/web/annual_${level}.json`);
export function loadMonthly(level: Level, wilaya?: string) {
  return getJson<MonthlyFile>(level === 'admin2' ? `${PRECIP.base}/web/monthly_admin2/${wilaya}.json` : `${PRECIP.base}/web/monthly_${level}.json`);
}

// ------------------------------------------------------------------ aggregation
export type Agg = 'year' | 'hydro' | 'DJF' | 'MAM' | 'JJA' | 'SON' | `m${number}`;
export const AGGREGATIONS: { id: Agg; label: string; short: string }[] = [
  { id: 'year', label: 'Calendar year (January–December)', short: 'Year' },
  { id: 'hydro', label: 'Agricultural year (September–August)', short: 'Sep–Aug' },
  { id: 'SON', label: 'Autumn (September–November)', short: 'SON' },
  { id: 'DJF', label: 'Winter (December–February)', short: 'DJF' },
  { id: 'MAM', label: 'Spring (March–May)', short: 'MAM' },
  { id: 'JJA', label: 'Summer (June–August)', short: 'JJA' },
  ...['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
    .map((m, i) => ({ id: `m${i + 1}` as Agg, label: m, short: m.slice(0, 3) })),
];

/** Months (1-12) and year offset (0 = key year, -1 = previous year) of each aggregate. */
function monthsOf(agg: Agg): [number, number][] {
  if (agg === 'year') return Array.from({ length: 12 }, (_, i) => [i + 1, 0]);
  if (agg === 'hydro') return [[9, -1], [10, -1], [11, -1], [12, -1], [1, 0], [2, 0], [3, 0], [4, 0], [5, 0], [6, 0], [7, 0], [8, 0]];
  if (agg === 'DJF') return [[12, -1], [1, 0], [2, 0]];
  if (agg === 'MAM') return [[3, 0], [4, 0], [5, 0]];
  if (agg === 'JJA') return [[6, 0], [7, 0], [8, 0]];
  if (agg === 'SON') return [[9, 0], [10, 0], [11, 0]];
  return [[Number(agg.slice(1)), 0]];
}

export function periodLabel(agg: Agg, year: number) {
  if (agg === 'hydro') return `Sep ${year - 1}–Aug ${year}`;
  if (agg === 'DJF') return `Dec ${year - 1}–Feb ${year}`;
  return String(year);
}

export interface Series { keys: number[]; values: (number | null)[]; normal: number | null; anomalies: (number | null)[]; anomaliesPct: (number | null)[] }

/**
 * Totals of `agg` for every key year whose months are all available. For 'year' the
 * published annual values are used directly (identical to the sum of monthly means
 * up to rounding); otherwise monthly means are summed.
 */
export function aggregate(agg: Agg, unitIndex: number, annual: AnnualFile, monthly?: MonthlyFile, monthlyIndex?: number): Series {
  let keys: number[], values: (number | null)[];
  if (agg === 'year') {
    keys = annual.years.slice();
    values = annual.annual[unitIndex].slice();
  } else {
    if (!monthly || monthlyIndex === undefined) throw new Error('monthly data required');
    const pos = new Map(monthly.months.map((m, i) => [m, i]));
    const row = monthly.monthly[monthlyIndex];
    const first = Number(monthly.months[0].slice(0, 4));
    const last = Number(monthly.months[monthly.months.length - 1].slice(0, 4));
    keys = []; values = [];
    for (let y = first; y <= last; y++) {
      let sum = 0, ok = true;
      for (const [m, off] of monthsOf(agg)) {
        const i = pos.get(`${y + off}-${String(m).padStart(2, '0')}`);
        const v = i === undefined ? null : row[i];
        if (v === null || v === undefined) { ok = false; break; }
        sum += v;
      }
      if (ok) { keys.push(y); values.push(Math.round(sum * 10) / 10); }
    }
  }
  const [b0, b1] = annual.baseline;
  const base = values.filter((_, i) => keys[i] >= b0 && keys[i] <= b1) as number[];
  const complete = base.length === b1 - b0 + 1;
  const normal = complete ? Math.round((base.reduce((a, b) => a + b, 0) / base.length) * 10) / 10 : null;
  const anomalies = values.map((v) => (v === null || normal === null ? null : Math.round((v - normal) * 10) / 10));
  const anomaliesPct = values.map((v) => (v === null || normal === null || normal < 1 ? null : Math.round((100 * (v - normal)) / normal * 10) / 10));
  return { keys, values, normal, anomalies, anomaliesPct };
}

export function slice(s: Series, from: number, to: number): Series {
  const idx = s.keys.map((k, i) => [k, i] as const).filter(([k]) => k >= from && k <= to).map(([, i]) => i);
  return { keys: idx.map((i) => s.keys[i]), values: idx.map((i) => s.values[i]), normal: s.normal,
    anomalies: idx.map((i) => s.anomalies[i]), anomaliesPct: idx.map((i) => s.anomaliesPct[i]) };
}

export function summarize(s: Series) {
  const pairs = s.keys.map((k, i) => [k, s.values[i]] as const).filter(([, v]) => v !== null) as [number, number][];
  const vals = pairs.map(([, v]) => v);
  const mean = vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
  const min = pairs.reduce((a, b) => (b[1] < a[1] ? b : a), pairs[0]);
  const max = pairs.reduce((a, b) => (b[1] > a[1] ? b : a), pairs[0]);
  const sd = vals.length > 1 && mean !== null ? Math.sqrt(vals.reduce((a, v) => a + (v - mean) ** 2, 0) / (vals.length - 1)) : null;
  const ts = theilSen(s.values, s.keys);
  const mk = mannKendall(s.values);
  return { n: vals.length, mean, sd, min, max, cv: mean && sd !== null ? (100 * sd) / mean : null, ts, mk };
}

export function toCsv(rows: Record<string, unknown>[]): string {
  if (!rows.length) return '';
  const cols = Object.keys(rows[0]);
  const esc = (v: unknown) => {
    const s = v === null || v === undefined ? '' : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [cols.join(','), ...rows.map((r) => cols.map((c) => esc(r[c])).join(','))].join('\n') + '\n';
}

export function download(name: string, content: string | Blob, type = 'text/csv;charset=utf-8') {
  const blob = content instanceof Blob ? content : new Blob([content], { type });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
}
