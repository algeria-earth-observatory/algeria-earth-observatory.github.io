// User journeys of the regional download workflow. Every test opens the downloaded
// file and checks its contents (identifiers, periods, variables, type, checksum).
import { test, expect } from '@playwright/test';
import { openDownloader, pickFromCombobox, setPeriod, download, parseCsv, sha256, manifest, publishedRows, tabTo } from './helpers';

const PRECIP_ANNUAL_W = '/data/aeo/products/precipitation/v1.0.0/tables/aeo_precip_annual_admin1_v1.0.0.csv';
const SPEI_MONTHLY_W = '/data/aeo/products/spei/v1.0.0/tables/aeo_spei_monthly_admin1_v1.0.0.csv';

test('1. annual precipitation statistics for Sétif', async ({ page }) => {
  await openDownloader(page, '/data/');
  await pickFromCombobox(page, '#rdd-wilaya', 'setif', '19');
  await expect(page.locator('#rdd-area')).toContainText('wilaya code 19');
  await expect(page.locator('#rdd-result')).toContainText('45 rows expected');
  const { buf, name } = await download(page);
  expect(name).toBe('aeo_w19-setif_precip_annual_1981_2025_v1.0.0.csv');
  const { cols, rows } = parseCsv(buf.toString('utf8'));
  expect(cols.slice(0, 6)).toEqual(['level', 'unit_code', 'unit_name', 'parent_code', 'year', 'precip_mm']);
  expect(rows).toHaveLength(45);
  expect(new Set(rows.map((r) => r.unit_code))).toEqual(new Set(['19']));
  expect([rows[0].year, rows.at(-1)!.year]).toEqual(['1981', '2025']);
  const pub = publishedRows(PRECIP_ANNUAL_W, '19');
  rows.forEach((r, i) => expect(Number(r.precip_mm)).toBe(Number(pub[i].precip_mm)));
  expect(rows[0].license).toContain('CC BY 4.0');
  await expect(page.locator('#rdd-status')).toContainText('45 rows');
});

test('2. monthly precipitation statistics for a commune', async ({ page }) => {
  await openDownloader(page, '/data/');
  await page.getByRole('radio', { name: 'Commune', exact: true }).check({ force: true });
  await pickFromCombobox(page, '#rdd-wilaya', '19', '19');
  await pickFromCombobox(page, '#rdd-commune', 'El Eulma', '1920');
  await page.getByRole('radio', { name: 'Monthly' }).check({ force: true });
  await setPeriod(page, '2010-01', '2010-12');
  await expect(page.locator('#rdd-result')).toContainText('12 months');
  await expect(page.locator('#rdd-result')).toContainText('wilaya partition');
  const { buf, name } = await download(page);
  expect(name).toMatch(/^aeo_c1920-el-eulma_precip_monthly_2010-01_2010-12_v1\.0\.0\.csv$/);
  const { cols, rows } = parseCsv(buf.toString('utf8'));
  expect(cols).toContain('month');
  expect(rows).toHaveLength(12);
  expect(rows.every((r) => r.unit_code === '1920' && r.parent_code === '19' && r.year === '2010')).toBe(true);
  expect(rows.map((r) => r.month)).toEqual(['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12']);
});

test('3. available wilaya precipitation GeoTIFF', async ({ page }) => {
  await openDownloader(page, '/data/');
  await pickFromCombobox(page, '#rdd-wilaya', 'Sétif', '19');
  await page.locator('input[name="rdd-format"][value="geotiff"]').check({ force: true });
  const asset = manifest('precipitation').download_assets.find((a: any) => a.level === 'admin1' && a.unit_code === '19');
  await expect(page.locator('#rdd-go')).toHaveAttribute('href', asset.href);
  await expect(page.locator('#rdd-result')).toContainText(asset.sha256);
  const { buf } = await download(page);
  expect(buf.subarray(0, 4).toString('latin1')).toBe('II*\u0000');
  expect(buf.length).toBe(asset.bytes);
  expect(sha256(buf)).toBe(asset.sha256);
});

test('4. wilaya SPEI statistics', async ({ page }) => {
  await openDownloader(page, '/data/');
  await pickFromCombobox(page, '#rdd-wilaya', 'setif', '19');
  await page.getByRole('radio', { name: /Drought \(SPEI\)/ }).check();
  await page.selectOption('#rdd-scale', '12');
  await setPeriod(page, '2020-01', '2025-12');
  const { buf, name } = await download(page);
  expect(name).toBe('aeo_w19-setif_spei_monthly_spei12_2020-01_2025-12_v1.0.0.csv');
  const { cols, rows } = parseCsv(buf.toString('utf8'));
  expect(cols).toContain('spei_12');
  expect(cols).not.toContain('spei_3');
  expect(rows).toHaveLength(72);
  expect(rows.every((r) => r.unit_code === '19' && r.unit_name === 'Sétif')).toBe(true);
  const pub = publishedRows(SPEI_MONTHLY_W, '19').filter((r) => Number(r.year) >= 2020);
  rows.forEach((r, i) => expect(Number(r.spei_12)).toBe(Number(pub[i].spei_12)));
});

test('5. unavailable SPEI wilaya GeoTIFF is explained, with working alternatives', async ({ page }) => {
  await openDownloader(page, '/data/');
  await pickFromCombobox(page, '#rdd-wilaya', 'setif', '19');
  await page.getByRole('radio', { name: /Drought \(SPEI\)/ }).check();
  await page.locator('input[name="rdd-format"][value="geotiff"]').check({ force: true });
  const result = page.locator('#rdd-result');
  await expect(result).toContainText('Not available for this selection');
  await expect(result).toContainText('SPEI grids are published for Algeria as a whole only');
  await expect(page.locator('#rdd-go')).toHaveCount(0);
  await result.getByRole('button', { name: 'GeoTIFF for Algeria' }).click();
  const nat = manifest('spei').download_assets.filter((a: any) => a.format === 'COG' && a.level === 'admin0').map((a: any) => a.href);
  await expect(page.locator('#rdd-go')).toHaveAttribute('href', new RegExp(nat.map((h: string) => h.replace(/[.]/g, '\\.')).join('|')));
});

test('6. switching between map and time series keeps the selection', async ({ page }) => {
  await page.goto('/drought/?level=admin1&unit=19&var=precip');
  await expect(page.locator('#az-title')).toContainText('Sétif');
  await page.selectOption('#az-wilaya', '05');
  await expect(page.locator('#az-title')).toContainText('Batna');
  await page.getByRole('tab', { name: 'Map' }).click();
  await expect(page.locator('#panel-map')).toBeVisible();
  await expect(page.locator('#az-title')).toContainText('Batna');
  await page.getByRole('tab', { name: 'Time series' }).click();
  await expect(page.locator('#az-ts svg')).toBeVisible();
  await expect(page.locator('#az-title')).toContainText('Batna');
  await expect(page.locator('#az-wilaya')).toHaveValue('05');
  // the page's download assistant follows the analysis
  await expect(page.locator('#rdd-wilaya')).toHaveValue(/05 — Batna/);
  // the filtered table can be downloaded
  await page.getByRole('tab', { name: 'Statistics' }).click();
  const [dl] = await Promise.all([page.waitForEvent('download'), page.click('#az-dl-table')]);
  const { rows } = parseCsv((await import('node:fs')).readFileSync((await dl.path())!, 'utf8'));
  expect(rows.length).toBeGreaterThan(40);
  expect(rows.every((r) => r.unit_code === '05')).toBe(true);
});

test('7a. keyboard only: Sétif statistics', async ({ page }) => {
  await openDownloader(page, '/data/');
  await page.locator('#rdd-h').evaluate((h) => { h.setAttribute('tabindex', '-1'); (h as HTMLElement).focus(); });
  await tabTo(page, 'input[name="rdd-level"]');
  await tabTo(page, '#rdd-wilaya');
  await page.keyboard.type('setif');
  await page.keyboard.press('Enter');
  await expect(page.locator('#rdd-wilaya')).toHaveValue('19 — Sétif');
  await tabTo(page, 'input[name="rdd-step"]');
  await page.keyboard.press('ArrowRight'); // Monthly
  await expect(page.locator('input[name="rdd-step"][value="monthly"]')).toBeChecked();
  await tabTo(page, '#rdd-go');
  const [dl] = await Promise.all([page.waitForEvent('download'), page.keyboard.press('Enter')]);
  const { rows } = parseCsv((await import('node:fs')).readFileSync((await dl.path())!, 'utf8'));
  // switching to monthly keeps the chosen years: 1981-01 to 2025-12
  expect(rows.length).toBe(540);
  expect([`${rows[0].year}-${rows[0].month}`, `${rows.at(-1)!.year}-${rows.at(-1)!.month}`]).toEqual(['1981-1', '2025-12']);
  expect(rows.every((r) => r.unit_code === '19')).toBe(true);
});

test('7b. keyboard only: unavailable SPEI GeoTIFF, then an alternative', async ({ page }) => {
  await openDownloader(page, '/data/');
  await page.locator('#rdd-h').evaluate((h) => { h.setAttribute('tabindex', '-1'); (h as HTMLElement).focus(); });
  await tabTo(page, '#rdd-wilaya');
  await page.keyboard.type('19');
  await page.keyboard.press('ArrowDown');
  await page.keyboard.press('Enter');
  await expect(page.locator('#rdd-wilaya')).toHaveValue('19 — Sétif');
  await tabTo(page, 'input[name="rdd-indicator"]');
  await page.keyboard.press('ArrowDown'); // Drought (SPEI)
  await expect(page.locator('input[name="rdd-indicator"][value="spei"]')).toBeChecked();
  await tabTo(page, 'input[name="rdd-format"]');
  await page.keyboard.press('ArrowDown'); // GeoTIFF
  await expect(page.locator('#rdd-result')).toContainText('Not available');
  await tabTo(page, '#rdd-result button');
  await page.keyboard.press('Enter');
  await expect(page.locator('#rdd-go')).toBeVisible();
});

test('8. regional download on a phone @mobile', async ({ page }) => {
  await openDownloader(page, '/regions/19/1901/');
  // preset to this commune
  await expect(page.locator('#rdd-commune')).toHaveValue('Sétif (1901)');
  const { buf } = await download(page);
  const { rows } = parseCsv(buf.toString('utf8'));
  expect(rows).toHaveLength(45);
  expect(rows.every((r) => r.unit_code === '1901' && r.level === 'admin2')).toBe(true);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});

test('8b. homepage regional download on a phone @mobile', async ({ page }) => {
  await openDownloader(page, '/data/');
  await pickFromCombobox(page, '#rdd-wilaya', 'oran', '31');
  await page.getByRole('radio', { name: 'Administrative boundaries' }).check();
  const { buf, name } = await download(page);
  expect(name).toBe('aeo_w31-oran_boundary_2026-11-20.geojson');
  const fc = JSON.parse(buf.toString('utf8'));
  expect(fc.features).toHaveLength(1);
  expect(fc.features[0].properties.wilaya_code).toBe('31');
  expect(fc.metadata.license).toBe('ODbL-1.0');
});

test('catalog Download opens the assistant with the product selected', async ({ page }) => {
  await openDownloader(page, '/data/');
  await page.getByRole('button', { name: /Download Algeria Drought Index SPEI/ }).click();
  await expect(page.locator('input[name="rdd-indicator"][value="spei"]')).toBeChecked();
  await expect(page.locator('#rdd-h')).toBeFocused();
});

test('product pages offer only manifest files (SPEI: no wilaya GeoTIFF)', async ({ page }) => {
  await page.goto('/data/aeo-dza-spei-terraclimate/');
  await page.locator('#all-files summary').click();
  await expect(page.locator('#all-files')).toContainText('no wilaya GeoTIFFs');
  await page.goto('/data/aeo-dza-precipitation-chirps3/');
  await page.locator('#all-files summary').click();
  await expect(page.locator('#all-files')).toContainText('69 wilaya GeoTIFFs');
});
