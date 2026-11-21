// @ts-check
/**
 * RegionDataDownloader — resolution of a selection to an exact file or extraction.
 *
 * Location → Indicator → Period → Format → Download.
 *
 * Every answer is derived from machine-readable sources only:
 *   - product manifests (download_assets with size and SHA-256),
 *   - the boundary catalog record (access entries with size and SHA-256),
 *   - regional partition indexes (scripts/pipelines/partition_regional.py), used only
 *     when their recorded source SHA-256 equals the manifest's.
 * Nothing here invents a file: if no published asset or extraction supports a
 * selection, resolve() says so and proposes alternatives that do exist.
 *
 * Plain JavaScript (checked by TypeScript via @ts-check) so that node --test can
 * import it directly (tests/js/region-download.test.mjs).
 */

/** @typedef {'admin0'|'admin1'|'admin2'} Level */
/** @typedef {{ href: string, format: string, level: string|null, unit_code?: string, title: string, bytes: number, sha256: string, role?: string }} Asset */
/** @typedef {{ id: string, label: string, kind: 'product'|'boundaries', manifest?: string, record?: string, partitions?: string, steps: string[], short: string }} IndicatorConfig */
/** @typedef {{ code: string, name: string, name_ar: string, wilaya?: string }} Unit */
/**
 * @typedef {{
 *   level: Level, wilaya: string, commune: string, indicator: string, step: string,
 *   from: string, to: string, format: string, layer?: string, scale?: string
 * }} Selection
 */

export const LEVEL_NAME = { admin0: 'Algeria', admin1: 'wilaya', admin2: 'commune' };
const PLURAL = { admin0: 'Algeria', admin1: 'all 69 wilayas', admin2: 'all 1,541 communes' };
export const SPEI_SCALES = ['1', '3', '6', '12'];

export const mb = (/** @type {number} */ b) => (b >= 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1e3))} kB`);
const slug = (/** @type {string} */ s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

/** Plain-language names for the Algeria-ready products the downloader serves. */
const PLAIN = {
  'aeo-dza-precipitation-chirps3': { id: 'precip', label: 'Precipitation', short: 'precipitation' },
  'aeo-dza-spei-terraclimate': { id: 'spei', label: 'Drought (SPEI)', short: 'SPEI' },
  'aeo-dza-spi-chirps3': { id: 'spi', label: 'Drought (SPI)', short: 'SPI' },
  'aeo-dza-soil-soilgrids': { id: 'soil', label: 'Soil properties (SoilGrids)', short: 'soil' },
  'aeo-dza-admin-boundaries': { id: 'boundaries', label: 'Administrative boundaries', short: 'boundary' },
};

/**
 * Indicators offered by the downloader, from catalog records: only records with
 * status "available" that AEO publishes (a product manifest, or the boundary set).
 * Planned AEO products are returned separately so the UI can list them as planned.
 * @param {any[]} records catalog records (src/content/datasets/*.json)
 */
export function indicatorsFromRecords(records) {
  /** @type {IndicatorConfig[]} */
  const available = [];
  const planned = [];
  for (const r of records) {
    const p = /** @type {Record<string, any>} */ (PLAIN)[r.id];
    if (p && r.status === 'available' && r.product?.manifest) {
      available.push({ ...p, kind: 'product', manifest: r.product.manifest, record: `/data/${r.id}.json`, steps: [] });
    } else if (p && r.status === 'available' && p.id === 'boundaries') {
      available.push({ ...p, kind: 'boundaries', record: `/data/${r.id}.json`, partitions: `/data/aeo/boundaries/${r.version}/by_wilaya/index.json`, steps: [] });
    } else if (String(r.origin).startsWith('aeo') && r.status === 'in-preparation') {
      planned.push({ id: r.id, title: r.title.split(':')[0] });
    }
  }
  const order = ['precip', 'spei', 'spi', 'soil', 'boundaries'];
  available.sort((a, b) => order.indexOf(a.id) - order.indexOf(b.id));
  return { available, planned };
}

/**
 * Build the context from the fetched sources.
 * @param {{ indicators: IndicatorConfig[], manifests: Record<string, any>, boundaryRecord: any, units: any, load: (url: string) => Promise<any> }} src
 */
export function makeContext(src) {
  const wilayas = new Map(src.units.wilayas.map((/** @type {string[]} */ w) => [w[0], { code: w[0], name: w[1], name_ar: w[2] }]));
  const communes = new Map(src.units.communes.map((/** @type {string[]} */ c) => [c[0], { code: c[0], name: c[1], name_ar: c[2], wilaya: c[3] }]));
  // time steps = those for which the manifest lists a statistics table
  const indicators = src.indicators.map((i) => {
    if (i.kind !== 'product') return i;
    const assets = /** @type {Asset[]} */ (src.manifests[i.id]?.download_assets ?? []);
    // 'stats' = a static table without a time dimension (e.g. soil properties)
    return { ...i, steps: ['annual', 'monthly', 'stats'].filter((s) => assets.some((a) => a.format === 'PARQUET' && a.href.includes(`_${s}_`))) };
  });
  return {
    indicators,
    manifests: src.manifests,
    boundaryRecord: src.boundaryRecord,
    boundaryVersion: src.units.boundary_version,
    national: src.units.national,
    wilayas, communes,
    load: src.load,
  };
}
/** @typedef {ReturnType<typeof makeContext>} Ctx */

/** @param {Ctx} ctx @param {Selection} sel */
export function area(ctx, sel) {
  if (sel.level === 'admin0') return { level: sel.level, code: 'DZ', name: 'Algeria', name_ar: ctx.national.name_ar, label: 'Algeria', file: 'dza' };
  if (sel.level === 'admin1') {
    const w = ctx.wilayas.get(sel.wilaya);
    if (!w) return null;
    return { level: sel.level, code: w.code, name: w.name, name_ar: w.name_ar, label: `${w.name} (wilaya ${w.code})`, file: `w${w.code}-${slug(w.name)}` };
  }
  const c = ctx.communes.get(sel.commune);
  if (!c || c.wilaya !== sel.wilaya) return null;
  const w = ctx.wilayas.get(c.wilaya);
  return { level: sel.level, code: c.code, name: c.name, name_ar: c.name_ar, wilaya: c.wilaya, wilayaName: w?.name, label: `${c.name} (commune ${c.code}, wilaya of ${w?.name})`, file: `c${c.code}-${slug(c.name)}` };
}

/** @param {Ctx} ctx @param {string} id */
export const indicator = (ctx, id) => ctx.indicators.find((i) => i.id === id);

/** Temporal coverage of a product and step, from the manifest. @param {Ctx} ctx @param {string} ind @param {string} step */
export function coverage(ctx, ind, step) {
  const m = ctx.manifests[ind];
  if (!m || step === 'stats') return null;
  const t = m.temporal_coverage;
  if (step === 'annual') return { from: String(t.annual[0]), to: String(t.annual[1]) };
  return { from: t.monthly[0], to: t.monthly[1] };
}

/** Number of periods between two keys (years or YYYY-MM), inclusive. */
export function periods(/** @type {string} */ from, /** @type {string} */ to) {
  if (from.length === 4) return Number(to) - Number(from) + 1;
  const [y0, m0] = from.split('-').map(Number), [y1, m1] = to.split('-').map(Number);
  return (y1 - y0) * 12 + (m1 - m0) + 1;
}

/** @param {Ctx} ctx @param {Selection} sel @returns {string|null} */
export function periodError(ctx, sel) {
  const cov = coverage(ctx, sel.indicator, sel.step);
  if (!cov) return null;
  const re = sel.step === 'annual' ? /^\d{4}$/ : /^\d{4}-(0[1-9]|1[0-2])$/;
  if (!re.test(sel.from) || !re.test(sel.to)) return 'Choose a start and an end.';
  if (sel.from < cov.from || sel.to > cov.to) return `Data cover ${cov.from} to ${cov.to}. Choose dates in that range.`;
  if (sel.from > sel.to) return 'The start must be before or equal to the end.';
  return null;
}

/** @param {Asset[]} assets @param {string} level @param {string} fmt @param {string} step */
const table = (assets, level, fmt, step) => assets.find((a) => a.level === level && a.format === fmt && a.href.includes(`_${step}_`));

/**
 * Format options for a selection. `available: false` options carry the reason; the UI
 * may still let the user pick them, to show the explanation and the alternatives.
 * @param {Ctx} ctx @param {Selection} sel
 */
export function formatsFor(ctx, sel) {
  const ind = indicator(ctx, sel.indicator);
  if (!ind) return [];
  const where = sel.level === 'admin0' ? 'Algeria' : sel.level === 'admin1' ? 'this wilaya' : 'this commune';
  if (ind.kind === 'boundaries') {
    const out = [{ id: 'geojson', label: `GeoJSON — boundary of ${where}`, available: true, regional: true }];
    if (sel.level !== 'admin0') out.push({ id: 'geojson-full', label: `GeoJSON — full file, ${PLURAL[sel.level]}`, available: true, regional: false });
    return out;
  }
  const assets = /** @type {Asset[]} */ (ctx.manifests[ind.id].download_assets);
  const spatial = /** @type {string[]} */ (ctx.manifests[ind.id].spatial_products_levels ?? []);
  const geotiffOk = spatial.includes(sel.level) && (ind.id !== 'precip' || sel.step === 'annual');
  const external = ctx.manifests[ind.id].external_rasters;
  const out = [
    { id: 'csv', label: `CSV — statistics for ${where} only`, available: true, regional: true },
    {
      id: 'geotiff',
      label: external && !spatial.length ? 'GeoTIFF — from the original source (not redistributed by AEO)' : geotiffOk ? `GeoTIFF — spatial grid${sel.level === 'admin1' ? ' for this wilaya' : ' for Algeria'}` : `GeoTIFF — ${!spatial.includes(sel.level) ? `not published for ${LEVEL_NAME[sel.level]}s` : 'annual values only'}`,
      available: geotiffOk, regional: sel.level !== 'admin0',
    },
  ];
  if (sel.level !== 'admin0') {
    if (table(assets, sel.level, 'CSV', sel.step)) out.push({ id: 'csv-full', label: `CSV — full table, ${PLURAL[sel.level]}`, available: true, regional: false });
    if (table(assets, sel.level, 'PARQUET', sel.step)) out.push({ id: 'parquet-full', label: `Parquet — full table, ${PLURAL[sel.level]}`, available: true, regional: false });
  } else if (table(assets, 'admin0', 'PARQUET', sel.step)) {
    out.push({ id: 'parquet-full', label: 'Parquet — same table, Parquet file', available: true, regional: true });
  }
  return out;
}

/**
 * Resolve a selection.
 * @param {Ctx} ctx @param {Selection} sel
 * @returns {Promise<any>}
 */
export async function resolve(ctx, sel) {
  const ind = indicator(ctx, sel.indicator);
  if (!ind) return { ok: false, kind: 'incomplete', reason: 'Choose an indicator.' };
  const a = area(ctx, sel);
  if (!a) return { ok: false, kind: 'incomplete', reason: sel.level === 'admin1' ? 'Choose a wilaya.' : 'Choose a commune of the selected wilaya.' };
  if (ind.kind === 'boundaries') return resolveBoundaries(ctx, sel, a);

  const m = ctx.manifests[ind.id];
  const assets = /** @type {Asset[]} */ (m.download_assets);
  const base = { area: a, indicator: ind, product: { id: m.product_id, version: m.version, license: m.license, source: m.source_product, sourceLicense: m.source_license, sourceDoi: m.source_doi, method: m.methodology_url, manifest: ind.manifest }, boundaryVersion: m.boundary_version };
  const notes = [];
  if (sel.level === 'admin2') {
    notes.push(ind.id === 'precip'
      ? 'Commune values are area-weighted means of ≈5.5 km CHIRPS cells; small communes hold only a few cells. The statistical_support column of the summary table states the support of each commune.'
      : 'Commune values are computed on the commune-average water balance of ≈3.7 km TerraClimate cells.');
  }
  if (ind.id === 'spei') notes.push('SPEI-n is empty for the first n − 1 months of the record (1961). In hyper-arid areas SPEI reflects evaporative demand rather than rainfall.');
  if (ind.id === 'spi') notes.push('SPI-n is empty for the first n − 1 months (1981). Units flagged arid (normal below 100 mm/year) have unstable SPI; calendar months that cannot be fitted are empty.');
  if (sel.step === 'stats' && ind.id === 'soil') {
    notes.length = 0;
    notes.push('SoilGrids values are model predictions (machine learning on soil profiles and covariates), not field measurements. Uncertainty is large in Algeria, where few profiles were available to the model.');
    notes.push('q05_mean and q95_mean are the unit averages of the pixel 5 % and 95 % prediction quantiles: an indication of pixel-level uncertainty, not a confidence interval of the mean.');
    notes.push('Concentrations are given per depth interval. The organic carbon stock (ocs, 0–30 cm) is the ISRIC stock product; AEO does not convert concentrations into stocks.');
  }

  // ---- spatial grids
  if (sel.format === 'geotiff') {
    const spatial = /** @type {string[]} */ (m.spatial_products_levels ?? []);
    if (m.external_rasters && !spatial.length) {
      return {
        ok: false, kind: 'unavailable', ...base,
        reason: 'AEO publishes regional statistics for this product but does not redistribute its rasters. Download the original GeoTIFFs from the provider.',
        external: { label: 'Original raster files (provider)', url: m.external_rasters.url, documentation: m.external_rasters.documentation },
        alternatives: [{ label: `CSV statistics for ${a.name}`, patch: { format: 'csv' } }],
      };
    }
    if (!spatial.includes(sel.level)) {
      const parent = sel.level === 'admin2' && spatial.includes('admin1');
      return {
        ok: false, kind: 'unavailable', ...base,
        reason: ind.id === 'spei'
          ? `SPEI grids are published for Algeria as a whole only. No ${LEVEL_NAME[sel.level]} GeoTIFF exists in the product manifest.`
          : `Spatial grids are published for Algeria and for each wilaya, not for communes: at ≈5.5 km resolution a commune holds only a few grid cells.`,
        alternatives: [
          parent ? { label: `GeoTIFF for the wilaya of ${a.wilayaName} (contains this commune)`, patch: { level: 'admin1', format: 'geotiff', step: 'annual' } } : null,
          { label: `CSV statistics for ${a.name}`, patch: { format: 'csv' } },
          { label: 'GeoTIFF for Algeria', patch: { level: 'admin0', format: 'geotiff', ...(ind.id === 'precip' ? { step: 'annual' } : {}) } },
        ].filter(Boolean),
      };
    }
    if (ind.id === 'precip' && sel.step !== 'annual') {
      return { ok: false, kind: 'unavailable', ...base, reason: 'The precipitation GeoTIFFs hold annual totals (one band per year). No monthly grids are published.', alternatives: [{ label: 'Annual GeoTIFF', patch: { step: 'annual' } }, { label: `Monthly CSV statistics for ${a.name}`, patch: { format: 'csv' } }] };
    }
    let file, layers = null;
    if (sel.level === 'admin1') file = assets.find((x) => x.format === 'COG' && x.level === 'admin1' && x.unit_code === a.code);
    else {
      layers = assets.filter((x) => x.format === 'COG' && x.level === 'admin0').map((x) => ({ id: x.href, label: x.title }));
      file = assets.find((x) => x.href === sel.layer) ?? assets.find((x) => x.format === 'COG' && x.level === 'admin0');
    }
    if (!file) return { ok: false, kind: 'unavailable', ...base, reason: 'No GeoTIFF for this area is listed in the product manifest.', alternatives: [{ label: `CSV statistics for ${a.name}`, patch: { format: 'csv' } }] };
    return {
      ok: true, kind: 'file', ...base, format: 'GeoTIFF', file, layers, href: file.href, filename: file.href.split('/').pop(), bytes: file.bytes, sha256: file.sha256,
      coverageText: sel.level === 'admin1' ? `Wilaya of ${a.name} (grid clipped to its boundary)` : 'Algeria',
      periodText: file.title, periodApplies: false,
      notes: [...notes.filter((n) => !n.startsWith('Commune')), 'The file covers the whole period stated in its title; your period selection does not subset it. Band descriptions name the years.'],
      button: `Download ${file.title} — ${sel.level === 'admin1' ? a.name + ', ' : ''}GeoTIFF, ${mb(file.bytes)}`,
    };
  }

  const perr = periodError(ctx, sel);
  if (perr && (sel.format === 'csv')) return { ok: false, kind: 'invalid', field: 'period', reason: perr, ...base };

  // ---- full tables (labelled: not a regional extract)
  if (sel.format === 'csv-full' || sel.format === 'parquet-full') {
    const fmt = sel.format === 'csv-full' ? 'CSV' : 'PARQUET';
    const file = table(assets, sel.level, fmt, sel.step);
    if (!file) {
      const other = table(assets, sel.level, fmt === 'CSV' ? 'PARQUET' : 'CSV', sel.step);
      return { ok: false, kind: 'unavailable', ...base, reason: `No ${fmt === 'CSV' ? 'CSV' : 'Parquet'} file of this table is published.`, alternatives: [other ? { label: `${other.format === 'CSV' ? 'CSV' : 'Parquet'} full table (${mb(other.bytes)})`, patch: { format: other.format === 'CSV' ? 'csv-full' : 'parquet-full' } } : null, { label: `CSV statistics for ${a.name} only`, patch: { format: 'csv' } }].filter(Boolean) };
    }
    const full = sel.level !== 'admin0';
    return {
      ok: true, kind: 'file', ...base, format: fmt === 'CSV' ? 'CSV' : 'Parquet', file, href: file.href, filename: file.href.split('/').pop(), bytes: file.bytes, sha256: file.sha256,
      fullTable: full, coverageText: full ? `${PLURAL[sel.level][0].toUpperCase()}${PLURAL[sel.level].slice(1)} — full administrative table, not a regional extract` : 'Algeria',
      periodText: `${coverage(ctx, ind.id, sel.step)?.from} to ${coverage(ctx, ind.id, sel.step)?.to} (${sel.step}), complete`, periodApplies: false, notes,
      button: `Download the full ${sel.step} ${ind.short} table${full ? `, ${PLURAL[sel.level]}` : ''} — ${fmt === 'CSV' ? 'CSV' : 'Parquet'}, ${mb(file.bytes)}`,
    };
  }

  // ---- regional statistics extract (CSV generated in the browser)
  const source = table(assets, sel.level, 'PARQUET', sel.step);
  if (!source) return { ok: false, kind: 'unavailable', ...base, reason: `No ${sel.step} statistics table is published at ${LEVEL_NAME[sel.level]} level.`, alternatives: [] };
  let readFrom = { href: source.href, bytes: source.bytes, sha256: source.sha256, kind: 'parquet' };
  let via = null;
  if (sel.level === 'admin2' && source.bytes > 1.5e6) {
    const idxUrl = source.href.replace(/[^/]+\.parquet$/, `by_wilaya/${source.href.split('/').pop()?.replace(/\.parquet$/, '')}/index.json`);
    const idx = await ctx.load(idxUrl).catch(() => null);
    const part = idx && idx.source?.href === source.href && idx.source?.sha256 === source.sha256
      ? idx.partitions.find((/** @type {any} */ p) => p.wilaya_code === a.wilaya && p.unit_codes.includes(a.code)) : null;
    if (part) { readFrom = { href: part.href, bytes: part.bytes, sha256: part.sha256, kind: 'parquet' }; via = idxUrl; }
  }
  if (sel.step === 'stats') {
    return {
      ok: true, kind: 'extract', ...base, format: 'CSV',
      filename: `aeo_${a.file}_${ind.id}_v${m.version}.csv`,
      source, readFrom, via,
      filter: { unit_code: a.code, step: 'stats' },
      columns: ['property', 'property_label', 'depth', 'units', 'mean', 'q05_mean', 'q95_mean', 'pixels_1km', 'valid_pct', 'total_stock_Mt', 'support'],
      rowsExpected: (m.layers ?? []).length,
      coverageText: a.label, periodText: `${m.temporal_coverage?.snapshot ?? 'static'}`, periodApplies: false,
      notes,
      button: `Download ${a.name} ${ind.short} statistics — CSV`,
    };
  }
  const isIndex = ind.id === 'spei' || ind.id === 'spi';
  const scale = isIndex ? (sel.scale && SPEI_SCALES.includes(sel.scale) ? sel.scale : 'all') : null;
  const scales = scale === 'all' ? SPEI_SCALES : [scale];
  const cols = ind.id === 'precip'
    ? (sel.step === 'annual' ? ['precip_mm', 'normal_1991_2020_mm', 'anomaly_mm', 'anomaly_pct', 'valid_area_pct'] : ['precip_mm', 'normal_1991_2020_mm', 'anomaly_mm'])
    : ind.id === 'spi' ? ['precip_mm', ...scales.map((s) => `spi_${s}`), 'arid']
    : ['p_mm', 'pet_mm', 'd_mm', ...scales.map((s) => `spei_${s}`)];
  const n = periods(sel.from, sel.to);
  const plabel = sel.from === sel.to ? sel.from : `${sel.from} to ${sel.to}`;
  const what = ind.id === 'precip' ? `${sel.step} precipitation` : `${ind.short}${scale === 'all' ? ' (1, 3, 6, 12 months)' : `-${scale}`}`;
  return {
    ok: true, kind: 'extract', ...base, format: 'CSV',
    filename: `aeo_${a.file}_${ind.id}_${sel.step}${scale && scale !== 'all' ? `_${ind.id}${scale}` : ''}_${sel.from}_${sel.to}_v${m.version}.csv`,
    source, readFrom, via,
    filter: { unit_code: a.code, step: sel.step, from: sel.from, to: sel.to },
    columns: cols, rowsExpected: n,
    coverageText: a.label, periodText: `${plabel} — ${n} ${sel.step === 'annual' ? (n === 1 ? 'year' : 'years') : (n === 1 ? 'month' : 'months')}`, periodApplies: true,
    notes,
    button: `Download ${a.name} ${what}, ${plabel} — CSV`,
  };
}

/** @param {Ctx} ctx @param {Selection} sel @param {any} a */
async function resolveBoundaries(ctx, sel, a) {
  const rec = ctx.boundaryRecord;
  const ind = indicator(ctx, 'boundaries');
  const files = (rec.access ?? []).filter((/** @type {any} */ x) => x.kind === 'download');
  const byName = (/** @type {string} */ n) => files.find((/** @type {any} */ x) => x.url.endsWith(`/${rec.version}/${n}`));
  const base = { area: a, indicator: ind, product: { id: rec.id, version: rec.version, license: rec.license?.spdx ?? rec.license?.name, source: rec.provider?.name, method: rec.documentation_url }, boundaryVersion: rec.version };
  const notes = ['Community-mapped boundaries (OpenStreetMap): not an official, legal or cadastral delineation. Attribute “© OpenStreetMap contributors” (ODbL 1.0).'];
  const asFile = (/** @type {any} */ f, /** @type {string} */ cov, full = false) => ({
    ok: true, kind: 'file', ...base, format: 'GeoJSON', file: f, href: f.url, filename: f.url.split('/').pop(), bytes: f.size_bytes, sha256: f.sha256,
    fullTable: full, coverageText: cov, periodText: `Boundary version ${rec.version}`, periodApplies: false, notes,
    button: `Download ${cov.split(' — ')[0]} boundaries — GeoJSON, ${mb(f.size_bytes)}`,
  });
  if (sel.level === 'admin0') {
    const f = byName('dza_adm0.geojson');
    if (!f) return { ok: false, kind: 'unavailable', ...base, reason: 'The national boundary file is not listed in the boundary record.', alternatives: [] };
    return asFile(f, 'Algeria');
  }
  const fullName = sel.level === 'admin1' ? 'dza_adm1_wilayas.geojson' : 'dza_adm2_communes.geojson';
  const full = byName(fullName);
  if (sel.format === 'geojson-full') {
    if (!full) return { ok: false, kind: 'unavailable', ...base, reason: 'This file is not listed in the boundary record.', alternatives: [] };
    return asFile(full, `${PLURAL[sel.level][0].toUpperCase()}${PLURAL[sel.level].slice(1)} — full file, not a regional extract`, true);
  }
  const idxUrl = ind?.partitions;
  const idx = idxUrl ? await ctx.load(idxUrl).catch(() => null) : null;
  const src = idx?.sources?.[sel.level];
  const ok = src && full && src.href === full.url && src.sha256 === full.sha256;
  const part = ok ? idx.partitions.find((/** @type {any} */ p) => p.wilaya_code === (a.wilaya ?? a.code)) : null;
  if (!part || (sel.level === 'admin2' && !part.commune_codes.includes(a.code))) {
    return { ok: false, kind: 'unavailable', ...base, reason: 'A single-area extract cannot be verified against the published boundary file right now.', alternatives: full ? [{ label: `Full file, ${PLURAL[sel.level]} (${mb(full.size_bytes)})`, patch: { format: 'geojson-full' } }] : [] };
  }
  return {
    ok: true, kind: 'extract', ...base, format: 'GeoJSON',
    filename: `aeo_${a.file}_boundary_${rec.version}.geojson`,
    source: { href: full.url, bytes: full.size_bytes, sha256: full.sha256, title: full.label },
    readFrom: { href: part.href, bytes: part.bytes, sha256: part.sha256, kind: 'geojson' }, via: idxUrl,
    filter: { code: a.code, level: sel.level },
    coverageText: a.label, periodText: `Boundary version ${rec.version}`, periodApplies: false, notes,
    button: `Download the boundary of ${a.name} — GeoJSON`,
  };
}
