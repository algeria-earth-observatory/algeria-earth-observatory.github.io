# Reference SPI values from the R package SPEI (spi(), Gamma, ub-pwm, reference 1991-2020)
# for the series in spi_input.csv (written by tests/python/make_spi_fixture.py).
# Output: spi_r_output.csv (unit, scale, index, value), converted to spi_r_cases.json by make_spi_fixture.py. -Inf (zero accumulations,
# see scripts/pipelines/aeo/spi.py) and NA are written as null.
args <- commandArgs(trailingOnly = TRUE)
dir <- if (length(args)) args[1] else "tests/fixtures"
d <- read.csv(file.path(dir, "spi_input.csv"), colClasses = c(unit = "character"))
rows <- list()
for (u in unique(d$unit)) {
  s <- d[d$unit == u, ]
  x <- ts(s$precip_mm, start = c(s$year[1], s$month[1]), frequency = 12)
  for (k in c(1, 3, 6, 12)) {
    r <- SPEI::spi(x, k, distribution = "Gamma", fit = "ub-pwm", na.rm = TRUE,
                   ref.start = c(1991, 1), ref.end = c(2020, 12), verbose = FALSE)
    v <- as.numeric(r$fitted)
    v[!is.finite(v)] <- NA
    rows[[length(rows) + 1]] <- data.frame(unit = u, scale = k, i = seq_along(v) - 1, value = v)
  }
}
out <- do.call(rbind, rows)
write.csv(out, file.path(dir, "spi_r_output.csv"), row.names = FALSE, na = "")
cat("SPEI", as.character(packageVersion("SPEI")), "R", as.character(getRversion()), "\n", file = file.path(dir, "spi_r_version.txt"))
