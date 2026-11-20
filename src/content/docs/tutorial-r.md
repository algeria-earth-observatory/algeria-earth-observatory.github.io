---
title: "Tutorial (R): rainfall per wilaya"
description: The same wilaya precipitation summary in R with the terra package.
section: Tutorials
order: 91
updated: 2026-11-19
---

This is the R counterpart of the [Python tutorial](/docs/tutorial-python/). AEO ran it with R 4.6.2 and terra 1.9.50 on 19 November 2026; results matched the Python version to within 0.0001 mm for all 69 wilayas.

## Requirements

```r
install.packages("terra")
```

## Script

```r
library(terra)

chirps_url  <- "https://data.chc.ucsb.edu/products/CHIRPS/v2.0/global_annual/tifs/chirps-v2.0.2024.tif"
wilayas_url <- "https://algeria-earth-observatory.github.io/data/aeo/boundaries/2026-11-19/dza_adm1_wilayas.geojson"

dir.create("aeo_tutorial", showWarnings = FALSE)
tif <- file.path("aeo_tutorial", "chirps-v2.0.2024.tif")
gj  <- file.path("aeo_tutorial", "dza_adm1_wilayas.geojson")
if (!file.exists(tif)) download.file(chirps_url, tif, mode = "wb")
if (!file.exists(gj))  download.file(wilayas_url, gj, mode = "wb")

r <- rast(tif)
NAflag(r) <- -9999                         # CHIRPS nodata value
w <- project(vect(gj), crs(r))             # match the raster CRS

r_dz <- crop(r, w)                         # read only the Algeria window
vals <- extract(r_dz, w, fun = mean, na.rm = TRUE)
w$precip_mm_2024 <- vals[, 2]

res <- as.data.frame(w)[, c("wilaya_code", "name", "precip_mm_2024")]
write.csv(res, file.path("aeo_tutorial", "wilaya_precip_2024_R.csv"), row.names = FALSE)
head(res[order(-res$precip_mm_2024), ], 10)
```

Note `mode = "wb"` in `download.file()`: on Windows, binary files are corrupted without it.

## Mapping the result

```r
plot(w, "precip_mm_2024", type = "continuous", main = "CHIRPS v2.0 precipitation 2024 (mm)")
```

Read the caveats in the Python tutorial: values are cell-centre means of a satellite–gauge blend, and a single year is not a climatology.
