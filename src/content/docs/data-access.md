---
title: Accessing data
description: What the catalog statuses mean, which providers require a free account, and how to get files onto your computer.
section: Getting started
order: 10
updated: 2026-11-19
---

## What AEO hosts and what it does not

The Algeria Earth Observatory is a documented **catalog**, not a data warehouse. Every record has one of four statuses:

| Status | Meaning | What the button does |
|---|---|---|
| **Available** | A file distributed by AEO (for example the wilaya boundaries), with version and SHA-256 checksum. | Downloads directly from this website. |
| **External source** | The dataset is held by its original producer. AEO documents it and links to the official source. | Opens the provider's site (“Access at source”). |
| **In preparation** | A planned AEO product. No data have been released. | No download is offered. |
| **Archived** | Superseded or no longer maintained; kept for reference. | Links remain where still valid. |

Most environmental datasets relevant to Algeria are **global or continental products**. Their records say so explicitly: you download from the provider and extract the Algeria area yourself (see [Subsetting data to Algeria](/docs/subsetting-algeria/)).

## Free accounts you are likely to need

Several major providers require a free registration before download. Records state this in the access list (“login required”).

- **NASA Earthdata Login** — MODIS, SMAP, IMERG, MERRA-2 and other NASA DAAC products (urs.earthdata.nasa.gov).
- **Copernicus Data Space Ecosystem** — Sentinel-1, -2, -3 and -5P products and the Copernicus DEM (dataspace.copernicus.eu).
- **Copernicus Climate Data Store (CDS)** — ERA5 and ERA5-Land; you must also accept the dataset licence once in your profile.
- **USGS EarthExplorer** — Landsat Collection 2 scenes.

Products such as CHIRPS, WorldCover, WorldCereal, SoilGrids, WorldPop and JRC Global Surface Water can be downloaded without an account.

## Choosing a download route

1. **Small area, few dates:** web portals or browser tools offered by the provider are often fastest.
2. **Long time series:** prefer the provider's single-file or aggregated products (for example a global monthly NetCDF) and subset locally, or use an API/THREDDS/OPeNDAP service when the record lists one.
3. **Cloud processing:** many records list a Google Earth Engine or AWS Open Data copy. These are convenient but check that the version matches the one you cite.

## Verifying what you downloaded

- For AEO-hosted files, compare the SHA-256 checksum shown on the dataset page:
  - Windows PowerShell: `Get-FileHash file.geojson -Algorithm SHA256`
  - macOS/Linux: `shasum -a 256 file.geojson`
- Record the **version** and **download date** of every external dataset in your project notes; global products are reprocessed and their values can change between versions.

## When a link is broken

Providers reorganise their websites. If a link on a dataset page fails, use **“Report an error or broken link”** at the bottom of that page. The catalog is re-checked with an automated link checker, but reports from users are the fastest signal.
