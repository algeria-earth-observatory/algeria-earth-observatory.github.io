# Scientific data architecture

## Principles

1. **Metadata first.** The catalog is a set of validated metadata records. Data stay with their producers unless AEO has a reason and the right to redistribute them.
2. **Static and free to run.** Everything is generated at build time and served as static files. No server, database, API key or paid service.
3. **Provenance is enforced, not requested.** Build-time validation rejects records that lack provenance, expose downloads for unreleased products, or whose hosted files do not match their checksums.
4. **Separation of code and data licences.**

## Components

```
                  ┌────────────────────────────────────────────────┐
 Contributors ──► │ GitHub issues (forms) ─► maintainer review     │
                  │ Pull requests ─► CI: validate + build + check  │
                  └───────────────┬────────────────────────────────┘
                                  ▼
 src/content/datasets/*.json ─► Zod schema (src/content.config.ts) ─┐
 src/content/docs/*.md        ─► docs collection                    ├─► Astro static build ─► dist/ ─► GitHub Pages
 src/data/map-layers.ts       ─► map registry (links to records)    │
 src/data/gibs-layers.json    ◄─ scripts/fetch_gibs_layers.py       │
 public/data/aeo/<product>/<version>/ ◄─ scripts/processing/*       ┘
```

### Catalog

- One JSON record per dataset (`docs/METADATA_SCHEMA.md`). Statuses: `available`, `external`, `in-preparation`, `archived`. Origins: `external`, `aeo-derived`, `aeo-original`. Data nature: `observed`, `derived`, `modeled`.
- Pre-build script `scripts/validate-catalog.mjs`: file name = id, unique ids, hosted files exist and match SHA-256 and size, map layer references exist.
- Zod schema: required provenance per status, URL formats, ISO dates, bbox sanity, DOI format.
- Outputs: catalog page with client-side faceted search (no index server), one HTML page per record, `/data/<id>.json`, `/data/<id>.stac.json` (STAC 1.0 Collection), `/catalog.json`, `/stac/catalog.json`, schema.org `Dataset` JSON-LD for search engines.

### Map explorer

- MapLibre GL JS with basemaps from OpenFreeMap (OSM vector tiles, no key) and NASA GIBS (imagery, relief).
- Overlays are provider-rendered raster tiles (NASA GIBS WMTS with a time dimension; JRC GSW tiles) and AEO GeoJSON (wilaya boundaries). Every overlay links to a catalog record; the map page fails to build otherwise.
- Time-enabled layers: available dates are expanded from the GIBS capability periods; requests snap to the nearest available date.
- Analysis is not done in the browser: overlays are for exploration, and users download the data for analysis.

### AEO-distributed data

- Versioned folders `public/data/aeo/<product>/<version>/` with a `PROVENANCE.json` and reproducible code in `scripts/processing/`.
- Size limit in practice: a few MB per file. Larger products go to a DOI-issuing archive and are linked.

## Planned repository split

The brief anticipates five repositories. Version 1 keeps everything in the website repository to reduce maintenance; the split is straightforward because the boundaries are already clean:

| Future repository | Content now located at |
|---|---|
| `algeria-earth-observatory.github.io` | this repository (website) |
| `data-catalog` | `src/content/datasets/`, `src/content.config.ts` schema, `scripts/validate-catalog.mjs`, `scripts/check-links.mjs` |
| `data-processing` | `scripts/processing/`, `scripts/fetch_gibs_layers.py`, `scripts/tutorials/` |
| `datasets` | `public/data/aeo/` (small files + manifests) |
| `community` | `CONTRIBUTING.md`, `GOVERNANCE.md`, `CODE_OF_CONDUCT.md`, issue forms |

When split, the website build would fetch the catalog at a pinned tag of `data-catalog` (git submodule or release artifact) so that every deployed site corresponds to an identifiable catalog version.

## Multilingual preparation

`src/i18n/ui.ts` defines locales (en published; fr, ar prepared), a string dictionary and direction handling (`dir="rtl"` for Arabic in `Base.astro`). Records support `title_fr` and `title_ar`. Astro's i18n routing is configured with English only; adding `fr`/`ar` to `locales` and creating `src/pages/fr/`, `src/pages/ar/` enables them once reviewed translations exist.

## Security and privacy

- No cookies, analytics or third-party scripts other than the map library bundled from npm. Map tiles are requested from their providers by the visitor's browser.
- Popups escape all attribute values before inserting HTML.
- No secrets; GitHub Actions uses the built-in token with least privilege.
