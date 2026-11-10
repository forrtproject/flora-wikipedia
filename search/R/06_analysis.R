source(file.path(Sys.getenv("FLORA_PROJECT_ROOT", unset = getwd()), "R/00_config.R"))

flora <- read_parquet(file.path(DATA_DIR, "flora_normalised.parquet"))
audit_long <- read_parquet(file.path(OUTPUT_DIR, "audit_long.parquet"))
audit_full <- read_parquet(file.path(OUTPUT_DIR, "flora_wikipedia_audit.parquet"))

cat("\n========== KEY FINDINGS (cleaner per-original view) ==========\n\n")

# Per unique doi_o: across ALL its replications, was at least one r co-cited on each citing page?
per_o <- audit_long |>
  group_by(doi_o_norm, lang, pageid, page_title) |>
  summarise(
    any_r_cited = any(r_also_cited),
    n_r_partners = n(),
    .groups = "drop"
  )

cat("--- Per (Wikipedia article × original DOI) ---\n")
cat(sprintf("Distinct (article, doi_o) pairs:   %d\n", nrow(per_o)))
cat(sprintf("Where ANY replication co-cited:    %d (%.1f%%)\n",
            sum(per_o$any_r_cited), 100 * mean(per_o$any_r_cited)))

cat("\n--- Per unique original DOI ---\n")
per_unique_o <- per_o |>
  group_by(doi_o_norm) |>
  summarise(
    n_articles_citing = n_distinct(pageid),
    any_co_cited = any(any_r_cited),
    .groups = "drop"
  ) |>
  left_join(
    flora |>
      group_by(doi_o_norm) |>
      summarise(
        outcomes = paste(sort(unique(outcome)), collapse = "; "),
        worst_outcome = case_when(
          any(outcome == "failed") ~ "failed",
          any(outcome == "mixed") ~ "mixed",
          any(outcome == "successful") ~ "successful",
          TRUE ~ first(outcome)
        ),
        .groups = "drop"
      ),
    by = "doi_o_norm"
  )

cat(sprintf("Unique originals cited on Wikipedia:        %d (of %d in dataset)\n",
            nrow(per_unique_o), n_distinct(flora$doi_o_norm)))
cat(sprintf("With at least one replication also cited:   %d (%.1f%%)\n",
            sum(per_unique_o$any_co_cited), 100 * mean(per_unique_o$any_co_cited)))

cat("\n--- By worst outcome among the original's replications ---\n")
per_unique_o |>
  group_by(worst_outcome) |>
  summarise(
    n_originals_on_wiki = n(),
    n_with_r_cited = sum(any_co_cited),
    pct = round(100 * mean(any_co_cited), 1),
    .groups = "drop"
  ) |>
  arrange(desc(n_originals_on_wiki)) |>
  print()

# Compare to the full dataset baseline (before Wikipedia filter)
cat("\n--- Wikipedia presence by replication outcome (denominator: all originals) ---\n")
flora |>
  group_by(doi_o_norm) |>
  summarise(
    worst_outcome = case_when(
      any(outcome == "failed") ~ "failed",
      any(outcome == "mixed") ~ "mixed",
      any(outcome == "successful") ~ "successful",
      TRUE ~ first(outcome)
    ),
    .groups = "drop"
  ) |>
  left_join(
    per_unique_o |> select(doi_o_norm, on_wiki = n_articles_citing, any_co_cited),
    by = "doi_o_norm"
  ) |>
  mutate(on_wiki = !is.na(on_wiki), any_co_cited = coalesce(any_co_cited, FALSE)) |>
  group_by(worst_outcome) |>
  summarise(
    n_originals = n(),
    n_on_wiki = sum(on_wiki),
    pct_on_wiki = round(100 * mean(on_wiki), 1),
    n_co_cited = sum(any_co_cited),
    pct_co_cited_of_on_wiki = round(100 * sum(any_co_cited) / max(sum(on_wiki), 1), 1),
    .groups = "drop"
  ) |>
  arrange(desc(n_originals)) |>
  print()

cat("\n--- Top 15 originals on Wikipedia without a detected replication DOI ---\n")
per_unique_o |>
  filter(!any_co_cited) |>
  arrange(desc(n_articles_citing)) |>
  head(15) |>
  left_join(
    audit_long |> group_by(doi_o_norm) |>
      summarise(
        pages = paste(unique(page_title)[1:min(3, n_distinct(page_title))], collapse = " | "),
        .groups = "drop"
      ),
    by = "doi_o_norm"
  ) |>
  select(doi_o_norm, worst_outcome, n_articles_citing, pages) |>
  mutate(pages = str_trunc(pages, 70)) |>
  print(n = Inf)

cat("\n--- Examples where both DOI strings are detected ---\n")
audit_full |>
  filter(any_co_citation, n_pages_citing_o >= 2) |>
  arrange(desc(n_pages_citing_o)) |>
  head(10) |>
  select(doi_o_norm, doi_r_norm, outcome, n_pages_citing_o, n_pages_citing_both, pages_citing_both) |>
  mutate(pages_citing_both = str_trunc(pages_citing_both, 60)) |>
  print(n = Inf)

# Save a clean per-original summary too.
per_unique_o |>
  arrange(desc(n_articles_citing)) |>
  write_csv(file.path(OUTPUT_DIR, "per_original_summary.csv"))

cat("\n\nWrote: output/per_original_summary.csv\n")
