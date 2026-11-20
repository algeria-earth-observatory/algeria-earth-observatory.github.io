## What does this change?

<!-- One or two sentences. Link the issue it addresses: "Closes #123". -->

## Type

- [ ] New dataset record
- [ ] Correction to an existing record
- [ ] AEO-derived data (files under `public/data/aeo/`)
- [ ] Documentation / guide
- [ ] Website code
- [ ] Other

## Checklist

- [ ] `npm run build` passes locally (schema validation, checksums, internal links).
- [ ] Facts come from official sources listed in `verification.sources_consulted`; nothing is invented.
- [ ] Unknown values are `null` and listed in `verification.unverified_fields`.
- [ ] Status is correct (`external` for provider-held data; `available` only for AEO-distributed files; no downloads on `in-preparation`).
- [ ] Data nature (`observed` / `derived` / `modeled`) and Algeria subset requirement are stated.
- [ ] Licence allows what this change does (listing or redistribution); attribution is correct.
- [ ] For AEO-derived files: processing code, `PROVENANCE.json`, versioned folder, and `npm run checksums` were run.
- [ ] Code in guides was run; software versions are stated.
- [ ] No personal, sensitive or restricted information is included.

## Notes for reviewers

<!-- Anything uncertain, and how you verified it. -->
