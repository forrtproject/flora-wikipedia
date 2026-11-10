source(file.path(Sys.getenv("FLORA_PROJECT_ROOT", unset = getwd()), "R/00_config.R"))

api_url <- function(lang = LANG) {
  if (length(lang) != 1L || !grepl("^[a-z]{2,3}$", lang)) stop("Invalid language")
  paste0("https://", lang, ".wikipedia.org/w/api.php")
}
is_mw_transient <- function(resp) {
  if (resp_status(resp) %in% c(429, 500, 502, 503, 504)) return(TRUE)
  if (resp_status(resp) != 200) return(FALSE)
  body <- tryCatch(resp_body_json(resp), error = function(e) NULL)
  !is.null(body$error$code) && body$error$code %in% c("maxlag", "ratelimited", "readonly")
}
mw_request <- function(lang) {
  assert_live()
  request(api_url(lang)) |>
    req_user_agent(USER_AGENT) |>
    req_timeout(45) |>
    req_throttle(capacity = 1, fill_time_s = 0.5, realm = "flora-wikimedia") |>
    req_retry(max_tries = 5, retry_on_failure = TRUE,
              backoff = ~ min(2^.x, 30), is_transient = is_mw_transient)
}
mw_body <- function(resp) {
  body <- resp_body_json(resp)
  if (!is.null(body$error)) stop("MediaWiki error: ", body$error$code)
  if (is.null(body$query)) stop("Malformed MediaWiki response")
  body
}
exturl_one <- function(lang, query, protocol = "", max_pages = 1000) {
  hits <- list(); continuation <- list()
  for (i in seq_len(max_pages)) {
    params <- c(list(action = "query", list = "exturlusage", euquery = query,
      eulimit = "500", euprotocol = protocol, eunamespace = "0",
      format = "json", maxlag = "5"), continuation)
    resp <- mw_request(lang) |> req_url_query(!!!params) |> req_perform()
    body <- mw_body(resp)
    hits <- c(hits, body$query$exturlusage)
    if (is.null(body$continue)) return(hits)
    continuation <- body$continue
  }
  stop("Pagination limit reached; query remains incomplete")
}
doi_query_variants <- function(doi) {
  encoded <- str_replace_all(doi, "/", "%2F")
  unique(c(paste0("doi.org/", doi), paste0("doi.org/", encoded),
           paste0("dx.doi.org/", doi), paste0("dx.doi.org/", encoded)))
}
exturl_for_doi <- function(lang, doi) {
  hits <- list()
  for (q in doi_query_variants(doi)) hits <- c(hits, exturl_one(lang, q, ""))
  if (length(hits) == 0) return(tibble(lang = character(), doi = character(),
    pageid = integer(), page_title = character(), url_hit = character()))
  tibble(lang = lang, doi = doi, pageid = map_int(hits, "pageid"),
    page_title = map_chr(hits, "title"), url_hit = map_chr(hits, "url")) |>
    distinct(pageid, .keep_all = TRUE)
}
run_exturlusage <- function(dois, lang = LANG, out_path,
                            log_every = 50, resume = TRUE) {
  dir_create(dirname(out_path))
  results <- if (resume && file_exists(out_path)) read_parquet(out_path) else
    tibble(lang = character(), doi_query = character(), doi = character(),
      pageid = integer(), page_title = character(), url_hit = character(), n_hits = integer())
  if (nrow(results) && any(results$lang != lang)) stop("Cache language mismatch")
  done <- unique(results$doi_query)
  todo <- setdiff(dois, done)
  cli_alert_info("To query on {lang}: {length(todo)} DOIs ({length(done)} cached)")
  failures <- list()
  for (i in seq_along(todo)) {
    doi <- todo[i]
    res <- tryCatch(exturl_for_doi(lang, doi), error = function(e) {
      failures[[length(failures) + 1L]] <<- list(doi = doi, error = conditionMessage(e))
      NULL
    })
    if (is.null(res)) next # A failed request is never a negative result.
    row <- if (nrow(res)) mutate(res, doi_query = doi, n_hits = nrow(res)) |>
      select(lang, doi_query, doi, pageid, page_title, url_hit, n_hits) else
      tibble(lang = lang, doi_query = doi, doi = doi, pageid = NA_integer_,
        page_title = NA_character_, url_hit = NA_character_, n_hits = 0L)
    row$queried_at <- format(Sys.time(), tz = "UTC", usetz = TRUE)
    results <- bind_rows(results, row)
    write_parquet(results, out_path) # checkpoint every completed DOI, including zero hits
    if (i %% log_every == 0 || i == length(todo)) cli_alert_info("[{i}/{length(todo)}] DOIs completed")
  }
  if (!file_exists(out_path)) write_parquet(results, out_path)
  if (length(failures)) {
    write_json(failures, paste0(out_path, ".errors.json"), pretty = TRUE, auto_unbox = TRUE)
    stop(length(failures), " DOI queries failed; rerun to resume. See .errors.json")
  }
  if (file_exists(paste0(out_path, ".errors.json"))) file_delete(paste0(out_path, ".errors.json"))
  invisible(results)
}
