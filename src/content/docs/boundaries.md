---
title: AEO boundary layers — method and versions
description: How the 69-wilaya boundary layer was built from OpenStreetMap, what was checked, what was fixed, and how new versions are published.
section: Working with data
order: 45
updated: 2026-11-19
---

## Why AEO builds its own boundary layer

Algeria's administrative geography changed twice in recent years: from 48 to 58 wilayas (Loi n° 19-12, 2019) and to 69 wilayas (Loi n° 26-06 of 4 April 2026, JO n° 25; names of wilayas 59–69 fixed by Décret présidentiel n° 26-206, JO n° 40). On 19 November 2026 the openly licensed boundary sets AEO checked — geoBoundaries, OCHA COD-AB and GADM — still represented 48 wilayas. OpenStreetMap contained all 69 wilaya relations.

## Method (version 2026-11-19)

1. **Download.** The Algeria country relation (OSM relation 192756, admin_level 2) and all admin_level 4 boundary relations inside it were retrieved from the Overpass API with member-way geometries.
2. **Assemble.** Polygons were built from member ways (`shapely.polygonize`), outer minus inner rings.
3. **Clip to land.** OSM's national boundary includes territorial sea. Wilaya polygons were clipped with the land polygon of geoBoundaries DZA ADM0 (also OSM-derived, ODbL), used only as a coastline mask.
4. **Check overlaps.** Pairs of wilayas overlapping by more than 1 km² were detected. One overlap was found: the new wilaya of El Aricha (63) was still included in the Tlemcen (13) relation. The newer wilaya takes precedence; the overlap (≈ 3,010 km²) was removed from Tlemcen. This rule is applied automatically and logged in `PROVENANCE.json`.
5. **Attributes.** `wilaya_code` (OSM `ref`), `iso_3166_2` (OSM tag, left empty when absent — El Aricha has none), names (`name` French, `name_ar`, `name_en`), `osm_relation`, `wikidata`, `area_km2` (planimetric area in a Lambert azimuthal equal-area projection).
6. **Display version.** A topology-preserving simplification (mapshaper, 4 % of vertices retained) is used by the website maps only.

The processing code is [`scripts/processing/build_boundaries.py`](https://github.com/algeria-earth-observatory/algeria-earth-observatory.github.io/blob/main/scripts/processing/build_boundaries.py).

## Checks

- 69 valid polygons; codes 01–69 present once each.
- No overlaps above 1 km² after the documented fix.
- Gap between the union of wilayas and the national land outline: below 200 km² (coastline differences).
- Areas of the mother wilayas are consistent with the communes transferred to new wilayas (for example El Bayadh after the creation of El Abiodh Sidi Cheikh).

## Limitations

- OpenStreetMap boundaries are community-mapped. They are **not** a legal or cadastral delineation and have not been checked against official survey data.
- During the transition defined by Loi n° 26-06, powers move from mother wilayas to the new wilayas by 31 December 2026 at the latest. Statistics for 2026 and earlier generally use 48 or 58 units.
- Positional accuracy may be lower for recently created wilayas.

## Versions

Each snapshot is published in its own folder, `/data/aeo/boundaries/<version>/`, and earlier versions remain available. The dataset record always states the current version and lists SHA-256 checksums for every file.
