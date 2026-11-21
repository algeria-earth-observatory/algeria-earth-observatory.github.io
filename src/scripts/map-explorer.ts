import {
  maplibregl, MAP_LAYERS, ALGERIA_BOUNDS, buildStyle, createMap, loadWilayas, bboxOf,
  setLayerVisible, setLayerOpacity, setLayerTime, resolveMosaic, refreshTiles, snapDate, stepDate, availableDates, defaultDate, escapeHtml,
  type MapState, type BasemapId,
} from './map-core';
import { inspectorHtml, type Selection } from './inspector';

export async function initExplorer() {
  const el = document.getElementById('map');
  if (!el) return;

  // ---------------------------------------------------------------- state
  const params = new URLSearchParams(location.search);
  const requested = (params.get('layers') ?? '').split(',').filter(Boolean);
  const state: MapState = { basemap: (params.get('basemap') as BasemapId) || 'satellite', layers: {} };
  for (const l of MAP_LAYERS) {
    const on = requested.length ? requested.includes(l.id) || l.id === 'wilayas' : !!l.defaultOn;
    state.layers[l.id] = { on, opacity: l.opacity, time: defaultDate(l) };
  }
  const dateParam = params.get('date');
  if (dateParam) for (const l of MAP_LAYERS) if (l.time && state.layers[l.id].on) state.layers[l.id].time = snapDate(l, dateParam);

  const syncUrl = () => {
    const p = new URLSearchParams();
    const on = MAP_LAYERS.filter((l) => state.layers[l.id].on && l.id !== 'wilayas').map((l) => l.id);
    if (on.length) p.set('layers', on.join(','));
    if (state.basemap !== 'satellite') p.set('basemap', state.basemap);
    const qs = p.toString();
    history.replaceState(null, '', `${location.pathname}${qs ? `?${qs}` : ''}${location.hash}`);
  };

  // ---------------------------------------------------------------- map
  // Mosaic layers requested in the URL get their tile search before the first render.
  await Promise.all(MAP_LAYERS.filter((l) => l.mosaic && state.layers[l.id].on).map(resolveMosaic));
  const map = createMap(el, await buildStyle(state), { hash: 'view' });
  map.addControl(new maplibregl.NavigationControl({ visualizePitch: false }), 'top-right');
  map.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-left');
  map.addControl(new maplibregl.FullscreenControl(), 'top-right');
  map.addControl({
    onAdd() {
      const div = document.createElement('div');
      div.className = 'maplibregl-ctrl maplibregl-ctrl-group aeo-reset';
      const b = document.createElement('button');
      b.type = 'button';
      b.textContent = 'Reset view';
      b.title = 'Reset the view to all of Algeria';
      b.addEventListener('click', () => {
        map.fitBounds(ALGERIA_BOUNDS, { padding: 24 });
        clearSelection();
        (document.getElementById('wilaya-select') as HTMLSelectElement).value = '';
      });
      div.appendChild(b);
      return div;
    },
    onRemove() {},
  }, 'top-right');
  map.dragRotate.disable();
  map.touchZoomRotate.disableRotation();

  // ---------------------------------------------------------------- wilayas
  const fc = await loadWilayas();
  const sel = document.getElementById('wilaya-select') as HTMLSelectElement;
  [...fc.features]
    .sort((a, b) => String(a.properties?.wilaya_code).localeCompare(String(b.properties?.wilaya_code)))
    .forEach((f) => {
      const o = document.createElement('option');
      o.value = String(f.properties?.wilaya_code);
      o.textContent = `${f.properties?.wilaya_code} — ${f.properties?.name}`;
      sel.appendChild(o);
    });

  let selected: string | null = null;
  let hovered: string | null = null;
  const popup = new maplibregl.Popup({ maxWidth: '300px', closeButton: true });
  const wide = window.matchMedia('(min-width: 1280px)');
  const inspectorBody = document.getElementById('inspector-body');
  let current: { sel: Selection; at: [number, number] } | null = null;
  async function showInspector(sel: Selection, at: [number, number]) {
    current = { sel, at };
    const html = await inspectorHtml(sel, state);
    if (current?.sel !== sel) return;
    if (wide.matches && inspectorBody) { inspectorBody.innerHTML = html; popup.remove(); }
    else popup.setLngLat(at).setHTML(`<div class="aeo-pop">${html}</div>`).addTo(map);
  }
  const refreshInspector = () => { if (current) showInspector(current.sel, current.at); };
  function clearSelection() {
    if (selected && map.getSource('aeo-wilayas')) map.setFeatureState({ source: 'aeo-wilayas', id: selected }, { selected: false });
    selected = null;
    current = null;
    popup.remove();
    if (inspectorBody) inspectorBody.textContent = 'Select a wilaya or commune on the map to see its indicators.';
  }
  function selectWilaya(code: string, fly: boolean) {
    const f = fc.features.find((x) => String(x.properties?.wilaya_code) === code);
    if (!f) return;
    clearSelection();
    selected = code;
    map.setFeatureState({ source: 'aeo-wilayas', id: code }, { selected: true });
    if (fly) map.fitBounds(bboxOf(f), { padding: 40, maxZoom: 9 });
    const b = bboxOf(f);
    if (fly) showInspector({ kind: 'wilaya', props: f.properties ?? {} }, [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2]);
  }
  sel.addEventListener('change', () => (sel.value ? selectWilaya(sel.value, true) : (clearSelection(), map.fitBounds(ALGERIA_BOUNDS, { padding: 24 }))));

  map.on('click', 'aeo-wilayas-fill', (e) => {
    const f = e.features?.[0];
    if (!f) return;
    if (state.layers.communes?.on && map.queryRenderedFeatures(e.point, { layers: ['aeo-communes-fill'] }).length) return;
    const code = String(f.properties?.wilaya_code);
    selectWilaya(code, false);
    sel.value = code;
    showInspector({ kind: 'wilaya', props: f.properties ?? {} }, [e.lngLat.lng, e.lngLat.lat]);
  });
  map.on('mousemove', 'aeo-wilayas-fill', (e) => {
    const id = String(e.features?.[0]?.properties?.wilaya_code ?? '');
    if (hovered && hovered !== id) map.setFeatureState({ source: 'aeo-wilayas', id: hovered }, { hover: false });
    hovered = id;
    map.setFeatureState({ source: 'aeo-wilayas', id }, { hover: true });
    map.getCanvas().style.cursor = 'pointer';
  });
  map.on('mouseleave', 'aeo-wilayas-fill', () => {
    if (hovered) map.setFeatureState({ source: 'aeo-wilayas', id: hovered }, { hover: false });
    hovered = null;
    map.getCanvas().style.cursor = '';
  });

  // communes: registered after the wilaya handler so a commune click wins
  let hoveredC: string | null = null;
  map.on('click', 'aeo-communes-fill', (e) => {
    const f = e.features?.[0];
    if (f) showInspector({ kind: 'commune', props: f.properties ?? {} }, [e.lngLat.lng, e.lngLat.lat]);
  });
  map.on('mousemove', 'aeo-communes-fill', (e) => {
    const id = String(e.features?.[0]?.properties?.commune_code ?? '');
    if (hoveredC && hoveredC !== id) map.setFeatureState({ source: 'aeo-communes', id: hoveredC }, { hover: false });
    hoveredC = id;
    map.setFeatureState({ source: 'aeo-communes', id }, { hover: true });
  });
  map.on('mouseleave', 'aeo-communes-fill', () => { if (hoveredC) map.setFeatureState({ source: 'aeo-communes', id: hoveredC }, { hover: false }); hoveredC = null; });

  const coords = document.getElementById('coords');
  map.on('mousemove', (e) => {
    if (coords) coords.textContent = `${e.lngLat.lat.toFixed(4)}°, ${e.lngLat.lng.toFixed(4)}°`;
  });

  // ---------------------------------------------------------------- tile errors
  map.on('error', (e: any) => {
    const src: string | undefined = e?.sourceId ?? e?.source?.id;
    if (!src?.startsWith('aeo-')) return;
    const id = src.slice(4);
    const layer = MAP_LAYERS.find((l) => l.id === id);
    if (layer?.emptyTiles404 && e?.error?.status === 404) return; // no data here (e.g. sea), not a failure
    const box = document.querySelector<HTMLElement>(`[data-error="${id}"]`);
    if (box) {
      box.textContent = 'Some tiles could not be loaded from the provider (no data for this date or area, or the service is unavailable).';
      box.classList.remove('hidden');
    }
  });

  // ---------------------------------------------------------------- legend
  const legend = document.getElementById('legend')!;
  function renderLegend() {
    const active = MAP_LAYERS.filter((l) => state.layers[l.id].on);
    legend.classList.toggle('hidden', active.length === 0);
    legend.innerHTML = `<p class="meta uppercase tracking-wider">Legend</p>` + active.map((l) => {
      const t = state.layers[l.id].time;
      let body = '';
      if (l.legend.kind === 'image' && l.legend.url) body = `<img src="${escapeHtml(l.legend.url)}" alt="Colour scale for ${escapeHtml(l.title)} (${escapeHtml(l.legend.caption ?? '')})" class="mt-1 w-full" loading="lazy" />`;
      else if (l.legend.kind === 'gradient' && l.legend.stops) body = `<div class="mt-1 h-2.5 rounded" style="background:linear-gradient(90deg,${l.legend.stops.join(',')})"></div><div class="mt-0.5 flex justify-between text-[0.7rem] text-slate"><span>${escapeHtml(l.legend.labels?.[0])}</span><span>${escapeHtml(l.legend.labels?.[1])}</span></div>`;
      else if (l.legend.kind === 'classes' && l.legend.classes) body = `<ul class="mt-1 grid grid-cols-1 gap-x-2 gap-y-0.5 sm:grid-cols-2">${l.legend.classes.map((c) => `<li class="flex items-center gap-1.5 text-[0.7rem] leading-tight text-graphite"><span class="inline-block h-2.5 w-2.5 shrink-0 rounded-sm border border-black/15" style="background:${escapeHtml(c.color)}"></span>${escapeHtml(c.label)}</li>`).join('')}</ul>`;
      else if (l.legend.kind === 'line') body = `<div class="mt-1 flex items-center gap-2"><span class="inline-block h-0 w-6 border-t-2 border-[#17252c]"></span><span class="text-[0.72rem] text-slate">${escapeHtml(l.legend.caption)}</span></div>`;
      const cap = l.legend.kind === 'line' ? '' : `<p class="mt-0.5 text-[0.7rem] text-slate">${escapeHtml(l.legend.caption)}</p>`;
      return `<div class="mt-2.5 border-t border-line pt-2"><p class="font-medium text-atlas leading-snug">${escapeHtml(l.title)}</p>${t ? `<p class="font-mono text-[0.7rem] text-teal-700">${l.time?.step === 'year' ? t.slice(0, 4) : t}</p>` : ''}${body}${cap}</div>`;
    }).join('');
  }

  // ---------------------------------------------------------------- panel wiring
  const showControls = (id: string, on: boolean) => {
    document.querySelector(`[data-layer-controls="${id}"]`)?.classList.toggle('hidden', !on);
  };

  for (const l of MAP_LAYERS) {
    const chk = document.querySelector<HTMLInputElement>(`[data-layer-toggle="${l.id}"]`);
    if (chk) chk.checked = state.layers[l.id].on;
    showControls(l.id, state.layers[l.id].on);
    chk?.addEventListener('change', async () => {
      state.layers[l.id].on = chk.checked;
      if (chk.checked && l.mosaic) {
        await resolveMosaic(l);
        refreshTiles(map, l, state.layers[l.id].time);
      }
      setLayerVisible(map, l.id, state.layers[l.id].on);
      showControls(l.id, chk.checked);
      renderLegend();
      syncUrl();
      refreshInspector();
    });
    document.querySelector<HTMLInputElement>(`[data-opacity="${l.id}"]`)?.addEventListener('input', (e) => {
      const v = Number((e.target as HTMLInputElement).value);
      state.layers[l.id].opacity = v;
      setLayerOpacity(map, l.id, v);
    });
    if (l.time?.step === 'year') {
      const range = document.querySelector<HTMLInputElement>(`[data-year="${l.id}"]`)!;
      const label = document.querySelector<HTMLOutputElement>(`[data-year-label="${l.id}"]`)!;
      const note = document.querySelector<HTMLElement>(`[data-date-note="${l.id}"]`)!;
      const ds = availableDates(l);
      range.max = String(ds.length - 1);
      let timer: number | undefined;
      const apply = (wanted: string, immediate = true) => {
        const snapped = snapDate(l, wanted);
        if (!snapped) return;
        state.layers[l.id].time = snapped;
        range.value = String(ds.indexOf(snapped));
        label.value = snapped.slice(0, 4);
        note.textContent = `Showing ${snapped.slice(0, 4)} (${ds[0].slice(0, 4)}–${ds[ds.length - 1].slice(0, 4)})`;
        document.querySelector(`[data-error="${l.id}"]`)?.classList.add('hidden');
        window.clearTimeout(timer);
        const go = () => { setLayerTime(map, l, snapped); renderLegend(); refreshInspector(); };
        if (immediate) go(); else timer = window.setTimeout(go, 120);
      };
      apply(state.layers[l.id].time ?? ds[ds.length - 1]);
      range.addEventListener('input', () => apply(ds[Number(range.value)], false));
      document.querySelectorAll<HTMLButtonElement>(`[data-step="${l.id}"]`).forEach((b) =>
        b.addEventListener('click', () => apply(stepDate(l, state.layers[l.id].time ?? ds[ds.length - 1], Number(b.dataset.dir) as 1 | -1))),
      );
    } else if (l.time) {
      const input = document.querySelector<HTMLInputElement>(`[data-date="${l.id}"]`)!;
      const note = document.querySelector<HTMLElement>(`[data-date-note="${l.id}"]`)!;
      const ds = availableDates(l);
      input.min = ds[0];
      input.max = ds[ds.length - 1];
      const apply = (wanted: string) => {
        const snapped = snapDate(l, wanted);
        if (!snapped) return;
        state.layers[l.id].time = snapped;
        input.value = snapped;
        note.textContent = snapped === wanted ? `Showing ${snapped}` : `Nearest available: ${snapped}`;
        document.querySelector(`[data-error="${l.id}"]`)?.classList.add('hidden');
        setLayerTime(map, l, snapped);
        renderLegend();
        refreshInspector();
      };
      input.value = state.layers[l.id].time ?? ds[ds.length - 1];
      note.textContent = `Latest available: ${ds[ds.length - 1]}`;
      input.addEventListener('change', () => input.value && apply(input.value));
      document.querySelectorAll<HTMLButtonElement>(`[data-step="${l.id}"]`).forEach((b) =>
        b.addEventListener('click', () => apply(stepDate(l, state.layers[l.id].time ?? input.value, Number(b.dataset.dir) as 1 | -1))),
      );
    }
  }
  document.querySelectorAll<HTMLButtonElement>('[data-info-toggle]').forEach((b) =>
    b.addEventListener('click', () => {
      const open = b.getAttribute('aria-expanded') === 'true';
      b.setAttribute('aria-expanded', String(!open));
      document.getElementById(`info-${b.dataset.infoToggle}`)?.classList.toggle('hidden', open);
    }),
  );
  document.querySelectorAll<HTMLInputElement>('input[name="basemap"]').forEach((r) => {
    r.checked = r.value === state.basemap;
    r.addEventListener('change', async () => {
      if (!r.checked) return;
      state.basemap = r.value as BasemapId;
      const keep = selected;
      map.setStyle(await buildStyle(state), { diff: false });
      map.once('styledata', () => { if (keep) { selected = null; selectWilaya(keep, false); } });
      syncUrl();
    });
  });

  // ---------------------------------------------------------------- layer search, basemap select
  const search = document.getElementById('layer-search') as HTMLInputElement | null;
  search?.addEventListener('input', () => {
    const q = search.value.trim().toLowerCase();
    let shown = 0;
    document.querySelectorAll<HTMLElement>('[data-layer-item]').forEach((li) => {
      const hit = !q || (li.dataset.search ?? '').includes(q);
      li.hidden = !hit;
      if (hit) shown++;
    });
    document.querySelectorAll<HTMLDetailsElement>('[data-layer-group]').forEach((g) => { g.hidden = !g.querySelector('[data-layer-item]:not([hidden])'); if (q && !g.hidden) g.open = true; });
    document.getElementById('layer-empty')?.classList.toggle('hidden', shown > 0);
  });
  const bsel = document.getElementById('basemap-select') as HTMLSelectElement | null;
  if (bsel) {
    bsel.value = state.basemap;
    bsel.addEventListener('change', () => {
      const r = document.querySelector<HTMLInputElement>(`input[name="basemap"][value="${bsel.value}"]`);
      if (r) { r.checked = true; r.dispatchEvent(new Event('change')); }
    });
  }
  wide.addEventListener('change', refreshInspector);

  renderLegend();
  syncUrl();
}
