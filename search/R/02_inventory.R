source(file.path(Sys.getenv("FLORA_PROJECT_ROOT", unset = getwd()), "R/02_exturlusage.R"))

# Enumerate the edition's DOI-resolver links once; doi.org includes subdomains.
# Complete continuation is required before absence can be interpreted as a zero hit.
resolver_doi <- function(url) {
  decoded <- curl::curl_unescape(url)
  decoded <- str_remove(decoded, regex("^https?://(?:[^/]+\\.)?doi\\.org/", ignore_case = TRUE))
  decoded <- str_remove(decoded, "[?#].*$")
  normalise_doi(decoded)
}
fetch_resolver_inventory <- function(lang = LANG, cache_dir = file.path(CACHE_DIR, "resolver_inventory"),
                                     max_chunks = 10000L) {
  dir_create(cache_dir)
  state_path <- file.path(cache_dir, "state.json")
  state <- if (file_exists(state_path)) read_json(state_path, simplifyVector = FALSE) else
    list(lang = lang, query = "doi.org", protocol = "", namespace = 0L,
         chunks = 0L, complete = FALSE, continuation = list())
  if (state$lang != lang) stop("Inventory cache language mismatch")
  if (!isTRUE(state$complete)) {
    for (i in seq_len(max_chunks)) {
      params <- c(list(action = "query", list = "exturlusage", euquery = "doi.org",
        euprotocol = "", eunamespace = "0", eulimit = "500", format = "json", maxlag = "5"),
        state$continuation)
      body <- mw_request(lang) |> req_url_query(!!!params) |> req_perform() |> mw_body()
      # Body first, state second: interrupted chunks are safely overwritten on resume.
      number <- as.integer(state$chunks) + 1L
      path <- file.path(cache_dir, sprintf("chunk-%06d.json", number))
      write_json(list(retrieved_at = format(Sys.time(), tz = "UTC", usetz = TRUE), body = body),
                 paste0(path, ".tmp"), auto_unbox = TRUE)
      if (!file.rename(paste0(path, ".tmp"), path)) stop("Cannot checkpoint inventory chunk")
      state$chunks <- number
      state$continuation <- body$continue %||% list()
      state$complete <- is.null(body$continue)
      state$updated_at <- format(Sys.time(), tz = "UTC", usetz = TRUE)
      write_json(state, paste0(state_path, ".tmp"), auto_unbox = TRUE, pretty = TRUE)
      if (!file.rename(paste0(state_path, ".tmp"), state_path)) stop("Cannot checkpoint inventory continuation")
      if (number %% 25L == 0L || state$complete) cli_alert_info("DOI inventory: {number} chunks; complete={state$complete}")
      if (state$complete) break
    }
    if (!isTRUE(state$complete)) stop("Inventory chunk limit reached; resume to continue")
  }
  rows <- map_dfr(seq_len(state$chunks), function(i) {
    x <- read_json(file.path(cache_dir, sprintf("chunk-%06d.json", i)), simplifyVector = FALSE)
    hits <- x$body$query$exturlusage
    if (!length(hits)) return(tibble(lang = character(), pageid = integer(),
      page_title = character(), url_hit = character(), queried_at = character()))
    tibble(lang = lang, pageid = map_int(hits, "pageid"), page_title = map_chr(hits, "title"),
           url_hit = map_chr(hits, "url"), queried_at = x$retrieved_at)
  })
  rows |> mutate(doi = resolver_doi(url_hit))
}
match_inventory <- function(inventory, dois, lang = LANG) {
  hits <- inventory |> filter(doi %in% dois) |> distinct(doi, pageid, .keep_all = TRUE) |>
    group_by(doi) |> mutate(n_hits = n()) |> ungroup() |> mutate(doi_query = doi) |>
    select(lang, doi_query, doi, pageid, page_title, url_hit, n_hits, queried_at)
  absent <- setdiff(dois, hits$doi)
  zero <- tibble(lang = lang, doi_query = absent, doi = absent, pageid = NA_integer_,
    page_title = NA_character_, url_hit = NA_character_, n_hits = 0L,
    queried_at = format(Sys.time(), tz = "UTC", usetz = TRUE))
  bind_rows(hits, zero)
}
run_inventory <- function(dois, lang = LANG, out_path) {
  inventory_path <- file.path(DATA_DIR, "resolver_inventory.parquet")
  if (file_exists(inventory_path)) {
    state <- read_json(file.path(CACHE_DIR, "resolver_inventory/state.json"), simplifyVector = TRUE)
    if (!isTRUE(state$complete) || state$lang != lang) stop("Inventory cache is incomplete or from another edition")
    inventory <- read_parquet(inventory_path)
    if (any(inventory$lang != lang)) stop("Inventory table language mismatch")
  } else {
    inventory <- fetch_resolver_inventory(lang)
    write_parquet(inventory, inventory_path)
  }
  results <- match_inventory(inventory, dois, lang)
  write_parquet(results, out_path)
  invisible(results)
}
