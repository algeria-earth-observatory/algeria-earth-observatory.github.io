# Usability, accessibility and regional download audit — 2026-11-20

**Scope:** homepage, Data catalog, Explore, Analyze, Regions, wilaya and commune profiles, product pages.

**Method**
- Measured in Microsoft Edge (Chromium) at 1440 × 1000 and at 390 × 844 (mobile), before and after the changes, with the same audit script (`report.json` in each screenshot folder).
- Accessibility rules: axe-core with the WCAG 2.2 AA tag set.
- Keyboard: tab-order walks through each page.
- Downloads: every download path was checked against the product manifests.

**Screenshots** (git-ignored, kept with the working data):
- `data-work/screenshots/usability-before/`
- `data-work/screenshots/usability-after/`

## Issues found

| # | Severity | Where | Issue | Resolution |
|---|---|---|---|---|
| 1 | Critical | SPEI product page | The download builder offered only precipitation variables and downloaded **precipitation data** from the SPEI page. | Replaced by `RegionDataDownloader`, which resolves every option from the SPEI manifest. |
| 2 | Critical | All product pages | “This selection (CSV)” was rebuilt from the website JSON files, so anomalies were recomputed and values could be rounded. It was not taken from the published tables and not checked against their checksums. | Extracts now read the published Parquet table, or a verified partition of it. The SHA-256 is checked in the browser before extraction, and values are copied, never recomputed. |
| 3 | High | Whole site | No place-first route: data for a wilaya or commune meant finding the product, then scrolling to a builder at the bottom of the page. | The download assistant is on the homepage, Data catalog, product pages, wilaya and commune profiles, and Analyze. |
| 4 | High | Download builder | Wilayas and communes were plain selects. They could not be searched, did not match names without accents or in Arabic, and the commune list held up to 50 entries. | ARIA 1.2 combobox: search by name, code or Arabic name, ignoring accents; communes limited to the selected wilaya; values are ONS codes. |
| 5 | High | Commune data | Commune monthly tables exist only as single Parquet files of 2.9 MB (precipitation) and 13.7 MB (SPEI) with no page index. Extracting one commune meant downloading most of the file (11.9 MB measured for SPEI). | Per-wilaya partitions (`scripts/pipelines/partition_regional.py`), identical rows verified by tests. One commune now reads its wilaya's partition: 8–157 kB for precipitation (median 45 kB) and 54–718 kB for SPEI (median 290 kB). |
| 6 | High | Product pages | File-availability text was generic. The SPEI page said “0 wilaya GeoTIFFs are listed in the manifest and offered in the builder above”. | The inventory sentence is computed from the manifest: “no wilaya GeoTIFFs”. The downloader explains why, and lists the alternatives that exist. |
| 7 | High | Commune selections | Nothing explained that commune GeoTIFFs do not exist. | GeoTIFF for a commune shows “Not available” with the reason, plus two alternatives: the wilaya file containing the commune, and the commune statistics. |
| 8 | Medium | Wilaya profiles | A 25.7 MB national commune boundary file was linked without a size or a warning. | Replaced by the single-wilaya or single-commune boundary extract, with full files labelled with their size. |
| 9 | Medium | All pages | 231 text elements were smaller than 12 px (down to 10 px). | 0 now. Minimum size is 12 px; labels and notes are 13–15 px; body text is 16 px. |
| 10 | Medium | All pages | 116 all-uppercase technical labels (mono, small, letter-spaced). | 17 left: one page eyebrow per page, a deliberate identity element. Labels and table headers are now sentence case. |
| 11 | Medium | All pages | 96 interactive targets were smaller than 24 × 24 px (WCAG 2.5.8): links, summaries, sliders, chart export buttons. | 39 left, almost all MapLibre attribution links (see “Remaining”). |
| 12 | Medium | Explore | 5 radio inputs without labels (the hidden basemap radios). | Labelled and removed from the tab order. |
| 13 | Medium | Analyze | The whole visualization column was an `aria-live` region, so screen readers re-read charts and tables after every change. | A single status message announces “Updated: …”. Tabs use the ARIA tab pattern. |
| 14 | Medium | Explore (mobile) | Region selection existed only inside the layer drawer. | A region selector sits above the map on mobile, next to the Layers button. |
| 15 | Medium | Homepage (mobile) | The product table needed horizontal scrolling (minimum width 46 rem). Screen-reader-only text escaped its scroll box and widened the page by 248 px during this work. | Products are a stacked list on mobile. Scroll containers are positioned, and a test checks that no page scrolls horizontally. |
| 16 | Medium | Data catalog | Planned and available products were mixed in one list. Each Download link left the page. | Separate “Available now” and “Planned” sections. Download opens the assistant on the same page with the product selected. |
| 17 | Medium | Homepage map | The map was the only way to choose a wilaya, and its values had no text equivalent. | Added a wilaya select and a table of all 69 values. |
| 18 | Low | Explore | The map scale label was 10 px. | 12 px. |

No broken internal links: the build checks every internal link and every file listed in a manifest.

## Results (same audit script, 18 page × viewport combinations)

| Measure | Before | After |
|---|---|---|
| Text smaller than 12 px | 231 | 0 |
| All-uppercase labels | 116 | 17 (page eyebrows) |
| Targets smaller than 24 px | 96 | 39 |
| Form fields without a label | 10 | 0 |
| Horizontal page scroll | 0 px | 0 px |
| Focus not visible (first 25 tab stops) | 0 | 0 |
| axe-core WCAG 2.2 AA violations | 0 | 0 (11 pages × 2 viewports, plus the download assistant states) |

## Automated tests added

- **`tests/js/region-download.test.mjs`** (13 tests). Checks resolution and extraction against the real published files:
  - every extract equals the published table, value by value;
  - partitions whose source SHA-256 differs are rejected;
  - files that fail their SHA-256 are refused;
  - every proposed alternative resolves.
- **`tests/python/test_partitions.py`**. Checks that the partitions reproduce their sources row by row and feature by feature.
- **`tests/e2e/downloads.spec.ts`** (Playwright). Covers the eight journeys in the brief:
  1. Sétif annual precipitation;
  2. a commune's monthly precipitation;
  3. the wilaya precipitation GeoTIFF, with its SHA-256 compared to the manifest;
  4. wilaya SPEI;
  5. the unavailable SPEI wilaya GeoTIFF, with its explanation and alternatives;
  6. switching between map and time series without losing the selection, plus the filtered table;
  7. the same workflows by keyboard only;
  8. regional download on a phone.

  It also covers the catalog's Download action and the manifest-derived inventories. Every test opens the downloaded file and checks identifiers, periods, variables and file type.
- **`tests/e2e/a11y.spec.ts`**:
  - axe-core on 11 pages at desktop and mobile widths, and on the assistant with the combobox open and in the unavailable state;
  - visible focus;
  - reduced motion;
  - no horizontal scroll on mobile.
- **CI.** `deploy.yml` now runs the Playwright suite on the built site. The site is deployed only if every journey passes.

## Remaining limitations

- **No manual screen-reader test yet.** I checked the ARIA structure with axe-core and the keyboard tests, but no test with NVDA, JAWS, VoiceOver or TalkBack has been done. Automated checks do not replace this. Before calling the site WCAG 2.2 AA conformant, test the download assistant combobox, the Analyze tabs and the status messages with at least NVDA + Firefox and VoiceOver + Safari (iOS).
- **Map attribution links** are MapLibre controls about 12 px high. They are the main remaining targets under 24 px.
- **No on-demand raster clipping.** Commune GeoTIFFs are not offered. Spatial grids exist for Algeria (both products) and per wilaya (precipitation only), as listed in the manifests.
- **Extracts are CSV only.** Parquet and GeoTIFF are offered as the published full files, labelled as full tables.
- **French and Arabic interfaces** are not yet available.
