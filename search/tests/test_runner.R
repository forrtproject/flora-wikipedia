script <- sub("^--file=", "", grep("^--file=", commandArgs(), value = TRUE)[1])
root <- normalizePath(file.path(dirname(script), ".."))
runner <- file.path(root, "R/run_audit.R")
invoke <- function(args) {
  suppressWarnings(system2("Rscript", c(shQuote(runner), args), stdout = TRUE, stderr = TRUE))
}
check <- function(x, name) {
  if (!isTRUE(x)) stop(name)
  cat("PASS:", name, "\n")
}
x <- invoke("--lang=es --run=spanish-sample --sample=11 --offline")
check(!is.null(attr(x, "status")) && any(grepl("Run scope changed", x)), "changed sample rejected before overwriting cache")
name <- paste0("test-lock-", Sys.getpid())
d <- file.path(root, "runs", name, "es")
dir.create(file.path(d, ".lock"), recursive = TRUE)
x <- invoke(paste0("--lang=es --run=", name, " --offline"))
check(!is.null(attr(x, "status")) && any(grepl("Run is locked", x)), "concurrent writer rejected")
unlink(file.path(root, "runs", name), recursive = TRUE)
previous <- getwd(); setwd(tempdir())
x <- invoke("--lang=es --run=spanish-sample --sample=12 --offline")
setwd(previous)
check(is.null(attr(x, "status")) && any(grepl("Completed es", x)), "offline sample runs from arbitrary working directory")
cat("All runner tests passed\n")
