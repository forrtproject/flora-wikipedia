source(file.path(Sys.getenv("FLORA_PROJECT_ROOT", unset = getwd()), "R/02_exturlusage.R"))

unique_dois <- read_parquet(file.path(DATA_DIR, "unique_dois.parquet"))

cli_h1("Stage 1: exturlusage on enwiki ({nrow(unique_dois)} DOIs)")

out_path <- file.path(DATA_DIR, paste0("exturlusage_", LANG, ".parquet"))

res <- run_exturlusage(
  dois     = unique_dois$doi,
  lang     = LANG,
  out_path = out_path,
  log_every = 100,
  resume   = TRUE
)

cli_h2("Summary")
hits <- res |> filter(n_hits > 0)
cli_alert_info("DOIs with at least one Wikipedia hit: {n_distinct(hits$doi_query)} / {nrow(unique_dois)}")
cli_alert_info("Total (page, doi) hit rows: {nrow(hits)}")
cli_alert_info("Distinct citing pages: {n_distinct(hits$pageid)}")
