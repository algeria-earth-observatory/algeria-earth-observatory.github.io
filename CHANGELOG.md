# Changelog

All notable changes to the Algeria Earth Observatory website and its data products. Product versions follow semantic versioning: patch = same method with more data; minor = new outputs; major = changed method or source.

## 2026-11-20

### Added
- **Algeria Precipitation (CHIRPS v3.0)**, product `aeo-dza-precipitation-chirps3` **v1.0.0**:
  - monthly and annual precipitation, 1991–2020 normals, anomalies and trends;
  - COGs for Algeria and each wilaya; CSV and Parquet statistics for 1 country, 69 wilayas and 1,541 communes;
  - manifest with SHA-256, provenance, method page and QA tests.
- **Administrative boundaries v2026-11-20**: 1,541 communes (ONS codes, French and Arabic names) nested in 69 wilayas, checked against Loi n° 26-06. Version 2026-11-19 is kept.
- **Analyze** page: area selection and comparison, seasonal aggregation, anomalies, Theil–Sen and Mann–Kendall trends, choropleth map, CSV, SVG and PNG exports.
- **Regions**: profiles for every wilaya and commune.
- Map layers: commune boundaries; annual precipitation and anomaly with a year slider; GACED30 cropland year slider (2000–2024); ESA WorldCover 2020 and 2021.
- Catalog: Algeria-ready product section, product manifests validated at build, download builder (country → wilaya → commune → variable → period → format), statuses *Experimental* and *Under validation*.
- QA: Python statistics and product tests, and JS–Python trend parity tests, run in CI and before deployment.
- Documentation: method page for precipitation, `docs/ADDING_PRODUCTS.md`, `docs/AUDIT_2026-11-20.md`.

### Changed
- Homepage centred on data: live wilaya precipitation map, indicators computed from the product, featured analyses.
- Navigation: Home · Data · Map · Analyze · Regions · Methods · Contribute · About.
- Status labels: "In preparation" is shown as *Planned*, and "Archived" as *Deprecated*.

## 2026-11-19
- First public version: catalog of 36 records (29 sources, 7 planned products), map explorer, 69-wilaya boundaries, methods and tutorials.
