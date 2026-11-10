source(file.path(Sys.getenv("FLORA_PROJECT_ROOT", unset = getwd()), "R/02_exturlusage.R"))

flora       <- read_parquet(file.path(DATA_DIR, "flora_normalised.parquet"))
unique_oa   <- read_parquet(file.path(DATA_DIR, "unique_dois_oa.parquet"))
hits        <- read_parquet(file.path(DATA_DIR, paste0("exturlusage_", LANG, ".parquet"))) |>
  filter(!is.na(pageid))

# Per-original: did we find any DOI hit, and what's its citation count?
per_o <- flora |>
  distinct(doi_o_norm) |>
  rename(doi = doi_o_norm) |>
  left_join(unique_oa |> select(doi, cited_by_count, publication_year, title),
            by = "doi") |>
  left_join(
    hits |> group_by(doi_query) |>
      summarise(n_pages = n_distinct(pageid), .groups = "drop") |>
      rename(doi = doi_query),
    by = "doi"
  ) |>
  mutate(
    n_pages = coalesce(n_pages, 0L),
    found_on_wiki = n_pages > 0,
    cited_by_count = coalesce(cited_by_count, 0L)
  )

# Bin by citation count to see Wikipedia presence rate
cat("\n========== Wikipedia presence by citation count (originals only) ==========\n")
per_o |>
  mutate(cite_bin = cut(cited_by_count,
                        breaks = c(-1, 10, 50, 200, 500, 1000, Inf),
                        labels = c("0-10","11-50","51-200","201-500","501-1000",">1000"))) |>
  group_by(cite_bin) |>
  summarise(
    n = n(),
    n_on_wiki = sum(found_on_wiki),
    pct_on_wiki = round(100 * mean(found_on_wiki), 1),
    median_pages = median(n_pages[found_on_wiki]),
    .groups = "drop"
  ) |>
  print()

cat("\n--- High-cited originals NOT found on Wikipedia via DOI ---\n")
candidates <- per_o |>
  filter(!found_on_wiki, cited_by_count >= 500) |>
  arrange(desc(cited_by_count))

cat(sprintf("%d high-cited (>=500 OpenAlex citations) originals with 0 enwiki DOI hits.\n", nrow(candidates)))
candidates |>
  head(20) |>
  select(doi, cited_by_count, publication_year, title) |>
  mutate(title = str_trunc(title, 60)) |>
  print(n = Inf)

# Wikipedia full-text search to see whether each is mentioned somewhere
# (in prose, in a cite template missing the DOI, etc.)
wiki_search <- function(query, limit = 5) {
  resp <- mw_request(LANG) |>
    req_url_query(
      action     = "query",
      list       = "search",
      srsearch   = query,
      srlimit    = as.character(limit),
      srnamespace = "0",
      srprop     = "snippet|titlesnippet",
      format     = "json",
      maxlag     = "5"
    ) |>
    req_perform()
  body <- resp_body_json(resp)
  res <- body$query$search
  if (length(res) == 0) return(tibble())
  tibble(
    page_title = map_chr(res, "title"),
    snippet    = map_chr(res, "snippet") |>
      str_replace_all("<[^>]+>", "") |>
      str_replace_all("&quot;|&amp;|&#039;", "'")
  )
}

# Build a search query per candidate: first author surname + a strong title
# noun + publication year. We don't have author lists in the OA fields we
# pulled, so use the title-only + year strategy.
build_query <- function(title, year) {
  if (is.na(title)) return(NA_character_)
  # Take first 6 words of title, drop trailing punctuation
  words <- str_split(str_remove_all(title, "[^[:alnum:][:space:]\\-]"), "\\s+")[[1]]
  q <- paste(words[seq_len(min(6, length(words)))], collapse = " ")
  if (!is.na(year)) q <- paste0("\"", q, "\" ", year)
  q
}

cat("\n--- Searching Wikipedia by title for top candidates ---\n")
top_n <- 50
to_search <- candidates |> head(top_n) |>
  mutate(query = map2_chr(title, publication_year, build_query))

found_in_wiki_text <- list()
for (i in seq_len(nrow(to_search))) {
  row <- to_search[i, ]
  if (is.na(row$query)) next
  res <- tryCatch(wiki_search(row$query, limit = 3),
                  error = function(e) tibble())
  if (nrow(res) > 0) {
    found_in_wiki_text[[length(found_in_wiki_text) + 1]] <- res |>
      mutate(doi = row$doi, query = row$query, cited_by_count = row$cited_by_count)
  }
  if (i %% 10 == 0) cli_alert_info("[{i}/{nrow(to_search)}] searched")
}

results <- bind_rows(found_in_wiki_text)

cat("\n--- Candidate misses (high-cited DOI-missed originals with possible Wikipedia matches) ---\n")
if (nrow(results) > 0) {
  results |>
    group_by(doi, cited_by_count, query) |>
    summarise(
      n_search_hits = n(),
      sample_pages = paste(head(page_title, 3), collapse = " | "),
      .groups = "drop"
    ) |>
    arrange(desc(cited_by_count)) |>
    head(30) |>
    print(n = Inf)

  write_csv(results, file.path(OUTPUT_DIR, "candidate_misses_by_title.csv"))
  cli_alert_success("Wrote output/candidate_misses_by_title.csv ({nrow(results)} hits across {n_distinct(results$doi)} candidates)")
}

# Save augmented per-original table
write_csv(per_o |> arrange(desc(cited_by_count)),
          file.path(OUTPUT_DIR, "per_original_with_citations.csv"))
write_parquet(per_o, file.path(OUTPUT_DIR, "per_original_with_citations.parquet"))
cli_alert_success("Wrote output/per_original_with_citations.csv")
