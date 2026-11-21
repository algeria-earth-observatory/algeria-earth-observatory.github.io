# AEO tutorial (R): recompute SPEI-12 for one wilaya with the R package SPEI and compare it
# with the AEO SPEI product.
#
# Objective: SPEI standardises the climatic water balance D = P - PET. AEO publishes P, PET
# and D for every wilaya (TerraClimate, area means). Here you fit the log-logistic
# distribution on 1991-2020 with the reference R implementation and check the AEO values.
#
# Requires: install.packages("SPEI")
# Downloads one CSV (about 3.4 MB) from the AEO website, or reads a local copy.
# Usage:  Rscript spei_wilaya.R [wilaya_code] [path/to/public]
args <- commandArgs(trailingOnly = TRUE)
code <- if (length(args) >= 1) args[1] else "19"
src <- "data/aeo/products/spei/v1.0.0/tables/aeo_spei_monthly_admin1_v1.0.0.csv"
path <- if (length(args) >= 2) file.path(args[2], src) else paste0("https://algeria-earth-observatory.github.io/", src)

d <- read.csv(path, colClasses = c(unit_code = "character", parent_code = "character"))
w <- d[d$unit_code == code, ]
w <- w[order(w$year, w$month), ]

balance <- ts(w$d_mm, start = c(w$year[1], w$month[1]), frequency = 12)   # D = P - PET, mm/month
fit <- SPEI::spei(balance, 12, distribution = "log-Logistic", fit = "ub-pwm",
                  ref.start = c(1991, 1), ref.end = c(2020, 12), verbose = FALSE)
w$spei_12_tutorial <- as.numeric(fit$fitted)

# AEO clips values beyond +/-3.09 (p < 0.001); compare the rest
ok <- !is.na(w$spei_12) & abs(w$spei_12) < 3.09
cat(sprintf("Wilaya %s: %d months compared; largest difference from the AEO product: %.4f\n",
            code, sum(ok), max(abs(w$spei_12_tutorial[ok] - w$spei_12[ok]))))
last <- tail(w[!is.na(w$spei_12), ], 1)
cat(sprintf("Latest SPEI-12 (%d-%02d): %+.2f\n", last$year, last$month, last$spei_12))
cat(sprintf("Months with SPEI-12 <= -1 since 2015: %d\n", sum(w$year >= 2015 & w$spei_12 <= -1, na.rm = TRUE)))
