import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import {
  PRECIP, AGGREGATIONS, loadAnnual, loadMonthly, aggregate, slice, summarize, periodLabel, toCsv, download,
  type Level, type Agg, type AnnualFile, type Series,
} from '../lib/precip';
import { lineChart, anomalyChart, svgString, svgToPng, SERIES_COLORS } from '../lib/charts';
import { describeTrend, theilSen, mannKendall } from '../lib/trend.js';
import { SPEI, loadSpei, speiSeries, speiClass, SPEI_CLASSES, MONTH_NAMES } from '../lib/spei';

const BOUNDARIES = '/data/aeo/boundaries/2026-11-20';
const LEVEL_NAME: Record<Level, string> = { admin0: 'national', admin1: 'wilaya', admin2: 'commune' };
const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const fmt0 = (v: number | null | undefined) => (v === null || v === undefined ? '—' : v.toLocaleString('en-US', { maximumFractionDigits: 0 }));
const fmt1 = (v: number | null | undefined) => (v === null || v === undefined ? '—' : v.toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 }));
const sign = (v: number | null | undefined, d = 0) => (v === null || v === undefined ? '—' : `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(d)}`);
const esc = (s: unknown) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!);

interface State { level: Level; unit: string; compare: string[]; agg: Agg; from: number; to: number; anom: 'mm' | 'pct'; mapYear: number; metric: 'anomaly' | 'annual'; grid: boolean; variable: 'precip' | 'spei'; scale: number; month: number; mapMonth: string }

export async function initAnalyze() {
  const speiMapP = fetch(`${SPEI.base}/map/map.json`).then((r) => r.json());
  const speiManP = fetch(`${SPEI.base}/manifest.json`).then((r) => r.json());
  const [a0, a1, a2, manifest, mapMeta] = await Promise.all([
    loadAnnual('admin0'), loadAnnual('admin1'), loadAnnual('admin2'),
    fetch(`${PRECIP.base}/manifest.json`).then((r) => r.json()),
    fetch(`${PRECIP.base}/map/map.json`).then((r) => r.json()),
  ]);
  const annual: Record<Level, AnnualFile> = { admin0: a0, admin1: a1, admin2: a2 };
  const years = a0.years;
  const byCode = (lvl: Level) => new Map(annual[lvl].units.map((u, i) => [u.code, i]));
  const idx: Record<Level, Map<string, number>> = { admin0: byCode('admin0'), admin1: byCode('admin1'), admin2: byCode('admin2') };
  const unitOf = (lvl: Level, code: string) => annual[lvl].units[idx[lvl].get(code)!];
  const unitLabel = (lvl: Level, code: string) => {
    const u = unitOf(lvl, code);
    if (!u) return code;
    if (lvl === 'admin0') return 'Algeria';
    if (lvl === 'admin1') return `${u.name} (wilaya ${u.code})`;
    return `${u.name} (commune ${u.code}, wilaya ${unitOf('admin1', u.parent!)?.name ?? u.parent})`;
  };

  // ---------------------------------------------------------------- state from URL
  const p = new URLSearchParams(location.search);
  const lvlParam = (p.get('level') as Level) || 'admin1';
  const state: State = {
    level: ['admin0', 'admin1', 'admin2'].includes(lvlParam) ? lvlParam : 'admin1',
    unit: p.get('unit') ?? '',
    compare: (p.get('compare') ?? '').split(',').filter(Boolean),
    agg: (AGGREGATIONS.some((a) => a.id === p.get('agg')) ? p.get('agg') : 'year') as Agg,
    from: Number(p.get('from')) || years[0],
    to: Number(p.get('to')) || years[years.length - 1],
    anom: p.get('anom') === 'pct' ? 'pct' : 'mm',
    mapYear: Number(p.get('map')) || years[years.length - 1],
    metric: p.get('metric') === 'annual' ? 'annual' : 'anomaly',
    grid: p.get('grid') === '1',
    variable: p.get('var') === 'spei' ? 'spei' : 'precip',
    scale: [1, 3, 6, 12].includes(Number(p.get('scale'))) ? Number(p.get('scale')) : 3,
    month: Math.min(12, Math.max(0, Number(p.get('month')) || 0)),
    mapMonth: p.get('mmonth') ?? '',
  };
  const speiMap = await speiMapP;
  const speiMan = await speiManP;
  if (!speiMap.months.includes(state.mapMonth)) state.mapMonth = speiMap.months[speiMap.months.length - 1];
  if (state.level === 'admin0') state.unit = 'DZ';
  if (!idx[state.level].has(state.unit)) state.unit = state.level === 'admin1' ? '19' : state.level === 'admin2' ? '1901' : 'DZ';
  state.compare = state.compare.filter((c) => idx[state.level].has(c) && c !== state.unit).slice(0, 4);

  const syncUrl = () => {
    const q = new URLSearchParams({ level: state.level, unit: state.unit, agg: state.agg, from: String(state.from), to: String(state.to) });
    if (state.compare.length) q.set('compare', state.compare.join(','));
    if (state.anom === 'pct') q.set('anom', 'pct');
    if (state.mapYear !== years[years.length - 1]) q.set('map', String(state.mapYear));
    if (state.metric === 'annual') q.set('metric', 'annual');
    if (state.grid) q.set('grid', '1');
    if (state.variable === 'spei') { q.set('var', 'spei'); q.set('scale', String(state.scale)); if (state.month) q.set('month', String(state.month)); q.set('mmonth', state.mapMonth); }
    history.replaceState(null, '', `${location.pathname}?${q}`);
  };

  // ---------------------------------------------------------------- controls
  const wSel = $<HTMLSelectElement>('az-wilaya');
  const cSel = $<HTMLSelectElement>('az-commune');
  const cSearch = $<HTMLInputElement>('az-commune-search');
  const cmpSel = $<HTMLSelectElement>('az-compare');
  wSel.innerHTML = a1.units.map((u) => `<option value="${u.code}">${u.code} — ${esc(u.name)}</option>`).join('');
  const fillYears = (sel: HTMLSelectElement, ys: number[] = years) => { sel.innerHTML = ys.map((y) => `<option value="${y}">${y}</option>`).join(''); };
  fillYears($<HTMLSelectElement>('az-map-year'));

  const communesOf = (w: string) => a2.units.filter((u) => u.parent === w);
  const fillCommunes = (list = communesOf(wSel.value)) => {
    cSel.innerHTML = list.map((u) => `<option value="${u.code}">${esc(u.name)} (${u.code})${u.parent !== wSel.value ? ` — ${esc(unitOf('admin1', u.parent!)?.name)}` : ''}</option>`).join('');
  };
  const fillCompare = () => {
    const opts = state.level === 'admin2' ? communesOf(currentWilaya()) : annual[state.level].units;
    cmpSel.innerHTML = state.level === 'admin0'
      ? '<option value="">(Algeria has no peers — choose Wilaya or Commune)</option>'
      : `<option value="">Choose…</option>` + opts.filter((u) => u.code !== state.unit).map((u) => `<option value="${u.code}">${esc(u.name)} (${u.code})</option>`).join('');
    cmpSel.disabled = state.level === 'admin0';
    $<HTMLUListElement>('az-compare-list').innerHTML = state.compare.map((c, i) =>
      `<li class="flex items-center gap-1 rounded-full border border-line py-0.5 pl-2 pr-1 text-[0.78rem]"><span class="inline-block h-2 w-2 rounded-full" style="background:${SERIES_COLORS[i + 1]}"></span>${esc(unitOf(state.level, c)?.name)}<button type="button" data-remove="${c}" class="rounded-full px-1 text-slate hover:bg-mist" aria-label="Remove ${esc(unitOf(state.level, c)?.name)}">×</button></li>`).join('');
  };
  const currentWilaya = () => (state.level === 'admin2' ? unitOf('admin2', state.unit)?.parent ?? '19' : state.level === 'admin1' ? state.unit : wSel.value);

  const applyControls = () => {
    document.querySelectorAll<HTMLInputElement>('input[name="level"]').forEach((r) => { r.checked = r.value === state.level; });
    $('wilaya-wrap').classList.toggle('hidden', state.level === 'admin0');
    $('commune-wrap').classList.toggle('hidden', state.level !== 'admin2');
    wSel.value = currentWilaya();
    if (state.level === 'admin2') { fillCommunes(); cSel.value = state.unit; }
    $<HTMLSelectElement>('az-agg').value = state.agg;
    const vy: number[] = [];
    const [y0, y1] = state.variable === 'spei' ? [Number(speiMan.temporal_coverage.monthly[0].slice(0, 4)), Number(speiMan.temporal_coverage.monthly[1].slice(0, 4))] : [years[0], years[years.length - 1]];
    for (let y = y0; y <= y1; y++) vy.push(y);
    fillYears($<HTMLSelectElement>('az-from'), vy); fillYears($<HTMLSelectElement>('az-to'), vy);
    if (state.from < y0 || state.from > y1) state.from = y0;
    if (state.to > y1 || state.to < y0) state.to = y1;
    $('az-source').innerHTML = state.variable === 'spei'
      ? `Source: TerraClimate (Abatzoglou et al. 2018, doi:10.1038/sdata.2017.191; CC0), SPEI computed by AEO — <a href="${SPEI.page}">product page</a>, <a href="${SPEI.method}">method</a>.`
      : `Source: CHIRPS v3.0 (Climate Hazards Center, UC Santa Barbara; doi:10.15780/G2JQ0P; CC BY 4.0), processed by AEO — <a href="${PRECIP.datasetPage}">product page</a>, <a href="${PRECIP.methodPage}">method</a>.`;
    $<HTMLSelectElement>('az-from').value = String(state.from);
    $<HTMLSelectElement>('az-to').value = String(state.to);
    $<HTMLSelectElement>('az-map-year').value = String(state.mapYear);
    $<HTMLSelectElement>('az-map-metric').value = state.metric;
    $<HTMLInputElement>('az-map-grid').checked = state.grid;
    document.querySelectorAll<HTMLInputElement>('input[name="anom-unit"]').forEach((r) => { r.checked = r.value === state.anom; });
    $<HTMLSelectElement>('az-variable').value = state.variable;
    if (state.level === 'admin2' && (state.scale === 1 || state.scale === 6)) state.scale = 3;
    $<HTMLSelectElement>('az-scale').value = String(state.scale);
    [...$<HTMLSelectElement>('az-scale').options].forEach((o) => { o.disabled = state.level === 'admin2' && (o.value === '1' || o.value === '6'); });
    $<HTMLSelectElement>('az-month').value = String(state.month);
    $('spei-controls').classList.toggle('hidden', state.variable !== 'spei');
    $('agg-wrap').classList.toggle('hidden', state.variable === 'spei');
    document.querySelectorAll<HTMLElement>('[data-precip-only]').forEach((e) => e.classList.toggle('hidden', state.variable === 'spei'));
    const ys = $<HTMLSelectElement>('az-map-year');
    ys.innerHTML = state.variable === 'spei' ? speiMap.months.map((m: string) => `<option value="${m}">${m}</option>`).join('') : years.map((y) => `<option value="${y}">${y}</option>`).join('');
    ys.value = state.variable === 'spei' ? state.mapMonth : String(state.mapYear);
    fillCompare();
  };

  document.querySelectorAll<HTMLInputElement>('input[name="level"]').forEach((r) => r.addEventListener('change', () => {
    const w = currentWilaya();
    state.level = r.value as Level;
    state.unit = state.level === 'admin0' ? 'DZ' : state.level === 'admin1' ? w : communesOf(w)[0].code;
    state.compare = [];
    refresh(true);
  }));
  wSel.addEventListener('change', () => {
    state.compare = [];
    state.unit = state.level === 'admin2' ? communesOf(wSel.value)[0].code : wSel.value;
    refresh(true);
  });
  cSel.addEventListener('change', () => { if (cSel.value) { state.unit = cSel.value; state.compare = []; refresh(true); } });
  cSearch.addEventListener('input', () => {
    const q = cSearch.value.trim().toLowerCase();
    fillCommunes(q.length < 2 ? communesOf(wSel.value) : a2.units.filter((u) => `${u.name} ${u.name_ar ?? ''} ${u.code}`.toLowerCase().includes(q)).slice(0, 60));
  });
  $('az-compare-add').addEventListener('click', () => {
    if (cmpSel.value && !state.compare.includes(cmpSel.value) && state.compare.length < 4) { state.compare.push(cmpSel.value); refresh(false); }
  });
  $('az-compare-list').addEventListener('click', (e) => {
    const c = (e.target as HTMLElement).closest('button')?.dataset.remove;
    if (c) { state.compare = state.compare.filter((x) => x !== c); refresh(false); }
  });
  $<HTMLSelectElement>('az-agg').addEventListener('change', (e) => { state.agg = (e.target as HTMLSelectElement).value as Agg; refresh(false); });
  $<HTMLSelectElement>('az-variable').addEventListener('change', (e) => { state.variable = (e.target as HTMLSelectElement).value as State['variable']; state.from = 0; state.to = 9999; refresh(true); });
  $<HTMLSelectElement>('az-scale').addEventListener('change', (e) => { state.scale = Number((e.target as HTMLSelectElement).value); refresh(false); });
  $<HTMLSelectElement>('az-month').addEventListener('change', (e) => { state.month = Number((e.target as HTMLSelectElement).value); refresh(false); });
  $<HTMLSelectElement>('az-from').addEventListener('change', (e) => { state.from = Number((e.target as HTMLSelectElement).value); if (state.from > state.to) state.to = state.from; refresh(false); });
  $<HTMLSelectElement>('az-to').addEventListener('change', (e) => { state.to = Number((e.target as HTMLSelectElement).value); if (state.to < state.from) state.from = state.to; refresh(false); });
  document.querySelectorAll<HTMLInputElement>('input[name="anom-unit"]').forEach((r) => r.addEventListener('change', () => { state.anom = r.value as 'mm' | 'pct'; refresh(false); }));
  $<HTMLSelectElement>('az-map-year').addEventListener('change', (e) => { const v = (e.target as HTMLSelectElement).value; if (state.variable === 'spei') state.mapMonth = v; else state.mapYear = Number(v); updateMap(); syncUrl(); });
  $<HTMLSelectElement>('az-map-metric').addEventListener('change', (e) => { state.metric = (e.target as HTMLSelectElement).value as State['metric']; updateMap(); syncUrl(); });
  $<HTMLInputElement>('az-map-grid').addEventListener('change', (e) => { state.grid = (e.target as HTMLInputElement).checked; updateMap(); syncUrl(); });

  // ---------------------------------------------------------------- computation
  let last: { series: Series[]; codes: string[]; labels: string[] } | null = null;
  async function seriesFor(code: string): Promise<Series> {
    const lvl = state.level;
    const ui = idx[lvl].get(code)!;
    if (state.agg === 'year') return aggregate('year', ui, annual[lvl]);
    const mon = await loadMonthly(lvl, lvl === 'admin2' ? unitOf('admin2', code).parent! : undefined);
    return aggregate(state.agg, ui, annual[lvl], mon, mon.units.indexOf(code));
  }

  async function compute() {
    if (state.variable === 'spei') return computeSpei();
    const codes = [state.unit, ...state.compare];
    const full = await Promise.all(codes.map(seriesFor));
    const series = full.map((s) => slice(s, state.from, state.to));
    const labels = codes.map((c) => unitLabel(state.level, c));
    last = { series, codes, labels };
    const aggInfo = AGGREGATIONS.find((a) => a.id === state.agg)!;
    const s0 = series[0];
    const sum = summarize(s0);
    const unit0 = unitOf(state.level, state.unit);

    $('az-title').textContent = `Precipitation — ${labels[0]}`;
    $('az-subtitle').textContent = `${aggInfo.label}, ${s0.keys[0] ?? state.from}–${s0.keys[s0.keys.length - 1] ?? state.to} · area-weighted mean over the ${LEVEL_NAME[state.level]} area · CHIRPS v3.0, AEO product v${PRECIP.version}`;
    const support = $('az-support');
    if (state.level === 'admin2') {
      support.classList.remove('hidden');
      support.textContent = unit0.support === 'adequate'
        ? `Commune value: average of the ${unit0.effective_cells.toFixed(1)} CHIRPS grid cells (≈5.5 km) covering this commune. It describes the commune area as a whole, not a local measurement.`
        : `Limited spatial support: this commune covers only ${unit0.effective_cells.toFixed(2)} CHIRPS grid cell(s) of about 5.5 km. Its values mostly reflect the surrounding cells; interpret with care.`;
    } else support.classList.add('hidden');

    // tiles
    const lastIdx = s0.values.length - 1;
    const tiles: [string, string, string?][] = [
      ['Mean, selected period', `${fmt0(sum.mean)} mm`, `${sum.n} ${state.agg === 'year' ? 'years' : 'periods'}`],
      ['Normal 1991–2020', `${fmt0(s0.normal)} mm`],
      ['Driest', sum.min ? `${fmt0(sum.min[1])} mm` : '—', sum.min ? periodLabel(state.agg, sum.min[0]) : ''],
      ['Wettest', sum.max ? `${fmt0(sum.max[1])} mm` : '—', sum.max ? periodLabel(state.agg, sum.max[0]) : ''],
      [`Latest (${s0.keys[lastIdx] !== undefined ? periodLabel(state.agg, s0.keys[lastIdx]) : '—'})`, `${fmt0(s0.values[lastIdx])} mm`, s0.anomaliesPct[lastIdx] !== null ? `${sign(s0.anomaliesPct[lastIdx])} % vs normal` : ''],
      ['Variability (CV)', sum.cv !== null ? `${sum.cv.toFixed(0)} %` : '—', 'std. dev. / mean'],
    ];
    $('az-tiles').innerHTML = tiles.map(([k, v, n]) => `<div class="rounded-md border border-line bg-surface px-3 py-2.5"><dt class="text-[0.75rem] text-slate">${esc(k)}</dt><dd class="mt-0.5 text-[1.15rem] font-semibold text-atlas">${esc(v)}</dd>${n ? `<dd class="text-[0.75rem] text-slate">${esc(n)}</dd>` : ''}</div>`).join('');

    // trend
    const ts = sum.ts, mk = sum.mk;
    $('az-trend').innerHTML = ts.slope === null || mk.p === null
      ? 'Trend: too few values in this period for a trend test (at least 8 needed).'
      : `<strong class="text-atlas">Trend ${s0.keys[0]}–${s0.keys[s0.keys.length - 1]} (n = ${mk.n}):</strong> ${esc(describeTrend({ slope: ts.slope! * 10, lo: ts.lo! * 10, hi: ts.hi! * 10 }, mk))}${mk.corrected ? ' Lag-1 autocorrelation was significant; the test variance was corrected.' : ''}`;

    // charts
    const keyLabel = (k: number) => (state.agg === 'hydro' ? `${String(k - 1).slice(2)}/${String(k).slice(2)}` : String(k));
    $('az-legend').innerHTML = series.length > 1 ? labels.map((l, i) => `<li class="flex items-center gap-1.5"><span class="inline-block h-0.5 w-4" style="background:${SERIES_COLORS[i]}"></span>${esc(l)}</li>`).join('') : '';
    lineChart($('az-ts'), series.map((s, i) => ({ name: codes.length > 1 ? (unitOf(state.level, codes[i])?.name ?? codes[i]) : 'Precipitation', keys: s.keys, values: s.values })), {
      yLabel: 'mm',
      reference: series.length === 1 && s0.normal !== null ? { value: s0.normal, label: `1991–2020 normal ${fmt0(s0.normal)} mm` } : null,
      trend: series.length === 1 && ts.slope !== null && mk.p !== null ? { slope: ts.slope, intercept: ts.intercept!, from: s0.keys[0], to: s0.keys[s0.keys.length - 1] } : null,
      keyLabel,
    }, `${aggInfo.label} precipitation, ${labels.join(', ')}`);
    const anomVals = state.anom === 'pct' ? s0.anomaliesPct : s0.anomalies;
    $('az-an-unit-note').textContent = state.anom === 'pct' ? '— in % of the 1991–2020 normal' : '— in mm';
    anomalyChart($('az-an'), s0.keys, anomVals, { yLabel: state.anom === 'pct' ? '% of normal' : 'mm', keyLabel }, `Anomalies, ${labels[0]}`);

    // table
    const head = ['Period', ...codes.map((c) => esc(unitOf(state.level, c)?.name ?? c)), 'Anomaly (mm)', 'Anomaly (%)'];
    $('az-table').innerHTML = `<thead class="sticky top-0 bg-surface"><tr>${head.map((h) => `<th class="border-b border-line py-1.5 pr-3 font-semibold">${h}</th>`).join('')}</tr></thead><tbody>` +
      s0.keys.map((k, i) => `<tr class="border-b border-line/60"><td class="py-1 pr-3">${periodLabel(state.agg, k)}</td>${series.map((s) => `<td class="py-1 pr-3 font-mono">${fmt1(s.values[s.keys.indexOf(k)])}</td>`).join('')}<td class="py-1 pr-3 font-mono">${sign(s0.anomalies[i], 1)}</td><td class="py-1 pr-3 font-mono">${sign(s0.anomaliesPct[i], 1)}</td></tr>`).join('') + '</tbody>';

    renderDownloads(manifest);
  }

  function selectionCsv() {
    if (!last) return '';
    const rows: Record<string, unknown>[] = [];
    last.series.forEach((s, si) => s.keys.forEach((k, i) => rows.push({
      level: state.level, unit_code: last!.codes[si], unit_name: unitOf(state.level, last!.codes[si])?.name,
      period_type: state.agg, period: periodLabel(state.agg, k), key_year: k,
      precip_mm: s.values[i], normal_1991_2020_mm: s.normal, anomaly_mm: s.anomalies[i], anomaly_pct: s.anomaliesPct[i],
      source: 'CHIRPS v3.0 (doi:10.15780/G2JQ0P), CC BY 4.0', product: `${PRECIP.id} v${PRECIP.version}`, boundary_version: annual[state.level].boundary_version,
    })));
    return toCsv(rows);
  }

  function renderDownloads(man: { download_assets: { href: string; format: string; level: string | null; unit_code?: string; title: string; bytes: number }[] }) {
    const mb = (b: number) => (b > 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1e3))} kB`);
    const items: string[] = [];
    items.push(`<li><button type="button" class="link-btn" id="dl-csv">This selection (CSV)</button> <span class="text-slate text-[0.8rem]">generated from the published tables</span></li>`);
    const nat = man.download_assets.find((a) => a.href.includes('_annual_') && a.level === 'admin0' && a.format === 'COG');
    if (nat) items.push(`<li><a href="${nat.href}" download>Algeria — annual grids (GeoTIFF)</a> <span class="text-slate text-[0.8rem]">${mb(nat.bytes)}</span></li>`);
    const w = state.level === 'admin1' ? state.unit : state.level === 'admin2' ? unitOf('admin2', state.unit).parent : null;
    const wa = w ? man.download_assets.find((a) => a.level === 'admin1' && a.unit_code === w) : null;
    if (wa) items.push(`<li><a href="${wa.href}" download>Wilaya ${esc(unitOf('admin1', w!)?.name)} — annual grids (GeoTIFF)</a> <span class="text-slate text-[0.8rem]">${mb(wa.bytes)}</span></li>`);
    if (state.level === 'admin2') items.push(`<li class="text-slate text-[0.85rem]">Commune grids are not published: at 5.5 km resolution a commune holds only a few cells. Use the wilaya file.</li>`);
    for (const a of man.download_assets.filter((x) => x.level === state.level && /annual|summary/.test(x.href) && x.format !== 'COG')) {
      items.push(`<li><a href="${a.href}" download>${esc(a.title)} (${a.format})</a> <span class="text-slate text-[0.8rem]">${mb(a.bytes)}</span></li>`);
    }
    items.push(`<li><a href="${PRECIP.base}/manifest.json">Metadata (manifest, JSON)</a> · <a href="${PRECIP.base}/PROVENANCE.json">provenance</a></li>`);
    $('az-downloads').innerHTML = items.join('');
    $('dl-csv')?.addEventListener('click', () => download(`aeo_precip_${state.level}_${state.unit}_${state.agg}_${state.from}-${state.to}.csv`, selectionCsv()));
  }

  document.querySelectorAll<HTMLButtonElement>('[data-export]').forEach((b) => b.addEventListener('click', async () => {
    const svg = document.querySelector<SVGSVGElement>(`#az-${b.dataset.export} svg`);
    if (!svg) return;
    const name = `aeo_precip_${b.dataset.export === 'ts' ? 'timeseries' : 'anomalies'}_${state.unit}_${state.agg}_${state.from}-${state.to}`;
    const footer = `${$('az-title').textContent} · ${AGGREGATIONS.find((a) => a.id === state.agg)!.label} · Source: CHIRPS v3.0 (CC BY 4.0), Algeria Earth Observatory`;
    if (b.dataset.fmt === 'svg') download(`${name}.svg`, svgString(svg), 'image/svg+xml');
    else download(`${name}.png`, await svgToPng(svg, footer));
  }));

  // ---------------------------------------------------------------- map
  const styleUrl = 'https://tiles.openfreemap.org/styles/dark';
  const map = new maplibregl.Map({ container: 'az-map', style: styleUrl, bounds: [-8.7, 18.9, 12.0, 37.2], fitBoundsOptions: { padding: 16 }, attributionControl: { compact: true } });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
  map.dragRotate.disable(); map.touchZoomRotate.disableRotation();
  let mapReady = false;
  const geo: Partial<Record<'admin1' | 'admin2', Promise<GeoJSON.FeatureCollection>>> = {};
  const loadGeo = (lvl: 'admin1' | 'admin2') => (geo[lvl] ??= fetch(`${BOUNDARIES}/${lvl === 'admin1' ? 'dza_adm1_wilayas_display' : 'dza_adm2_communes_display'}.geojson`).then((r) => r.json()));
  const mapLevel = () => (state.level === 'admin2' ? 'admin2' : 'admin1') as 'admin1' | 'admin2';
  const codeProp = () => (mapLevel() === 'admin2' ? 'commune_code' : 'wilaya_code');

  function classColor(v: number | null, breaks: number[], colors: string[]) {
    if (v === null || Number.isNaN(v)) return '#d9dee2';
    let i = 0;
    while (i < breaks.length && v >= breaks[i]) i++;
    return colors[i];
  }

  async function updateMap() {
    if (!mapReady) return;
    if (state.variable === 'spei') return updateMapSpei();
    const lvl = mapLevel();
    const data = await loadGeo(lvl);
    const file = annual[lvl];
    const yi = file.years.indexOf(state.mapYear);
    const meta = state.metric === 'anomaly' ? mapMeta.anomaly : mapMeta.annual;
    const expr: unknown[] = ['match', ['get', codeProp()]];
    file.units.forEach((u, i) => {
      const v = file.annual[i][yi];
      const n = file.normal[i];
      const val = state.metric === 'anomaly' ? (v === null || n === null || n < 1 ? null : (100 * (v - n)) / n) : v;
      expr.push(u.code, classColor(val, meta.breaks, meta.colors));
    });
    expr.push('#d9dee2');
    const src = map.getSource('units') as maplibregl.GeoJSONSource | undefined;
    if (!src) {
      map.addSource('units', { type: 'geojson', data });
      const before = map.getStyle().layers.find((l) => l.type === 'symbol')?.id;
      map.addSource('grid', { type: 'image', url: `${PRECIP.base}/map/annual_${state.mapYear}.png`, coordinates: mapMeta.coordinates });
      map.addLayer({ id: 'grid', type: 'raster', source: 'grid', paint: { 'raster-opacity': 0.9, 'raster-resampling': 'nearest' }, layout: { visibility: 'none' } }, before);
      map.addLayer({ id: 'units-fill', type: 'fill', source: 'units', paint: { 'fill-color': expr as any, 'fill-opacity': 0.85 } }, before);
      map.addSource('outside', { type: 'geojson', data: `${BOUNDARIES}/dza_outside_mask.geojson` });
      map.addLayer({ id: 'outside-mask', type: 'fill', source: 'outside', paint: { 'fill-color': '#050a14', 'fill-opacity': 0.82 } });
      map.addLayer({ id: 'units-line', type: 'line', source: 'units', paint: { 'line-color': '#0d1626', 'line-width': 0.6 } }, before);
      map.addLayer({ id: 'units-sel', type: 'line', source: 'units', paint: { 'line-color': '#ffffff', 'line-width': 2.5 }, filter: ['in', ['get', codeProp()], ['literal', []]] });
      map.on('click', 'units-fill', (e) => {
        const code = String(e.features?.[0]?.properties?.[codeProp()] ?? '');
        if (!code) return;
        if (state.level === 'admin0') state.level = 'admin1';
        state.unit = code; state.compare = [];
        refresh(true);
      });
      map.on('mouseenter', 'units-fill', () => { map.getCanvas().style.cursor = 'pointer'; });
      map.on('mouseleave', 'units-fill', () => { map.getCanvas().style.cursor = ''; });
    } else {
      if ((src as any)._lastLevel !== lvl) src.setData(data);
      map.setPaintProperty('units-fill', 'fill-color', expr as any);
    }
    (map.getSource('units') as any)._lastLevel = lvl;
    const gridSrc = map.getSource('grid') as maplibregl.ImageSource;
    gridSrc.updateImage({ url: `${PRECIP.base}/map/${state.metric === 'anomaly' ? 'anomaly' : 'annual'}_${state.mapYear}.png`, coordinates: mapMeta.coordinates });
    map.setLayoutProperty('grid', 'visibility', state.grid ? 'visible' : 'none');
    map.setPaintProperty('units-fill', 'fill-opacity', state.grid ? 0 : 0.85);
    const sel = state.level === 'admin0' ? [] : [state.unit, ...state.compare];
    map.setFilter('units-sel', ['in', ['get', codeProp()], ['literal', sel]]);
    $('az-map-level').textContent = (lvl === 'admin2' ? 'commune' : 'wilaya') + ' — calendar-year ' + (state.metric === 'anomaly' ? 'anomaly' : 'total') + ', ' + state.mapYear;
    $('az-map-legend').innerHTML = `<span class="text-slate">${state.metric === 'anomaly' ? '% of 1991–2020 normal' : 'mm'}:</span>` +
      meta.colors.map((c: string, i: number) => {
        const lo = i === 0 ? null : meta.breaks[i - 1], hi = i < meta.breaks.length ? meta.breaks[i] : null;
        const lab = lo === null ? `< ${hi}` : hi === null ? `≥ ${lo}` : `${lo} – ${hi}`;
        return `<span class="flex items-center gap-1"><span class="inline-block h-2.5 w-3.5 rounded-sm border border-black/10" style="background:${c}"></span>${lab}</span>`;
      }).join('') + `<span class="flex items-center gap-1"><span class="inline-block h-2.5 w-3.5 rounded-sm" style="background:#d9dee2"></span>no data</span>`;
  }
  map.on('load', () => { mapReady = true; updateMap(); });

  // ---------------------------------------------------------------- SPEI
  async function speiFileFor(code: string) {
    const lvl = state.level;
    return loadSpei(lvl, lvl === 'admin2' ? unitOf('admin2', code).parent! : undefined);
  }
  let lastSpei: { codes: string[]; series: ReturnType<typeof speiSeries>[] } | null = null;

  async function computeSpei() {
    const codes = [state.unit, ...state.compare];
    const files = await Promise.all(codes.map(speiFileFor));
    const series = codes.map((c, i) => speiSeries(files[i], c, state.scale, state.month, state.from, state.to));
    lastSpei = { codes, series };
    const s0 = series[0];
    const labels = codes.map((c) => unitLabel(state.level, c));
    const vals = s0.values.filter((v): v is number => v !== null);
    const nDry = vals.filter((v) => v <= -1).length, nSev = vals.filter((v) => v <= -1.5).length;
    let worst: number | null = null, worstAt = '';
    s0.values.forEach((v, i) => { if (v !== null && (worst === null || v < worst)) { worst = v; worstAt = s0.labels[i]; } });
    const li = s0.values.length - 1;
    const latest = s0.values[li] ?? null;
    const cls = speiClass(latest);
    const per = state.month ? `${MONTH_NAMES[state.month - 1]} only` : 'all months';
    $('az-title').textContent = `SPEI-${state.scale} — ${labels[0]}`;
    $('az-subtitle').textContent = `Drought index (${per}), ${state.from}–${state.to} · computed on the area-weighted water balance P − PET · TerraClimate, AEO product v${SPEI.version}`;
    const support = $('az-support');
    if (s0.unit?.hyper_arid) {
      support.classList.remove('hidden');
      support.textContent = 'Hyper-arid area (normal precipitation below 100 mm/year): SPEI here reflects anomalies of evaporative demand (heat), not of water supply. Interpret as an aridity-stress signal, not as rainfall drought.';
    } else if (state.level === 'admin2') {
      support.classList.remove('hidden');
      support.textContent = 'Commune value computed on the commune-average water balance from ≈3.7 km TerraClimate cells; TerraClimate is an interpolated product with few stations in Algeria.';
    } else support.classList.add('hidden');
    const tiles: [string, string, string?][] = [
      [`Latest (${s0.labels[li] ?? '—'})`, latest === null ? '—' : sign(latest, 2), cls?.label ?? ''],
      ['Periods ≤ −1 (dry)', vals.length ? `${Math.round((100 * nDry) / vals.length)} %` : '—', `${nDry} of ${vals.length}`],
      ['Periods ≤ −1.5 (severe)', vals.length ? `${Math.round((100 * nSev) / vals.length)} %` : '—', `${nSev} of ${vals.length}`],
      ['Driest', worst === null ? '—' : sign(worst, 2), worstAt],
      ['Expected share ≤ −1', '≈ 16 %', 'in the 1991–2020 reference'],
      ['Timescale', `SPEI-${state.scale}`, `${state.scale}-month water balance`],
    ];
    $('az-tiles').innerHTML = tiles.map(([k, v, n]) => `<div class="rounded-md border border-line bg-surface px-3 py-2.5"><dt class="text-[0.75rem] text-slate">${esc(k)}</dt><dd class="mt-0.5 text-[1.15rem] font-semibold text-atlas">${esc(v)}</dd>${n ? `<dd class="text-[0.75rem] text-slate">${esc(n)}</dd>` : ''}</div>`).join('');
    if (state.month) {
      const ts = theilSen(s0.values, s0.keys), mk = mannKendall(s0.values);
      $('az-trend').innerHTML = ts.slope === null || mk.p === null ? 'Trend: too few years (at least 8 needed).'
        : `<strong class="text-atlas">Trend of ${MONTH_NAMES[state.month - 1]} SPEI-${state.scale}, ${s0.keys[0]}–${s0.keys[s0.keys.length - 1]} (n = ${mk.n}):</strong> ${esc(describeTrend({ slope: ts.slope * 10, lo: ts.lo! * 10, hi: ts.hi! * 10 }, mk, 'SPEI units'))}`;
    } else {
      $('az-trend').textContent = 'Trend tests are shown for one calendar month at a time (choose a month): consecutive monthly SPEI values overlap and are strongly autocorrelated.';
    }
    $('az-legend').innerHTML = series.length > 1 ? labels.map((l, i) => `<li class="flex items-center gap-1.5"><span class="inline-block h-0.5 w-4" style="background:${SERIES_COLORS[i]}"></span>${esc(l)}</li>`).join('') : '';
    const keyLabel = (k: number) => (state.month ? String(k) : String(Math.floor(k + 1e-9)));
    lineChart($('az-ts'), series.map((s, i) => ({ name: codes.length > 1 ? (unitOf(state.level, codes[i])?.name ?? codes[i]) : `SPEI-${state.scale}`, keys: s.keys, values: s.values })),
      { yLabel: `SPEI-${state.scale}`, reference: { value: -1, label: 'dry threshold −1' }, keyLabel, format: (v: number) => v.toFixed(1) }, `SPEI-${state.scale}, ${labels.join(', ')}`);
    $('az-an-unit-note').textContent = `— SPEI-${state.scale} of ${labels[0]} (blue wet, red dry)`;
    anomalyChart($('az-an'), s0.keys, s0.values, { yLabel: `SPEI-${state.scale}`, keyLabel, format: (v: number) => `${v > 0 ? '+' : ''}${v.toFixed(1)}` }, `SPEI-${state.scale} anomalies, ${labels[0]}`);
    const head = ['Month', ...codes.map((c) => esc(unitOf(state.level, c)?.name ?? c)), 'Class'];
    $('az-table').innerHTML = `<thead class="sticky top-0 bg-surface"><tr>${head.map((h) => `<th class="border-b border-line py-1.5 pr-3 font-semibold">${h}</th>`).join('')}</tr></thead><tbody>` +
      s0.labels.map((lab, i) => `<tr class="border-b border-line/60"><td class="py-1 pr-3">${lab}</td>${series.map((s) => `<td class="py-1 pr-3 font-mono">${s.values[i] === null || s.values[i] === undefined ? '—' : sign(s.values[i], 2)}</td>`).join('')}<td class="py-1 pr-3 text-slate">${speiClass(s0.values[i])?.label ?? ''}</td></tr>`).join('') + '</tbody>';
    const mb = (b: number) => (b > 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1e3))} kB`);
    const items = [`<li><button type="button" class="link-btn" id="dl-csv">This selection (CSV)</button> <span class="text-slate text-[0.8rem]">generated from the published tables</span></li>`];
    for (const a of speiMan.download_assets.filter((x: any) => x.format === 'COG' || x.level === state.level)) {
      items.push(`<li><a href="${a.href}" download>${esc(a.title)} (${a.format})</a> <span class="text-slate text-[0.8rem]">${mb(a.bytes)}</span></li>`);
    }
    items.push(`<li><a href="${SPEI.base}/manifest.json">Metadata (manifest)</a> · <a href="${SPEI.base}/PROVENANCE.json">provenance</a> · <a href="${SPEI.method}">method</a></li>`);
    $('az-downloads').innerHTML = items.join('');
    $('dl-csv')?.addEventListener('click', () => {
      const rows: Record<string, unknown>[] = [];
      lastSpei!.series.forEach((s, si) => s.labels.forEach((lab, i) => rows.push({ level: state.level, unit_code: lastSpei!.codes[si], unit_name: unitOf(state.level, lastSpei!.codes[si])?.name,
        month: lab, [`spei_${state.scale}`]: s.values[i], class: speiClass(s.values[i])?.label ?? null, hyper_arid: s.unit?.hyper_arid ?? null,
        source: 'TerraClimate (doi:10.1038/sdata.2017.191), CC0', product: `${SPEI.id} v${SPEI.version}` })));
      download(`aeo_spei${state.scale}_${state.level}_${state.unit}_${state.month || 'all'}_${state.from}-${state.to}.csv`, toCsv(rows));
    });
  }

  async function updateMapSpei() {
    const lvl = mapLevel();
    const data = await loadGeo(lvl);
    const scaleKey = state.level === 'admin2' && (state.scale === 1 || state.scale === 6) ? '3' : String(state.scale);
    const f = lvl === 'admin2' ? await loadSpei('admin2', unitOf('admin2', state.unit).parent!) : await loadSpei('admin1');
    const t = f.months.indexOf(state.mapMonth);
    const expr: unknown[] = ['match', ['get', codeProp()]];
    f.units.forEach((u, i) => {
      const v = t < 0 ? null : f.spei[scaleKey]?.[i]?.[t] ?? null;
      expr.push(u.code, u.hyper_arid ? '#5c5340' : (speiClass(v)?.color ?? '#5c5340'));
    });
    expr.push('#1a2433');
    const src = map.getSource('units') as maplibregl.GeoJSONSource | undefined;
    if (!src) { state.variable = 'precip'; await updateMap(); state.variable = 'spei'; }
    const s2 = map.getSource('units') as maplibregl.GeoJSONSource;
    if ((s2 as any)._lastLevel !== lvl) { s2.setData(data); (s2 as any)._lastLevel = lvl; }
    map.setPaintProperty('units-fill', 'fill-color', expr as any);
    const k = state.scale === 12 ? 12 : 3;
    (map.getSource('grid') as maplibregl.ImageSource).updateImage({ url: `${SPEI.base}/map/spei${k}_${state.mapMonth}.png`, coordinates: speiMap.coordinates });
    map.setLayoutProperty('grid', 'visibility', state.grid ? 'visible' : 'none');
    map.setPaintProperty('units-fill', 'fill-opacity', state.grid ? 0 : 0.85);
    map.setFilter('units-sel', ['in', ['get', codeProp()], ['literal', state.level === 'admin0' ? [] : [state.unit, ...state.compare]]]);
    $('az-map-level').textContent = `${lvl === 'admin2' ? 'commune (selected wilaya)' : 'wilaya'} — SPEI-${scaleKey} in ${state.mapMonth}${state.grid ? `; grid: SPEI-${k}` : ''}`;
    $('az-map-legend').innerHTML = SPEI_CLASSES.map((c) => `<span class="flex items-center gap-1"><span class="inline-block h-2.5 w-3.5 rounded-sm" style="background:${c.color}"></span>${c.label}</span>`).join('') +
      `<span class="flex items-center gap-1"><span class="inline-block h-2.5 w-3.5 rounded-sm" style="background:#5c5340"></span>hyper-arid / no data</span>`;
  }

  // ---------------------------------------------------------------- go
  let busy = false, pending = false;
  async function refresh(controls: boolean) {
    if (controls) applyControls(); else fillCompare();
    syncUrl();
    if (busy) { pending = true; return; }
    busy = true;
    try {
      do { pending = false; await compute(); await updateMap(); } while (pending);
    } catch (err) {
      $('az-title').textContent = 'Could not load the data';
      $('az-subtitle').textContent = String(err);
    } finally { busy = false; }
  }
  refresh(true);
}
