/**
 * Client-side catalog filtering. All records are rendered server-side; this
 * script only shows/hides and reorders them, so the page works (unfiltered)
 * without JavaScript. Within a facet, options combine with OR; across facets
 * with AND. State is mirrored in the URL query string for shareable links.
 */
const FACETS = ['kind', 'domain', 'status', 'access', 'nature', 'res', 'period', 'coverage', 'format', 'provider'] as const;
type Facet = (typeof FACETS)[number];
// Attribute on each card holding the facet value(s); multi-valued ones are "|"-separated.
const ATTR: Record<Facet, string> = {
  kind: 'kind', domain: 'domain', status: 'status', access: 'access', nature: 'nature', res: 'res',
  period: 'period', coverage: 'coverage', format: 'format', provider: 'provider',
};
const MULTI: Facet[] = ['domain', 'period', 'format'];

export function initCatalog() {
  const form = document.getElementById('f-panel') as HTMLFormElement | null;
  const q = document.getElementById('q') as HTMLInputElement | null;
  const sort = document.getElementById('sort') as HTMLSelectElement | null;
  const results = document.getElementById('results');
  const countEl = document.getElementById('result-count');
  const empty = document.getElementById('no-results');
  if (!form || !q || !sort || !results || !countEl || !empty) return;

  const cards = Array.from(results.querySelectorAll<HTMLElement>('[data-dataset]'));
  const original = [...cards];
  const total = cards.length;

  // --- restore state from URL
  const params = new URLSearchParams(location.search);
  q.value = params.get('q') ?? '';
  if (params.get('sort')) sort.value = params.get('sort')!;
  for (const f of FACETS) {
    const vals = (params.get(f) ?? '').split(',').filter(Boolean);
    form.querySelectorAll<HTMLInputElement>(`input[name="${f}"]`).forEach((i) => (i.checked = vals.includes(i.value)));
  }

  const selected = (): Record<Facet, string[]> => {
    const out = {} as Record<Facet, string[]>;
    for (const f of FACETS) {
      out[f] = Array.from(form.querySelectorAll<HTMLInputElement>(`input[name="${f}"]:checked`)).map((i) => i.value);
    }
    return out;
  };

  const cardValues = (c: HTMLElement, f: Facet) => {
    const v = c.dataset[ATTR[f]] ?? '';
    return MULTI.includes(f) ? v.split('|').filter(Boolean) : [v];
  };

  const matches = (c: HTMLElement, sel: Record<Facet, string[]>, terms: string[], skip?: Facet) => {
    for (const f of FACETS) {
      if (f === skip || sel[f].length === 0) continue;
      const vals = cardValues(c, f);
      if (!sel[f].some((s) => vals.includes(s))) return false;
    }
    const hay = c.dataset.search ?? '';
    return terms.every((t) => hay.includes(t));
  };

  function apply() {
    const sel = selected();
    const terms = q!.value.toLowerCase().split(/\s+/).filter(Boolean);
    let shown = 0;
    for (const c of cards) {
      const ok = matches(c, sel, terms);
      c.hidden = !ok;
      if (ok) shown++;
    }
    // Facet counts reflect the other active filters (standard faceted search).
    form!.querySelectorAll<HTMLElement>('[data-facet-count]').forEach((el) => {
      const [f, v] = (el.dataset.facetCount ?? '').split('::') as [Facet, string];
      const n = cards.filter((c) => matches(c, sel, terms, f) && cardValues(c, f).includes(v)).length;
      el.textContent = String(n);
    });

    // Sorting
    const s = sort!.value;
    const sorted = s === 'relevance' ? original : [...cards].sort((a, b) => {
      if (s === 'name') return (a.dataset.title ?? '').localeCompare(b.dataset.title ?? '');
      const k = s === 'published' ? 'published' : 'updated';
      return (b.dataset[k] ?? '').localeCompare(a.dataset[k] ?? '') || (a.dataset.title ?? '').localeCompare(b.dataset.title ?? '');
    });
    sorted.forEach((c) => results!.appendChild(c));

    countEl!.textContent = `Showing ${shown} of ${total} records`;
    empty!.classList.toggle('hidden', shown > 0);

    // URL state
    const p = new URLSearchParams();
    if (q!.value.trim()) p.set('q', q!.value.trim());
    if (s !== 'relevance') p.set('sort', s);
    for (const f of FACETS) if (sel[f].length) p.set(f, sel[f].join(','));
    const qs = p.toString();
    history.replaceState(null, '', qs ? `?${qs}` : location.pathname);
  }

  let t: number | undefined;
  q.addEventListener('input', () => { clearTimeout(t); t = window.setTimeout(apply, 120); });
  sort.addEventListener('change', apply);
  form.addEventListener('change', apply);
  document.getElementById('f-reset')?.addEventListener('click', () => {
    form.reset();
    q.value = '';
    sort.value = 'relevance';
    apply();
  });
  const toggle = document.getElementById('f-toggle');
  toggle?.addEventListener('click', () => {
    const open = toggle.getAttribute('aria-expanded') === 'true';
    toggle.setAttribute('aria-expanded', String(!open));
    toggle.textContent = open ? 'Show filters' : 'Hide filters';
    form.classList.toggle('hidden', open);
  });
  if ([...params.keys()].some((k) => (FACETS as readonly string[]).includes(k))) {
    // Open the panel on mobile when the page is loaded with active filters.
    form.classList.remove('hidden');
    toggle?.setAttribute('aria-expanded', 'true');
    if (toggle) toggle.textContent = 'Hide filters';
  }
  apply();
}
