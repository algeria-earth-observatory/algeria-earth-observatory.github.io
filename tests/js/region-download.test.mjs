// RegionDataDownloader: resolution and extraction against the real published files.
// Every extract is compared with the published table it comes from.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { join } from 'node:path';
import { parquetReadObjects } from 'hyparquet';
import { makeContext, indicatorsFromRecords, resolve, formatsFor, periodError } from '../../src/lib/region-download.js';
import { runExtract } from '../../src/lib/region-extract.js';

const ROOT = new URL('../../', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const PUB = join(ROOT, 'public');
const pub = (href) => join(PUB, href);
const json = (p) => JSON.parse(readFileSync(p, 'utf8'));
const buf = (href) => { const b = readFileSync(pub(href)); return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength); };

const records = readdirSync(join(ROOT, 'src/content/datasets')).filter((f) => f.endsWith('.json')).map((f) => json(join(ROOT, 'src/content/datasets', f)));
const { available, planned } = indicatorsFromRecords(records);
const manifests = Object.fromEntries(available.filter((i) => i.manifest).map((i) => [i.id, json(pub(i.manifest))]));
const boundaryRecord = records.find((r) => r.id === 'aeo-dza-admin-boundaries');

// units, as served by src/pages/data/admin-units.json.ts
const csv = readFileSync(pub('/data/aeo/boundaries/2026-11-20/dza_admin_units.csv'), 'utf8').trim().split(/\r?\n/);
const head = csv[0].split(',');
const rows = csv.slice(1).map((l) => Object.fromEntries(l.split(',').map((v, i) => [head[i], v])));
const adm1 = json(pub('/data/aeo/boundaries/2026-11-20/dza_adm1_wilayas.geojson')).features.map((f) => f.properties);
const units = {
  boundary_version: '2026-11-20', national: { code: 'DZ', name: 'Algeria', name_ar: 'الجزائر' },
  wilayas: adm1.map((w) => [w.wilaya_code, w.name, w.name_ar ?? '']),
  communes: rows.map((r) => [r.commune_code, r.name, r.name_ar, r.wilaya_code]),
};
const ctx = (load = async (u) => json(pub(u))) => makeContext({ indicators: available, manifests, boundaryRecord, units, load });
const io = { fetchBuffer: async (u) => buf(u), unitName: (c) => units.wilayas.find((w) => w[0] === c)?.[1] ?? units.communes.find((x) => x[0] === c)?.[1] };
const sel = (o) => ({ level: 'admin1', wilaya: '19', commune: '', indicator: 'precip', step: 'annual', from: '1981', to: '2025', format: 'csv', ...o });
const parseCsv = (t) => { const [h, ...r] = t.trim().split(/\r?\n/); const k = h.split(','); return r.map((l) => Object.fromEntries(l.split(',').map((v, i) => [k[i], v]))); };
const num = (v) => (v === '' ? null : Number(v));

test('indicators: only available AEO products; planned ones listed separately', () => {
  assert.deepEqual(available.map((i) => i.id), ['precip', 'spei', 'boundaries']);
  assert.ok(planned.length > 0 && planned.every((p) => !available.some((a) => a.id === p.id)));
  const c = ctx();
  assert.deepEqual(c.indicators.find((i) => i.id === 'precip').steps, ['annual', 'monthly']);
  assert.deepEqual(c.indicators.find((i) => i.id === 'spei').steps, ['monthly']);
});

test('journey 1: annual precipitation statistics for Sétif (wilaya 19)', async () => {
  const r = await resolve(ctx(), sel({}));
  assert.equal(r.ok, true); assert.equal(r.kind, 'extract');
  assert.equal(r.readFrom.href, '/data/aeo/products/precipitation/v1.0.0/tables/aeo_precip_annual_admin1_v1.0.0.parquet');
  assert.match(r.button, /Sétif/);
  const out = await runExtract(r, io);
  const got = parseCsv(out.text);
  assert.equal(got.length, 45);
  assert.ok(got.every((x) => x.unit_code === '19' && x.level === 'admin1' && x.unit_name === 'Sétif'));
  assert.deepEqual([got[0].year, got.at(-1).year], ['1981', '2025']);
  // identical to the published CSV
  const pubRows = parseCsv(readFileSync(pub('/data/aeo/products/precipitation/v1.0.0/tables/aeo_precip_annual_admin1_v1.0.0.csv'), 'utf8')).filter((x) => x.unit_code === '19');
  for (const [i, x] of got.entries()) for (const c of ['year', 'precip_mm', 'normal_1991_2020_mm', 'anomaly_mm', 'anomaly_pct']) assert.equal(num(x[c]), num(pubRows[i][c]), `${c} ${x.year}`);
  assert.equal(got[0].product_id, 'aeo-dza-precipitation-chirps3');
  assert.equal(got[0].boundary_version, '2026-11-20');
});

test('journey 2: monthly precipitation for a commune is read from the verified wilaya partition', async () => {
  const r = await resolve(ctx(), sel({ level: 'admin2', commune: '1901', step: 'monthly', from: '2000-01', to: '2000-12' }));
  assert.equal(r.ok, true);
  assert.match(r.readFrom.href, /by_wilaya\/aeo_precip_monthly_admin2_v1\.0\.0\/19\.parquet$/);
  const out = await runExtract(r, io);
  const got = parseCsv(out.text);
  assert.equal(got.length, 12);
  assert.ok(got.every((x) => x.unit_code === '1901' && x.year === '2000'));
  assert.deepEqual(got.map((x) => x.month), ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12']);
  const src = (await parquetReadObjects({ file: buf('/data/aeo/products/precipitation/v1.0.0/tables/aeo_precip_monthly_admin2_v1.0.0.parquet') }))
    .filter((x) => x.unit_code === '1901' && Number(x.year) === 2000);
  for (const [i, x] of got.entries()) assert.equal(num(x.precip_mm), src[i].precip_mm);
});

test('partition index whose source SHA-256 differs is not used (falls back to the full table)', async () => {
  const load = async (u) => { const j = json(pub(u)); return { ...j, source: { ...j.source, sha256: '0'.repeat(64) } }; };
  const r = await resolve(ctx(load), sel({ level: 'admin2', commune: '1901', step: 'monthly', from: '2000-01', to: '2000-12' }));
  assert.equal(r.readFrom.href, r.source.href);
});

test('journey 3: wilaya precipitation GeoTIFF is the exact published file', async () => {
  const r = await resolve(ctx(), sel({ format: 'geotiff' }));
  assert.equal(r.ok, true); assert.equal(r.kind, 'file');
  assert.match(r.href, /raster\/wilaya\/aeo_precip_annual_w19_/);
  const b = readFileSync(pub(r.href));
  assert.equal(b.length, r.bytes);
  assert.equal(createHash('sha256').update(b).digest('hex'), r.sha256);
  assert.equal(b.subarray(0, 4).toString('latin1'), 'II*\u0000');
});

test('journey 4: SPEI statistics for a wilaya, one timescale', async () => {
  const r = await resolve(ctx(), sel({ indicator: 'spei', step: 'monthly', from: '1961-01', to: '2025-12', scale: '12' }));
  assert.equal(r.ok, true);
  const out = await runExtract(r, io);
  const got = parseCsv(out.text);
  assert.equal(got.length, 780);
  assert.ok('spei_12' in got[0] && !('spei_3' in got[0]));
  assert.equal(got[0].unit_name, 'Sétif');
  assert.equal(got[0].spei_12, ''); // SPEI-12 undefined for the first 11 months
  const pubRows = parseCsv(readFileSync(pub('/data/aeo/products/spei/v1.0.0/tables/aeo_spei_monthly_admin1_v1.0.0.csv'), 'utf8')).filter((x) => x.unit_code === '19');
  for (const [i, x] of got.entries()) assert.equal(num(x.spei_12), num(pubRows[i].spei_12));
});

test('journey 5: SPEI wilaya GeoTIFF is explained as unavailable, with real alternatives', async () => {
  const c = ctx();
  const f = formatsFor(c, sel({ indicator: 'spei', step: 'monthly' })).find((x) => x.id === 'geotiff');
  assert.equal(f.available, false);
  const r = await resolve(c, sel({ indicator: 'spei', step: 'monthly', from: '2025-01', to: '2025-12', format: 'geotiff' }));
  assert.equal(r.ok, false); assert.equal(r.kind, 'unavailable');
  assert.match(r.reason, /Algeria as a whole/);
  assert.ok(r.alternatives.some((a) => a.patch.level === 'admin0' && a.patch.format === 'geotiff'));
  assert.ok(r.alternatives.some((a) => a.patch.format === 'csv'));
  for (const alt of r.alternatives) {
    const rr = await resolve(c, { ...sel({ indicator: 'spei', step: 'monthly', from: '2025-01', to: '2025-12', format: 'geotiff' }), ...alt.patch });
    assert.equal(rr.ok, true, `alternative "${alt.label}" must resolve`);
  }
});

test('commune GeoTIFF: no file implied; parent wilaya file and commune statistics proposed', async () => {
  const r = await resolve(ctx(), sel({ level: 'admin2', commune: '1901', format: 'geotiff' }));
  assert.equal(r.ok, false);
  assert.ok(r.alternatives.some((a) => a.patch.level === 'admin1'));
  const rr = await resolve(ctx(), { ...sel({ level: 'admin2', commune: '1901', format: 'geotiff' }), ...r.alternatives[0].patch });
  assert.equal(rr.ok, true); assert.match(rr.href, /w19_/);
});

test('period validation', () => {
  const c = ctx();
  assert.match(periodError(c, sel({ from: '2010', to: '2000' })), /before or equal/);
  assert.match(periodError(c, sel({ from: '1970', to: '2000' })), /1981 to 2025/);
  assert.equal(periodError(c, sel({ from: '2025', to: '2025' })), null);
  assert.match(periodError(c, sel({ step: 'monthly', from: '2026-11', to: '2026-12' })), /2026-10/);
});

test('full tables are labelled and only offered when published', async () => {
  const fm = formatsFor(ctx(), sel({ level: 'admin2', commune: '1901', step: 'monthly' }));
  assert.ok(!fm.some((f) => f.id === 'csv-full')); // no CSV of the commune monthly table is published
  const pq = fm.find((f) => f.id === 'parquet-full');
  assert.match(pq.label, /all 1,541 communes/);
  const r = await resolve(ctx(), sel({ level: 'admin2', commune: '1901', step: 'monthly', format: 'parquet-full' }));
  assert.equal(r.fullTable, true); assert.match(r.coverageText, /not a regional extract/);
});

test('boundaries: single commune extracted unchanged from the full-detail file', async () => {
  const r = await resolve(ctx(), sel({ indicator: 'boundaries', level: 'admin2', commune: '1901', format: 'geojson' }));
  assert.equal(r.ok, true); assert.equal(r.kind, 'extract');
  const out = await runExtract(r, io);
  const fc = JSON.parse(out.text);
  assert.equal(fc.features.length, 1);
  const src = json(pub('/data/aeo/boundaries/2026-11-20/dza_adm2_communes.geojson')).features.find((f) => f.properties.commune_code === '1901');
  assert.deepEqual(fc.features[0], src);
  const w = await runExtract(await resolve(ctx(), sel({ indicator: 'boundaries', format: 'geojson' })), io);
  assert.equal(JSON.parse(w.text).features[0].properties.wilaya_code, '19');
});

test('integrity: a file that does not match its SHA-256 is refused', async () => {
  const r = await resolve(ctx(), sel({}));
  await assert.rejects(runExtract({ ...r, readFrom: { ...r.readFrom, sha256: 'f'.repeat(64) } }, io), /Integrity check failed/);
});

test('a commune must belong to the selected wilaya', async () => {
  const r = await resolve(ctx(), sel({ level: 'admin2', wilaya: '05', commune: '1901' }));
  assert.equal(r.ok, false); assert.equal(r.kind, 'incomplete');
});
