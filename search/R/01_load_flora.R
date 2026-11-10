source(file.path(Sys.getenv("FLORA_PROJECT_ROOT", unset = getwd()), "R/00_config.R"))

FLORA_URL <- "https://raw.githubusercontent.com/forrtproject/FReD-data/main/output/flora.csv"
FLORA_CSV <- file.path(DATA_DIR, "flora.csv")

if (!file_exists(FLORA_CSV)) {
  assert_live()
  cli_alert_info("Downloading flora.csv...")
  download.file(FLORA_URL, FLORA_CSV, quiet = TRUE)
}

flora_raw <- read_csv(FLORA_CSV, show_col_types = FALSE, na = c("", "NA"))

# Current FLoRA no longer supplies these optional fields. Preserve absence as NA.
if (!"self_identified_replication" %in% names(flora_raw)) flora_raw$self_identified_replication <- NA
if (!"replication_intent_confidence" %in% names(flora_raw)) flora_raw$replication_intent_confidence <- NA_character_

flora <- flora_raw |>
  mutate(
    doi_o_norm = normalise_doi(doi_o),
    doi_r_norm = normalise_doi(doi_r),
    pair_id    = row_number()
  ) |>
  filter(!is.na(doi_o_norm), !is.na(doi_r_norm))

cli_alert_success("Loaded {nrow(flora)} pairs ({n_distinct(flora$doi_o_norm)} unique originals, {n_distinct(flora$doi_r_norm)} unique replications)")

unique_dois <- bind_rows(
  tibble(doi = flora$doi_o_norm, role = "original"),
  tibble(doi = flora$doi_r_norm, role = "replication")
) |>
  group_by(doi) |>
  summarise(
    is_original    = any(role == "original"),
    is_replication = any(role == "replication"),
    .groups = "drop"
  ) |>
  mutate(
    has_special_chars = str_detect(doi, "[<>;()%]")
  )

cli_alert_info("Total unique DOIs to query: {nrow(unique_dois)} ({sum(unique_dois$has_special_chars)} with special chars)")

write_parquet(flora, file.path(DATA_DIR, "flora_normalised.parquet"))
write_parquet(unique_dois, file.path(DATA_DIR, "unique_dois.parquet"))
