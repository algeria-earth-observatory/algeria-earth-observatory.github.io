---
title: Metadata schema
description: The fields every AEO catalog record contains, the status rules enforced at build time, and the JSON and STAC exports.
section: Scientific practice
order: 80
updated: 2026-11-19
---

Each dataset is described by one JSON file in the website repository (`src/content/datasets/<id>.json`). Records are validated on every build; an invalid record stops the build with a message naming the field.

## Core fields

| Field | Content |
|---|---|
| `id` | Persistent identifier (kebab-case). Equals the file name and never changes after publication. |
| `title`, `title_fr`, `title_ar` | Title; French and Arabic titles are optional and prepare multilingual search. |
| `description`, `purpose` | What the dataset is; why it is useful for Algeria. |
| `domain`, `categories`, `keywords` | One or more of: agriculture, climate-drought, water, land-ecosystems, hazards, human-change, reference. |
| `status` | `available` · `external` · `in-preparation` · `archived` |
| `origin` | `external` · `aeo-derived` · `aeo-original` |
| `data_nature` | `observed` · `derived` · `modeled` |
| `data_type` | `raster` · `vector` · `tabular` · `imagery` · `point` |
| `provider`, `creator` | Organisation distributing the data; team credited by the source. |
| `source_url`, `documentation_url` | Official landing page; user guide or data paper. |
| `license`, `license_notes` | Licence name, SPDX identifier and URL; attribution requirements. |
| `citation`, `doi`, `references` | Recommended citation as requested by the provider; dataset DOI; reference papers. |
| `spatial_extent` | `coverage` (global/continental/regional/algeria), `algeria_subset` (extract/country-file/native), `bbox`. |
| `temporal_extent` | `start`, `end`, `ongoing`, `frequency`. |
| `resolution` | Spatial (text and approximate metres) and temporal resolution. |
| `format`, `crs`, `variables` | File formats, coordinate reference system, variables with units. |
| `processing`, `validation`, `limitations` | Production method; reported validation (never invented); scientific limitations. |
| `version`, `published_date`, `updated_date` | Version and dates from the provider. |
| `download_url`, `preview_url`, `access` | Access routes, each with `kind` (download/external/api/viewer), login requirement, and for AEO-hosted files `size_bytes` and `sha256`. |
| `code_url` | Processing code (required for AEO-derived products). |
| `algeria_notes` | Algeria-specific relevance and caveats. |
| `map_layers` | Map explorer layers that preview the dataset. |
| `verification` | Date checked, whether URLs were tested, fields that could not be confirmed, sources consulted. |

## Rules enforced at build time

- `in-preparation` records cannot contain any download link.
- `external`, `available` and `archived` records must have provider, source URL, licence, citation, extents, resolution, formats, CRS (except tabular data) and at least one access route.
- `available` is reserved for files distributed by AEO and requires a direct download; every AEO-hosted file must exist and match its recorded SHA-256 checksum and size.
- AEO-derived products must link to their processing code.
- Map layers named in a record must exist in the map registry, and every map overlay must link to an existing record.

## Machine-readable exports

- Full catalog: [`/catalog.json`](/catalog.json)
- One record: `/data/<id>.json`
- STAC 1.0 Collection per published record: `/data/<id>.stac.json`, linked from the static root catalog [`/stac/catalog.json`](/stac/catalog.json).

The STAC files are static metadata. They do not imply a STAC API, and assets of external datasets point to their providers.
