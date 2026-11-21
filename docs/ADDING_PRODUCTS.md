# Adding an Algeria-ready product

This guide is for contributors adding a new derived product (temperature, SPI, NDVI anomalies, cropland area and so on). Every product follows the pattern set by the reference product **Algeria Precipitation (CHIRPS v3.0)** (`scripts/pipelines/precip/`). Copy that folder and adapt it.

## 1. Before writing code

- Check the source: licence (must allow redistribution of derived files), version, DOI, citation, resolution and period. Record them in `research/` and, if new, add a source record in `src/content/datasets/` with status `external`.
- Decide the **administrative levels** the source resolution supports:
  - admin 0 (Algeria) and admin 1 (wilayas) are almost always defensible;
  - admin 2 (communes) only if the method states what a commune value means. Use the support classes from `aeo.stats` (effective cells), as precipitation does.
- Write the method page first (`src/content/docs/method-<product>.md`): definitions, reference period, formulas, aggregation (intensive → weighted mean; extensive → area-weighted sum), missing-data rules and limitations.

## 2. Pipeline layout

```
scripts/pipelines/<product>/
  fetch_<source>.py   # step 1: retrieve the Algeria subset, record source URLs, dates, checksums (data-work/, not committed)
  build_<product>.py  # steps 2-8: QC, indicator, zonal statistics, exports, manifest, PROVENANCE
  make_record.py      # step 9: write the catalog record from the manifest
scripts/pipelines/aeo/stats.py   # shared: Grid, sparse_coverage, ZonalWeights, theil_sen, mann_kendall
```

Rules:
- **Boundaries:** use one boundary version (`public/data/aeo/boundaries/<version>/`) and record it in the manifest. Build wilaya and national weights with `ZonalWeights.merge` from commune weights, so the levels nest.
- **Areas:** compute areas geodesically or in an equal-area projection (`Grid.cell_area_km2`, LAEA), never from raw pixel counts in degrees.
- **Missing data:** never fill gaps silently. Report the valid-area share and drop incomplete periods.
- **Outputs** go to `public/data/aeo/products/<name>/v<semver>/`:
  - `raster/`: COGs for Algeria and for each wilaya, only where meaningful;
  - `tables/`: CSV and Parquet;
  - `web/`: compact JSON for the site;
  - `map/`: display images or tiles;
  - `manifest.json` and `PROVENANCE.json`.
- **Size:** keep the total for one product version below about 100 MB in the repository, and no single file above 50 MB. Larger national rasters go to external object storage or a GitHub Release, and the manifest points there (with size and SHA-256).

## 3. Manifest (validated at build)

`scripts/validate-catalog.mjs` checks, for every record with a `product` block:
- required fields are present and contain no `VERIFY` placeholders;
- `product_id` equals the record id, and status, version, boundary version and levels match the record;
- every `download_assets[]` entry exists under `public/`, with the recorded size and SHA-256;
- record downloads under the product folder are listed in the manifest.

Use semantic versions:
- patch: same method, data appended;
- minor: new outputs;
- major: method or source change.

Never overwrite a published version folder. Add a new one and keep the old one listed. Add an entry to `CHANGELOG.md`.

## 4. Tests

Add `tests/python/test_<product>.py` (see `test_precip_product.py`). It should cover:
- coverage of every cell inside Algeria;
- CRS, resolution and no-data;
- temporal completeness;
- units and value ranges;
- aggregation consistency (national vs wilaya; annual vs monthly where relevant);
- checksums.

Synthetic data may be used in unit tests only, and must be labelled as such.

Run:

```
python -m pytest tests/python -q
node --test tests/js/*.test.mjs
npm run build
```

## 5. Website

- **Catalog record** (from `make_record.py`): `origin: "aeo-derived"`, the `product` block, `map_layers`, and status `available`, `experimental` or `under-validation`. The status must be honest: `available` only after the method page and the tests exist.
- **Map:** add layers to `src/data/map-layers.ts`.
- **Analyze:** add the variable to the variable list only when the web JSON exists. The UI must never list a variable without data.
- **Regions:** add the indicator to `src/lib/regions-data.ts` and the profile pages.
- **Regional downloads** (`RegionDataDownloader`):
  - Add the product's plain-language name to `PLAIN` in `src/lib/region-download.js`. Formats, levels, periods and files are then read from the manifest.
  - Publish one Parquet statistics table per level and time step, named `*_{annual|monthly}_{level}_*.parquet`, with the columns `level`, `unit_code`, `parent_code`, `year` (and `month`).
  - If a commune-level table is larger than 1.5 MB, run `python scripts/pipelines/partition_regional.py` after the build (add the table to `TABLES` there).
    - The script writes per-wilaya partitions and an index that records the source file's SHA-256.
    - The site uses a partition only if that SHA-256 equals the manifest's. `validate-catalog.mjs` and `tests/python/test_partitions.py` fail if a source changes without re-partitioning.
  - Extend `tests/js/region-download.test.mjs` and `tests/e2e/downloads.spec.ts` with a journey for the new product.

## 6. Review checklist

Use `docs/DATASET_REVIEW_CHECKLIST.md`, plus:
- [ ] method page complete, with limitations;
- [ ] commune-level output justified, or not published;
- [ ] all tests pass, and the build validates the manifest;
- [ ] numbers shown on the website are read from the published files, never typed by hand.
