source(file.path(Sys.getenv("FLORA_PROJECT_ROOT", unset = getwd()), "R/00_config.R"))

OPENALEX_MAILTO <- Sys.getenv("OPENALEX_MAILTO", unset = "")

openalex_batch <- function(dois, batch_size = 50) {
  assert_live()
  out <- list()
  batches <- split(dois, ceiling(seq_along(dois) / batch_size))

  for (i in seq_along(batches)) {
    chunk <- batches[[i]]
    filter_val <- paste0("doi:", paste(chunk, collapse = "|"))

    resp <- request("https://api.openalex.org/works") |>
      req_user_agent(USER_AGENT) |>
      req_throttle(rate = 8) |>
      req_retry(max_tries = 4, backoff = ~ min(2^.x, 30)) |>
      req_url_query(
        filter   = filter_val,
        select   = "id,doi,cited_by_count,publication_year,title",
        `per-page` = as.character(batch_size),
        mailto   = OPENALEX_MAILTO
      ) |>
      req_perform()

    body <- resp_body_json(resp)
    res <- body$results

    if (length(res) > 0) {
      out[[length(out) + 1]] <- tibble(
        openalex_id    = map_chr(res, "id", .default = NA_character_),
        doi_url        = map_chr(res, "doi", .default = NA_character_),
        cited_by_count = map_int(res, "cited_by_count", .default = NA_integer_),
        publication_year = map_int(res, "publication_year", .default = NA_integer_),
        title          = map_chr(res, "title", .default = NA_character_)
      )
    }

    if (i %% 10 == 0 || i == length(batches)) {
      cli_alert_info("[{i}/{length(batches)}] batches fetched")
    }
  }

  bind_rows(out) |>
    mutate(doi = str_remove(str_to_lower(doi_url), "^https?://(dx\\.)?doi\\.org/"))
}

if (sys.nframe() == 0 || identical(environment(), globalenv())) {
  unique_dois <- read_parquet(file.path(DATA_DIR, "unique_dois.parquet"))
  cli_h1("OpenAlex: fetching citation counts for {nrow(unique_dois)} DOIs")

  oa <- openalex_batch(unique_dois$doi, batch_size = 50)

  cli_alert_info("OpenAlex returned {nrow(oa)} works ({sum(!unique_dois$doi %in% oa$doi)} DOIs not matched)")

  augmented <- unique_dois |>
    left_join(oa |> select(doi, openalex_id, cited_by_count, publication_year, title),
              by = "doi")

  write_parquet(augmented, file.path(DATA_DIR, "unique_dois_oa.parquet"))

  cli_alert_success("Wrote data/unique_dois_oa.parquet")

  cat("\n--- Distribution of citation counts ---\n")
  print(summary(augmented$cited_by_count))

  cat("\n--- Top 20 most-cited originals overall ---\n")
  augmented |>
    filter(is_original) |>
    arrange(desc(cited_by_count)) |>
    head(20) |>
    select(doi, cited_by_count, publication_year, title) |>
    mutate(title = str_trunc(title, 60)) |>
    print(n = Inf)
}
