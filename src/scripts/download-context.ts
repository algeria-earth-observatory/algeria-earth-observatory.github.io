/**
 * Shared loader for regional downloads: units, product manifests and the boundary record,
 * fetched once per page and turned into the resolver context (src/lib/region-download.js).
 * Used by RegionDataDownloader and RegionInspector so both resolve files identically.
 */
import { makeContext, resolve, mb } from '../lib/region-download.js';

const cache = new Map<string, Promise<any>>();
export const getJson = (url: string) => {
  if (!cache.has(url)) cache.set(url, fetch(url).then((r) => { if (!r.ok) throw new Error(`${r.status} ${url}`); return r.json(); }));
  return cache.get(url)!;
};

let ctxP: Promise<any> | null = null;
export function getDownloadContext(indicators: any[]) {
  ctxP ??= (async () => {
    const [units, boundaryRecord, ...mans] = await Promise.all([
      getJson('/data/admin-units.json'),
      getJson(indicators.find((i) => i.kind === 'boundaries')?.record ?? '/data/aeo-dza-admin-boundaries.json'),
      ...indicators.filter((i) => i.manifest).map((i) => getJson(i.manifest)),
    ]);
    const manifests = Object.fromEntries(indicators.filter((i) => i.manifest).map((i, k) => [i.id, mans[k]]));
    return makeContext({ indicators, manifests, boundaryRecord, units, load: getJson });
  })();
  return ctxP;
}

/** Resolve a selection, extract it in the browser (or link the published file) and save it. */
export async function downloadSelection(ctx: any, sel: any): Promise<string> {
  const r = await resolve(ctx, sel);
  if (!r.ok) throw new Error(r.reason);
  if (r.kind === 'file') {
    const a = document.createElement('a');
    a.href = r.href; a.download = r.filename;
    document.body.appendChild(a); a.click(); a.remove();
    return `Download started: ${r.filename} (${mb(r.bytes)}).`;
  }
  const { runExtract } = await import('../lib/region-extract.js');
  const out = await runExtract(r, {
    fetchBuffer: async (u: string) => { const res = await fetch(u); if (!res.ok) throw new Error(`The file ${u} could not be fetched (${res.status}).`); return res.arrayBuffer(); },
    unitName: (c: string) => (ctx.wilayas.get(c) ?? ctx.communes.get(c))?.name ?? (c === 'DZ' ? 'Algeria' : undefined),
  });
  if (out.rows === 0) throw new Error('No rows match this selection in the published table.');
  const blob = new Blob([out.text], { type: out.mime });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = r.filename;
  document.body.appendChild(a); a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 2000);
  return `Downloaded ${r.filename}: ${out.rows} rows, ${mb(blob.size)}.`;
}
