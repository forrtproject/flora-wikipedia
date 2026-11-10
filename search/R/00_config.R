suppressPackageStartupMessages({
  library(httr2)
  library(dplyr)
  library(readr)
  library(tidyr)
  library(stringr)
  library(purrr)
  library(jsonlite)
  # nanoparquet is a small, portable alternative to Arrow.
  if (!requireNamespace("arrow", quietly = TRUE) &&
      !requireNamespace("nanoparquet", quietly = TRUE))
    stop("Install arrow or nanoparquet; see R/setup.R")
  library(fs)
  library(glue)
  library(cli)
})

PROJECT_ROOT <- normalizePath(Sys.getenv("FLORA_PROJECT_ROOT", unset = getwd()), mustWork = TRUE)
LANG <- Sys.getenv("FLORA_LANG", unset = "en")
if (!grepl("^[a-z]{2,3}$", LANG)) stop("Invalid Wikipedia language code")
RUN_DIR <- Sys.getenv("FLORA_RUN_DIR", unset = PROJECT_ROOT)

DATA_DIR   <- file.path(RUN_DIR, "data")
CACHE_DIR  <- file.path(RUN_DIR, "cache")
OUTPUT_DIR <- file.path(RUN_DIR, "output")
WIKITEXT_DIR <- file.path(CACHE_DIR, "wikitext")

USER_AGENT <- "FLoRA-Wikipedia-Audit/0.2 (https://github.com/forrtproject/flora-wikipedia)"
OFFLINE <- identical(Sys.getenv("FLORA_OFFLINE"), "1")
dir_create(c(DATA_DIR, CACHE_DIR, OUTPUT_DIR))
read_parquet <- function(path) {
  if (requireNamespace("arrow", quietly = TRUE)) return(arrow::read_parquet(path))
  tibble::as_tibble(nanoparquet::read_parquet(path))
}
write_parquet <- function(x, path) {
  tmp <- paste0(path, ".tmp")
  if (requireNamespace("arrow", quietly = TRUE)) arrow::write_parquet(x, tmp)
  else nanoparquet::write_parquet(as.data.frame(x), tmp)
  if (!file.rename(tmp, path)) stop("Cannot atomically replace ", path)
}
assert_live <- function() if (OFFLINE) stop("Network prohibited in offline mode")

LANGS_PRIMARY <- c("en")
LANGS_EXTENDED <- c("en", "de", "fr", "es", "it", "nl", "pt", "ru", "ja", "zh")

DOI_REGEX <- "10\\.[0-9]{4,9}/[^\\s|}\\]<>\"'\\\\]+"

normalise_doi <- function(x) {
  x <- str_trim(x)
  x <- str_to_lower(x)
  x <- str_replace_all(x, "%3c", "<")
  x <- str_replace_all(x, "%3e", ">")
  x <- str_replace(x, "^https?://(dx\\.)?doi\\.org/", "")
  x <- str_replace(x, "^doi:", "")
  x <- str_replace_all(x, "[\\.,;:\\)\\]\\}'\"]+$", "")
  x
}
