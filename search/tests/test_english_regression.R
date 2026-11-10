script <- sub("^--file=", "", grep("^--file=", commandArgs(), value = TRUE)[1])
root <- normalizePath(file.path(dirname(script), ".."))
Sys.setenv(FLORA_PROJECT_ROOT = root)
source(file.path(root, "R/00_config.R"))
new_dir <- file.path(root, "runs/english-regression/en/output")
for (f in c("audit_long.parquet", "flora_wikipedia_audit.parquet")) {
  old <- read_parquet(file.path(root, "output", f)); new <- read_parquet(file.path(new_dir, f))
  keys <- if (f == "audit_long.parquet") c("lang", "pageid", "pair_id") else "pair_id"
  old <- as.data.frame(arrange(old, across(all_of(keys)))); new <- as.data.frame(arrange(new, across(all_of(keys))))
  stopifnot(isTRUE(all.equal(old, new, check.attributes = FALSE)))
  cat("PASS: archived English", f, "all rows/fields unchanged\n")
}
old <- read_csv(file.path(root, "output/per_original_summary.csv"), show_col_types = FALSE) |> arrange(doi_o_norm)
new <- read_csv(file.path(new_dir, "per_original_summary.csv"), show_col_types = FALSE) |> arrange(doi_o_norm)
stopifnot(isTRUE(all.equal(old, new, check.attributes = FALSE)))
s <- read_json(file.path(new_dir, "summary.json"), simplifyVector = TRUE)
stopifnot(s$originals_detected == 422, s$originals_with_any_co_citing_page == 54,
          s$article_original_combinations == 847,
          s$article_original_combinations_with_any_replication_doi == 66)
cat("PASS: full English summary unchanged; original denominator 54/422, page-original denominator 66/847\n")
