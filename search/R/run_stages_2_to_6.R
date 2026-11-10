source(file.path(Sys.getenv("FLORA_PROJECT_ROOT", unset = getwd()), "R/03_wikitext.R"))
source(file.path(Sys.getenv("FLORA_PROJECT_ROOT", unset = getwd()), "R/05_audit.R"))

cli_h1("Stage 2: fetch wikitext for candidate pages")
hits <- read_parquet(file.path(DATA_DIR, paste0("exturlusage_", LANG, ".parquet"))) |>
  filter(!is.na(pageid))
fetch_all_wikitext(hits)

cli_h1("Stage 3-4: build audit table")
audit <- build_audit()

cli_h1("Stage 5: extract citation contexts")
contexts <- build_contexts()

cli_h1("Stage 6: headline summary")
flora <- read_parquet(file.path(DATA_DIR, "flora_normalised.parquet"))

n_pairs <- nrow(flora)
n_o_with_any_hit <- audit |> filter(n_pages_citing_o > 0) |> nrow()
n_pairs_co_cited <- audit |> filter(any_co_citation) |> nrow()

cat("\n========== HEADLINE NUMBERS ==========\n")
cat(sprintf("Total flora pairs:                        %d\n", n_pairs))
cat(sprintf("Pairs where doi_o is cited on Wikipedia:  %d (%.1f%%)\n",
            n_o_with_any_hit, 100 * n_o_with_any_hit / n_pairs))
cat(sprintf("Pairs where doi_r is ALSO cited:          %d (%.1f%% of cited)\n",
            n_pairs_co_cited, 100 * n_pairs_co_cited / max(n_o_with_any_hit, 1)))

cat("\n--- By replication outcome ---\n")
audit |>
  filter(n_pages_citing_o > 0) |>
  group_by(outcome) |>
  summarise(
    n_pairs           = n(),
    n_co_cited        = sum(any_co_citation),
    pct_co_cited      = round(100 * n_co_cited / n_pairs, 1),
    median_pages      = median(n_pages_citing_o),
    .groups = "drop"
  ) |>
  arrange(desc(n_pairs)) |>
  print(n = Inf)

cat("\n--- Top 20 most-cited originals on Wikipedia ---\n")
audit |>
  filter(n_pages_citing_o > 0) |>
  arrange(desc(n_pages_citing_o)) |>
  head(20) |>
  select(doi_o_norm, outcome, n_pages_citing_o, n_pages_citing_both, citing_pages) |>
  mutate(citing_pages = str_trunc(citing_pages, 80)) |>
  print(n = Inf)
