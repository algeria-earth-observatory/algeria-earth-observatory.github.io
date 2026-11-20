# Governance

Algeria Earth Observatory (AEO) is an independent, open, non-commercial scientific initiative in its initial development phase. It is not a government body, is not officially registered or nationally mandated, and is not affiliated with or endorsed by any institution.

This document describes a deliberately simple model suited to the current stage. It will be revised as the community grows.

## Roles

**Founding maintainer.** Sets overall project direction, has final responsibility for what is published, and appoints maintainers. Currently: Walid Ouaret (GitHub `ouaretw`).

**Maintainers.** Review and merge contributions, maintain the catalog and infrastructure, and apply the review checklist. Maintainers are named in `src/config/site.ts` and on the Community page **only after they have accepted the role**.

**Scientific advisers.** May be invited to advise on specific domains (for example agriculture, hydrology, climate). Named publicly only after accepting.

**Contributors.** Anyone who proposes a dataset, reports an error, reviews, writes documentation or contributes code. Contributors are credited in the relevant change and, with their consent, on the Community page.

## How decisions are made

1. Proposals are made in public as GitHub issues or pull requests.
2. A maintainer reviews against three criteria:
   - **Scientific documentation** — authentic source, correct citation, documented definitions, resolution, period, validation and limitations;
   - **Legal sharing conditions** — the licence permits listing or redistribution, attribution is correct, no restricted or sensitive data;
   - **Technical compatibility** — the record validates, links work, formats and CRS are stated, code is reproducible.
3. Changes are merged when a maintainer approves them. Substantial changes to scope, governance or licensing are decided by the founding maintainer after public discussion on an issue.
4. Disagreements are discussed openly on the issue; the founding maintainer decides if consensus is not reached and records the reasoning.

## Publication rules

- Nothing submitted by users is published automatically.
- Datasets are labelled by status: Available, External source, In preparation, Archived. In-preparation products never expose downloads.
- AEO-derived or original products are released only with documented methods, input and output versions, reproducible code and, where applicable, validation.
- Unverified information is marked as such or left out.

## Conflicts of interest

Maintainers and reviewers declare relevant interests (for example authorship of a dataset under review, or a funding relationship) on the issue and do not approve contributions in which they have a direct stake. Any financial or in-kind support will be listed publicly on the Support page with its source and purpose, and support does not confer editorial control.

## Code of conduct

All participation is subject to the [Code of Conduct](CODE_OF_CONDUCT.md).

## Changes to this document

Proposed through a pull request and discussed publicly before adoption.
