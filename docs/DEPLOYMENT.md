# Deployment and maintenance guide

The site is a static Astro build deployed by GitHub Actions to GitHub Pages at the root of the organisation domain: **https://algeria-earth-observatory.github.io/**.

## 1. One-time setup (organisation owner)

Creating a GitHub organisation cannot be done from the command line; it requires the account owner in a browser.

1. **Create the organisation.** Signed in to GitHub, open https://github.com/organizations/plan, choose the **Free** plan, and set:
   - Organization account name: `algeria-earth-observatory`
   - Display name (Settings → Profile): `Algeria Earth Observatory`
   - Contact email: an address you are willing to make public, or leave the profile email empty.
   - “This organization belongs to: My personal account.”
2. **Create the website repository** inside the organisation: name it exactly `algeria-earth-observatory.github.io`, **Public**, with no README, licence or .gitignore (the local repository already has them).
3. **Create the profile repository**: a public repository named `.github`. Copy `org/.github/profile/README.md` from this project into it as `profile/README.md`. GitHub shows it on the organisation page.
4. **Push the website** from this folder:
   ```bash
   git remote add origin https://github.com/algeria-earth-observatory/algeria-earth-observatory.github.io.git
   git push -u origin main
   ```
5. **Enable Pages from Actions**: repository → Settings → Pages → *Build and deployment* → Source: **GitHub Actions**. The `Build and deploy to GitHub Pages` workflow runs on every push to `main`; re-run it from the Actions tab after changing this setting.
6. **Recommended repository settings**
   - Settings → General → Features: enable **Issues**; optionally **Discussions**.
   - Settings → Code security → enable **Private vulnerability reporting** (used by SECURITY.md) and **Dependabot alerts**.
   - Settings → Branches → add a protection rule for `main`: require a pull request and the `Validate pull request` check before merging (once there is more than one maintainer).
   - Settings → Actions → General → Workflow permissions: **Read repository contents** is sufficient.
   - Create the issue labels used by the templates: `dataset-proposal`, `needs-review`, `metadata`, `enhancement`, `bug`, `collaboration`, `volunteer` (GitHub creates missing labels automatically only for some; creating them avoids warnings).
7. **Verify the live site** (after the first successful deploy):
   - https://algeria-earth-observatory.github.io/ loads, with the hero image.
   - Direct links and refresh work: `/data/`, `/data/speibase/`, `/map/`, `/docs/data-access/`.
   - `/map/` shows the basemap, wilaya boundaries, and an overlay when toggled.
   - A download on `/data/aeo-dza-admin-boundaries/` returns the GeoJSON; its SHA-256 matches the page.
   - `/catalog.json`, `/stac/catalog.json` and `/sitemap-index.xml` return JSON/XML.
   - An unknown path (e.g. `/nope/`) shows the custom 404 page.
   - Run `npm run check:links` locally: the two self-links that failed before deployment (`/docs/boundaries/`, GitHub `build_boundaries.py`) now pass.

## 2. Day-to-day maintenance

| Task | How |
|---|---|
| Add or fix a dataset | Edit `src/content/datasets/<id>.json`, run `npm run build`, open a PR. |
| Broken external link | Weekly link check (Actions → *Weekly external link check*) or user reports. Update the record and `verification.checked`. |
| Refresh NASA GIBS layer metadata (dates, legends) | `python scripts/fetch_gibs_layers.py`, then build. The live map always requests the date the user picks; the JSON only sets defaults and the date picker range. Re-run monthly. |
| New boundary snapshot | `python scripts/processing/build_boundaries.py --version YYYY-MM-DD` (conda env with geopandas; Node for mapshaper), update `BOUNDARY_VERSION` in `src/data/map-layers.ts`, add the new files to the boundary record, `npm run checksums`, build. Keep old version folders. |
| AEO-hosted file changed | `npm run checksums` (only after verifying the file), then build; the build fails if a checksum does not match. |
| Dependency updates | `npm outdated`; update one major version at a time and run `npm run build && npm run check`. Versions are pinned exactly. |
| Mission end / version changes | When a provider retires a product (e.g. Terra MODIS from 1 Dec 2026, CHIRPS v2 after Dec 2026), update `temporal_extent`, `alert` and `limitations`; set `status: "archived"` when a product is no longer distributed. |

## 3. Local development

```bash
npm install
npm run dev          # http://localhost:4321
npm run build        # catalog validation + static build + internal link check
npm run preview      # serve dist/
npm run check        # TypeScript/Astro diagnostics
```

On Windows without a global Node.js, a portable Node 22 can be put on `PATH` for the session.

## 4. Hosting constraints

GitHub Pages serves static files only (soft limits: 1 GB site, 100 GB/month bandwidth; files over 100 MB are rejected by git). Keep AEO-hosted files small (a few MB). Large AEO products should be archived in a DOI-issuing repository (for example Zenodo, which accepts up to 50 GB per record) and linked from the record with checksums, or distributed as Cloud Optimized GeoTIFFs/PMTiles from an object store once a sustainable host exists. No server-side processing is possible or expected.

## 5. If the organisation name changes

Update `site` in `astro.config.mjs`, `SITE.url` and `SITE.github` in `src/config/site.ts`, `public/robots.txt`, the boundary record's `code_url`/`documentation_url`, and URLs in tutorials. Search the repository for `algeria-earth-observatory`.
