/** Client-side access to the AEO SPEI product (scripts/pipelines/spei/build_spei.py). */
export const SPEI = {
  id: 'aeo-dza-spei-terraclimate',
  version: '1.0.0',
  base: '/data/aeo/products/spei/v1.0.0',
  page: '/data/aeo-dza-spei-terraclimate/',
  method: '/docs/method-spei/',
};

export interface SpeiFile {
  months: string[]; reference: [number, number];
  units: { code: string; name: string; name_ar: string | null; parent: string | null; hyper_arid: boolean }[];
  spei: Record<string, (number | null)[][]>;
}
const cache = new Map<string, Promise<SpeiFile>>();
export function loadSpei(level: 'admin0' | 'admin1' | 'admin2', wilaya?: string): Promise<SpeiFile> {
  const url = level === 'admin2' ? `${SPEI.base}/web/admin2/${wilaya}.json` : `${SPEI.base}/web/${level}.json`;
  if (!cache.has(url)) cache.set(url, fetch(url).then((r) => { if (!r.ok) throw new Error(`${r.status} ${url}`); return r.json(); }));
  return cache.get(url)!;
}

export const SPEI_CLASSES = [
  { max: -2, label: 'extremely dry', color: '#6b1515' },
  { max: -1.5, label: 'severely dry', color: '#d03b3b' },
  { max: -1, label: 'moderately dry', color: '#ee8d81' },
  { max: 1, label: 'near normal', color: '#f0efec' },
  { max: 1.5, label: 'moderately wet', color: '#86b6ef' },
  { max: 2, label: 'very wet', color: '#3987e5' },
  { max: Infinity, label: 'extremely wet', color: '#0d366b' },
];
/** McKee et al. (1993) classes: ≤ −2, ≤ −1.5, ≤ −1 dry; < 1 normal; < 1.5, < 2, ≥ 2 wet. */
export function speiClass(v: number | null) {
  if (v === null || Number.isNaN(v)) return null;
  const i = v <= -2 ? 0 : v <= -1.5 ? 1 : v <= -1 ? 2 : v < 1 ? 3 : v < 1.5 ? 4 : v < 2 ? 5 : 6;
  return SPEI_CLASSES[i];
}

export const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

/** Series for one unit: all months (key = decimal year) or one calendar month (key = year). */
export function speiSeries(f: SpeiFile, code: string, scale: number, month: number, from: number, to: number) {
  const i = f.units.findIndex((u) => u.code === code);
  const row = f.spei[String(scale)]?.[i] ?? [];
  const keys: number[] = [], labels: string[] = [], values: (number | null)[] = [];
  f.months.forEach((m, t) => {
    const y = Number(m.slice(0, 4)), mo = Number(m.slice(5));
    if (y < from || y > to || (month && mo !== month)) return;
    keys.push(month ? y : y + (mo - 1) / 12);
    labels.push(m);
    values.push(row[t] ?? null);
  });
  return { keys, labels, values, unit: f.units[i] };
}
