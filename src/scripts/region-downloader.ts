/**
 * Controller for src/components/RegionDataDownloader.astro.
 * Location → Indicator → Period → Format → resolved download.
 */
import { Combobox, searchKey, escapeHtml as esc } from './combobox';
import { makeContext, resolve, formatsFor, coverage, periodError, mb } from '../lib/region-download.js';

type Sel = { level: 'admin0' | 'admin1' | 'admin2'; wilaya: string; commune: string; indicator: string; step: string; from: string; to: string; format: string; layer?: string; scale?: string };
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

const cache = new Map<string, Promise<any>>();
const getJson = (url: string) => {
  if (!cache.has(url)) cache.set(url, fetch(url).then((r) => { if (!r.ok) throw new Error(`${r.status} ${url}`); return r.json(); }));
  return cache.get(url)!;
};

export async function initRegionDownloader() {
  const root = document.querySelector<HTMLElement>('[data-rdd]');
  if (!root) return;
  const $ = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
  const cfg = JSON.parse($('rdd-config').textContent!);
  const form = $<HTMLFormElement>('rdd-form');
  const loading = $('rdd-loading');
  const result = $('rdd-result');
  const status = $('rdd-status');
  form.setAttribute('aria-busy', 'true');

  let ctx: any;
  try {
    const [units, boundaryRecord, ...mans] = await Promise.all([
      getJson('/data/admin-units.json'),
      getJson(cfg.indicators.find((i: any) => i.kind === 'boundaries')?.record ?? '/data/aeo-dza-admin-boundaries.json'),
      ...cfg.indicators.filter((i: any) => i.manifest).map((i: any) => getJson(i.manifest)),
    ]);
    const manifests = Object.fromEntries(cfg.indicators.filter((i: any) => i.manifest).map((i: any, k: number) => [i.id, mans[k]]));
    ctx = makeContext({ indicators: cfg.indicators, manifests, boundaryRecord, units, load: getJson });
  } catch (e) {
    loading.textContent = 'The list of files could not be loaded. Check your connection and reload the page. All files are also listed on the product pages.';
    loading.classList.add('rdd-error');
    form.removeAttribute('aria-busy');
    return;
  }
  loading.hidden = true;
  form.removeAttribute('aria-busy');

  // ------------------------------------------------------------ state
  const p = cfg.preset;
  const params = new URLSearchParams(location.search);
  const sel: Sel = {
    level: (params.get('rdd_level') as Sel['level']) || p.level,
    wilaya: params.get('rdd_wilaya') || p.wilaya || '',
    commune: params.get('rdd_commune') || p.commune || '',
    indicator: params.get('rdd_ind') || p.indicator,
    step: '', from: '', to: '', format: 'csv', scale: 'all',
  };
  if (sel.commune && !sel.wilaya) sel.wilaya = ctx.communes.get(sel.commune)?.wilaya ?? '';
  if (sel.level === 'admin1' && !sel.wilaya) sel.wilaya = '';

  // ------------------------------------------------------------ location
  const wOpts = [...ctx.wilayas.values()].map((w: any) => ({ value: w.code, label: `${w.code} — ${w.name}`, hint: w.name_ar, search: searchKey(w.code, w.name, w.name_ar) }));
  const wCb = new Combobox($<HTMLInputElement>('rdd-wilaya'), $<HTMLUListElement>('rdd-wilaya-list'), (v) => { sel.wilaya = v; sel.commune = ''; fillCommunes(); update(); });
  const cCb = new Combobox($<HTMLInputElement>('rdd-commune'), $<HTMLUListElement>('rdd-commune-list'), (v) => { sel.commune = v; update(); });
  wCb.setOptions(wOpts); wCb.set(sel.wilaya, false);
  function fillCommunes() {
    const list = [...ctx.communes.values()].filter((c: any) => c.wilaya === sel.wilaya)
      .map((c: any) => ({ value: c.code, label: `${c.name} (${c.code})`, hint: c.name_ar, search: searchKey(c.code, c.name, c.name_ar) }))
      .sort((a, b) => a.label.localeCompare(b.label, 'fr'));
    cCb.setOptions(list, true);
    cCb.set(sel.commune, false);
    sel.commune = cCb.value;
    const inp = $<HTMLInputElement>('rdd-commune');
    inp.disabled = !sel.wilaya;
    inp.placeholder = sel.wilaya ? `Search ${list.length} communes` : 'Choose a wilaya first';
  }
  fillCommunes();
  form.querySelectorAll<HTMLInputElement>('input[name="rdd-level"]').forEach((r) => {
    r.checked = r.value === sel.level;
    r.addEventListener('change', () => { sel.level = r.value as Sel['level']; update(); });
  });

  // ------------------------------------------------------------ indicator
  form.querySelectorAll<HTMLInputElement>('input[name="rdd-indicator"]').forEach((r) => {
    r.checked = r.value === sel.indicator;
    r.addEventListener('change', () => { sel.indicator = r.value; sel.step = ''; sel.format = sel.indicator === 'boundaries' ? 'geojson' : 'csv'; update(); });
  });
  if (sel.indicator === 'boundaries') sel.format = 'geojson';

  // ------------------------------------------------------------ period
  const fy = $<HTMLSelectElement>('rdd-from-y'), fm = $<HTMLSelectElement>('rdd-from-m');
  const ty = $<HTMLSelectElement>('rdd-to-y'), tm = $<HTMLSelectElement>('rdd-to-m');
  const monthOpts = MONTHS.map((m, i) => `<option value="${String(i + 1).padStart(2, '0')}">${m}</option>`).join('');
  fm.innerHTML = monthOpts; tm.innerHTML = monthOpts;
  form.querySelectorAll<HTMLInputElement>('input[name="rdd-step"]').forEach((r) => r.addEventListener('change', () => { setStep(r.value, true); update(); }));
  [fy, fm, ty, tm].forEach((s) => s.addEventListener('change', () => { readPeriod(); update(); }));
  $<HTMLSelectElement>('rdd-scale').addEventListener('change', (e) => { sel.scale = (e.target as HTMLSelectElement).value; update(); });
  $<HTMLSelectElement>('rdd-layer').addEventListener('change', (e) => { sel.layer = (e.target as HTMLSelectElement).value; update(); });

  function setStep(step: string, keepYears: boolean) {
    const prev = { from: sel.from, to: sel.to };
    sel.step = step;
    const cov = coverage(ctx, sel.indicator, step);
    if (!cov) return;
    const y0 = Number(cov.from.slice(0, 4)), y1 = Number(cov.to.slice(0, 4));
    const yrs = []; for (let y = y0; y <= y1; y++) yrs.push(`<option>${y}</option>`);
    fy.innerHTML = yrs.join(''); ty.innerHTML = yrs.join('');
    let from = cov.from, to = cov.to;
    if (keepYears && prev.from) {
      const a = prev.from.slice(0, 4), b = prev.to.slice(0, 4);
      from = step === 'annual' ? a : `${a}-01`; to = step === 'annual' ? b : `${b}-12`;
      if (from < cov.from) from = cov.from; if (to > cov.to) to = cov.to;
      if (from > to) { from = cov.from; to = cov.to; }
    }
    writePeriod(from, to);
  }
  function writePeriod(from: string, to: string) {
    sel.from = from; sel.to = to;
    fy.value = from.slice(0, 4); ty.value = to.slice(0, 4);
    if (from.length > 4) { fm.value = from.slice(5, 7); tm.value = to.slice(5, 7); }
  }
  function readPeriod() {
    sel.from = sel.step === 'annual' ? fy.value : `${fy.value}-${fm.value}`;
    sel.to = sel.step === 'annual' ? ty.value : `${ty.value}-${tm.value}`;
  }

  // ------------------------------------------------------------ render
  let seq = 0;

  async function update() {
    const my = ++seq;
    status.textContent = '';
    // location
    root!.querySelectorAll<HTMLElement>('[data-when]').forEach((el) => { el.hidden = !el.dataset.when!.split(' ').includes(sel.level); });
    const ind = ctx.indicators.find((i: any) => i.id === sel.indicator) ?? ctx.indicators[0];
    sel.indicator = ind.id;
    // period
    const steps: string[] = ind.steps;
    const stepWrap = $('rdd-step-wrap'), range = $('rdd-range'), stat = $('rdd-period-static');
    if (ind.kind === 'boundaries') {
      stepWrap.hidden = true; range.hidden = true; stat.hidden = false;
      stat.textContent = `Boundaries are a single snapshot: version ${ctx.boundaryVersion}. No period to choose.`;
    } else {
      if (!steps.includes(sel.step)) setStep(steps[0], false);
      stepWrap.hidden = steps.length < 2;
      stat.hidden = steps.length > 1;
      stat.textContent = steps.length === 1 ? `${ind.label}: ${sel.step} values only.` : '';
      form.querySelectorAll<HTMLInputElement>('input[name="rdd-step"]').forEach((r) => { r.checked = r.value === sel.step; r.disabled = !steps.includes(r.value); });
      range.hidden = false;
      fm.hidden = tm.hidden = sel.step !== 'monthly';
    }
    $('rdd-scale-wrap').hidden = ind.id !== 'spei';
    // formats
    const fmts = formatsFor(ctx, sel);
    if (!fmts.some((f: any) => f.id === sel.format)) sel.format = fmts[0]?.id ?? '';
    $('rdd-formats').innerHTML = fmts.map((f: any) => `<label class="rdd-choice"${f.available ? '' : ' data-unavailable'}><input type="radio" name="rdd-format" value="${f.id}" class="accent-[#3458d4]"${f.id === sel.format ? ' checked' : ''} /><span class="rdd-fmt-label">${esc(f.label)}${f.regional ? '' : ''}</span></label>`).join('');
    $('rdd-formats').querySelectorAll<HTMLInputElement>('input').forEach((r) => r.addEventListener('change', () => { sel.format = r.value; update(); }));
    // area line
    const a = sel.level === 'admin0' ? null : sel.level === 'admin1' ? ctx.wilayas.get(sel.wilaya) : ctx.communes.get(sel.commune);
    $('rdd-area').innerHTML = sel.level === 'admin0'
      ? `Algeria (code DZ) · boundaries ${ctx.boundaryVersion}`
      : a ? `${esc(a.name)}${a.name_ar ? ` · <span lang="ar" dir="rtl">${esc(a.name_ar)}</span>` : ''} · ${sel.level === 'admin1' ? 'wilaya' : 'commune'} code ${a.code} · boundaries ${ctx.boundaryVersion}` : '';
    // period validation (shown next to the fields)
    const perr = ind.kind === 'boundaries' || sel.format !== 'csv' ? null : periodError(ctx, sel);
    const err = $('rdd-period-err');
    err.hidden = !perr; err.textContent = perr ? `${perr}` : '';
    [fy, fm, ty, tm].forEach((s) => (perr ? s.setAttribute('aria-invalid', 'true') : s.removeAttribute('aria-invalid')));
    // resolve
    const r = await resolve(ctx, sel);
    if (my !== seq) return;

    // layers (national GeoTIFFs)
    const lw = $('rdd-layer-wrap'), ls = $<HTMLSelectElement>('rdd-layer');
    if (r.ok && r.layers?.length > 1) {
      lw.hidden = false;
      ls.innerHTML = r.layers.map((l: any) => `<option value="${esc(l.id)}">${esc(l.label)}</option>`).join('');
      ls.value = r.href;
    } else lw.hidden = true;
    const rangeDisabled = r.ok && r.periodApplies === false;
    [fy, fm, ty, tm].forEach((s) => (s.disabled = rangeDisabled));
    $('rdd-range').title = rangeDisabled ? 'This file covers a fixed period' : '';
    render(r);
  }

  function render(r: any) {
    const hl = 'h3';
    result.classList.toggle('rdd-unavailable', !r.ok && r.kind === 'unavailable');
    if (!r.ok) {
      const alts = (r.alternatives ?? []).map((x: any, i: number) => `<li><button type="button" class="btn btn-secondary !py-2 text-left" data-alt="${i}">${esc(x.label)}</button></li>`).join('');
      result.innerHTML = r.kind === 'unavailable'
        ? `<${hl} class="text-[1.0625rem] font-medium text-atlas">Not available for this selection</${hl}><p class="mt-2 max-w-3xl text-[0.9375rem] text-atlas">${esc(r.reason)}</p>${alts ? `<p class="mt-4 text-[0.875rem] font-medium text-atlas">Available instead:</p><ul class="mt-2 flex flex-wrap gap-2">${alts}</ul>` : ''}`
        : `<p class="text-[0.9375rem] text-slate">${esc(r.reason)}</p>`;
      result.querySelectorAll<HTMLButtonElement>('[data-alt]').forEach((b) => b.addEventListener('click', () => apply(r.alternatives[Number(b.dataset.alt)].patch)));
      return;
    }
    const isExtract = r.kind === 'extract';
    const size = isExtract
      ? (r.format === 'CSV' ? `${r.rowsExpected} rows expected (generated in your browser)` : 'One feature (generated in your browser)')
      : mb(r.bytes);
    const rows: [string, string][] = [
      ['File', `<span class="font-mono text-[0.875rem]">${esc(r.filename)}</span>`],
      ['Format', `${r.format}${isExtract ? ' — extract for the selected area only' : r.fullTable ? ' — <strong>full administrative table, not a regional extract</strong>' : ' — published file'}`],
      ['Area', esc(r.coverageText)],
      ['Period', esc(r.periodText)],
      ['Size', esc(size)],
      ['Source', `${esc(r.product.source ?? '')}${r.product.sourceLicense ? ` (${esc(r.product.sourceLicense)})` : ''}. Processed by AEO: ${esc(r.product.id)} v${esc(r.product.version)}, licence ${esc(r.product.license)}.${r.product.method ? ` <a href="${esc(r.product.method)}">Method</a>` : ''}`],
      ...(isExtract
        ? [['Taken from', `${esc(r.source.href.split('/').pop())} (${mb(r.source.bytes)})${r.readFrom.href !== r.source.href ? `, via its verified wilaya partition (${mb(r.readFrom.bytes)})` : ''}. The SHA-256 checksum is verified before extraction.`] as [string, string]]
        : [['Checksum', `<span class="font-mono text-[0.8125rem]">SHA-256 ${esc(r.sha256)}</span>`] as [string, string]]),
    ];
    const notes = (r.notes ?? []).map((n: string) => `<li>${esc(n)}</li>`).join('');
    const icon = '<svg class="icon-download" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 4v11M7 10l5 5 5-5M5 20h14" /></svg>';
    const action = isExtract
      ? `<button type="button" id="rdd-go" class="btn btn-primary">${icon}${esc(r.button)}</button>`
      : `<a id="rdd-go" class="btn btn-primary" href="${esc(r.href)}" download="${esc(r.filename)}">${icon}${esc(r.button)}</a>`;
    result.innerHTML = `<${hl} class="text-[1.0625rem] font-medium text-atlas">Your download</${hl}>
      <dl class="mt-3">${rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')}</dl>
      ${notes ? `<ul class="mt-4 list-disc space-y-1 pl-5 text-[0.875rem] text-slate">${notes}</ul>` : ''}
      <div class="mt-5 flex flex-wrap items-center gap-3">${action}</div>`;
    const go = $('rdd-go');
    if (isExtract) go.addEventListener('click', () => doExtract(r));
    else go.addEventListener('click', () => { status.textContent = `Download started: ${r.filename} (${mb(r.bytes)}).`; });
  }

  async function doExtract(r: any) {
    const go = $<HTMLButtonElement>('rdd-go');
    go.disabled = true; go.setAttribute('aria-busy', 'true');
    status.classList.remove('rdd-error');
    status.textContent = `Preparing ${r.filename}…`;
    try {
      const { runExtract } = await import('../lib/region-extract.js');
      const out = await runExtract(r, {
        fetchBuffer: async (u) => { const res = await fetch(u); if (!res.ok) throw new Error(`The file ${u} could not be fetched (${res.status}).`); return res.arrayBuffer(); },
        unitName: (c) => (ctx.wilayas.get(c) ?? ctx.communes.get(c))?.name ?? (c === 'DZ' ? 'Algeria' : undefined),
      });
      if (r.format === 'CSV' && out.rows === 0) throw new Error('No rows match this selection in the published table.');
      const blob = new Blob([out.text], { type: out.mime });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob); a.download = r.filename;
      document.body.appendChild(a); a.click();
      setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 2000);
      status.textContent = `Downloaded ${r.filename}: ${r.format === 'CSV' ? `${out.rows} rows, ` : ''}${mb(blob.size)}.`;
    } catch (e) {
      status.classList.add('rdd-error');
      status.textContent = `Download failed. ${(e as Error).message}`;
    } finally {
      go.disabled = false; go.removeAttribute('aria-busy');
    }
  }

  function apply(patch: Partial<Sel>) {
    const prevStep = sel.step;
    Object.assign(sel, patch);
    if (patch.indicator) { const i = ctx.indicators.find((x: any) => x.id === patch.indicator); if (i && !i.steps.includes(sel.step)) sel.step = ''; }
    if (patch.step && patch.step !== prevStep) setStep(patch.step, true);
    if (patch.level === 'admin1' && !sel.wilaya && sel.commune) sel.wilaya = ctx.communes.get(sel.commune)?.wilaya ?? '';
    form.querySelectorAll<HTMLInputElement>('input[name="rdd-level"]').forEach((x) => (x.checked = x.value === sel.level));
    form.querySelectorAll<HTMLInputElement>('input[name="rdd-indicator"]').forEach((x) => (x.checked = x.value === sel.indicator));
    if (patch.wilaya !== undefined) { wCb.set(sel.wilaya, false); fillCommunes(); }
    if (patch.commune !== undefined) cCb.set(sel.commune, false);
    if (patch.from && patch.to) { writePeriod(patch.from, patch.to); }
    $<HTMLSelectElement>('rdd-scale').value = sel.scale ?? 'all';
    update();
  }

  window.addEventListener('aeo:rdd-set', (e) => {
    const d = (e as CustomEvent).detail as Partial<Sel> & { focus?: boolean };
    const { focus, ...patch } = d;
    if (patch.indicator === 'boundaries' && !patch.format) patch.format = 'geojson';
    else if (patch.indicator && !patch.format) patch.format = 'csv';
    apply(patch);
    if (focus) { root!.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' }); $('rdd-h').setAttribute('tabindex', '-1'); $('rdd-h').focus({ preventScroll: true }); }
  });
  (window as any).__rdd = { sel, ctx }; // for tests and debugging
  update();
}
