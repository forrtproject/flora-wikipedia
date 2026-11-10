source(file.path(Sys.getenv("FLORA_PROJECT_ROOT", unset = getwd()), "R/04_extract_dois.R"))

# Extract surrounding context for each DOI mention. Returns one row per
# (lang, pageid, doi, occurrence) with the <ref>...</ref> block when present
# and the paragraph (or section heading) it sits in.
extract_contexts <- function(lang, pageid, target_dois) {
  path <- file.path(WIKITEXT_DIR, lang, paste0(pageid, ".txt"))
  if (!file_exists(path)) return(tibble())
  text <- paste(readLines(path, warn = FALSE, encoding = "UTF-8"), collapse = "\n")
  if (length(target_dois) == 0) return(tibble())

  rows <- list()
  for (doi in target_dois) {
    pat <- regex(paste0("10\\.", str_split(doi, "/", n = 2)[[1]][1] |> str_replace("^10\\.", ""),
                        "/", str_replace_all(str_split(doi, "/", n = 2)[[1]][2], "([\\.\\?\\+\\*\\(\\)\\[\\]\\{\\}\\^\\$\\|\\\\])", "\\\\\\1")),
                 ignore_case = TRUE)
    # Search both literal and percent-encoded forms by replacing `/` with alternation.
    encoded <- str_replace_all(doi, "/", "%2F")
    pat_either <- regex(paste0("(?:", str_replace_all(doi,    "([\\.\\?\\+\\*\\(\\)\\[\\]\\{\\}\\^\\$\\|\\\\])", "\\\\\\1"),
                               "|",  str_replace_all(encoded,"([\\.\\?\\+\\*\\(\\)\\[\\]\\{\\}\\^\\$\\|\\\\])", "\\\\\\1"),
                               ")"),
                        ignore_case = TRUE)

    locs <- str_locate_all(text, pat_either)[[1]]
    if (nrow(locs) == 0) next

    for (j in seq_len(nrow(locs))) {
      pos <- locs[j, "start"]

      # Find enclosing <ref>...</ref> if any.
      ref_block <- NA_character_
      ref_starts <- str_locate_all(text, regex("<ref\\b[^>]*>", ignore_case = TRUE))[[1]]
      ref_ends   <- str_locate_all(text, regex("</ref>",     ignore_case = TRUE))[[1]]
      if (nrow(ref_starts) > 0 && nrow(ref_ends) > 0) {
        prior_starts <- ref_starts[ref_starts[, "end"] < pos, , drop = FALSE]
        if (nrow(prior_starts) > 0) {
          s <- prior_starts[nrow(prior_starts), "start"]
          following_ends <- ref_ends[ref_ends[, "start"] > pos, , drop = FALSE]
          if (nrow(following_ends) > 0) {
            e <- following_ends[1, "end"]
            candidate <- str_sub(text, s, e)
            opening <- str_sub(text, s, prior_starts[nrow(prior_starts), "end"])
            before_doi <- str_sub(text, s, pos - 1L)
            if (!str_detect(opening, "/>\\s*$") &&
                !str_detect(before_doi, regex("</ref>", ignore_case = TRUE))) ref_block <- candidate
          }
        }
      }

      # Whole raw paragraph; separators have variable length.
      breaks <- str_locate_all(text, "\\n\\n+")[[1]]
      starts <- c(1L, if (nrow(breaks)) breaks[, "end"] + 1L else integer())
      ends <- c(if (nrow(breaks)) breaks[, "start"] - 1L else integer(), nchar(text))
      idx <- which(starts <= pos & ends >= pos)[1]
      paragraph <- if (!is.na(idx)) str_sub(text, starts[idx], ends[idx]) else NA_character_

      # Section heading: nearest preceding `==Heading==`.
      head_locs <- str_locate_all(str_sub(text, 1, pos), regex("^==+\\s*([^=].*?)\\s*==+\\s*$", multiline = TRUE))[[1]]
      section <- NA_character_
      if (nrow(head_locs) > 0) {
        last <- head_locs[nrow(head_locs), ]
        section <- str_trim(str_replace_all(str_sub(text, last[1], last[2]), "^=+\\s*|\\s*=+$", ""))
      }

      rows[[length(rows) + 1]] <- tibble(
        lang = lang, pageid = pageid, doi = doi,
        match_pos = pos, ref_block = ref_block,
        paragraph = paragraph, section = section
      )
    }
  }

  bind_rows(rows)
}

build_audit <- function() {
  flora <- read_parquet(file.path(DATA_DIR, "flora_normalised.parquet"))
  hits  <- read_parquet(file.path(DATA_DIR, paste0("exturlusage_", LANG, ".parquet"))) |>
    filter(!is.na(pageid))

  # All DOIs found in each candidate article (from cached wikitext).
  article_dois <- build_article_dois()
  write_parquet(article_dois, file.path(DATA_DIR, "article_dois.parquet"))

  # For each (lang, pageid) that hit any flora DOI, check co-citation.
  candidate_pages <- hits |> distinct(lang, pageid, page_title)

  # Long-format: for each candidate page x flora pair, did doi_o hit and is doi_r also there?
  doi_set_by_page <- article_dois |>
    group_by(lang, pageid) |>
    summarise(doi_set = list(doi), .groups = "drop")

  audit_long <- candidate_pages |>
    inner_join(doi_set_by_page, by = c("lang", "pageid")) |>
    mutate(idx = row_number()) |>
    rowwise() |>
    mutate(
      pairs = list(
        flora |>
          filter(doi_o_norm %in% doi_set) |>
          mutate(
            r_also_cited = doi_r_norm %in% doi_set,
            o_also_cited = TRUE
          ) |>
          select(pair_id, doi_o_norm, doi_r_norm, outcome, type, source,
                 self_identified_replication, replication_intent_confidence,
                 r_also_cited)
      )
    ) |>
    ungroup() |>
    select(lang, pageid, page_title, pairs) |>
    unnest(pairs)

  if (!"pair_id" %in% names(audit_long)) {
    audit_long <- bind_cols(candidate_pages[0, ],
      flora[0, ] |> select(pair_id, doi_o_norm, doi_r_norm, outcome, type, source,
        self_identified_replication, replication_intent_confidence),
      tibble(r_also_cited = logical()))
  }
  write_parquet(audit_long, file.path(OUTPUT_DIR, "audit_long.parquet"))

  audit_summary <- audit_long |>
    group_by(pair_id, doi_o_norm, doi_r_norm, outcome, type, source) |>
    summarise(
      n_pages_citing_o      = n(),
      n_pages_citing_both   = sum(r_also_cited, na.rm = TRUE),
      citing_pages          = paste0(unique(page_title), collapse = " | "),
      pages_citing_both     = paste0(unique(page_title[r_also_cited]), collapse = " | "),
      .groups = "drop"
    ) |>
    mutate(any_co_citation = n_pages_citing_both > 0)

  # Pairs with no Wikipedia hit are absent from audit_long. Add them as zero rows.
  missing_pairs <- flora |>
    anti_join(audit_summary, by = "pair_id") |>
    transmute(pair_id, doi_o_norm, doi_r_norm, outcome, type, source,
              n_pages_citing_o = 0L, n_pages_citing_both = 0L,
              citing_pages = "", pages_citing_both = "", any_co_citation = FALSE)

  audit_full <- bind_rows(audit_summary, missing_pairs) |>
    arrange(desc(n_pages_citing_o))

  write_csv(audit_full, file.path(OUTPUT_DIR, "flora_wikipedia_audit.csv"))
  write_parquet(audit_full, file.path(OUTPUT_DIR, "flora_wikipedia_audit.parquet"))

  invisible(audit_full)
}

build_contexts <- function() {
  flora <- read_parquet(file.path(DATA_DIR, "flora_normalised.parquet"))
  audit_long <- read_parquet(file.path(OUTPUT_DIR, "audit_long.parquet"))

  to_extract <- audit_long |> distinct(lang, pageid, doi_o_norm, doi_r_norm)

  cli_alert_info("Extracting contexts for {nrow(to_extract)} (page, pair) combos")

  rows <- list()
  for (i in seq_len(nrow(to_extract))) {
    r <- to_extract[i, ]
    target_dois <- c(r$doi_o_norm, r$doi_r_norm)
    ctx <- extract_contexts(r$lang, r$pageid, target_dois)
    if (nrow(ctx) > 0) {
      ctx <- ctx |>
        mutate(
          pair_doi_o = r$doi_o_norm,
          pair_doi_r = r$doi_r_norm,
          doi_role = case_when(
            doi == r$doi_o_norm ~ "original",
            doi == r$doi_r_norm ~ "replication",
            TRUE ~ "other"
          )
        )
      rows[[length(rows) + 1]] <- ctx
    }
  }

  contexts <- if (length(rows)) bind_rows(rows) else tibble(
    lang = character(), pageid = integer(), doi = character(), match_pos = integer(),
    ref_block = character(), paragraph = character(), section = character(),
    pair_doi_o = character(), pair_doi_r = character(), doi_role = character())
  write_parquet(contexts, file.path(OUTPUT_DIR, "citation_contexts.parquet"))

  # Joined view with flora outcome.
  out <- contexts |>
    left_join(flora |> select(pair_doi_o = doi_o_norm, pair_doi_r = doi_r_norm,
                              outcome, type, source) |> distinct(),
              by = c("pair_doi_o", "pair_doi_r"))
  write_csv(out, file.path(OUTPUT_DIR, "citation_contexts.csv"))

  invisible(contexts)
}
