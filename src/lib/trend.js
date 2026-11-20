// @ts-check
/**
 * Trend statistics for the browser — the same methods as scripts/pipelines/aeo/stats.py
 * (tests/js/trend.test.mjs checks both give the same results).
 *
 *  - Theil–Sen slope with the Sen (1968) / Gilbert (1987) 95 % confidence interval.
 *  - Two-sided Mann–Kendall test with tie correction. If the lag-1 autocorrelation of the
 *    Sen-detrended series is significant at 5 % (|r1| > 1.96 / sqrt(n)), Var(S) is
 *    multiplied by 1 + 2 Σ_{k=1}^{n-1} (1 - k/n) r1^k (Yue & Wang 2004, AR(1) case).
 *  - Missing values (null / NaN) are removed; at least 8 values are needed for the test.
 */

/** Standard normal CDF via erfc (fractional error < 1.2e-7; enough for p-values to 4 decimals).
 * @param {number} z */
export function normCdf(z) {
  return 0.5 * erfc(-z / Math.SQRT2);
}

/** @param {number} x */
function erfc(x) {
  // Numerical Recipes erfcc (Chebyshev fit), fractional error < 1.2e-7 everywhere
  const z = Math.abs(x);
  const t = 1 / (1 + 0.5 * z);
  const r = t * Math.exp(-z * z - 1.26551223 + t * (1.00002368 + t * (0.37409196 + t * (0.09678418 +
    t * (-0.18628806 + t * (0.27886807 + t * (-1.13520398 + t * (1.48851587 +
    t * (-0.82215223 + t * 0.17087277)))))))));
  return x >= 0 ? r : 2 - r;
}

/** Inverse standard normal CDF (Acklam's algorithm, refined).
 * @param {number} p */
export function normPpf(p) {
  const a = [-3.969683028665376e1, 2.209460984245205e2, -2.759285104469687e2, 1.38357751867269e2, -3.066479806614716e1, 2.506628277459239];
  const b = [-5.447609879822406e1, 1.615858368580409e2, -1.556989798598866e2, 6.680131188771972e1, -1.328068155288572e1];
  const c = [-7.784894002430293e-3, -3.223964580411365e-1, -2.400758277161838, -2.549732539343734, 4.374664141464968, 2.938163982698783];
  const d = [7.784695709041462e-3, 3.224671290700398e-1, 2.445134137142996, 3.754408661907416];
  const pl = 0.02425;
  let q, r, x;
  if (p < pl) { q = Math.sqrt(-2 * Math.log(p)); x = (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1); }
  else if (p <= 1 - pl) { q = p - 0.5; r = q * q; x = (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1); }
  else { q = Math.sqrt(-2 * Math.log(1 - p)); x = -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1); }
  const e = normCdf(x) - p;
  const u = e * Math.sqrt(2 * Math.PI) * Math.exp((x * x) / 2);
  return x - u / (1 + (x * u) / 2);
}

/** @param {(number|null)[]} y @param {number[]} [x] */
function clean(y, x) {
  /** @type {number[]} */ const xs = [];
  /** @type {number[]} */ const ys = [];
  y.forEach((v, i) => {
    if (v !== null && v !== undefined && !Number.isNaN(v)) { ys.push(v); xs.push(x ? x[i] : i); }
  });
  return { xs, ys };
}

/** @param {number[]} ys */
function varS(ys) {
  const n = ys.length;
  const counts = new Map();
  for (const v of ys) counts.set(v, (counts.get(v) ?? 0) + 1);
  let ties = 0;
  for (const t of counts.values()) ties += t * (t - 1) * (2 * t + 5);
  return (n * (n - 1) * (2 * n + 5) - ties) / 18;
}

/**
 * @param {(number|null)[]} y
 * @param {number[]} [x]
 * @returns {{slope:number|null, lo:number|null, hi:number|null, intercept:number|null, n:number}}
 */
export function theilSen(y, x, alpha = 0.05) {
  const { xs, ys } = clean(y, x);
  const n = ys.length;
  if (n < 3) return { slope: null, lo: null, hi: null, intercept: null, n };
  const slopes = [];
  for (let i = 0; i < n - 1; i++) for (let j = i + 1; j < n; j++) {
    const dx = xs[j] - xs[i];
    if (dx !== 0) slopes.push((ys[j] - ys[i]) / dx);
  }
  slopes.sort((a, b) => a - b);
  const median = (/** @type {number[]} */ arr) => { const m = arr.length; return m % 2 ? arr[(m - 1) / 2] : (arr[m / 2 - 1] + arr[m / 2]) / 2; };
  const slope = median(slopes);
  const c = normPpf(1 - alpha / 2) * Math.sqrt(varS(ys));
  const m = slopes.length;
  const m1 = (m - c) / 2, m2 = (m + c) / 2;
  const lo = slopes[Math.min(Math.max(Math.floor(m1) - 1, 0), m - 1)];
  const hi = slopes[Math.min(Math.max(Math.ceil(m2), 0), m - 1)];
  const intercept = median(ys.map((v, i) => v - slope * xs[i]).sort((a, b) => a - b));
  return { slope, lo, hi, intercept, n };
}

/**
 * @param {(number|null)[]} y
 * @returns {{n:number, s:number|null, tau:number|null, z:number|null, p:number|null, r1:number|null, corrected:boolean}}
 */
export function mannKendall(y) {
  const { xs, ys } = clean(y);
  const n = ys.length;
  if (n < 8) return { n, s: null, tau: null, z: null, p: null, r1: null, corrected: false };
  let s = 0;
  for (let i = 0; i < n - 1; i++) for (let j = i + 1; j < n; j++) s += Math.sign(ys[j] - ys[i]);
  let v = varS(ys);
  const { slope } = theilSen(ys, xs);
  const resid = ys.map((val, i) => val - /** @type {number} */ (slope) * xs[i]);
  const mean = resid.reduce((a, b) => a + b, 0) / n;
  const d = resid.map((r) => r - mean);
  const den = d.reduce((a, b) => a + b * b, 0);
  let num = 0;
  for (let i = 0; i < n - 1; i++) num += d[i] * d[i + 1];
  const r1 = den > 0 ? num / den : 0;
  const corrected = Math.abs(r1) > 1.96 / Math.sqrt(n);
  if (corrected) {
    let ratio = 1;
    for (let k = 1; k < n; k++) ratio += 2 * (1 - k / n) * r1 ** k;
    v *= Math.max(ratio, 1e-9);
  }
  const z = s > 0 ? (s - 1) / Math.sqrt(v) : s < 0 ? (s + 1) / Math.sqrt(v) : 0;
  const p = 2 * (1 - normCdf(Math.abs(z)));
  return { n, s, tau: s / (0.5 * n * (n - 1)), z, p, r1, corrected };
}

/**
 * Plain-language summary of a trend result (no claim of significance unless p < alpha).
 * @param {{slope:number|null, lo:number|null, hi:number|null}} ts
 * @param {{p:number|null}} mk
 */
export function describeTrend(ts, mk, unit = 'mm', per = 'decade', alpha = 0.05) {
  if (ts.slope === null || mk.p === null) return 'Too few years for a trend test (at least 8 needed).';
  const f = (/** @type {number|null} */ v) => (v === null ? '—' : `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(1)}`);
  const sig = mk.p < alpha;
  return `${f(ts.slope)} ${unit} per ${per} (95 % interval ${f(ts.lo)} to ${f(ts.hi)}); Mann–Kendall p = ${mk.p < 0.001 ? '< 0.001' : mk.p.toFixed(3)}` +
    (sig ? ` — statistically significant at ${alpha * 100} %.` : ` — not statistically significant at ${alpha * 100} %.`);
}
