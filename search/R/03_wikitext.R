source(file.path(Sys.getenv("FLORA_PROJECT_ROOT", unset = getwd()), "R/02_exturlusage.R"))
wikitext_path <- function(lang, pageid) {
  if (!grepl("^[a-z]{2,3}$", lang) || !is.finite(pageid) || pageid < 1) stop("Invalid page key")
  d <- file.path(WIKITEXT_DIR, lang); dir_create(d)
  file.path(d, paste0(pageid, ".txt"))
}
fetch_wikitext_one <- function(lang, pageid) {
  resp <- mw_request(lang) |> req_url_query(action = "query", prop = "revisions",
    rvprop = "content|ids|timestamp", rvslots = "main", pageids = as.character(pageid),
    format = "json", maxlag = "5") |> req_perform()
  body <- mw_body(resp); page <- body$query$pages[[1]]
  if (!is.null(page$missing) || is.null(page$revisions)) stop("Page missing or unavailable: ", pageid)
  rev <- page$revisions[[1]]
  content <- rev$slots$main$`*` %||% rev$slots$main$content
  if (is.null(content)) stop("Revision content unavailable")
  list(title = page$title, revid = rev$revid, content = content,
       revision_timestamp = rev$timestamp, retrieved_at = format(Sys.time(), tz = "UTC", usetz = TRUE))
}
fetch_all_wikitext <- function(hits, log_every = 25) {
  pages <- hits |> filter(!is.na(pageid)) |> distinct(lang, pageid) |> arrange(lang, pageid)
  for (i in seq_len(nrow(pages))) {
    row <- pages[i, ]; path <- wikitext_path(row$lang, row$pageid)
    if (file_exists(path)) next
    res <- fetch_wikitext_one(row$lang, row$pageid) # fail visibly; completed pages remain cached
    tmp <- paste0(path, ".tmp")
    writeLines(enc2utf8(res$content), tmp, useBytes = TRUE)
    # Sidecar before text: interrupted writes never create a text-only new cache.
    write_json(res[setdiff(names(res), "content")], paste0(path, ".json"), auto_unbox = TRUE, pretty = TRUE)
    if (!file.rename(tmp, path)) stop("Cannot install wikitext cache")
    if (i %% log_every == 0 || i == nrow(pages)) cli_alert_info("[{i}/{nrow(pages)}] wikitext fetched")
  }
  meta_path <- file.path(DATA_DIR, "wikitext_meta.parquet")
  legacy <- if (file_exists(meta_path)) read_parquet(meta_path) else tibble()
  meta <- map_dfr(seq_len(nrow(pages)), function(i) {
    row <- pages[i, ]; path <- wikitext_path(row$lang, row$pageid)
    if (file_exists(paste0(path, ".json"))) {
      x <- read_json(paste0(path, ".json"), simplifyVector = TRUE)
      return(tibble(lang = row$lang, pageid = row$pageid, title = x$title, revid = x$revid,
        revision_timestamp = x$revision_timestamp, retrieved_at = x$retrieved_at))
    }
    old <- if (nrow(legacy)) filter(legacy, lang == row$lang, pageid == row$pageid) else tibble()
    tibble(lang = row$lang, pageid = row$pageid,
      title = if (nrow(old)) old$title[1] else NA_character_,
      revid = if (nrow(old)) old$revid[1] else NA_integer_,
      revision_timestamp = NA_character_, retrieved_at = NA_character_)
  })
  write_parquet(meta, meta_path)
  invisible(meta)
}
