# Adjudication packet: source metadata and unmodified UTF-8 wikitext, no automatic edits.
long <- read_parquet(file.path(OUTPUT_DIR, "audit_long.parquet"))
meta <- read_parquet(file.path(DATA_DIR, "wikitext_meta.parquet"))
per_page <- long |> group_by(lang, pageid, page_title, doi_o_norm) |>
  summarise(any_replication_doi = any(r_also_cited), .groups = "drop")
summary <- list(language = LANG, scope_pairs = nrow(flora),
  scope_originals = n_distinct(flora$doi_o_norm),
  discovery_dois = nrow(unique_dois),
  originals_detected = n_distinct(long$doi_o_norm),
  originals_with_any_co_citing_page = n_distinct(long$doi_o_norm[long$r_also_cited]),
  article_original_combinations = nrow(per_page),
  article_original_combinations_with_any_replication_doi = sum(per_page$any_replication_doi),
  original_citing_pages = n_distinct(long$pageid),
  candidate_pages = n_distinct(hits$pageid[!is.na(hits$pageid)]))
write_json(summary, file.path(OUTPUT_DIR, "summary.json"), auto_unbox = TRUE, pretty = TRUE)
examples <- long |>
  left_join(flora |> select(pair_id, title_o, year_o, title_r, year_r, apa_ref_r), by = "pair_id") |>
  left_join(meta, by = c("lang", "pageid")) |>
  mutate(page_url = paste0("https://", lang, ".wikipedia.org/wiki/", vapply(page_title,
    function(x) URLencode(gsub(" ", "_", x), reserved = TRUE), character(1))),
    revision_url = if_else(!is.na(revid), paste0("https://", lang,
      ".wikipedia.org/w/index.php?oldid=", revid), NA_character_),
    assessment = if_else(r_also_cited, "Both DOI strings detected; inspect relevance",
      "Replication DOI not detected; acknowledgement remains unaudited"),
    review_prompt = if (LANG == "es")
      "Revisar el contexto completo, referencias sin DOI, revisiones y fuentes secundarias. La ausencia del DOI no demuestra falta de reconocimiento."
      else "Review full context, DOI-free references, revisions, and secondary sources. DOI absence does not establish lack of acknowledgement.")
write_csv(examples, file.path(OUTPUT_DIR, "adjudication_pairs.csv"))
# Shared DOI keys are cross-language duplicates, not independent studies or equivalent pages.
baseline <- read_parquet(file.path(PROJECT_ROOT, "output/audit_long.parquet"))
cross <- examples |> distinct(lang, pageid, page_title, doi_o_norm) |>
  inner_join(baseline |> distinct(doi_o_norm, english_page = page_title, english_pageid = pageid),
    by = "doi_o_norm", relationship = "many-to-many")
write_csv(cross, file.path(OUTPUT_DIR, "cross_language_doi_overlap.csv"))
