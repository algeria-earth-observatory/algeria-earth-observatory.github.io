/**
 * Minimal, dependency-free SVG charts for AEO analyses.
 * Conventions (dataviz method): one y-axis, thin 2px lines, >= 8px markers on hover,
 * recessive grid, text in ink colours (never the series colour), legend for >= 2
 * series, crosshair + tooltip on hover, data table available elsewhere.
 */

// dataviz reference palette, dark-mode steps (fixed order, never cycled)
export const SERIES_COLORS = ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181'];
export const DRY = '#e66767';
export const WET = '#3987e5';
const INK = '#e8f0f8', MUTED = '#8fa3b6', GRID = '#1c2a40', AXIS = '#3a5070';

export interface LineSeries { name: string; keys: number[]; values: (number | null)[] }
export interface LineOpts {
  yLabel: string; reference?: { value: number; label: string } | null;
  trend?: { slope: number; intercept: number; from: number; to: number } | null;
  format?: (v: number) => string; keyLabel?: (k: number) => string;
}

const W = 760, H = 300, M = { t: 18, r: 18, b: 34, l: 58 };
const svgNs = 'http://www.w3.org/2000/svg';

function el<K extends keyof SVGElementTagNameMap>(tag: K, attrs: Record<string, string | number>, parent?: Element) {
  const e = document.createElementNS(svgNs, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, String(v));
  parent?.appendChild(e);
  return e;
}

function niceTicks(min: number, max: number, count = 5) {
  if (min === max) { min -= 1; max += 1; }
  const span = max - min;
  const step0 = span / count;
  const mag = 10 ** Math.floor(Math.log10(step0));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => span / s <= count) ?? 10 * mag;
  const lo = Math.floor(min / step) * step, hi = Math.ceil(max / step) * step;
  const ticks = [];
  for (let v = lo; v <= hi + step / 2; v += step) ticks.push(Math.round(v * 1e6) / 1e6);
  return { lo, hi, ticks };
}

function frame(container: HTMLElement, title: string) {
  container.innerHTML = '';
  container.classList.add('relative');
  const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': title, class: 'w-full h-auto', 'font-family': 'Inter Variable, Inter, system-ui, sans-serif' });
  el('title', {}, svg).textContent = title;
  container.appendChild(svg);
  const tip = document.createElement('div');
  tip.className = 'aeo-tip pointer-events-none absolute z-10 hidden rounded-md border border-line-strong bg-surface-2 px-2.5 py-1.5 text-[0.78rem] shadow-lg';
  container.appendChild(tip);
  return { svg, tip };
}

function axes(svg: SVGSVGElement, x: (k: number) => number, y: (v: number) => number, keys: number[], yt: number[], yLabel: string, fmt: (v: number) => string, keyLabel: (k: number) => string) {
  const g = el('g', { 'font-size': 11, fill: MUTED }, svg);
  for (const t of yt) {
    el('line', { x1: M.l, x2: W - M.r, y1: y(t), y2: y(t), stroke: GRID, 'stroke-width': 1 }, g);
    const tx = el('text', { x: M.l - 8, y: y(t) + 4, 'text-anchor': 'end' }, g);
    tx.textContent = fmt(t);
  }
  const span = keys[keys.length - 1] - keys[0];
  const every = span > 60 ? 10 : span > 25 ? 5 : span > 10 ? 2 : 1;
  for (const k of keys) {
    if (k % every !== 0 && keys.length > 12) continue;
    const tx = el('text', { x: x(k), y: H - M.b + 18, 'text-anchor': 'middle' }, g);
    tx.textContent = keyLabel(k);
  }
  el('line', { x1: M.l, x2: W - M.r, y1: H - M.b, y2: H - M.b, stroke: AXIS }, g);
  const yl = el('text', { x: 14, y: M.t + (H - M.t - M.b) / 2, transform: `rotate(-90 14 ${M.t + (H - M.t - M.b) / 2})`, 'text-anchor': 'middle', fill: MUTED }, g);
  yl.textContent = yLabel;
}

function hover(container: HTMLElement, svg: SVGSVGElement, tip: HTMLElement, keys: number[], x: (k: number) => number, html: (k: number) => string, markers: (k: number) => { y: number; color: string }[]) {
  const cross = el('line', { y1: M.t, y2: H - M.b, stroke: AXIS, 'stroke-dasharray': '3 3', visibility: 'hidden' }, svg);
  const dots = el('g', {}, svg);
  const overlay = el('rect', { x: M.l, y: M.t, width: W - M.l - M.r, height: H - M.t - M.b, fill: 'transparent' }, svg);
  const move = (clientX: number) => {
    const r = svg.getBoundingClientRect();
    const px = ((clientX - r.left) / r.width) * W;
    let best = keys[0];
    for (const k of keys) if (Math.abs(x(k) - px) < Math.abs(x(best) - px)) best = k;
    cross.setAttribute('x1', String(x(best))); cross.setAttribute('x2', String(x(best)));
    cross.setAttribute('visibility', 'visible');
    dots.innerHTML = '';
    for (const m of markers(best)) el('circle', { cx: x(best), cy: m.y, r: 4.5, fill: m.color, stroke: '#fff', 'stroke-width': 2 }, dots);
    tip.innerHTML = html(best);
    tip.classList.remove('hidden');
    const left = (x(best) / W) * r.width;
    tip.style.left = `${Math.min(Math.max(left + 12, 0), r.width - tip.offsetWidth - 4)}px`;
    tip.style.top = '8px';
  };
  overlay.addEventListener('pointermove', (e) => move((e as PointerEvent).clientX));
  overlay.addEventListener('pointerleave', () => { tip.classList.add('hidden'); cross.setAttribute('visibility', 'hidden'); dots.innerHTML = ''; });
  container.tabIndex = 0;
  let idx = keys.length - 1;
  container.addEventListener('keydown', (e) => {
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
    idx = Math.min(keys.length - 1, Math.max(0, idx + (e.key === 'ArrowRight' ? 1 : -1)));
    const r = svg.getBoundingClientRect();
    move(r.left + (x(keys[idx]) / W) * r.width);
    e.preventDefault();
  });
  container.addEventListener('blur', () => tip.classList.add('hidden'));
}

export function lineChart(container: HTMLElement, series: LineSeries[], opts: LineOpts, title: string) {
  const fmt = opts.format ?? ((v: number) => v.toLocaleString('en-US', { maximumFractionDigits: 0 }));
  const keyLabel = opts.keyLabel ?? ((k: number) => String(k));
  const keys = [...new Set(series.flatMap((s) => s.keys))].sort((a, b) => a - b);
  const vals = series.flatMap((s) => s.values.filter((v): v is number => v !== null));
  if (opts.reference) vals.push(opts.reference.value);
  const { lo, hi, ticks } = niceTicks(Math.min(0, ...vals), Math.max(...vals));
  const x = (k: number) => M.l + (keys.length === 1 ? 0.5 : (k - keys[0]) / (keys[keys.length - 1] - keys[0])) * (W - M.l - M.r);
  const y = (v: number) => H - M.b - ((v - lo) / (hi - lo)) * (H - M.t - M.b);
  const { svg, tip } = frame(container, title);
  axes(svg, x, y, keys, ticks, opts.yLabel, fmt, keyLabel);
  if (opts.reference) {
    el('line', { x1: M.l, x2: W - M.r, y1: y(opts.reference.value), y2: y(opts.reference.value), stroke: INK, 'stroke-width': 1.25, 'stroke-dasharray': '5 4' }, svg);
    const t = el('text', { x: W - M.r - 4, y: y(opts.reference.value) - 6, 'text-anchor': 'end', 'font-size': 11, fill: INK }, svg);
    t.textContent = opts.reference.label;
  }
  if (opts.trend) {
    const { slope, intercept, from, to } = opts.trend;
    el('line', { x1: x(from), x2: x(to), y1: y(intercept + slope * from), y2: y(intercept + slope * to), stroke: MUTED, 'stroke-width': 1.5 }, svg);
  }
  series.forEach((s, si) => {
    const color = SERIES_COLORS[si % SERIES_COLORS.length];
    let d = '';
    s.keys.forEach((k, i) => {
      const v = s.values[i];
      if (v === null) { d += ' '; return; }
      d += `${d && !d.endsWith(' ') ? 'L' : 'M'}${x(k).toFixed(1)},${y(v).toFixed(1)}`;
    });
    el('path', { d, fill: 'none', stroke: color, 'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }, svg);
  });
  hover(container, svg, tip, keys, x,
    (k) => `<p class="font-semibold text-atlas">${keyLabel(k)}</p>` + series.map((s, si) => {
      const v = s.values[s.keys.indexOf(k)];
      return `<p class="flex items-center gap-1.5"><span class="inline-block h-2 w-2 rounded-full" style="background:${SERIES_COLORS[si]}"></span><span class="text-slate">${s.name}</span> <span class="ml-auto pl-3 font-mono text-graphite">${v === null || v === undefined ? '—' : fmt(v)}</span></p>`;
    }).join('') + (opts.reference ? `<p class="text-slate">${opts.reference.label}: <span class="font-mono">${fmt(opts.reference.value)}</span></p>` : ''),
    (k) => series.map((s, si) => ({ v: s.values[s.keys.indexOf(k)], color: SERIES_COLORS[si] }))
      .filter((m): m is { v: number; color: string } => m.v !== null && m.v !== undefined).map((m) => ({ y: y(m.v), color: m.color })));
  return svg;
}

export function anomalyChart(container: HTMLElement, keys: number[], values: (number | null)[], opts: { yLabel: string; format?: (v: number) => string; keyLabel?: (k: number) => string }, title: string) {
  const fmt = opts.format ?? ((v: number) => `${v > 0 ? '+' : ''}${v.toLocaleString('en-US', { maximumFractionDigits: 0 })}`);
  const keyLabel = opts.keyLabel ?? ((k: number) => String(k));
  const vals = values.filter((v): v is number => v !== null);
  const ext = Math.max(1, ...vals.map(Math.abs));
  const { lo, hi, ticks } = niceTicks(-ext, ext);
  const n = keys.length;
  const band = (W - M.l - M.r) / Math.max(n, 1);
  const x = (k: number) => M.l + (keys.indexOf(k) + 0.5) * band;
  const y = (v: number) => H - M.b - ((v - lo) / (hi - lo)) * (H - M.t - M.b);
  const { svg, tip } = frame(container, title);
  axes(svg, x, y, keys, ticks, opts.yLabel, fmt, keyLabel);
  el('line', { x1: M.l, x2: W - M.r, y1: y(0), y2: y(0), stroke: INK, 'stroke-width': 1 }, svg);
  const bw = Math.max(2, band - 2);
  keys.forEach((k, i) => {
    const v = values[i];
    if (v === null) return;
    const top = Math.min(y(v), y(0)), h = Math.max(1, Math.abs(y(v) - y(0)));
    const r = Math.min(4, bw / 2, h);
    // rounded data end, square at the baseline
    const x0 = x(k) - bw / 2, x1 = x0 + bw;
    const d = v >= 0
      ? `M${x0},${y(0)}V${top + r}Q${x0},${top} ${x0 + r},${top}H${x1 - r}Q${x1},${top} ${x1},${top + r}V${y(0)}Z`
      : `M${x0},${y(0)}V${top + h - r}Q${x0},${top + h} ${x0 + r},${top + h}H${x1 - r}Q${x1},${top + h} ${x1},${top + h - r}V${y(0)}Z`;
    el('path', { d, fill: v >= 0 ? WET : DRY }, svg);
  });
  hover(container, svg, tip, keys, x,
    (k) => { const v = values[keys.indexOf(k)]; return `<p class="font-semibold text-atlas">${keyLabel(k)}</p><p class="text-slate">${v === null ? 'no data' : `${fmt(v)} ${opts.yLabel.includes('%') ? '' : 'mm'} ${v >= 0 ? '(wetter than normal)' : '(drier than normal)'}`}</p>`; },
    () => []);
  return svg;
}

export function svgString(svg: SVGSVGElement) {
  const clone = svg.cloneNode(true) as SVGSVGElement;
  clone.setAttribute('xmlns', svgNs);
  clone.setAttribute('width', String(W)); clone.setAttribute('height', String(H));
  const bg = document.createElementNS(svgNs, 'rect');
  bg.setAttribute('width', '100%'); bg.setAttribute('height', '100%'); bg.setAttribute('fill', '#ffffff');
  clone.insertBefore(bg, clone.firstChild);
  clone.querySelectorAll('rect[fill="transparent"]').forEach((r) => r.remove());
  // exports use the light (print) palette
  const swap: Record<string, string> = { [INK]: '#202b33', [MUTED]: '#5b6872', [GRID]: '#e3e8ec', [AXIS]: '#9aa7b1',
    '#3987e5': '#2a78d6', '#d95926': '#eb6834', '#199e70': '#1baf7a', '#c98500': '#eda100', '#d55181': '#e87ba4', '#e66767': '#d03b3b' };
  let out = new XMLSerializer().serializeToString(clone);
  for (const [a, b] of Object.entries(swap)) out = out.split(a).join(b);
  return out;
}

export async function svgToPng(svg: SVGSVGElement, footer: string): Promise<Blob> {
  const scale = 2;
  const img = new Image();
  const url = URL.createObjectURL(new Blob([svgString(svg)], { type: 'image/svg+xml' }));
  await new Promise((res, rej) => { img.onload = res; img.onerror = rej; img.src = url; });
  const canvas = document.createElement('canvas');
  canvas.width = W * scale; canvas.height = (H + 26) * scale;
  const ctx = canvas.getContext('2d')!;
  ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(img, 0, 0, W * scale, H * scale);
  ctx.fillStyle = MUTED; ctx.font = `${11 * scale}px Inter, system-ui, sans-serif`;
  ctx.fillText(footer, M.l * scale, (H + 16) * scale);
  URL.revokeObjectURL(url);
  return new Promise((res) => canvas.toBlob((b) => res(b!), 'image/png'));
}
