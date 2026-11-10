source(file.path(Sys.getenv("FLORA_PROJECT_ROOT", unset = getwd()), "R/02_exturlusage.R"))

# Smoke test: 5 known-Wikipedia DOIs to validate the fetcher.
known_dois <- c(
  "10.1126/science.aac4716",                   # Reproducibility Project: Psychology
  "10.1037/0022-3514.74.5.1252",               # Baumeister et al. ego depletion
  "10.1126/science.1736359",                   # Mischel marshmallow follow-up
  "10.1037/h0076484",                          # Zimbardo / Stanford prison adjacent
  "10.1177/0956797610383437"                   # Carney et al. power posing
) |> normalise_doi()

cli_h1("Smoke test on selected wiki")
out <- file.path(DATA_DIR, paste0("smoke_exturlusage_", LANG, ".parquet"))

res <- run_exturlusage(known_dois, lang = LANG, out_path = out, log_every = 1, resume = TRUE)

cat("\n=== Results ===\n")
res |>
  filter(n_hits > 0) |>
  select(doi_query, page_title, url_hit) |>
  print(n = Inf)

cat("\n=== Per-DOI summary ===\n")
res |>
  group_by(doi_query) |>
  summarise(n_pages = sum(!is.na(pageid)), .groups = "drop") |>
  print()
