/**
 * Explore controller: light map, one primary indicator at a time, RegionInspector beside it.
 * Place (search or click) → indicator → period → statistics, chart, download or source link.
 * URL: ?ind=<layer>&t=<date>&v=<variant>&w=<wilaya>&c=<commune>  plus the map view in the hash.
 */
import {
  maplibregl, MAP_LAYERS, ALGERIA_BOUNDS, buildStyle, createMap, loadWilayas, bboxOf,
  setLayerVisible, setLayerOpacity, setLayerTime, setChoropleth, resolveMosaic, refreshTiles, snapDate, stepDate, availableDates, defaultDate, escapeHtml as esc,
  type MapState, type BasemapId,
} from './map-core';
import { soilLegend, type MapLayer } from '../data/map-layers';
import { Combobox, searchKey } from './combobox';
import { RegionInspector, type InspectorRegion } from './region-inspector';

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

export async function initExplore() {
  const el = document.getElementById('map');
  if (!el) return;
  const $ = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
  const data = JSON.parse($('ex-data').textContent!);
  const root = $('explore');
  const inspectorEl = $('inspector');
  const inspector = new RegionInspector($('inspector-body'), data.layers, data.datasets, data.indicators);

  // ---------------------------------------------------------------- state
  const params = new URLSearchParams(location.search);
  const legacy = (params.get('layers') ?? '').split(',').filter(Boolean); // links from earlier versions
  let primary: string | null = params.get('ind') ?? legacy.find((id) => id !== 'communes' && MAP_LAYERS.some((l) => l.id === id)) ?? 'precip-annual';
  if (primary && !MAP_LAYERS.some((l) => l.id === primary)) primary = 'precip-annual';
  const state: MapState = { basemap: (params.get('basemap') as BasemapId) || 'light', layers: {} };
  for (const l of MAP_LAYERS) state.layers[l.id] = { on: l.id === 'wilayas' || l.id === primary || (l.id === 'communes' && (legacy.includes('communes') || !!params.get('c'))), opacity: l.opacity, time: defaultDate(l), variant: l.variants?.default ?? null };
  if (primary && params.get('t')) { const l = layer(primary)!; if (l.time) state.layers[primary].time = snapDate(l, params.get('t')!.length === 4 ? `${params.get('t')}-01-01` : params.get('t')!.length === 7 ? `${params.get('t')}-01` : params.get('t')!); }
  if (primary && params.get('v')) state.layers[primary].variant = params.get('v');
  let region: InspectorRegion | null = null;
  function layer(id: string | null) { return id ? MAP_LAYERS.find((l) => l.id === id) ?? null : null; }

  const syncUrl = () => {
    const p = new URLSearchParams();
    p.set('ind', primary ?? '');
    const st = primary ? state.layers[primary] : null;
    const l = layer(primary);
    if (st?.time && l?.time) p.set('t', l.time.step === 'year' ? st.time.slice(0, 4) : l.time.step === 'month' ? st.time.slice(0, 7) : st.time);
    if (st?.variant && l?.variants) p.set('v', st.variant);
    if (region) { p.set('w', region.wilaya); if (region.level === 'admin2') p.set('c', region.code); }
    if (state.basemap !== 'light') p.set('basemap', state.basemap);
    history.replaceState(null, '', `${location.pathname}?${p}${location.hash}`);
  };

  // ---------------------------------------------------------------- map
  if (primary) await resolveMosaic(layer(primary)!);
  const map = createMap(el, await buildStyle(state), { hash: 'view' });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
  map.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-left');
  map.dragRotate.disable();
  map.touchZoomRotate.disableRotation();
  (window as any).__aeoExploreMap = map; // for end-to-end tests
  map.addControl({
    onAdd() {
      const div = document.createElement('div');
      div.className = 'maplibregl-ctrl maplibregl-ctrl-group aeo-reset';
      const b = document.createElement('button');
      b.type = 'button'; b.textContent = 'All Algeria'; b.title = 'Zoom out to all of Algeria';
      b.addEventListener('click', () => map.fitBounds(ALGERIA_BOUNDS, { padding: 24 }));
      div.appendChild(b);
      return div;
    },
    onRemove() {},
  }, 'top-right');

  // ---------------------------------------------------------------- places
  const fc = await loadWilayas();
  const wByCode = new Map(fc.features.map((f) => [String(f.properties?.wilaya_code), f]));
  const wCb = new Combobox($<HTMLInputElement>('ex-wilaya'), $<HTMLUListElement>('ex-wilaya-list'), (v) => { if (v) selectWilaya(v, true); });
  wCb.setOptions([...wByCode.values()].sort((a, b) => String(a.properties?.wilaya_code).localeCompare(String(b.properties?.wilaya_code)))
    .map((f) => { const p = f.properties!; return { value: String(p.wilaya_code), label: `${p.wilaya_code} — ${p.name}`, search: searchKey(String(p.wilaya_code), p.name) }; }));

  let selW: string | null = null, selC: string | null = null;
  const setSel = (src: string, id: string | null, prev: string | null) => {
    if (prev && map.getSource(src)) map.setFeatureState({ source: src, id: prev }, { selected: false });
    if (id && map.getSource(src)) map.setFeatureState({ source: src, id }, { selected: true });
  };
  function openInspector() {
    inspectorEl.hidden = false;
    root.dataset.inspector = 'open';
    requestAnimationFrame(() => map.resize());
  }
  function closeInspector() {
    inspectorEl.hidden = true;
    root.dataset.inspector = 'closed';
    setSel('aeo-wilayas', null, selW); setSel('aeo-communes', null, selC);
    selW = selC = null; region = null;
    wCb.set('', false);
    requestAnimationFrame(() => map.resize());
    syncUrl();
  }
  $('ins-close').addEventListener('click', () => { closeInspector(); $('ex-wilaya').focus(); });

  function selectWilaya(code: string, fly: boolean) {
    const f = wByCode.get(code);
    if (!f) return;
    const p = f.properties!;
    setSel('aeo-communes', null, selC); selC = null;
    setSel('aeo-wilayas', code, selW); selW = code;
    wCb.set(code, false);
    region = { level: 'admin1', code, name: p.name, wilaya: code, areaKm2: Number(p.area_km2) };
    openInspector();
    if (fly) map.fitBounds(bboxOf(f), { padding: 40, maxZoom: 8.5 });
    refresh();
  }
  function selectCommune(p: Record<string, any>) {
    const code = String(p.commune_code);
    setSel('aeo-wilayas', null, selW); selW = null;
    setSel('aeo-communes', code, selC); selC = code;
    wCb.set(String(p.wilaya_code), false);
    region = { level: 'admin2', code, name: p.name, wilaya: String(p.wilaya_code), wilayaName: p.wilaya_name, areaKm2: Number(p.area_km2) };
    openInspector();
    refresh();
  }

  map.on('click', 'aeo-wilayas-fill', (e) => {
    if (state.layers.communes.on && map.queryRenderedFeatures(e.point, { layers: ['aeo-communes-fill'] }).length) return;
    const code = String(e.features?.[0]?.properties?.wilaya_code ?? '');
    if (code) selectWilaya(code, false);
  });
  map.on('click', 'aeo-communes-fill', (e) => { const p = e.features?.[0]?.properties; if (p) selectCommune(p); });
  let hov: string | null = null;
  map.on('mousemove', 'aeo-wilayas-fill', (e) => {
    const id = String(e.features?.[0]?.properties?.wilaya_code ?? '');
    if (hov && hov !== id) map.setFeatureState({ source: 'aeo-wilayas', id: hov }, { hover: false });
    hov = id; map.setFeatureState({ source: 'aeo-wilayas', id }, { hover: true });
    map.getCanvas().style.cursor = 'pointer';
  });
  map.on('mouseleave', 'aeo-wilayas-fill', () => { if (hov) map.setFeatureState({ source: 'aeo-wilayas', id: hov }, { hover: false }); hov = null; map.getCanvas().style.cursor = ''; });

  const communesBox = $<HTMLInputElement>('ex-communes');
  communesBox.checked = state.layers.communes.on;
  communesBox.addEventListener('change', () => { state.layers.communes.on = communesBox.checked; setLayerVisible(map, 'communes', communesBox.checked); });

  // ---------------------------------------------------------------- indicator
  const radios = [...document.querySelectorAll<HTMLInputElement>('input[name="ex-ind"]')];
  radios.forEach((r) => { r.checked = r.value === (primary ?? ''); r.addEventListener('change', () => r.checked && setPrimary(r.value || null)); });
  async function setPrimary(id: string | null) {
    stopPlay();
    if (primary) { state.layers[primary].on = false; setLayerVisible(map, primary, false); }
    primary = id;
    if (id) {
      const l = layer(id)!;
      state.layers[id].on = true;
      if (l.mosaic) { await resolveMosaic(l); refreshTiles(map, l, state.layers[id].time); }
      setLayerVisible(map, id, true);
      setLayerOpacity(map, id, Number($<HTMLInputElement>('ex-opacity').value));
      if (l.type === 'choropleth') await setChoropleth(map, l, state.layers[id].time, state.layers[id].variant);
      if (l.focusView && !region) { const [z, lat, lng] = l.focusView.split('/').map(Number); map.easeTo({ zoom: z, center: [lng, lat] }); }
    }
    renderPeriod(); renderLegend(); renderInfo(); refresh();
  }

  const domainSel = $<HTMLSelectElement>('ex-domain');
  domainSel.addEventListener('change', () => {
    const g = domainSel.value;
    document.querySelectorAll<HTMLElement>('[data-group-wrap]').forEach((w) => { w.hidden = !!g && w.dataset.groupWrap !== g; });
  });
  if (params.get('domain')) { domainSel.value = params.get('domain')!; domainSel.dispatchEvent(new Event('change')); }
  else if (primary) { const lab = document.querySelector<HTMLElement>(`[data-layer="${primary}"]`); if (lab) { domainSel.value = lab.dataset.group ?? ''; domainSel.dispatchEvent(new Event('change')); } }

  // ---------------------------------------------------------------- period / variant control
  function renderPeriod() {
    const box = $('ex-period'), ctl = $('ex-period-ctl'), note = $('ex-period-note'), lbl = $('ex-period-l');
    const l = layer(primary);
    if (!l || (!l.time && !l.variants)) { box.hidden = true; ctl.innerHTML = ''; return; }
    box.hidden = false;
    const st = state.layers[l.id];
    if (l.variants) {
      lbl.textContent = l.variants.label;
      ctl.innerHTML = `<select id="ex-variant" class="field" aria-labelledby="ex-period-l">${l.variants.options.map((o) => `<option value="${esc(o.id)}"${o.id === st.variant ? ' selected' : ''}>${esc(o.label)}</option>`).join('')}</select>`;
      note.textContent = l.variants.note ?? 'Static map: no time dimension.';
      $<HTMLSelectElement>('ex-variant').addEventListener('change', (e) => { st.variant = (e.target as HTMLSelectElement).value; apply(); });
      return;
    }
    const ds = availableDates(l);
    const step = l.time!.step;
    if (step === 'year') {
      lbl.textContent = 'Year';
      ctl.innerHTML = `<div class="flex items-center gap-2"><button type="button" class="btn btn-secondary !px-2.5 !py-1" data-dir="-1" aria-label="Previous year">‹</button>
        <input id="ex-range" type="range" min="0" max="${ds.length - 1}" step="1" class="min-w-0 flex-1 accent-[#3458d4]" aria-labelledby="ex-period-l" aria-valuetext="${(st.time ?? '').slice(0, 4)}" />
        <button type="button" class="btn btn-secondary !px-2.5 !py-1" data-dir="1" aria-label="Next year">›</button>
        <output id="ex-range-out" class="tabular w-12 text-right font-mono text-[0.9375rem] text-atlas"></output></div>`;
      const range = $<HTMLInputElement>('ex-range');
      range.value = String(Math.max(0, ds.indexOf(st.time ?? ds[ds.length - 1])));
      range.addEventListener('input', () => { st.time = ds[Number(range.value)]; apply(true); });
    } else if (step === 'month') {
      lbl.textContent = 'Month';
      const years = [...new Set(ds.map((d) => d.slice(0, 4)))];
      ctl.innerHTML = `<div class="flex items-center gap-2"><button type="button" class="btn btn-secondary !px-2.5 !py-1" data-dir="-1" aria-label="Previous month">‹</button>
        <select id="ex-m" class="field" aria-label="Month">${MONTHS.map((m, i) => `<option value="${String(i + 1).padStart(2, '0')}">${m}</option>`).join('')}</select>
        <select id="ex-y" class="field !w-28" aria-label="Year">${years.map((y) => `<option>${y}</option>`).join('')}</select>
        <button type="button" class="btn btn-secondary !px-2.5 !py-1" data-dir="1" aria-label="Next month">›</button>
        <button type="button" id="ex-play" class="btn btn-secondary !px-2.5 !py-1" aria-pressed="false" aria-label="Play the last 24 months">▶</button></div>`;
      const play = $<HTMLButtonElement>('ex-play');
      play.addEventListener('click', () => {
        if (playing) { stopPlay(); return; }
        const i0 = Math.max(0, ds.length - 24);
        let i = ds.indexOf(st.time ?? '') >= i0 && ds.indexOf(st.time ?? '') < ds.length - 1 ? ds.indexOf(st.time ?? '') : i0;
        playing = window.setInterval(() => {
          st.time = ds[i]; apply();
          if (++i >= ds.length) stopPlay();
        }, 900);
        play.setAttribute('aria-pressed', 'true'); play.textContent = '❚❚'; play.setAttribute('aria-label', 'Stop');
      });
      const onCh = () => { st.time = snapDate(l, `${$<HTMLSelectElement>('ex-y').value}-${$<HTMLSelectElement>('ex-m').value}-01`); apply(); };
      $('ex-m').addEventListener('change', onCh); $('ex-y').addEventListener('change', onCh);
    } else {
      lbl.textContent = 'Date';
      ctl.innerHTML = `<div class="flex items-center gap-2"><button type="button" class="btn btn-secondary !px-2.5 !py-1" data-dir="-1" aria-label="Previous date">‹</button>
        <input id="ex-date" type="date" class="field" min="${ds[0]}" max="${ds[ds.length - 1]}" aria-labelledby="ex-period-l" />
        <button type="button" class="btn btn-secondary !px-2.5 !py-1" data-dir="1" aria-label="Next date">›</button></div>`;
      $<HTMLInputElement>('ex-date').addEventListener('change', (e) => { const v = (e.target as HTMLInputElement).value; if (v) { st.time = snapDate(l, v); apply(); } });
    }
    ctl.querySelectorAll<HTMLButtonElement>('[data-dir]').forEach((b) => b.addEventListener('click', () => { st.time = stepDate(l, st.time ?? ds[ds.length - 1], Number(b.dataset.dir) as 1 | -1); apply(); }));
    writePeriod();
  }
  function writePeriod() {
    const l = layer(primary); if (!l?.time) return;
    const st = state.layers[l.id]; const ds = availableDates(l); const t = st.time ?? ds[ds.length - 1];
    const range = document.getElementById('ex-range') as HTMLInputElement | null;
    if (range) { range.value = String(ds.indexOf(t)); range.setAttribute('aria-valuetext', t.slice(0, 4)); $('ex-range-out').textContent = t.slice(0, 4); }
    const m = document.getElementById('ex-m') as HTMLSelectElement | null;
    if (m) { m.value = t.slice(5, 7); ($('ex-y') as HTMLSelectElement).value = t.slice(0, 4); }
    const d = document.getElementById('ex-date') as HTMLInputElement | null;
    if (d) d.value = t;
    $('ex-period-note').textContent = l.time.step === 'year' ? `Showing ${t.slice(0, 4)} (available ${ds[0].slice(0, 4)}–${ds[ds.length - 1].slice(0, 4)})` : `Showing ${l.time.step === 'month' ? t.slice(0, 7) : t} (latest ${l.time.step === 'month' ? ds[ds.length - 1].slice(0, 7) : ds[ds.length - 1]})`;
  }
  let timer: number | undefined;
  let playing: number | undefined;
  function stopPlay() {
    window.clearInterval(playing); playing = undefined;
    const b = document.getElementById('ex-play');
    if (b) { b.setAttribute('aria-pressed', 'false'); b.textContent = '▶'; b.setAttribute('aria-label', 'Play the last 24 months'); }
  }
  function apply(debounce = false) {
    const l = layer(primary); if (!l) return;
    const st = state.layers[l.id];
    writePeriod();
    window.clearTimeout(timer);
    const go = () => { setLayerTime(map, l, st.time, st.variant); renderLegend(); refresh(); };
    if (debounce) timer = window.setTimeout(go, 150); else go();
  }

  // ---------------------------------------------------------------- legend + info
  const legend = $('legend');
  function renderLegend() {
    const l = layer(primary);
    if (!l) { legend.classList.add('hidden'); return; }
    const st = state.layers[l.id];
    let lg: MapLayer['legend'] = l.legend;
    if (l.variants && st.variant) { const s = soilLegend(l.id, st.variant); if (s) lg = { kind: 'classes', ...s }; }
    let body = '';
    if (lg.kind === 'image' && lg.url) body = `<img src="${esc(lg.url)}" alt="Colour scale: ${esc(lg.caption ?? '')}" class="mt-1 w-full" loading="lazy" />`;
    else if (lg.kind === 'gradient' && lg.stops) body = `<div class="mt-1 h-2.5 rounded" style="background:linear-gradient(90deg,${lg.stops.join(',')})"></div><div class="mt-0.5 flex justify-between text-slate"><span>${esc(lg.labels?.[0])}</span><span>${esc(lg.labels?.[1])}</span></div>`;
    else if (lg.kind === 'classes' && lg.classes) body = `<ul class="mt-1.5 space-y-0.5">${lg.classes.map((c) => `<li class="flex items-center gap-2 leading-tight"><span class="inline-block h-3 w-3 shrink-0 rounded-sm border border-black/20" style="background:${esc(c.color)}"></span>${esc(c.label)}</li>`).join('')}</ul>`;
    const t = st.time, v = st.variant;
    legend.innerHTML = `<p class="font-medium leading-snug text-atlas">${esc(l.title)}</p>
      ${t && l.time ? `<p class="tabular font-mono text-slate">${l.time.step === 'year' ? t.slice(0, 4) : l.time.step === 'month' ? t.slice(0, 7) : t}</p>` : ''}
      ${v && l.variants ? `<p class="text-slate">${esc(l.variants.label)}: ${esc(l.variants.options.find((o) => o.id === v)?.label ?? v)}</p>` : ''}
      ${body}<p class="mt-1 text-slate">${esc(lg.caption ?? '')}</p>`;
    legend.classList.remove('hidden');
  }
  function renderInfo() {
    const l = layer(primary);
    const d = l?.dataset ? data.datasets[l.dataset] : null;
    $('ex-info').innerHTML = !l ? '<p>Only the administrative boundaries are shown.</p>'
      : `<p>${esc(l.summary)}</p>${l.caveat ? `<p class="text-slate">${esc(l.caveat)}</p>` : ''}
        ${d ? `<p><a href="/data/${esc(l.dataset)}/">Dataset record</a>${d.source_url ? ` · <a href="${esc(d.source_url)}" target="_blank" rel="noopener">Source</a>` : ''}</p>` : ''}`;
  }

  // ---------------------------------------------------------------- options
  const opacity = $<HTMLInputElement>('ex-opacity');
  opacity.addEventListener('input', () => { if (primary) { state.layers[primary].opacity = Number(opacity.value); setLayerOpacity(map, primary, Number(opacity.value)); } });
  const bsel = $<HTMLSelectElement>('ex-basemap');
  bsel.value = state.basemap;
  bsel.addEventListener('change', async () => {
    state.basemap = bsel.value as BasemapId;
    map.setStyle(await buildStyle(state), { diff: false });
    map.once('idle', () => {
      if (selW) setSel('aeo-wilayas', selW, null); if (selC) setSel('aeo-communes', selC, null);
      const l = layer(primary); if (l?.type === 'choropleth') setChoropleth(map, l, state.layers[l.id].time, state.layers[l.id].variant);
    });
    syncUrl();
  });

  // ---------------------------------------------------------------- inspector
  function refresh() {
    syncUrl();
    if (!region) return;
    const st = primary ? state.layers[primary] : null;
    inspector.render(region, { layer: primary, time: st?.time ?? null, variant: st?.variant ?? null });
  }

  renderPeriod(); renderLegend(); renderInfo();
  map.once('load', () => { const l = layer(primary); if (l?.type === 'choropleth') setChoropleth(map, l, state.layers[l.id].time, state.layers[l.id].variant); });
  map.once('idle', () => {
    const w = params.get('w'), c = params.get('c');
    if (c) {
      const tryC = () => {
        const f = (map.querySourceFeatures('aeo-communes', { filter: ['==', ['get', 'commune_code'], c] }) ?? [])[0];
        if (f) { selectCommune(f.properties!); return true; }
        return false;
      };
      if (!tryC()) map.once('idle', () => { if (!tryC() && w) selectWilaya(w, false); });
    } else if (w) selectWilaya(w, false);
  });
  syncUrl();
}
