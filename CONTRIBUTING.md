# Contributing to Algeria Earth Observatory

Thank you for helping build an open, well-documented resource for Algeria's environmental data. Contributions of every kind are welcome — you do not need to program.

## Ways to contribute

| You want to… | Do this |
|---|---|
| Propose a dataset | Open a [dataset proposal](../../issues/new?template=dataset-proposal.yml) |
| Report a broken link or wrong metadata | Use the link at the bottom of the dataset page, or open a [metadata error report](../../issues/new?template=metadata-error.yml) |
| Suggest an improvement | [Feature request](../../issues/new?template=feature-request.yml) |
| Report a website bug | [Bug report](../../issues/new?template=bug-report.yml) |
| Propose a scientific collaboration | [Collaboration proposal](../../issues/new?template=collaboration.yml) |
| Volunteer as reviewer or maintainer | [Volunteer form](../../issues/new?template=volunteer.yml) |
| Fix text, a guide or code | Open a pull request (below) |

### If you have never used GitHub

1. Create a free account at https://github.com/signup.
2. Open one of the forms above. Fill in the fields and click **Create**.
3. Maintainers answer on the issue page; GitHub notifies you by email.

That is enough to propose datasets, report errors and volunteer. Maintainers turn accepted proposals into catalog records and credit you.

## Never post sensitive information

Issues and pull requests are public. Do not include personal data, farmers' or respondents' names, exact field or survey locations, unpublished or restricted data, security-sensitive geospatial data, or anything you are not authorised to share. Describe such material in general terms and ask for a private channel. AEO does not accept restricted data through public submissions, and submitted files are never published automatically.

## Contributing a dataset record (pull request)

1. Fork the repository and create a branch: `git checkout -b dataset/<id>`.
2. Add `src/content/datasets/<id>.json`. Start from a similar record. Key rules:
   - Use only facts from official sources (provider pages, user guides, data papers, DOI landing pages). List the pages in `verification.sources_consulted`.
   - Never invent accuracy figures, DOIs, dates or file sizes. Unknown → `null`, and list the field in `verification.unverified_fields`.
   - Use `status: "external"` for data held by providers; label actions “Access at source”. `available` is only for files AEO distributes.
   - State clearly whether users must extract the Algeria subset (`spatial_extent.algeria_subset`).
   - Label the data nature honestly: `observed`, `derived` or `modeled`.
   - Include Algeria-specific notes and real scientific limitations.
3. Run `npm install` then `npm run build`. Fix any schema errors reported.
4. Optionally run `npm run check:links`.
5. Open a pull request and complete the template.

## Contributing AEO-derived data

Derived files (for example a dataset clipped or aggregated for Algeria) must:

- be permitted by the input licence (some licences, such as HydroSHEDS v1, forbid redistribution);
- be small enough for the repository (a few MB); larger files go to a DOI-issuing archive (for example Zenodo) and are linked;
- come with reproducible code in `scripts/processing/`, a versioned folder under `public/data/aeo/<product>/<version>/`, a `PROVENANCE.json`, and SHA-256 checksums (`npm run checksums`);
- document the clipping boundary, processing steps, input version and output version.

## Contributing documentation

Guides live in `src/content/docs/*.md` with front matter (`title`, `description`, `section`, `order`, `updated`). Code in guides must be run before submission; say which software versions you used.

## Translations

The site is English-first and prepared for French and Arabic (`src/i18n/ui.ts`). Translations are published only when complete and reviewed by a fluent speaker with subject knowledge; partial or machine translations are not merged. Arabic pages render right-to-left.

## Development notes

- Node.js ≥ 20.3. `npm run dev` for live reload.
- Pages are in `src/pages/`; components in `src/components/`; client scripts in `src/scripts/`.
- Keep JavaScript small; use static rendering wherever possible.
- Accessibility: semantic HTML, labelled controls, visible focus, keyboard operation, sufficient contrast.

## Review

Maintainers review scientific documentation, licence and sharing conditions, and technical compatibility using [docs/DATASET_REVIEW_CHECKLIST.md](docs/DATASET_REVIEW_CHECKLIST.md). See [GOVERNANCE.md](GOVERNANCE.md).

By contributing you agree that your code contributions are licensed under the MIT License and your text contributions under CC BY 4.0.
