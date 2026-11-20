// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import tailwindcss from '@tailwindcss/vite';

// Deployed at the root of the GitHub Pages organisation domain.
export default defineConfig({
  site: 'https://algeria-earth-observatory.github.io',
  base: '/',
  trailingSlash: 'ignore',
  build: { format: 'directory' },
  integrations: [sitemap()],
  markdown: { shikiConfig: { theme: 'github-dark-high-contrast' } },
  // English is live. French and Arabic are prepared (see src/i18n) but not
  // routed until complete, reviewed translations exist.
  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
    routing: { prefixDefaultLocale: false },
  },
  // Cast: @tailwindcss/vite is typed against a newer Vite than Astro 5 bundles (type-only mismatch).
  vite: { plugins: [/** @type {any} */ (tailwindcss())] },
});
