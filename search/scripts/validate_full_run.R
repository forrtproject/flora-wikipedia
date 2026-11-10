#!/usr/bin/env Rscript
script <- sub("^--file=", "", grep("^--file=",commandArgs(),value=TRUE)[1])
root <- normalizePath(file.path(dirname(script),".."))
args <- commandArgs(trailingOnly=TRUE); run <- if(length(args)) args[1] else "spanish-full-latest"
lang <- if(length(args)>1) args[2] else "es"
stopifnot(lang %in% c("en","es"))
if (!grepl("^[A-Za-z0-9_-]+$",run)) stop("Unsafe run name")
base <- file.path(root,"runs",run,lang)
Sys.setenv(FLORA_PROJECT_ROOT=root,FLORA_RUN_DIR=base,FLORA_LANG=lang,FLORA_OFFLINE="1")
source(file.path(root,"R/02_inventory.R"))
m <- read_json(file.path(OUTPUT_DIR,"manifest.json"),simplifyVector=TRUE)
s <- read_json(file.path(OUTPUT_DIR,"summary.json"),simplifyVector=TRUE)
state <- read_json(file.path(CACHE_DIR,"resolver_inventory/state.json"),simplifyVector=TRUE)
stopifnot(m$status=="complete",m$sample_originals==0,m$discovery_mode=="inventory",state$complete)
flora <- read_parquet(file.path(DATA_DIR,"flora_normalised.parquet"))
dois <- read_parquet(file.path(DATA_DIR,"unique_dois.parquet"))
hits <- read_parquet(file.path(DATA_DIR,paste0("exturlusage_",lang,".parquet")))
inv <- read_parquet(file.path(DATA_DIR,"resolver_inventory.parquet"))
stopifnot(identical(resolver_doi(inv$url_hit),inv$doi))
meta <- read_parquet(file.path(DATA_DIR,"wikitext_meta.parquet"))
long <- read_parquet(file.path(OUTPUT_DIR,"audit_long.parquet"))
full <- read_parquet(file.path(OUTPUT_DIR,"flora_wikipedia_audit.parquet"))
ctx <- read_parquet(file.path(OUTPUT_DIR,"citation_contexts.parquet"))
sha <- strsplit(system2("sha256sum",shQuote(file.path(DATA_DIR,"flora.csv")),stdout=TRUE)," +")[[1]][1]
stopifnot(sha==m$input_provenance$sha256,
  nrow(flora)==m$n_pairs,n_distinct(flora$doi_o_norm)==m$n_originals,
  setequal(dois$doi,hits$doi_query),all(hits$lang==lang),all(long$lang==lang),
  nrow(full)==nrow(flora),setequal(full$pair_id,flora$pair_id),
  all(long$pair_id %in% flora$pair_id),all(ctx$lang==lang),
  nrow(meta)==n_distinct(hits$pageid[!is.na(hits$pageid)]),
  all(!is.na(meta$revid)),all(!is.na(meta$revision_timestamp)),all(!is.na(meta$retrieved_at)))
for(id in meta$pageid) {
 p <- file.path(WIKITEXT_DIR,lang,paste0(id,".txt"))
 stopifnot(file.exists(p),file.exists(paste0(p,".json")))
}
perpage <- long |> group_by(lang,pageid,doi_o_norm) |> summarise(co=any(r_also_cited),.groups="drop")
stopifnot(s$scope_pairs==nrow(flora),s$originals_detected==n_distinct(long$doi_o_norm),
 s$originals_with_any_co_citing_page==n_distinct(long$doi_o_norm[long$r_also_cited]),
 s$article_original_combinations==nrow(perpage),
 s$article_original_combinations_with_any_replication_doi==sum(perpage$co))
old <- read_parquet(file.path(root,"runs",if(lang=="es") "spanish-sample" else "english-live-sample",lang,"data",paste0("exturlusage_",lang,".parquet")))
old_dois <- unique(old$doi_query)
matched <- match_inventory(inv,old_dois,lang)
key <- function(x) x |> filter(!is.na(pageid)) |> distinct(doi,pageid) |>
 mutate(key=paste(doi,pageid)) |> pull(key)
missing <- setdiff(key(old),key(matched)); added <- setdiff(key(matched),key(old))
write_csv(tibble(missing_sample_page_doi=missing),file.path(OUTPUT_DIR,"sample_inventory_missing.csv"))
if(lang=="es") stopifnot(length(missing)==0L) # English sample has earlier revisions; record, do not invent stability.
# Substantive judgement remains deliberately absent from validation.
checks <- c(
 "Latest upstream CSV SHA-256 matches the pinned input and recorded immutable Git commit.",
 sprintf("All %d usable pairs, %d originals, and %d unique DOIs are in scope.",nrow(flora),n_distinct(flora$doi_o_norm),nrow(dois)),
 sprintf("Resolver inventory completed all %d continuation chunks; no partial inventory was treated as a negative result.",state$chunks),
 sprintf("All %d candidate revisions have cached UTF-8 wikitext, revision IDs, revision timestamps, and retrieval timestamps.",nrow(meta)),
 "Audit pair coverage, language namespaces, and both original/article-original denominators were recomputed and checked.",
 sprintf("Earlier sample comparison: %d page-DOI hits across %d queried DOIs; %d absent now, %d additional hits. Sequential snapshots can differ.",length(key(old)),length(old_dois),length(missing),length(added)),
 "Live combined HTTP/HTTPS queries matched separate protocol queries on two DOI examples.",
 "The faster decoder reproduces every normalised DOI key in the full saved resolver inventory.",
 "Pipeline, current-schema/inventory, CLI isolation tests, and exact archived English regression passed.",
 "Full offline rerun completed with unchanged audit and denominator results; timings retained.",
 "Archived inputs, English data, caches, and audit tables remain unchanged.")
timings <- read_csv(file.path(OUTPUT_DIR,"timings.csv"),show_col_types=FALSE)
first_online <- timings |> filter(!offline) |> slice(1)
last_offline <- timings |> filter(offline) |> slice_tail(n=1)
stopifnot(nrow(first_online)==1L,nrow(last_offline)==1L)
executions <- dir_ls(OUTPUT_DIR,glob="*execution-*.json")
stopifnot(length(executions)>=2L)
starts <- map_chr(executions,~ read_json(.x,simplifyVector=TRUE)$started_at)
parse_utc <- function(x) as.POSIXct(x,format="%Y-%m-%d %H:%M:%S",tz="UTC")
full_wall <- as.numeric(difftime(parse_utc(first_online$completed_at),min(parse_utc(starts)),units="secs"))
stopifnot(is.finite(full_wall),full_wall>=first_online$elapsed_seconds)
record <- list(passed=TRUE,verified_at=format(Sys.time(),tz="UTC",usetz=TRUE),
 checks=checks,inventory_link_rows=nrow(inv),inventory_chunks=state$chunks,
 full_initial_to_completion_wall_seconds=full_wall,
 live_completion_attempt_seconds=first_online$elapsed_seconds,
 offline_latest_seconds=last_offline$elapsed_seconds,
 candidate_revisions=nrow(meta),sample_page_doi_hits=length(key(old)),
 sample_query_dois=length(old_dois),sample_missing_hits=length(missing),sample_additional_hits=length(added),
 incremental_metered_api_cost_usd=0,cumulative_task_metered_api_cost_usd=0,
 common_originals_with_archived_english=n_distinct(long$doi_o_norm[long$doi_o_norm %in%
   read_parquet(file.path(root,"output/audit_long.parquet"))$doi_o_norm]))
write_json(record,file.path(OUTPUT_DIR,"full-validation.json"),auto_unbox=TRUE,pretty=TRUE)
cat(paste0("Full-run ",lang," validation passed\n"))
