# Dataset review checklist

Used by maintainers before merging a new or changed dataset record. Copy into the pull request review and tick each item.

## Authenticity and provenance

- [ ] The source is the original producer or its official distributor (not a third-party mirror).
- [ ] Title, version, producer and dates match the provider's pages.
- [ ] Citation is the one the provider requests; DOI resolves (check with `https://doi.org/api/handles/<doi>` if the publisher blocks bots).
- [ ] `verification.sources_consulted` lists the pages actually used; `unverified_fields` lists anything not confirmed.
- [ ] No invented accuracy figures, file sizes, dates or DOIs. Reported validation numbers name their source.

## Scientific description

- [ ] `data_nature` is correct (observed / derived / modeled). Reanalyses, projections and gridded population are modeled.
- [ ] Spatial coverage and `algeria_subset` are honest: global products are not presented as Algeria-specific.
- [ ] Resolution, temporal extent and frequency are correct; ongoing products are marked `ongoing`.
- [ ] Definitions that affect comparison are stated (e.g. what counts as cropland).
- [ ] Limitations include at least one Algeria-relevant point (drylands, Sahara, gauge density, fallow, topography) where applicable.
- [ ] Known provider issues (bugs, mission ends, version changes) appear in `limitations` and, if serious, in `alert`.

## Licence and sharing

- [ ] Licence name and URL come from the provider. If none is stated, the record says “Not stated by provider”.
- [ ] Attribution requirements are recorded in `license_notes`.
- [ ] If AEO hosts files: the licence allows redistribution; output licence is compatible (e.g. ODbL share-alike).
- [ ] No personal, sensitive, restricted or security-sensitive data.

## Access

- [ ] Every access link was opened; login requirements are flagged.
- [ ] `status` is correct: `external` for provider-held data; `available` only for AEO-distributed files; no downloads for `in-preparation`.
- [ ] Download buttons point to real files (direct-download URLs tested with a HEAD request).

## AEO-derived products (additionally)

- [ ] Processing code in `scripts/processing/` runs from documented inputs.
- [ ] Versioned output folder with `PROVENANCE.json` (inputs and versions, clipping boundary, steps, fixes).
- [ ] `npm run checksums` run after verifying outputs; checksums shown on the page.
- [ ] Validation or quality checks documented; uncertainty stated.

## Technical

- [ ] `npm run build` passes (schema, checksums, internal links).
- [ ] `npm run check` passes.
- [ ] Map layers referenced in `map_layers` exist and display correctly.
