/**
 * RegionInspector — statistics of one indicator for one wilaya or commune.
 *
 * Inputs: region (level + stable code), indicator (map layer id), period (time) and variant
 * (e.g. soil depth). Outputs: name, value with units and period, a comparison where the
 * product supports one, a small chart with a table equivalent, source and resolution, and
 * a download of the regional data.
 *
 * Values are read from the published AEO product files (the same files as Drought and the
 * downloads). Indicators that AEO has not processed get an honest availability message and
 * a link to the original source; no value is ever estimated or filled in.
 */
import { loadAnnual } from '../lib/precip';
import { loadSpei, speiClass } from '../lib/spei';
import { loadSpi } from '../lib/spi';
import { lineChart, anomalyChart } from '../lib/charts';
import { getJson, getDownloadContext, downloadSelection } from './download-context';

export interface InspectorRegion {
  level: 'admin1' | 'admin2';
  code: string;
  name: string;
  nameAr?: string | null;
  wilaya: string;
  wilayaName?: string;
  areaKm2?: number | null;
}
export interface InspectorQuery { layer: string | null; time: string | null; variant: string | null }
export interface LayerInfo { id: string; title: string; dataset: string | null; nature: string; caveat?: string }
export interface DatasetInfo { title: string; provider?: string; source_url?: string; documentation_url?: string; status: string; resolution?: string }

const esc = (s: unknown) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!);
const fmt = (v: number | null | undefined, d = 0) => (v === null || v === undefined || Number.isNaN(v) ? '—' : v.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d }));
const signed = (v: number | null | undefined, d = 0) => (v === null || v === undefined ? '—' : `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(d)}`);
const SOIL = '/data/aeo/products/soil/v1.0.0/web';

/** Indicators for which AEO publishes regional statistics. */
export const hasAeoStats = (id: string | null) => !!id && (/^precip-(annual|anomaly)$/.test(id) || /^(spei|spi)-(3|12)$/.test(id) || id.startsWith('soil-'));

interface Block {
  indicator: string; period: string; value: string; units: string;
  lines: string[]; source: string; method: string; drought?: string;
  chart?: (el: HTMLElement) => void; table?: string; download?: Record<string, string>;
  notes?: string[];
}

export class RegionInspector {
  el: HTMLElement;
  layers: Map<string, LayerInfo>;
  datasets: Record<string, DatasetInfo>;
  indicators: any[];
  private seq = 0;

  constructor(el: HTMLElement, layers: LayerInfo[], datasets: Record<string, DatasetInfo>, indicators: any[]) {
    this.el = el; this.layers = new Map(layers.map((l) => [l.id, l])); this.datasets = datasets; this.indicators = indicators;
  }

  async render(region: InspectorRegion, q: InspectorQuery) {
    const my = ++this.seq;
    const head = `<p class="text-[0.875rem] text-slate">${region.level === 'admin1' ? `Wilaya ${esc(region.code)}` : `Commune ${esc(region.code)} · wilaya of ${esc(region.wilayaName ?? region.wilaya)}`}${region.nameAr ? ` · <span lang="ar" dir="rtl">${esc(region.nameAr)}</span>` : ''}</p>
      <h2 id="ins-h" class="mt-1 text-[1.375rem] font-medium leading-tight text-atlas" tabindex="-1">${esc(region.name)} <span class="font-normal text-slate">— Environmental profile</span></h2>`;
    this.el.innerHTML = `${head}<p class="mt-4 text-[0.9375rem] text-slate" role="status">Loading statistics…</p>`;
    let body: string;
    let block: Block | null = null;
    try {
      if (!q.layer) body = this.noIndicator(region);
      else if (hasAeoStats(q.layer)) { block = await this.block(region, q); body = block ? this.blockHtml(block) : this.notAvailable(region, q); }
      else body = this.external(q);
    } catch (e) {
      body = `<p class="note note-warn mt-4">The statistics could not be loaded (${esc((e as Error).message)}). Reload the page or use the product page.</p>`;
    }
    if (my !== this.seq) return;
    const profile = region.level === 'admin1' ? `/regions/${region.code}/` : `/regions/${region.wilaya}/${region.code}/`;
    this.el.innerHTML = `${head}${body}
      <div class="mt-6 border-t border-line pt-4 text-[0.9375rem]">
        <p><a href="${profile}">Full profile of ${esc(region.name)}</a> · <a href="${profile}#download">All data for this place</a></p>
        ${region.areaKm2 ? `<p class="mt-1 text-[0.875rem] text-slate">Area ${fmt(region.areaKm2, region.level === 'admin1' ? 0 : 1)} km² · AEO boundaries 2026-11-20 (OpenStreetMap)</p>` : ''}
      </div>`;
    if (block?.chart) { const c = this.el.querySelector<HTMLElement>('[data-ins-chart]'); if (c) block.chart(c); }
    const dl = this.el.querySelector<HTMLButtonElement>('[data-ins-dl]');
    if (dl && block?.download) {
      dl.addEventListener('click', async () => {
        const st = this.el.querySelector<HTMLElement>('[data-ins-status]')!;
        dl.disabled = true; st.textContent = 'Preparing the file…';
        try {
          const ctx = await getDownloadContext(this.indicators);
          st.textContent = await downloadSelection(ctx, { ...block!.download, level: region.level, wilaya: region.wilaya, commune: region.level === 'admin2' ? region.code : '' });
        } catch (e) { st.textContent = `Download failed. ${(e as Error).message}`; }
        dl.disabled = false;
      });
    }
  }

  private blockHtml(b: Block) {
    return `<section class="mt-5" aria-label="${esc(b.indicator)}">
      <p class="text-[0.9375rem] font-medium text-atlas">${esc(b.indicator)}</p>
      <p class="text-[0.875rem] text-slate">${esc(b.period)}</p>
      <p class="tabular mt-2 font-mono text-[2rem] leading-none text-atlas">${b.value}<span class="ml-1.5 font-sans text-[1rem] text-slate">${esc(b.units)}</span></p>
      <ul class="tabular mt-3 space-y-1 text-[0.9375rem] text-graphite">${b.lines.map((l) => `<li>${l}</li>`).join('')}</ul>
      ${b.chart ? `<div class="mt-4" data-ins-chart></div>` : ''}
      ${b.table ? `<details class="mt-1 text-[0.875rem]"><summary class="cursor-pointer text-slate">Values as a table</summary><div class="relative mt-2 max-h-56 overflow-auto" tabindex="0" role="region" aria-label="Values">${b.table}</div></details>` : ''}
      ${b.notes?.length ? `<ul class="mt-3 list-disc space-y-1 pl-5 text-[0.875rem] text-slate">${b.notes.map((n) => `<li>${n}</li>`).join('')}</ul>` : ''}
      <p class="mt-3 text-[0.875rem] text-slate">${b.source}</p>
      <div class="mt-4 flex flex-wrap items-center gap-2">
        ${b.download ? `<button type="button" class="btn btn-primary" data-ins-dl><svg class="icon-download" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 4v11M7 10l5 5 5-5M5 20h14" /></svg>Download CSV</button>` : ''}
        <a class="btn btn-secondary" href="${esc(b.method)}">Methods</a>
        ${b.drought ? `<a class="btn btn-secondary" href="${esc(b.drought)}">Open in Drought</a>` : ''}
      </div>
      <p class="mt-2 text-[0.875rem] text-atlas" data-ins-status role="status" aria-live="polite"></p>
    </section>`;
  }

  private noIndicator(region: InspectorRegion) {
    return `<p class="mt-5 text-[0.9375rem] text-graphite">Choose an indicator on the left to see its statistics for ${esc(region.name)}.</p>
      <p class="mt-2 text-[0.875rem] text-slate">AEO statistics are available for precipitation, drought (SPEI) and soil properties. Other layers are shown from their original providers.</p>`;
  }

  private notAvailable(region: InspectorRegion, q: InspectorQuery) {
    return `<p class="mt-5 text-[0.9375rem] text-graphite">No AEO statistics for ${esc(region.name)} for this indicator and period.</p>`;
  }

  private external(q: InspectorQuery) {
    const l = this.layers.get(q.layer!);
    const d = l?.dataset ? this.datasets[l.dataset] : null;
    return `<section class="mt-5">
      <p class="text-[0.9375rem] font-medium text-atlas">${esc(l?.title ?? q.layer)}</p>
      <p class="note mt-3">Available from external source — regional statistics not yet processed by AEO.</p>
      <p class="mt-3 text-[0.875rem] text-slate">The map shows the provider's display images; their colours are not measured values for this area.</p>
      ${d ? `<div class="mt-4 flex flex-wrap gap-2">
        ${d.source_url ? `<a class="btn btn-secondary" href="${esc(d.source_url)}" target="_blank" rel="noopener">Visit source <span aria-hidden="true">↗</span></a>` : ''}
        <a class="btn btn-secondary" href="/data/${esc(l!.dataset)}/">Dataset record</a></div>
        <p class="mt-2 text-[0.875rem] text-slate">${esc(d.provider ?? '')}${d.resolution ? ` · ${esc(d.resolution)}` : ''}</p>` : ''}
    </section>`;
  }

  // ------------------------------------------------------------------ providers
  private async block(region: InspectorRegion, q: InspectorQuery): Promise<Block | null> {
    const id = q.layer!;
    if (id === 'precip-annual' || id === 'precip-anomaly') return this.precip(region, q);
    if (id === 'spei-3' || id === 'spei-12') return this.spei(region, q, id === 'spei-3' ? '3' : '12');
    if (id === 'spi-3' || id === 'spi-12') return this.spei(region, q, id === 'spi-3' ? '3' : '12', 'spi');
    if (id.startsWith('soil-')) return this.soil(region, q);
    return null;
  }

  private async precip(region: InspectorRegion, q: InspectorQuery): Promise<Block | null> {
    const f = await loadAnnual(region.level);
    const i = f.units.findIndex((u) => u.code === region.code);
    if (i < 0) return null;
    const year = Number((q.time ?? '').slice(0, 4)) || f.years[f.years.length - 1];
    const k = f.years.indexOf(year);
    const v = k >= 0 ? f.annual[i][k] : null;
    const n = f.normal[i];
    const pct = v !== null && n !== null && n >= 1 ? (100 * (v - n)) / n : null;
    const t = f.trend[i];
    const anomaly = q.layer === 'precip-anomaly';
    const vals = f.annual[i];
    const pcts = vals.map((x) => (x === null || n === null || n < 1 ? null : (100 * (x - n)) / n));
    const unit = f.units[i];
    const notes: string[] = [];
    if (region.level === 'admin2') notes.push(unit.support === 'adequate'
      ? `Commune value: mean of ${unit.effective_cells.toFixed(1)} CHIRPS cells (≈5.5 km).`
      : `Limited spatial support: only ${unit.effective_cells.toFixed(2)} CHIRPS cell(s) of ≈5.5 km cover this commune; the value mostly reflects surrounding cells.`);
    if (anomaly && n !== null && n < 100) notes.push('The normal is below 100 mm per year: relative anomalies are large and unstable here.');
    return {
      indicator: anomaly ? 'Precipitation anomaly' : 'Annual precipitation',
      period: `Calendar year ${year}`,
      value: anomaly ? signed(pct) : fmt(v),
      units: anomaly ? '% of the 1991–2020 normal' : 'mm',
      lines: [
        anomaly ? `Total ${fmt(v)} mm against a normal of ${fmt(n)} mm` : `1991–2020 normal ${fmt(n)} mm · ${signed(pct)} %`,
        t.slope_mm_per_decade === null ? 'Trend: too few years' : `Trend ${t.period}: ${signed(t.slope_mm_per_decade, 1)} mm per decade, ${t.mk_p !== null && t.mk_p < 0.05 ? 'statistically significant' : 'not statistically significant'} (Mann–Kendall p = ${t.mk_p?.toFixed(2)})`,
        `Regional value: area-weighted mean of the 0.05° grid cells over the ${region.level === 'admin1' ? 'wilaya' : 'commune'}`,
      ],
      chart: (el) => (anomaly
        ? anomalyChart(el, f.years, pcts, { yLabel: '% of normal', format: (x) => `${x > 0 ? '+' : ''}${Math.round(x)}`, compact: true }, `Precipitation anomaly, ${region.name}`)
        : lineChart(el, [{ name: 'Annual precipitation', keys: f.years, values: vals }], { yLabel: 'mm', reference: n !== null ? { value: n, label: 'normal' } : null, compact: true }, `Annual precipitation, ${region.name}`)),
      table: `<table class="tabular w-full text-left"><thead><tr><th scope="col" class="py-1 pr-3 font-medium">Year</th><th scope="col" class="py-1 pr-3 text-right font-medium">mm</th><th scope="col" class="py-1 text-right font-medium">% vs normal</th></tr></thead><tbody>${f.years.map((y, j) => `<tr class="border-t border-line"><td class="py-0.5 pr-3">${y}</td><td class="py-0.5 pr-3 text-right">${fmt(vals[j])}</td><td class="py-0.5 text-right">${signed(pcts[j])}</td></tr>`).join('')}</tbody></table>`,
      notes,
      source: 'CHIRPS v3.0 (Climate Hazards Center, UC Santa Barbara; CC BY 4.0), 0.05° ≈ 5.5 km, processed by AEO (product v1.0.0).',
      method: '/docs/method-precipitation/',
      drought: `/drought/?level=${region.level}&unit=${region.code}&var=precip`,
      download: { indicator: 'precip', step: 'annual', from: String(f.years[0]), to: String(f.years[f.years.length - 1]), format: 'csv' },
    };
  }

  private async spei(region: InspectorRegion, q: InspectorQuery, scale: string, kind: 'spei' | 'spi' = 'spei'): Promise<Block | null> {
    const f = await (kind === 'spi' ? loadSpi : loadSpei)(region.level, region.level === 'admin2' ? region.wilaya : undefined);
    const L = kind === 'spi' ? 'SPI' : 'SPEI';
    const i = f.units.findIndex((u) => u.code === region.code);
    if (i < 0) return null;
    const month = (q.time ?? '').slice(0, 7) || f.months[f.months.length - 1];
    const mi = f.months.indexOf(month);
    const series = f.spei[scale]?.[i] ?? [];
    const v = mi >= 0 ? series[mi] ?? null : null;
    const cls = speiClass(v);
    // last 10 years up to the selected month
    const end = mi >= 0 ? mi : f.months.length - 1;
    const start = Math.max(0, end - 119);
    const keys = f.months.slice(start, end + 1).map((m) => Number(m.slice(0, 4)) + (Number(m.slice(5, 7)) - 0.5) / 12);
    const vals = series.slice(start, end + 1);
    const dry = vals.filter((x) => x !== null && x <= -1).length, n = vals.filter((x) => x !== null).length;
    const arid = (f.units[i] as any).hyper_arid;
    return {
      indicator: kind === 'spi' ? `Precipitation index SPI-${scale}` : `Drought index SPEI-${scale}`,
      period: `Month ${month} (${scale}-month ${kind === 'spi' ? 'precipitation' : 'water balance'} ending that month)`,
      value: signed(v, 2),
      units: cls ? cls.label.toLowerCase() : 'no value',
      lines: [
        `${dry} of ${n} months at or below −1 (dry) in the 10 years to ${month}; about 16 % expected`,
        'Calibrated on 1991–2020; 0 = normal for the calendar month',
        kind === 'spi' ? 'Regional value: SPI of the area-mean monthly precipitation' : 'Regional value: SPEI of the area-mean water balance P − PET',
      ],
      chart: (el) => lineChart(el, [{ name: `${L}-${scale}`, keys, values: vals }], { yLabel: `${L}-${scale}`, reference: { value: -1, label: 'dry (−1)' }, keyLabel: (k) => String(Math.floor(k)), format: (x) => x.toFixed(1), compact: true }, `${L}-${scale}, ${region.name}, 10 years`),
      table: `<table class="tabular w-full text-left"><thead><tr><th scope="col" class="py-1 pr-3 font-medium">Month</th><th scope="col" class="py-1 text-right font-medium">${L}-${scale}</th></tr></thead><tbody>${f.months.slice(start, end + 1).map((m, j) => `<tr class="border-t border-line"><td class="py-0.5 pr-3">${m}</td><td class="py-0.5 text-right">${signed(vals[j], 2)}</td></tr>`).reverse().join('')}</tbody></table>`,
      notes: arid ? [kind === 'spi' ? 'Arid area (normal below 100 mm/year): rainfall is rare and SPI is unstable.' : 'Hyper-arid area: SPEI here reflects evaporative demand (heat), not rainfall drought.'] : [],
      source: kind === 'spi'
        ? 'CHIRPS v3.0 (Climate Hazards Center, UCSB; CC BY 4.0) unit-mean precipitation; SPI computed by AEO (gamma, reference 1991–2020, product v1.0.0).'
        : 'TerraClimate P and PET (Abatzoglou et al. 2018; CC0), 1/30° ≈ 3.7 km; SPEI computed by AEO (log-logistic, product v1.0.0).',
      method: kind === 'spi' ? '/docs/method-spi/' : '/docs/method-spei/',
      drought: `/drought/?level=${region.level}&unit=${region.code}&var=${kind}&scale=${scale}`,
      download: { indicator: kind, step: 'monthly', from: f.months[0], to: f.months[f.months.length - 1], scale, format: 'csv' },
    };
  }

  private async soil(region: InspectorRegion, q: InspectorQuery): Promise<Block | null> {
    const url = region.level === 'admin1' ? `${SOIL}/admin1.json` : `${SOIL}/admin2/${region.wilaya}.json`;
    const f = await getJson(url);
    const i = f.units.findIndex((u: any) => u.code === region.code);
    if (i < 0) return null;
    const prop = q.layer!.replace(/^soil-/, '');
    const depth = q.variant ?? f.layers.find((l: any) => l.property === prop)?.depth;
    const lid = `${prop}_${depth}`;
    const meta = f.layers.find((l: any) => l.id === lid);
    if (!meta) return null;
    const v = f.mean[lid][i], lo = f.q05[lid][i], hi = f.q95[lid][i], valid = f.valid_pct[lid][i];
    const d = prop === 'phh2o' || prop === 'bdod' ? 2 : 1;
    const depths = f.layers.filter((l: any) => l.property === prop);
    const unit = f.units[i];
    const lines = [
      `Pixel 5–95 % prediction range (unit average): ${fmt(lo, d)} to ${fmt(hi, d)} ${esc(meta.units)}`,
      `Mean of the 1 km SoilGrids pixels in the ${region.level === 'admin1' ? 'wilaya' : 'commune'}; ${fmt(valid, 0)} % of them have a prediction`,
    ];
    if (prop === 'ocs' && f.total_stock_Mt?.[i] != null) lines.unshift(`Total stock 0–30 cm over predicted pixels: ${fmt(f.total_stock_Mt[i], 2)} million tonnes of carbon`);
    const notes = ['Model prediction (SoilGrids 2.0 machine learning), not a field measurement. Uncertainty is large in Algeria, where few soil profiles were available to the model.'];
    if (prop === 'soc') notes.push('Concentration in the fine earth (g of carbon per kg of soil) for this depth interval. It is not a stock: a stock also needs bulk density, coarse fragments and depth (see “Organic carbon stock”).');
    if (unit.support !== 'adequate') notes.push(`Spatial support: ${esc(unit.support)}.`);
    return {
      indicator: `${meta.label}, ${depth.replace('cm', ' cm').replace('-', '–')}`,
      period: 'SoilGrids 2.0 predictions (static map)',
      value: fmt(v, d), units: meta.units, lines, notes,
      chart: depths.length > 1 ? (el) => { el.innerHTML = depthBars(depths.map((x: any) => ({ label: x.depth.replace('cm', ' cm').replace('-', '–'), v: f.mean[x.id][i], lo: f.q05[x.id][i], hi: f.q95[x.id][i] })), meta.units, d); } : undefined,
      table: `<table class="tabular w-full text-left"><thead><tr><th scope="col" class="py-1 pr-3 font-medium">Depth</th><th scope="col" class="py-1 pr-3 text-right font-medium">Mean</th><th scope="col" class="py-1 text-right font-medium">5–95 % range</th></tr></thead><tbody>${depths.map((x: any) => `<tr class="border-t border-line"><td class="py-0.5 pr-3">${x.depth}</td><td class="py-0.5 pr-3 text-right">${fmt(f.mean[x.id][i], d)}</td><td class="py-0.5 text-right">${fmt(f.q05[x.id][i], d)}–${fmt(f.q95[x.id][i], d)}</td></tr>`).join('')}</tbody></table>`,
      source: 'ISRIC SoilGrids 2.0 (Poggio et al. 2021; CC BY 4.0), 250 m predictions aggregated to 1 km, summarised by AEO (product v1.0.0).',
      method: '/docs/method-soil/',
      download: { indicator: 'soil', step: 'stats', format: 'csv' },
    };
  }
}

/** Horizontal bars by depth with the 5–95 % range as a whisker (SVG, with a text title). */
function depthBars(rows: { label: string; v: number | null; lo: number | null; hi: number | null }[], units: string, d: number) {
  const max = Math.max(...rows.map((r) => r.hi ?? r.v ?? 0)) || 1;
  const W = 300, rowH = 30, L = 64, R = 56;
  const x = (v: number) => L + ((W - L - R) * v) / max;
  const bars = rows.map((r, i) => {
    const y = 6 + i * rowH;
    return `<text x="0" y="${y + 13}" font-size="12" fill="#586268">${r.label}</text>
      ${r.v !== null ? `<rect x="${L}" y="${y + 3}" width="${Math.max(1, x(r.v) - L)}" height="12" rx="2" fill="#8f6a3b"/>` : ''}
      ${r.lo !== null && r.hi !== null ? `<line x1="${x(r.lo)}" x2="${x(r.hi)}" y1="${y + 9}" y2="${y + 9}" stroke="#17252c" stroke-width="1.5"/><line x1="${x(r.lo)}" x2="${x(r.lo)}" y1="${y + 4}" y2="${y + 14}" stroke="#17252c" stroke-width="1.5"/><line x1="${x(r.hi)}" x2="${x(r.hi)}" y1="${y + 4}" y2="${y + 14}" stroke="#17252c" stroke-width="1.5"/>` : ''}
      <text x="${W - R + 6}" y="${y + 13}" font-size="12" fill="#17252c" font-family="IBM Plex Mono, monospace">${r.v === null ? '—' : r.v.toFixed(d)}</text>`;
  }).join('');
  return `<svg viewBox="0 0 ${W} ${rows.length * rowH + 8}" class="w-full" role="img" aria-label="Mean by depth with the 5–95 % prediction range, in ${units}"><title>Mean by depth (bars) and 5–95 % prediction range (whiskers), ${units}</title>${bars}</svg>
    <p class="mt-1 text-[0.8125rem] text-slate">Bars: mean (${esc(units)}). Whiskers: average pixel 5–95 % prediction range.</p>`;
}
