// @ts-check
/**
 * In-browser regional extraction for RegionDataDownloader.
 *
 * Reads the exact file chosen by resolve() (a published Parquet table, a verified
 * regional partition of one, or a boundary partition), checks its SHA-256 against the
 * manifest or partition index, filters by stable administrative code and period, and
 * returns the output text. Values are copied, never recomputed.
 */
import { parquetReadObjects } from 'hyparquet';

/** @param {ArrayBuffer} buf */
export async function sha256Hex(buf) {
  const d = await crypto.subtle.digest('SHA-256', buf);
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

/** @param {unknown} v */
const cell = (v) => {
  if (v === null || v === undefined || (typeof v === 'number' && Number.isNaN(v))) return '';
  const s = typeof v === 'bigint' ? v.toString() : String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

/**
 * @param {any} res resolution from resolve() with kind === 'extract'
 * @param {{ fetchBuffer: (url: string) => Promise<ArrayBuffer>, unitName?: (code: string) => string|undefined }} io
 * @returns {Promise<{ text: string, rows: number, mime: string }>}
 */
export async function runExtract(res, io) {
  const buf = await io.fetchBuffer(res.readFrom.href);
  const sha = await sha256Hex(buf);
  if (sha !== res.readFrom.sha256) throw new Error(`Integrity check failed for ${res.readFrom.href}: the file does not match its published SHA-256. Nothing was downloaded.`);
  if (res.readFrom.kind === 'geojson') return extractGeojson(res, buf);
  return extractTable(res, buf, io.unitName);
}

/** @param {any} res @param {ArrayBuffer} buf @param {((code: string) => string|undefined)=} unitName */
async function extractTable(res, buf, unitName) {
  const f = res.filter;
  const monthly = f.step === 'monthly';
  const rows = /** @type {Record<string, any>[]} */ (await parquetReadObjects({ file: buf }));
  const key = (/** @type {any} */ r) => (monthly ? `${Number(r.year)}-${String(Number(r.month)).padStart(2, '0')}` : String(Number(r.year)));
  const sel = rows.filter((r) => r.unit_code === f.unit_code && key(r) >= f.from && key(r) <= f.to);
  sel.sort((a, b) => (key(a) < key(b) ? -1 : key(a) > key(b) ? 1 : 0));
  const head = ['level', 'unit_code', 'unit_name', 'parent_code', 'year', ...(monthly ? ['month'] : []), ...res.columns,
    'product_id', 'product_version', 'boundary_version', 'source', 'license'];
  const meta = [res.product.id, res.product.version, res.boundaryVersion, `${res.product.source}${res.product.sourceDoi ? ` (doi:${res.product.sourceDoi})` : ''}`, `${res.product.license}${res.product.sourceLicense && res.product.sourceLicense !== res.product.license ? `; source data ${res.product.sourceLicense}` : ''}`];
  const lines = [head.join(',')];
  for (const r of sel) {
    const name = r.unit_name ?? unitName?.(r.unit_code) ?? '';
    lines.push([r.level, r.unit_code, name, r.parent_code ?? '', Number(r.year), ...(monthly ? [Number(r.month)] : []), ...res.columns.map((/** @type {string} */ c) => r[c]), ...meta].map(cell).join(','));
  }
  return { text: lines.join('\n') + '\n', rows: sel.length, mime: 'text/csv;charset=utf-8' };
}

/** @param {any} res @param {ArrayBuffer} buf */
function extractGeojson(res, buf) {
  const fc = JSON.parse(new TextDecoder().decode(buf));
  const feat = res.filter.level === 'admin1'
    ? fc.features.find((/** @type {any} */ x) => x.properties.wilaya_code === res.filter.code && !('commune_code' in x.properties))
    : fc.features.find((/** @type {any} */ x) => x.properties.commune_code === res.filter.code);
  if (!feat) throw new Error(`No feature with code ${res.filter.code} in ${res.readFrom.href}.`);
  const out = {
    type: 'FeatureCollection',
    name: res.filename.replace(/\.geojson$/, ''),
    metadata: {
      dataset: res.product.id, boundary_version: res.boundaryVersion, source_file: res.source.href, source_sha256: res.source.sha256,
      license: 'ODbL-1.0', attribution: '© OpenStreetMap contributors; processing: Algeria Earth Observatory',
      note: 'Feature copied unchanged from the published full-detail file. Community-mapped; not an official, legal or cadastral delineation.',
    },
    features: [feat],
  };
  return { text: JSON.stringify(out), rows: 1, mime: 'application/geo+json' };
}
