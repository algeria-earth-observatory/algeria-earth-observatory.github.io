import { defineConfig } from '@playwright/test';

// End-to-end tests of the built site (run `npm run build` first).
// Locally they use the installed Microsoft Edge; in CI, Playwright's Chromium.
const CI = !!process.env.CI;

export default defineConfig({
  testDir: 'tests/e2e',
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: true,
  workers: CI ? 2 : 3,
  retries: CI ? 1 : 0,
  reporter: CI ? [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]] : 'list',
  use: {
    baseURL: 'http://127.0.0.1:4321',
    acceptDownloads: true,
    channel: CI ? undefined : 'msedge',
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'desktop', use: { viewport: { width: 1440, height: 1000 } }, grepInvert: /@mobile/ },
    { name: 'mobile', use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true }, grep: /@mobile/ },
  ],
  webServer: {
    command: 'npx astro preview --port 4321 --host 127.0.0.1',
    url: 'http://127.0.0.1:4321',
    reuseExistingServer: !CI,
    timeout: 120_000,
  },
});
