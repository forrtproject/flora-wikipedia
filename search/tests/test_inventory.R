script <- sub("^--file=", "", grep("^--file=", commandArgs(), value = TRUE)[1])
root <- normalizePath(file.path(dirname(script), "..")); tmp <- tempfile("inventory-tests-")
Sys.setenv(FLORA_PROJECT_ROOT=root, FLORA_RUN_DIR=tmp, FLORA_LANG="es", FLORA_OFFLINE="0")
source(file.path(root,"R/02_inventory.R"))
check <- function(ok,label) { if (!isTRUE(ok)) stop(label); cat("PASS:",label,"\n") }
x <- tibble(lang="es",pageid=c(1L,2L),page_title=c("España","Réplicas"),
  url_hit=c("http://dx.doi.org/10.1234%2FABC","https://doi.org/10.1234/abc"),queried_at="UTC")
x$doi <- resolver_doi(x$url_hit)
y <- match_inventory(x,c("10.1234/abc","10.1234/absent"))
check(nrow(y)==3L && sum(y$n_hits==0)==1L && all(y$doi==c("10.1234/abc","10.1234/abc","10.1234/absent")),
      "inventory URL decoding, aliases, case, and negative rows")
check(!"10.1234/ab" %in% y$doi, "inventory DOI match does not treat prefix as a study")
original_request <- mw_request; original_perform <- req_perform
mw_request <- function(lang) request("https://example.test")
calls <- character()
req_perform <- function(req) {
  calls <<- c(calls,req$url)
  if (length(calls)==2L) stop("interrupted inventory")
  body <- list(query=list(exturlusage=list(list(pageid=1L,title="España",url="https://doi.org/10.1234/abc"))),
               continue=list(eucontinue="NEXT",continue="-||"))
  response(headers=list(`Content-Type`="application/json"), body=charToRaw(toJSON(body,auto_unbox=TRUE)))
}
cache <- file.path(CACHE_DIR,"resolver_inventory")
check(inherits(try(fetch_resolver_inventory("es",cache),silent=TRUE),"try-error"), "inventory failure surfaced")
state <- read_json(file.path(cache,"state.json"),simplifyVector=TRUE)
check(state$chunks==1 && !state$complete && state$continuation$eucontinue=="NEXT", "completed inventory chunks and continuation checkpointed")
calls <- character()
req_perform <- function(req) {
  calls <<- c(calls,req$url)
  body <- list(query=list(exturlusage=list(list(pageid=2L,title="Réplicas",url="http://dx.doi.org/10.1234%2FABC"))))
  response(headers=list(`Content-Type`="application/json"), body=charToRaw(toJSON(body,auto_unbox=TRUE)))
}
inv <- fetch_resolver_inventory("es",cache)
check(length(calls)==1L && grepl("eucontinue=NEXT",calls[1]) && nrow(inv)==2L,
      "inventory resumes at saved continuation without losing earlier chunks")
calls <- character(); OFFLINE <- TRUE; inv <- fetch_resolver_inventory("es",cache)
check(length(calls)==0 && nrow(inv)==2L, "complete inventory is reusable offline without requests")
check(inherits(try(fetch_resolver_inventory("en",cache),silent=TRUE),"try-error"), "inventory rejects edition mismatch")
write_parquet(inv,file.path(DATA_DIR,"resolver_inventory.parquet"))
calls <- character(); r <- run_inventory(c("10.1234/abc","10.1234/absent"),"es",file.path(DATA_DIR,"matched.parquet"))
check(length(calls)==0 && nrow(r)==3L, "online resume reuses complete normalised inventory table")
mw_request <- original_request; req_perform <- original_perform
# Current upstream removes optional fields: retain their absence, never impute outcomes.
f <- read_csv(file.path(root,"data/flora.csv"),show_col_types=FALSE) |> head(5) |>
  select(-self_identified_replication,-replication_intent_confidence)
write_csv(f,file.path(DATA_DIR,"flora.csv"))
source(file.path(root,"R/01_load_flora.R"))
check(all(is.na(flora$self_identified_replication)) && all(is.na(flora$replication_intent_confidence)) &&
      identical(flora$outcome, f$outcome[!is.na(f$doi_o) & !is.na(f$doi_r)]),
      "latest FLoRA missing optional metadata stays NA; outcomes preserved")
unlink(tmp,recursive=TRUE)
cat("All inventory tests passed\n")
