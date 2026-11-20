// Parity test: src/lib/trend.js must reproduce scripts/pipelines/aeo/stats.py
// on the synthetic cases in tests/fixtures/trend_cases.json (regenerate with
// tests/python/make_trend_fixture.py).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { theilSen, mannKendall, normCdf, normPpf } from '../../src/lib/trend.js';

const cases = JSON.parse(readFileSync(new URL('../fixtures/trend_cases.json', import.meta.url)));
const close = (a, b, tol, msg) => assert.ok(Math.abs(a - b) <= tol, `${msg}: ${a} vs ${b}`);

test('normal distribution helpers', () => {
  close(normCdf(0), 0.5, 1e-7, 'cdf(0)');
  close(normCdf(1.959963985), 0.975, 2e-7, 'cdf(1.96)');
  close(normPpf(0.975), 1.959963985, 1e-6, 'ppf(0.975)');
});

cases.forEach((c, i) => {
  test(`case ${i} (n=${c.mann_kendall.n})`, () => {
    const ts = theilSen(c.y);
    close(ts.slope, c.theil_sen.slope, 1e-9, 'slope');
    close(ts.lo, c.theil_sen.lo, 1e-9, 'ci low');
    close(ts.hi, c.theil_sen.hi, 1e-9, 'ci high');
    close(ts.intercept, c.theil_sen.intercept, 1e-9, 'intercept');
    const mk = mannKendall(c.y);
    assert.equal(mk.n, c.mann_kendall.n);
    assert.equal(mk.s, c.mann_kendall.s);
    assert.equal(mk.corrected, c.mann_kendall.corrected);
    close(mk.tau, c.mann_kendall.tau, 1e-12, 'tau');
    close(mk.r1, c.mann_kendall.r1, 1e-9, 'r1');
    close(mk.z, c.mann_kendall.z, 1e-9, 'z');
    close(mk.p, c.mann_kendall.p, 1e-6, 'p');
  });
});
