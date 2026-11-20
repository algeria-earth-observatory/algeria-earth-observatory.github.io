# AEO tutorial: mean annual CHIRPS precipitation per wilaya (R, terra).
# Requires: install.packages("terra")
# Downloads ~58 MB (CHIRPS v2.0 global annual total for 2024) and the AEO wilaya layer.
library(terra)

chirps_url  <- "https://data.chc.ucsb.edu/products/CHIRPS/v2.0/global_annual/tifs/chirps-v2.0.2024.tif"
wilayas_url <- "https://algeria-earth-observatory.github.io/data/aeo/boundaries/2026-11-19/dza_adm1_wilayas.geojson"

dir.create("aeo_tutorial", showWarnings = FALSE)
tif <- file.path("aeo_tutorial", "chirps-v2.0.2024.tif")
gj  <- file.path("aeo_tutorial", "dza_adm1_wilayas.geojson")
if (!file.exists(tif)) download.file(chirps_url, tif, mode = "wb")
if (!file.exists(gj))  download.file(wilayas_url, gj, mode = "wb")

r <- rast(tif)
NAflag(r) <- -9999                      # CHIRPS nodata value
w <- vect(gj)
w <- project(w, crs(r))                 # always match the raster CRS

r_dz <- crop(r, w)                      # read only the Algeria window
vals <- extract(r_dz, w, fun = mean, na.rm = TRUE)   # one row per wilaya (ID = row order)
w$precip_mm_2024 <- vals[, 2]

res <- as.data.frame(w)[, c("wilaya_code", "name", "precip_mm_2024")]
write.csv(res, file.path("aeo_tutorial", "wilaya_precip_2024_R.csv"), row.names = FALSE)
print(head(res[order(-res$precip_mm_2024), ], 10))
