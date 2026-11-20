---
title: Working with vector datasets
description: Load the AEO wilaya boundaries, join statistics by wilaya code, and handle the 48/58/69-wilaya configurations safely.
section: Working with data
order: 40
updated: 2026-11-19
---

## Load the AEO wilaya boundaries

The [boundary dataset](/data/aeo-dza-admin-boundaries/) provides 69 wilaya polygons in EPSG:4326 with the attributes `wilaya_code`, `iso_3166_2`, `name`, `name_ar`, `name_en`, `osm_relation`, `wikidata` and `area_km2`.

```python
import geopandas as gpd
url = "https://algeria-earth-observatory.github.io/data/aeo/boundaries/2026-11-19/dza_adm1_wilayas.geojson"
wil = gpd.read_file(url)
print(len(wil), wil.crs)          # 69 EPSG:4326
```

```r
library(terra)
w <- vect("https://algeria-earth-observatory.github.io/data/aeo/boundaries/2026-11-19/dza_adm1_wilayas.geojson")
nrow(w)
```

In QGIS: *Layer → Add Layer → Add Vector Layer*, choose *Protocol: HTTP(S)* and paste the URL, or download the file and drag it onto the map.

## Join tables by code, not by name

Wilaya names have several spellings in French, Arabic and English (for example *Aïn Oussara / Aïn Ouessara*, *El M'Ghair / El M'Ghaier*). Join statistics on the two-digit **`wilaya_code`** stored as text (`"01"` … `"69"`), and keep the leading zero.

```python
import pandas as pd
stats = pd.read_csv("my_statistics.csv", dtype={"wilaya_code": str})
merged = wil.merge(stats, on="wilaya_code", how="left", validate="one_to_one")
```

## Check the administrative configuration

Algeria has had three wilaya configurations in recent years:

| Configuration | Legal basis | Units |
|---|---|---|
| 48 wilayas | Loi n° 84-09 (1984) | codes 01–48 |
| 58 wilayas | Loi n° 19-12 (2019); names by Décret n° 21-117 (2021) | codes 49–58 added |
| 69 wilayas | Loi n° 26-06 of 4 April 2026 (JO n° 25); names by Décret présidentiel n° 26-206 (JO n° 40) | codes 59–69 added |

New wilayas were formed by regrouping existing communes, so the national total of 1,541 communes did not change. Statistics for past years are usually reported on 48 or 58 units; joining them to the 69-unit layer leaves the new wilayas empty and over-states the parent wilayas' areas. Aggregate the 69 polygons back to the configuration of your statistics, or obtain statistics on the matching geography.

## Areas and distances

Polygon areas in degrees are meaningless. Reproject to an equal-area CRS first:

```python
laea = "+proj=laea +lat_0=28 +lon_0=3 +datum=WGS84 +units=m"
wil["area_km2_check"] = wil.to_crs(laea).area / 1e6
```

The `area_km2` attribute was computed this way from the full-detail polygons. It is not an official statistic.
