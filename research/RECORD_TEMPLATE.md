# AEO dataset record format (v1)

One JSON file per dataset at `src/content/datasets/<id>.json`. The file name (without `.json`) is the `id`.
All fields below are required unless marked optional. Use `null` (not empty strings) for unknown optional values.

```jsonc
{
  "id": "esa-worldcover",                 // kebab-case, persistent; must equal file name
  "title": "ESA WorldCover 10 m Land Cover",
  "description": "1–3 sentence neutral scientific description of what the product is.",
  "purpose": "1–3 sentences: why it is useful for Algeria-focused work (no hype).",
  "domain": ["land-ecosystems"],          // 1+ of: agriculture, climate-drought, water, land-ecosystems, hazards, human-change (primary first)
  "categories": ["Land-cover maps"],      // free text sub-categories from the AEO brief
  "keywords": ["land cover", "Sentinel-1", "Sentinel-2"],
  "status": "external",                   // external | available | in-preparation | archived
  "origin": "external",                   // external | aeo-derived | aeo-original
  "data_nature": "derived",               // observed (direct measurement / imagery) | derived (algorithmic product from observations, incl. classifications & satellite-gauge blends) | modeled (reanalysis, model output, projections)
  "data_type": "raster",                  // raster | vector | tabular | imagery | point
  "provider": { "name": "European Space Agency (ESA)", "url": "https://..." },
  "creator": "WorldCover consortium led by VITO",  // dataset creator / processing team as credited by the source
  "source_url": "https://...",            // official landing page (verified HTTP 200 or reachable)
  "documentation_url": "https://..." ,     // product user guide / ATBD / data paper (or null)
  "license": { "name": "Creative Commons Attribution 4.0 International", "spdx": "CC-BY-4.0", "url": "https://creativecommons.org/licenses/by/4.0/" },
  "license_notes": "Attribution wording required by the provider, if any (or null)",
  "citation": "Full recommended dataset citation exactly as the provider asks (authors, year, title, version, publisher, DOI).",
  "doi": "10.5281/zenodo.7254221",        // dataset DOI without https://doi.org/ prefix, or null
  "references": [                         // peer-reviewed / technical references (can be empty)
    { "citation": "Zanaga, D. et al. (2022) ...", "doi": "10.5281/...", "url": null }
  ],
  "spatial_extent": {
    "coverage": "global",                 // global | continental | regional | algeria
    "description": "Global land surface. Algeria is covered; users must select tiles/subset Algeria themselves.",
    "algeria_subset": "extract",          // extract (user must clip) | country-file (provider offers an Algeria file) | native (Algeria-only product)
    "bbox": [-180, -60, 180, 82.75]       // [west, south, east, north] in WGS84 of the product as distributed
  },
  "temporal_extent": {
    "start": "2021-01-01",                // ISO date (YYYY-MM-DD) or null
    "end": "2021-12-31",                  // ISO date or null if ongoing
    "ongoing": false,
    "frequency": "single epoch",          // e.g. daily, 8-day, 16-day, monthly, annual, single epoch, irregular
    "description": "Reference year 2021 (v200); a 2020 map (v100) also exists."
  },
  "resolution": { "spatial": "10 m", "spatial_m": 10, "temporal": "single epoch" },  // spatial_m numeric approx (degrees → metres at equator, e.g. 0.05° ≈ 5566), or null for tabular
  "format": ["GeoTIFF (Cloud Optimized)"],
  "crs": "EPSG:4326 (WGS 84)",
  "variables": [ { "name": "Map", "units": "class code", "description": "11 land-cover classes (FAO LCCS-based legend)" } ],
  "processing": "2–4 sentences on how the provider produced it (inputs, algorithm), from official docs.",
  "validation": "Reported validation from official docs WITH source, e.g. 'The v200 product validation report states a global overall accuracy of 76.7%.' or null if none stated. NEVER invent numbers.",
  "limitations": ["Concrete scientific limitation 1", "Algeria-specific caveat (e.g. dryland confusion of fallow vs bare)"],
  "version": "v200",
  "published_date": "2022-10-28",         // first publication of this version (ISO) or null if unknown
  "updated_date": "2022-10-28",           // last update by provider (ISO) or null
  "download_url": null,                   // a single direct-download URL ONLY if verified to be a real file (else null)
  "preview_url": null,                    // leave null (AEO fills map previews)
  "access": [                             // every verified access route
    { "label": "Access at source", "url": "https://...", "kind": "external", "format": "GeoTIFF", "requires_login": false, "notes": "Tiles downloadable via web viewer or AWS S3" }
  ],                                      // kind: external (landing/portal) | download (direct file) | api | viewer
  "code_url": null,                       // provider processing / example code repo if any
  "algeria_notes": "1–3 sentences on Algeria-specific relevance or caveats (definitions, drylands, Sahara, fallow).",
  "verification": {
    "checked": "2026-11-19",
    "urls_checked": true,                 // true only if you actually fetched the URLs
    "unverified_fields": [],              // names of fields you could NOT confirm from an official source
    "sources_consulted": ["https://..."], // official pages you read
    "notes": "Anything a reviewer should know"
  }
}
```

Rules
- Only facts confirmed from official provider pages, data papers or DOI landing pages. If not confirmable, set null/omit and list the field in `verification.unverified_fields`.
- Never fabricate accuracy numbers, file sizes, DOIs or dates.
- Keep descriptions neutral, precise, short. No marketing language.
- Global datasets: say clearly that Algeria must be subset by the user.
