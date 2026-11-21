import { expect, type Page, type Download } from '@playwright/test';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

export const PUBLIC = join(process.cwd(), 'public');
export const manifest = (product: 'precipitation' | 'spei') =>
  JSON.parse(readFileSync(join(PUBLIC, 'data/aeo/products', product, 'v1.0.0/manifest.json'), 'utf8'));

/** Open a page and wait until the download assistant has loaded its sources. */
export async function openDownloader(page: Page, path: string) {
  await page.goto(path);
  await expect(page.locator('#rdd-loading')).toBeHidden();
  await expect(page.locator('#rdd-form')).not.toHaveAttribute('aria-busy', 'true');
}

export async function pickFromCombobox(page: Page, input: string, query: string, code: string) {
  const box = page.locator(input);
  await box.click();
  await box.fill(query);
  const opt = page.locator(`${input}-list li[data-value="${code}"]`);
  await expect(opt).toBeVisible();
  await opt.click();
  await expect(box).toHaveAttribute('aria-expanded', 'false');
}

export async function setPeriod(page: Page, from: string, to: string) {
  await page.selectOption('#rdd-from-y', from.slice(0, 4));
  if (from.length > 4) await page.selectOption('#rdd-from-m', from.slice(5, 7));
  await page.selectOption('#rdd-to-y', to.slice(0, 4));
  if (to.length > 4) await page.selectOption('#rdd-to-m', to.slice(5, 7));
}

/** Click the resolved Download action and return the downloaded file. */
export async function download(page: Page): Promise<{ dl: Download; buf: Buffer; name: string }> {
  const go = page.locator('#rdd-go');
  await expect(go).toBeVisible();
  const [dl] = await Promise.all([page.waitForEvent('download'), go.click()]);
  const path = await dl.path();
  return { dl, buf: readFileSync(path!), name: dl.suggestedFilename() };
}

export function parseCsv(text: string) {
  const [head, ...rows] = text.trim().split(/\r?\n/);
  const cols = head.split(',');
  return { cols, rows: rows.map((l) => Object.fromEntries(splitCsvLine(l).map((v, i) => [cols[i], v]))) };
}
function splitCsvLine(line: string) {
  const out: string[] = []; let cur = '', q = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (q) { if (ch === '"' && line[i + 1] === '"') { cur += '"'; i++; } else if (ch === '"') q = false; else cur += ch; }
    else if (ch === '"') q = true; else if (ch === ',') { out.push(cur); cur = ''; } else cur += ch;
  }
  out.push(cur);
  return out;
}

export const sha256 = (b: Buffer) => createHash('sha256').update(b).digest('hex');

export function publishedRows(href: string, unit: string) {
  return parseCsv(readFileSync(join(PUBLIC, href), 'utf8')).rows.filter((r) => r.unit_code === unit);
}

/** Press Tab until the focused element matches the selector (keyboard-only navigation). */
export async function tabTo(page: Page, selector: string, max = 60) {
  for (let i = 0; i < max; i++) {
    await page.keyboard.press('Tab');
    if (await page.evaluate((s) => document.activeElement?.matches(s) ?? false, selector)) return;
  }
  throw new Error(`Tab never reached ${selector}`);
}
