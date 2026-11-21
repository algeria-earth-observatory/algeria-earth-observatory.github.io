// Automated accessibility checks (axe-core, WCAG 2.2 AA rule set). These do not
// replace manual keyboard and screen-reader testing (see docs/USABILITY_AUDIT.md).
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { openDownloader, pickFromCombobox } from './helpers';

const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const PAGES = ['/', '/data/', '/data/aeo-dza-precipitation-chirps3/', '/data/aeo-dza-spei-terraclimate/', '/data/aeo-dza-spi-chirps3/', '/data/aeo-dza-soil-soilgrids/', '/data/aeo-dza-admin-boundaries/',
  '/map/', '/drought/', '/science/', '/science/publications/', '/regions/', '/regions/19/', '/regions/19/1901/', '/about/'];

const scan = async (page: import('@playwright/test').Page) => {
  const r = await new AxeBuilder({ page }).withTags(TAGS).exclude('.maplibregl-canvas').analyze();
  return r.violations.map((v) => `${v.id} (${v.impact}): ${v.nodes.slice(0, 3).map((n) => n.target.join(' ')).join(' | ')}`);
};

for (const path of PAGES) {
  test(`axe ${path}`, async ({ page }) => {
    await page.goto(path);
    await page.waitForLoadState('networkidle');
    expect(await scan(page)).toEqual([]);
  });
  test(`axe ${path} @mobile`, async ({ page }) => {
    await page.goto(path);
    await page.waitForLoadState('networkidle');
    expect(await scan(page)).toEqual([]);
  });
}

test('axe: download assistant with the combobox open and in the unavailable state', async ({ page }) => {
  await openDownloader(page, '/data/');
  await page.locator('#rdd-wilaya').click();
  await page.locator('#rdd-wilaya').fill('se');
  expect(await scan(page)).toEqual([]);
  await pickFromCombobox(page, '#rdd-wilaya', 'setif', '19');
  await page.getByRole('radio', { name: /Drought \(SPEI\)/ }).check();
  await page.locator('input[name="rdd-format"][value="geotiff"]').check({ force: true });
  expect(await scan(page)).toEqual([]);
});

test('focus is visible on the download assistant controls', async ({ page }) => {
  await openDownloader(page, '/data/');
  for (const sel of ['#rdd-wilaya', 'input[name="rdd-indicator"]:checked', '#rdd-from-y']) {
    await page.locator(sel).focus();
    const style = await page.locator(sel).evaluate((el) => {
      const cs = getComputedStyle(el); const pcs = getComputedStyle(el.closest('label') ?? el);
      return { o: cs.outlineStyle, w: cs.outlineWidth, po: pcs.outlineStyle };
    });
    expect(style.o !== 'none' || style.po !== 'none', `${sel} shows no focus outline`).toBe(true);
  }
});

test('reduced motion is respected', async ({ browser }) => {
  const ctx = await browser.newContext({ reducedMotion: 'reduce' });
  const page = await ctx.newPage();
  await page.goto('/data/');
  const d = await page.locator('.btn-primary').first().evaluate((el) => getComputedStyle(el).transitionDuration);
  expect(['0s', '1e-05s', '0.00001s']).toContain(d);
  await ctx.close();
});

for (const path of PAGES) {
  test(`no horizontal page scroll ${path} @mobile`, async ({ page }) => {
    await page.goto(path);
    await page.waitForLoadState('networkidle');
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });
}
