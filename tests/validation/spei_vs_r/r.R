.libPaths(c(Sys.getenv("R_LIBS_USER"), .libPaths()))
suppressMessages(library(SPEI))
a <- commandArgs(TRUE)[1]
x <- read.csv(file.path(a, "py.csv"))
d <- ts(x$d, start=c(1961,1), frequency=12)
res <- sapply(c(1,3,6,12), function(k) as.numeric(spei(d, k, ref.start=c(1991,1), ref.end=c(2020,12), verbose=FALSE)$fitted))
colnames(res) <- paste0("r", c(1,3,6,12))
write.csv(res, file.path(a, "r.csv"), row.names=FALSE)
