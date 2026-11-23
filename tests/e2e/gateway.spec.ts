// The nine required tests of the "scientific gateway" brief: map, regional inspector,
// indicators, external sources, publications, downloads, mobile/keyboard, honest gaps.
import { test, expect, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const pubs = JSON.parse(readFileSync(join(process.cwd(), 'src/data/publications.json'), 'utf8'));
const SETIF: [number, number] = [5.45, 36.05]; // inside the wilaya of Sétif (lng, lat)

async function openExplore(page: Page, query = '') {
  await page.goto(`/map/${query}`);
  await page.waitForFunction(() => (window as any).__aeoExploreMap?.loaded?.() && (window as any).__aeoExploreMap.getLayer('aeo-wilayas-fill'));
  await page.waitForFunction(() => (window as any).__aeoExploreMap.isSourceLoaded('aeo-wilayas'));
}
async function clickLngLat(page: Page, lngLat: [number, number]) {
  const pt = await page.evaluate((ll) => { const m = (window as any).__aeoExploreMap; const p = m.project(ll); const r = m.getCanvas().getBoundingClientRect(); return { x: r.left + p.x, y: r.top + p.y }; }, lngLat);
  await page.mouse.click(pt.x, pt.y);
}

test('1. homepage: bright map of Algeria, clearly visible', async ({ page }) => {
  await page.goto('/');
  // first screen: the pixel-atlas image of Algeria (docs/BRAND.md §7)
  const hero = page.locator('img[src*="algeria-pixel"]');
  await expect(hero).toBeVisible();
  const hb = await hero.boundingBox();
  expect(hb!.width).toBeGreaterThan(340); expect(hb!.y).toBeLessThan(1000);
  // then the live monitor map
  const map = page.locator('#home-map canvas');
  await map.scrollIntoViewIfNeeded();
  await expect(map).toBeVisible();
  const box = await map.boundingBox();
  expect(box!.width).toBeGreaterThan(330); expect(box!.height).toBeGreaterThan(380);
  // light basemap (OpenFreeMap Positron) and a light page; no dark style
  await page.waitForFunction(() => (window as any).__aeoHomeMap?.isStyleLoaded?.());
  const rgb = await page.evaluate(() => {
    const bgLayer = (window as any).__aeoHomeMap.getStyle().layers.find((l: any) => l.type === 'background');
    const el = document.createElement('div'); el.style.color = String(bgLayer?.paint?.['background-color'] ?? ''); document.body.appendChild(el);
    const c = getComputedStyle(el).color; el.remove(); return c.match(/\d+/g)!.slice(0, 3).map(Number);
  });
  expect(Math.min(...rgb)).toBeGreaterThan(200); // light basemap background
  const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  expect(bg).toBe('rgb(242, 239, 231)');
  await expect(page.locator('#home-legend')).toContainText('SPI-3');
  await expect(page.getByRole('link', { name: 'Explore Algeria' })).toBeVisible();
});

test('2. Explore: clicking Sétif opens the adjacent inspector with its identifier', async ({ page }) => {
  await openExplore(page, '?ind=precip-annual');
  await expect(page.locator('#inspector')).toBeHidden();
  await clickLngLat(page, SETIF);
  await expect(page.locator('#inspector')).toBeVisible();
  await expect(page.locator('#inspector-body')).toContainText('Wilaya 19');
  await expect(page.locator('#ins-h')).toContainText('Sétif');
  // beside the map, not over it (desktop)
  const ins = await page.locator('#inspector').boundingBox(), m = await page.locator('#map').boundingBox();
  expect(ins!.x).toBeGreaterThanOrEqual(m!.x + m!.width - 1);
  await expect(page).toHaveURL(/w=19/);
});

test('3. precipitation: real statistics and a chart for the selected wilaya', async ({ page }) => {
  await openExplore(page, '?ind=precip-annual&t=2020&w=19');
  const body = page.locator('#inspector-body');
  await expect(body).toContainText('Annual precipitation');
  await expect(body).toContainText('Calendar year 2020');
  const annual = JSON.parse(readFileSync(join(process.cwd(), 'public/data/aeo/products/precipitation/v1.0.0/web/annual_admin1.json'), 'utf8'));
  const i = annual.units.findIndex((u: any) => u.code === '19');
  const v = annual.annual[i][annual.years.indexOf(2020)];
  await expect(body).toContainText(`${Math.round(v).toLocaleString('en-US')}`);
  await expect(body.locator('[data-ins-chart] svg')).toBeVisible();
  await expect(body).toContainText('CHIRPS v3.0');
});

test('4. changing the indicator keeps the geographic selection', async ({ page }) => {
  await openExplore(page, '?ind=precip-annual&w=19');
  await expect(page.locator('#ins-h')).toContainText('Sétif');
  await page.locator('label[data-layer="spi-3"]').click();
  await expect(page.locator('#inspector-body')).toContainText('Precipitation index SPI-3');
  await expect(page.locator('#ins-h')).toContainText('Sétif');
  await page.locator('label[data-layer="spei-12"]').click();
  await expect(page.locator('#inspector-body')).toContainText('Drought index SPEI-12');
  await expect(page.locator('#ins-h')).toContainText('Sétif');
  await expect(page).toHaveURL(/ind=spei-12/);
});

test('5. an external soil dataset is marked external and its source link works', async ({ page, request }) => {
  await page.goto('/data/?kind=external');
  const row = page.locator('[data-list="external"] > li', { hasText: 'SoilGrids' }).first();
  await expect(row).toContainText('External source');
  const link = row.getByRole('link', { name: /Visit source/ });
  const href = await link.getAttribute('href');
  expect(href).toMatch(/^https:\/\/(www\.)?isric\.org\//);
  const r = await request.get(href!, { maxRedirects: 5 });
  expect(r.status()).toBeLessThan(400);
  await expect(row.getByRole('button', { name: /Download/ })).toHaveCount(0);
});

test('6. a publication DOI resolves to the right publication', async ({ page, request }) => {
  await page.goto('/science/publications/');
  const p = pubs.find((x: any) => x.doi === '10.5194/soil-7-217-2021');
  const link = page.locator(`a[href="https://doi.org/${p.doi}"]`);
  await expect(link).toHaveText(`doi.org/${p.doi}`);
  const h = await request.get(`https://doi.org/api/handles/${p.doi}`);
  expect((await h.json()).responseCode).toBe(1);
  const cr = await request.get(`https://api.crossref.org/works/${p.doi}`);
  const m = (await cr.json()).message;
  expect(m.title[0]).toContain('SoilGrids 2.0');
  expect(m.author[0].family).toBe('Poggio');
  await expect(page.locator(`li:has(> div a[href="https://doi.org/${p.doi}"])`)).toContainText(p.journal);
});

test('7. downloading from the inspector gives the right place, units, dates and source', async ({ page }) => {
  await openExplore(page, '?ind=precip-annual&w=19');
  const [dl] = await Promise.all([page.waitForEvent('download'), page.locator('[data-ins-dl]').click()]);
  const text = readFileSync((await dl.path())!, 'utf8');
  const [head, ...rows] = text.trim().split(/\r?\n/);
  expect(head).toContain('precip_mm');
  expect(rows.length).toBe(45);
  expect(rows.every((r) => r.split(',')[1] === '19')).toBe(true);
  expect(rows[0]).toContain('1981'); expect(rows.at(-1)).toContain('2025');
  expect(text).toContain('CHIRPS v3.0');
});

test('8a. keyboard: choose a wilaya and an indicator without the mouse', async ({ page }) => {
  await openExplore(page, '?ind=precip-annual');
  await page.locator('#ex-wilaya').focus();
  await page.keyboard.type('setif');
  await page.keyboard.press('Enter');
  await expect(page.locator('#ins-h')).toContainText('Sétif');
  await page.locator('input[name="ex-ind"][value="precip-annual"]').focus();
  await page.keyboard.press('ArrowDown');
  await expect(page.locator('input[name="ex-ind"][value="precip-anomaly"]')).toBeChecked();
  await expect(page.locator('#inspector-body')).toContainText('Precipitation anomaly');
  await expect(page.locator('#ins-close')).toBeVisible();
  await page.locator('#ins-close').focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#inspector')).toBeHidden();
});

test('8b. Explore on a phone: place first, map, then statistics @mobile', async ({ page }) => {
  await openExplore(page, '?ind=precip-annual&w=31');
  const place = await page.locator('#ex-wilaya').boundingBox(), map = await page.locator('#map').boundingBox(), ins = await page.locator('#inspector').boundingBox();
  expect(place!.y).toBeLessThan(map!.y);
  expect(ins!.y).toBeGreaterThanOrEqual(map!.y + map!.height - 1);
  await expect(page.locator('#ins-h')).toContainText('Oran');
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});

test('9. no AEO statistics: an honest message, never a number', async ({ page }) => {
  await openExplore(page, '?ind=ndvi-16day&w=19');
  const body = page.locator('#inspector-body');
  await expect(body).toContainText('Available from external source — regional statistics not yet processed by AEO.');
  await expect(body.locator('.font-mono.text-\\[2rem\\]')).toHaveCount(0);
  await expect(body.getByRole('link', { name: /Visit source/ })).toHaveAttribute('href', /^https:\/\//);
});

test('No Arabic script in the pages (not yet translated and reviewed)', async ({ page }) => {
  for (const url of ['/', '/regions/', '/regions/19/', '/regions/19/1901/', '/data/aeo-dza-admin-boundaries/']) {
    await page.goto(url);
    const html = await page.content();
    expect(html.match(/[؀-ۿ]+/g), url).toBeNull();
  }
});
