script <- sub("^--file=", "", grep("^--file=", commandArgs(), value = TRUE)[1])
root <- normalizePath(file.path(dirname(script), ".."))
tmp <- tempfile("flora-tests-"); dir.create(tmp)
Sys.setenv(FLORA_PROJECT_ROOT = root, FLORA_RUN_DIR = tmp, FLORA_LANG = "es", FLORA_OFFLINE = "0")
source(file.path(root, "R/03_wikitext.R"))
source(file.path(root, "R/05_audit.R"))
check <- function(ok, name) { if (!isTRUE(ok)) stop(name); cat("PASS:", name, "\n") }
check(api_url("es") == "https://es.wikipedia.org/w/api.php" &&
      api_url("en") == "https://en.wikipedia.org/w/api.php", "endpoint selection")
check(inherits(try(api_url("../en"), silent = TRUE), "try-error"), "unsafe language rejected")
check(wikitext_path("es", 123) != wikitext_path("en", 123), "same page ID isolated by language")
check(DATA_DIR != file.path(root, "data") && OUTPUT_DIR != file.path(root, "output"), "run isolation")
check(length(doi_query_variants("10.1234/abc")) == 4L, "encoded and dx DOI discovery")
text <- "== Réplicas y discusión ==\n\nUna revisión previa.<ref>Anterior</ref>\n\nEl hallazgo se estudió en España.<ref>{{cita publicación|título=Psicología y emoción|doi=10.1234/abc}}</ref>\n\nTambién se discutió 10.1234/def fuera de una referencia.\n\n== Referencias ==\n"
writeLines(enc2utf8(text), wikitext_path("es", 123), useBytes = TRUE)
ctx <- extract_contexts("es", 123, c("10.1234/abc", "10.1234/def"))
check(nrow(ctx) == 2 && ctx$section[1] == "Réplicas y discusión" &&
      grepl("España", ctx$paragraph[1]) && grepl("Psicología", ctx$ref_block[1]), "Spanish UTF-8 raw context")
check(is.na(ctx$ref_block[2]), "previous closed ref cannot enclose later prose DOI")
writeLines("<ref name='x'/> texto 10.1234/def <ref>posterior</ref>", wikitext_path("es", 124))
check(is.na(extract_contexts("es", 124, "10.1234/def")$ref_block), "self-closing ref not enclosing")
writeLines("10.1234/english", wikitext_path("en", 123))
check(!"10.1234/english" %in% build_article_dois("es")$doi, "article extraction excludes other edition")
check(identical(extract_dois_from_text("{{cite journal|doi=10.1234/ABC}}"), "10.1234/abc"), "English DOI extraction contract")
original_fetch <- exturl_for_doi
calls <- character()
exturl_for_doi <- function(lang, doi) {
  calls <<- c(calls, doi)
  if (doi == "10.1234/fail") stop("transient fixture failure")
  tibble(lang = character(), doi = character(), pageid = integer(), page_title = character(), url_hit = character())
}
out <- file.path(DATA_DIR, "test.parquet")
check(inherits(try(run_exturlusage(c("10.1234/zero", "10.1234/fail"), "es", out), silent = TRUE), "try-error"), "failure surfaced")
check(identical(read_parquet(out)$doi_query, "10.1234/zero"), "failed DOI never checkpointed as zero")
exturl_for_doi <- function(lang, doi) {
  calls <<- c(calls, doi)
  tibble(lang = character(), doi = character(), pageid = integer(), page_title = character(), url_hit = character())
}
calls <- character()
run_exturlusage(c("10.1234/zero", "10.1234/fail"), "es", out)
check(identical(calls, "10.1234/fail"), "resume retries only failed DOI")
calls <- character(); run_exturlusage(c("10.1234/zero", "10.1234/fail"), "es", out)
check(length(calls) == 0, "zero-hit queries cached; repeat makes no requests")
check(inherits(try(run_exturlusage("10.1234/zero", "en", out), silent = TRUE), "try-error"), "mixed language discovery cache rejected")
exturl_for_doi <- original_fetch
# Real HTTP retry path: 429, HTTP 200 maxlag, then success.
portfile <- file.path(tmp, "port")
system2("python3", c(shQuote(file.path(root, "tests/retry_server.py")), shQuote(portfile)),
        wait = FALSE, stdout = file.path(tmp, "server.log"), stderr = file.path(tmp, "server.err"))
for (i in 1:50) { if (file.exists(portfile)) break; Sys.sleep(.1) }
port <- readLines(portfile)
original_api <- api_url
api_url <- function(lang) paste0("http://127.0.0.1:", port)
b <- mw_request("es") |> req_perform() |> mw_body()
check(b$query$requests == 3, "actual HTTP retries 429 and maxlag")
api_url <- original_api
# Revision retrieval interruption: saved page sidecars recover metadata on resume.
original_page_fetch <- fetch_wikitext_one
page_calls <- integer()
fetch_wikitext_one <- function(lang, pageid) {
  page_calls <<- c(page_calls, pageid)
  if (pageid == 202L) stop("interrupted page fixture")
  list(title = "Página", revid = 123L, content = "España 10.1234/abc",
       revision_timestamp = "2026-01-01T00:00:00Z", retrieved_at = "2026-10-03 00:00:00 UTC")
}
page_hits <- tibble(lang = "es", pageid = c(201L, 202L))
check(inherits(try(fetch_all_wikitext(page_hits), silent = TRUE), "try-error") &&
      file.exists(wikitext_path("es", 201)) && !file.exists(wikitext_path("es", 202)),
      "interrupted page fetch preserves completed cache only")
fetch_wikitext_one <- function(lang, pageid) {
  page_calls <<- c(page_calls, pageid)
  list(title = "Página", revid = 124L, content = "Réplicas 10.1234/abc",
       revision_timestamp = "2026-02-01T00:00:00Z", retrieved_at = "2026-10-03 00:00:00 UTC")
}
page_calls <- integer(); m <- fetch_all_wikitext(page_hits)
check(identical(page_calls, 202L) && nrow(m) == 2 && all(!is.na(m$revision_timestamp)),
      "page resume recovers sidecar provenance and fetches only unfinished page")
page_calls <- integer(); fetch_all_wikitext(page_hits)
check(length(page_calls) == 0, "cached page rerun makes no fetches")
fetch_wikitext_one <- original_page_fetch
# Continuation cannot silently become a successful zero-hit result.
original_request <- mw_request; original_perform <- req_perform
mw_request <- function(lang) request("https://example.test")
request_urls <- character()
req_perform <- function(req) {
  request_urls <<- c(request_urls, req$url)
  body <- list(query = list(exturlusage = list(list(pageid = 1L, title = "Página", url = "https://doi.org/10.1234/abc"))))
  if (length(request_urls) == 1L) body$continue <- list(euoffset = "NEXT", continue = "-||")
  httr2::response(headers = list(`Content-Type` = "application/json"),
                  body = charToRaw(jsonlite::toJSON(body, auto_unbox = TRUE)))
}
h <- exturl_one("es", "doi.org/10.1234/abc")
check(length(h) == 2 && grepl("euoffset=NEXT", request_urls[2]), "pagination follows complete continuation")
request_urls <- character()
check(inherits(try(exturl_one("es", "doi.org/10.1234/abc", max_pages = 1), silent = TRUE), "try-error"),
      "pagination cap leaves query incomplete")
mw_request <- original_request; req_perform <- original_perform
OFFLINE <- TRUE
check(inherits(try(mw_request("es"), silent = TRUE), "try-error"), "offline mode blocks network")
# Empty discovery must still produce all zero rows and typed context files.
f <- read_parquet(file.path(root, "data/flora_normalised.parquet")) |> head(1)
write_parquet(f, file.path(DATA_DIR, "flora_normalised.parquet"))
write_parquet(tibble(lang = "es", doi_query = f$doi_o_norm, doi = f$doi_o_norm,
  pageid = NA_integer_, page_title = NA_character_, url_hit = NA_character_, n_hits = 0L),
  file.path(DATA_DIR, "exturlusage_es.parquet"))
a <- build_audit(); c <- build_contexts()
check(nrow(a) == 1 && a$n_pages_citing_o == 0 && nrow(c) == 0,
      "zero-hit audit and context outputs remain usable")
unlink(tmp, recursive = TRUE)
cat("All pipeline tests passed\n")
