/** Client-side access to the AEO SPI product (scripts/pipelines/spi/build_spi.py). */
import type { SpeiFile } from './spei';

export const SPI = {
  id: 'aeo-dza-spi-chirps3',
  version: '1.0.0',
  base: '/data/aeo/products/spi/v1.0.0',
  page: '/data/aeo-dza-spi-chirps3/',
  method: '/docs/method-spi/',
};

interface SpiFileRaw {
  months: string[]; reference: string;
  units: { code: string; name: string; parent: string | null; arid: boolean }[];
  spi: Record<string, (number | null)[][]>;
}
const cache = new Map<string, Promise<SpeiFile>>();
/** Same shape as an SPEI file (`spei` holds the index values, `hyper_arid` the arid flag). */
export function loadSpi(level: 'admin0' | 'admin1' | 'admin2', wilaya?: string): Promise<SpeiFile> {
  const url = level === 'admin2' ? `${SPI.base}/web/admin2/${wilaya}.json` : `${SPI.base}/web/${level}.json`;
  if (!cache.has(url)) {
    cache.set(url, fetch(url).then((r) => { if (!r.ok) throw new Error(`${r.status} ${url}`); return r.json(); }).then((f: SpiFileRaw) => ({
      months: f.months,
      reference: [1991, 2020] as [number, number],
      units: f.units.map((u) => ({ code: u.code, name: u.name, name_ar: null, parent: u.parent, hyper_arid: u.arid })),
      spei: f.spi,
    })));
  }
  return cache.get(url)!;
}
