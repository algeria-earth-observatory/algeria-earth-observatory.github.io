/**
 * Map explorer inspector: values of the active AEO layers for the selected wilaya or
 * commune, read from the published product JSON (the same files Analyze uses).
 * Layers without AEO statistics are listed as display-only, never given a value.
 */
import { loadAnnual } from '../lib/precip';
import { loadSpei, speiClass } from '../lib/spei';
import { MAP_LAYERS } from '../data/map-layers';
import type { MapState } from './map-core';

const esc = (s: unknown) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!);
const num = (v: number | null | undefined, d = 0) => (v === null || v === undefined ? '—' : v.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d }));
const signed = (v: number | null | undefined, d = 0) => (v === null || v === undefined ? '—' : `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(d)}`);

export type Selection = { kind: 'wilaya' | 'commune'; props: Record<string, any> };

export async function inspectorHtml(sel: Selection, state: MapState): Promise<string> {
  const p = sel.props;
  const isW = sel.kind === 'wilaya';
  const code = String(isW ? p.wilaya_code : p.commune_code);
  const wilaya = String(p.wilaya_code);
  const level = isW ? 'admin1' : 'admin2';
  const rows: string[] = [];
  const display: string[] = [];
  let analyze = `/analyze/?level=${level}&unit=${code}`;

  for (const l of MAP_LAYERS) {
    if (!state.layers[l.id]?.on || l.id === 'wilayas' || l.id === 'communes') continue;
    const t = state.layers[l.id].time ?? '';
    if (l.id === 'precip-annual' || l.id === 'precip-anomaly') {
      const f = await loadAnnual(level);
      const i = f.units.findIndex((u) => u.code === code);
      const yi = f.years.indexOf(Number(t.slice(0, 4)));
      const v = i >= 0 && yi >= 0 ? f.annual[i][yi] : null;
      const n = i >= 0 ? f.normal[i] : null;
      const pct = v !== null && n !== null && n >= 1 ? (100 * (v - n)) / n : null;
      rows.push(`<div class="border-t border-line py-3"><p class="text-graphite">Precipitation <span class="font-mono text-[0.72rem] text-slate">${esc(t.slice(0, 4))}</span></p>
        <p class="tabular mt-1 text-[1.25rem] text-atlas">${num(v)} <span class="text-[0.8rem] text-slate">mm</span></p>
        <p class="tabular font-mono text-[0.72rem] text-slate">${signed(pct)} % vs 1991–2020 normal (${num(n)} mm)</p>
        <p class="mt-1 text-[0.72rem] text-slate">CHIRPS v3.0 · area-weighted mean of 0.05° cells${!isW ? ' · commune support: ' + esc(f.units[i]?.support) : ''}</p></div>`);
    } else if (l.id === 'spei-3' || l.id === 'spei-12') {
      const k = l.id === 'spei-3' ? '3' : '12';
      const f = await loadSpei(level, isW ? undefined : wilaya);
      const i = f.units.findIndex((u) => u.code === code);
      const mi = f.months.indexOf(t.slice(0, 7));
      const v = i >= 0 && mi >= 0 ? f.spei[k]?.[i]?.[mi] ?? null : null;
      const arid = i >= 0 && f.units[i].hyper_arid;
      rows.push(`<div class="border-t border-line py-3"><p class="text-graphite">SPEI-${k} <span class="font-mono text-[0.72rem] text-slate">${esc(t.slice(0, 7))}</span></p>
        <p class="tabular mt-1 text-[1.25rem] text-atlas">${signed(v, 2)}</p>
        <p class="text-[0.75rem] text-slate">${esc(speiClass(v)?.label ?? 'no value')}</p>
        ${arid ? '<p class="mt-1 text-[0.72rem] text-[#e6c46f]">Hyper-arid: reflects evaporative demand only.</p>' : ''}
        <p class="mt-1 text-[0.72rem] text-slate">TerraClimate · unit water balance P − PET · 1991–2020 calibration</p></div>`);
      analyze = `/analyze/?level=${level}&unit=${code}&var=spei&scale=${k}`;
    } else {
      display.push(l.title);
    }
  }
  const facts = isW
    ? `<dt>Code</dt><dd class="font-mono">${esc(code)}</dd><dt>Communes</dt><dd>${esc(p.n_communes ?? '—')}</dd><dt>Area</dt><dd>${num(Number(p.area_km2))} km²</dd>`
    : `<dt>ONS code</dt><dd class="font-mono">${esc(code)}</dd><dt>Wilaya</dt><dd>${esc(p.wilaya_name)} (${esc(wilaya)})</dd><dt>Area</dt><dd>${num(Number(p.area_km2), 1)} km²</dd>`;
  return `
    <p class="font-mono text-[0.68rem] uppercase tracking-[0.08em] text-slate">${isW ? 'Wilaya' : 'Commune'}</p>
    <p class="mt-1 text-[1.25rem] font-medium leading-tight text-atlas">${esc(p.name)}</p>
    ${p.name_ar ? `<p class="text-[1rem] text-graphite" lang="ar" dir="rtl">${esc(p.name_ar)}</p>` : ''}
    <dl class="tabular mt-3 grid grid-cols-[6rem_1fr] gap-y-1 text-[0.78rem] [&_dt]:text-slate [&_dd]:text-graphite">${facts}</dl>
    <div class="mt-4">${rows.join('') || '<p class="border-t border-line py-3 text-[0.78rem] text-slate">Switch on a precipitation or SPEI layer to see values for this area.</p>'}</div>
    ${display.length ? `<p class="border-t border-line py-3 text-[0.72rem] text-slate">Display only, no AEO statistics: ${display.map(esc).join(', ')}.</p>` : ''}
    <div class="mt-2 flex flex-col gap-2 border-t border-line pt-4 text-[0.8125rem]">
      <a href="${analyze}" class="btn btn-primary justify-center !py-2">Open analysis</a>
      <a href="/regions/${esc(wilaya)}/${isW ? '' : esc(code) + '/'}" class="btn btn-secondary justify-center !py-2">${isW ? 'Wilaya' : 'Commune'} profile</a>
      <a href="/data/" class="text-center">Download data</a>
    </div>`;
}
