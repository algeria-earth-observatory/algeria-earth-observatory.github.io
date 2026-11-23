// Water, cropland and climate products: values shown on the site must equal the published files,
// the outlook must appear only where verified, and reservoir values must never be called a filling rate.
import { test, expect, type Page } from '@playwright/test';
import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';

const P = join(process.cwd(), 'public/data/aeo/products');
const json = (rel: string) => JSON.parse(readFileSync(join(P, rel), 'utf8'));

async function openExplore(page: Page, query = '') {
  await page.goto(`/map/${query}`);
  await page.waitForFunction(() => (window as any).__aeoExploreMap?.loaded?.() && (window as any).__aeoExploreMap.getLayer('aeo-wilayas-fill'));
}

test('Explore: ET over stable cropland for Sétif matches the published file', async ({ page }) => {
  const f = json('et-soil-moisture/v1.0.0/web/admin1.json');
  const i = f.units.findIndex((u: any) => u.code === '19');
  const j = f.months.indexOf('2026-04');
  const v = f.series.aeti_crop[i][j];
  await openExplore(page, '?ind=et-aeti&w=19&t=2026-04');
  const ins = page.locator('#inspector');
  await expect(ins).toContainText('Actual evapotranspiration (WaPOR v3)');
  await expect(ins).toContainText('Month 2026-04');
  await expect(ins.locator('.font-mono').first()).toContainText(v.toFixed(1));
  await expect(ins).toContainText('Stable cropland');
  // two series → a legend, so identity is not carried by colour alone
  await expect(ins).toContainText('All land');
});

test('Explore: the seasonal outlook shows equal chances where hindcasts have no skill', async ({ page }) => {
  const o = json('seasonal-outlook/v0.1.0/web/outlook.json');
  const skilful = o.outlook.find((x: any) => x.skilful && x.unit_code !== 'DZ');
  const notSkilful = o.outlook.find((x: any) => !x.skilful && x.unit_code !== 'DZ');
  if (skilful) {
    await openExplore(page, `?ind=outlook-nmme&w=${skilful.unit_code}&v=${encodeURIComponent(skilful.target)}`);
    await expect(page.locator('#inspector')).toContainText(`${Math.round(skilful.p_below * 100)} %`);
    await expect(page.locator('#inspector')).toContainText('better than climatology');
  }
  await openExplore(page, `?ind=outlook-nmme&w=${notSkilful.unit_code}&v=${encodeURIComponent(notSkilful.target)}`);
  await expect(page.locator('#inspector')).toContainText('Equal chances');
  await expect(page.locator('#inspector')).toContainText('not better than climatology');
});

test('Drought: the outlook table lists exactly the published (skilful) outlooks', async ({ page }) => {
  const o = json('seasonal-outlook/v0.1.0/web/outlook.json');
  const pub = o.outlook.filter((x: any) => x.skilful && x.unit_code !== 'DZ');
  await page.goto('/drought/#outlook');
  await expect(page.locator('#outlook-h')).toContainText('Experimental test');
  const rows = page.getByRole('region', { name: 'Published outlooks' }).locator('tbody tr');
  await expect(rows).toHaveCount(pub.length);
  await expect(page.locator('#outlook')).toContainText('not an official forecast');
  await expect(page.getByRole('region', { name: /Where seasonal forecasts work/ })).toBeVisible();
});

test('Water: reservoir table matches the product and never claims a filling rate', async ({ page }) => {
  const g = json('reservoirs/v1.0.0/web/reservoirs.geojson');
  const withData = g.features.filter((f: any) => f.properties.latest_month);
  await page.goto('/water/');
  const rows = page.getByRole('region', { name: 'Reservoirs table' }).locator('tbody tr');
  await expect(rows).toHaveCount(withData.length);
  const bh = withData.find((f: any) => f.properties.name === 'Beni Haroun')?.properties;
  if (bh) {
    const row = rows.filter({ hasText: 'Beni Haroun' });
    await expect(row).toContainText(bh.latest_month);
    await expect(row).toContainText(String(Math.round(bh.latest_pct_of_max)));
  }
  await expect(page.locator('#res-h ~ p.note, .note').first()).toContainText('not a filling rate');
  await page.waitForFunction(() => (window as any).__aeoWaterMap?.getLayer?.('res-c'));
  await expect(page.locator('#tws-chart svg')).toBeVisible();
});

test('Climate: national warming summary and the wilaya table come from the product', async ({ page }) => {
  test.skip(!existsSync(join(P, 'climate-projections/v1.0.0/web/projections.json')), 'projections not built');
  const f = json('climate-projections/v1.0.0/web/projections.json');
  const nat = f.values.all.tx_mean['ssp245|2041-2070'].DZ;
  await page.goto('/climate/?ind=tx_mean&sc=ssp245%7C2041-2070');
  await expect(page.locator('#cl-summary')).toContainText(`+${nat[0].toFixed(1)}`);
  await expect(page.locator('#cl-body tr')).toHaveCount(Object.keys(f.values.all.tx_mean['ssp245|2041-2070']).length - 1);
  await page.getByLabel('Stable cropland only').check();
  await expect(page.locator('#cl-note')).toContainText('10,000 ha');
});

test('Homepage: "Algeria now" cards give the month each value describes', async ({ page }) => {
  await page.goto('/');
  const cards = page.getByRole('region', { name: 'Algeria now' }).locator('#now-cards > li');
  await expect(cards.first()).toBeVisible();
  expect(await cards.count()).toBeGreaterThanOrEqual(4);
  for (const c of await cards.all()) await expect(c).toContainText(/(19|20)\d\d/);
});

test('Homepage live monitor: cards switch the map, readout equals the published tables, Latin-only labels', async ({ page }) => {
  const sg = (v: number, d: number) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(d)}`;
  await page.goto('/');
  await page.waitForFunction(() => (window as any).__aeoHomeMap?.isStyleLoaded?.());
  // SPI-3, latest month, Setif (default wilaya)
  const spi = await (await page.request.get('/data/aeo/products/spi/v1.0.0/web/admin1.json')).json();
  const i = spi.units.findIndex((u: any) => u.code === '19');
  await expect(page.locator('#hp-month')).toContainText('latest');
  await expect(page.locator('#hp-value')).toHaveText(sg(spi.spi['3'][i].at(-1), 2));
  // the slider moves the month and the value follows the table
  await page.locator('#hp-slider').fill('0');
  await expect(page.locator('#hp-value')).toHaveText(sg(spi.spi['3'][i].at(-24), 2)); // default zoom: the last 2 years
  // full record: the strip covers every month, the slider reaches the first one
  await page.click('#hp-zoom button[data-zoom="all"]');
  await expect(page.locator('#hp-zoom button[data-zoom="all"]')).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('#hp-ctx-svg rect')).toHaveCount(spi.months.length);
  await expect(page.locator('#hp-t0')).toHaveText(/1981/);
  await page.locator('#hp-slider').fill('0');
  const v0 = spi.spi['3'][i][0];
  await expect(page.locator('#hp-value')).toHaveText(v0 === null ? '—' : sg(v0, 2));
  // hovering the detail chart previews a month with a tooltip
  await page.locator('#hp-spark').hover({ position: { x: 30, y: 50 } });
  await expect(page.locator('#hp-tip')).toBeVisible();
  await expect(page.locator('#hp-month')).toContainText('preview');
  await page.mouse.move(0, 0);
  await page.click('#hp-zoom button[data-zoom="now"]');
  await expect(page.locator('#hp-month')).toContainText('latest');
  // soil moisture on cropland
  await page.click('#now-cards button[data-mode="sm"]');
  await expect(page.locator('#now-cards button[data-mode="sm"]')).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('#home-legend')).toContainText('2018–2025');
  const et = await (await page.request.get('/data/aeo/products/et-soil-moisture/v1.0.0/web/admin1.json')).json();
  const j = et.units.findIndex((u: any) => u.code === '19');
  await expect(page.locator('#hp-value')).toHaveText(sg(et.series.rsm_crop_dep_pp[j].at(-1), 1));
  // reservoirs: surface area wording, never a filling rate
  await page.click('#now-cards button[data-mode="res"]');
  await expect(page.locator('#hp-note')).toContainText('not volume');
  // outlook: equal chances unless skilful
  await page.click('#now-cards button[data-mode="outlook"]');
  const out = await (await page.request.get('/data/aeo/products/seasonal-outlook/v0.1.0/web/outlook.json')).json();
  const first = (await (await page.request.get('/data/aeo/products/seasonal-outlook/v0.1.0/web/choropleth.json')).json()).targets[0];
  const o = out.outlook.find((r: any) => r.unit_code === '19' && r.target === first);
  expect(o).toBeTruthy();
  if (!o.skilful) await expect(page.locator('#hp-value')).toHaveText('Equal chances');
  if (o.skilful) await expect(page.locator('#hp-value')).toHaveText(`${Math.round(Math.max(o.p_below, o.p_above) * 100)} %`);
  // basemap labels: no Arabic glyph runs (MapLibre cannot shape Arabic without a plugin)
  const nonLatin = await page.evaluate(() => (window as any).__aeoHomeMap.getStyle().layers
    .filter((l: any) => l.type === 'symbol' && JSON.stringify(l.layout?.['text-field'] ?? '').includes('nonlatin')).map((l: any) => l.id));
  expect(nonLatin).toEqual([]);
});
