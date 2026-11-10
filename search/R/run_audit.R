#!/usr/bin/env Rscript
# Invoke from any directory: Rscript /path/to/repo/R/run_audit.R ...
main <- function() {
  script <- sub("^--file=", "", grep("^--file=", commandArgs(), value = TRUE)[1])
  root <- normalizePath(file.path(dirname(script), ".."))
  args <- commandArgs(trailingOnly = TRUE)
  option <- function(name, default) {
    x <- grep(paste0("^--", name, "="), args, value = TRUE)
    if (length(x) > 1L) stop("Duplicate option: ", name)
    if (length(x)) sub(paste0("^--", name, "="), "", x) else default
  }
  known <- grepl("^--(lang|run|sample|input|discovery)=", args) | args %in% c("--offline", "--legacy", "--help")
  if (any(!known)) stop("Unknown option: ", paste(args[!known], collapse = " "))
  if ("--help" %in% args) {
    cat("Rscript R/run_audit.R --lang=en|es --run=NAME [--sample=N] [--input=CSV] [--discovery=per-doi|inventory] [--offline] [--legacy]\n",
        "Default full scope; sample selects top N originals by archived English page count.\n",
        "--legacy copies archived English discovery/cache, with the original query limitations.\n")
    quit(status = 0)
  }
  lang <- option("lang", "en"); run <- option("run", "audit")
  sample_n <- as.integer(option("sample", "0"))
  if (!lang %in% c("en", "es")) stop("Supported editions: en, es")
  if (!grepl("^[A-Za-z0-9_-]+$", run)) stop("Run name must contain only letters, digits, _ or -")
  if (is.na(sample_n) || sample_n < 0) stop("Invalid sample size")
  discovery <- option("discovery", "per-doi")
  if (!discovery %in% c("per-doi", "inventory")) stop("Invalid discovery mode")
  legacy <- "--legacy" %in% args
  if (legacy && discovery != "per-doi") stop("Legacy import requires per-doi discovery")
  if (legacy && lang != "en") stop("Legacy import is English only")
  run_dir <- file.path(root, "runs", run, lang)
  Sys.setenv(FLORA_PROJECT_ROOT = root, FLORA_LANG = lang, FLORA_RUN_DIR = run_dir,
             FLORA_OFFLINE = if ("--offline" %in% args) "1" else "0")
  source(file.path(root, "R/00_config.R"), local = TRUE)
  lock_dir <- file.path(run_dir, ".lock")
  if (!dir.create(lock_dir, showWarnings = FALSE))
    stop("Run is locked. Do not run two writers in the same namespace. If a process was killed, verify it has stopped before removing ", lock_dir)
  on.exit(unlink(lock_dir, recursive = TRUE), add = TRUE)
  writeLines(as.character(Sys.getpid()), file.path(lock_dir, "pid"))
  start <- Sys.time()
  # Pin an explicit snapshot or the supplied clone snapshot; never silently refresh.
  requested_input <- option("input", file.path(root, "data/flora.csv"))
  if (!file_exists(requested_input)) stop("Input CSV not found: ", requested_input)
  input <- file.path(DATA_DIR, "flora.csv")
  if (!file_exists(input)) {
    file_copy(requested_input, input)
    provenance_path <- paste0(requested_input, ".provenance.json")
    if (file_exists(provenance_path)) file_copy(provenance_path, file.path(DATA_DIR, "flora_source.json"))
  }
  if (any(grepl("^--input=", args)) && unname(tools::md5sum(requested_input)) != unname(tools::md5sum(input)))
    stop("Explicit input differs from pinned run snapshot; choose a new --run name")
  input_provenance <- if (file_exists(file.path(DATA_DIR, "flora_source.json")))
    read_json(file.path(DATA_DIR, "flora_source.json"), simplifyVector = TRUE) else NULL
  manifest_path <- file.path(OUTPUT_DIR, "manifest.json")
  input_md5 <- unname(tools::md5sum(input))
  if (file_exists(manifest_path)) {
    old <- read_json(manifest_path, simplifyVector = TRUE)
    old_discovery <- old$discovery_mode %||% "per-doi"
    if (old_discovery != discovery || old$input_md5 != input_md5 || old$sample_originals != sample_n || old$legacy_import != legacy)
      stop("Run scope changed; choose a new --run name")
  }
  source(file.path(root, "R/01_load_flora.R"), local = TRUE)
  if (sample_n > 0) {
    baseline <- read_csv(file.path(root, "output/per_original_summary.csv"), show_col_types = FALSE)
    chosen <- baseline |> arrange(desc(n_articles_citing), doi_o_norm) |> head(sample_n) |> pull(doi_o_norm)
    flora <- flora |> filter(doi_o_norm %in% chosen)
    unique_dois <- unique_dois |> filter(doi %in% c(flora$doi_o_norm, flora$doi_r_norm))
    write_parquet(flora, file.path(DATA_DIR, "flora_normalised.parquet"))
    write_parquet(unique_dois, file.path(DATA_DIR, "unique_dois.parquet"))
  }
  scope <- flora |> select(pair_id, doi_o_norm, doi_r_norm)
  scope_path <- file.path(DATA_DIR, "scope.csv")
  if (file_exists(scope_path)) {
    previous_scope <- read_csv(scope_path, show_col_types = FALSE)
    if (!isTRUE(all.equal(as.data.frame(scope), as.data.frame(previous_scope), check.attributes = FALSE)))
      stop("Selected pairs changed; choose a new --run name")
  }
  write_csv(scope, scope_path)
  manifest <- list(language = lang, endpoint = paste0("https://", lang, ".wikipedia.org/w/api.php"),
    input_source = if (is.null(input_provenance)) "https://github.com/forrtproject/FReD-data/blob/main/output/flora.csv" else input_provenance$source_url,
    input_provenance = input_provenance,
    input_md5 = input_md5, input_pin = if (is.null(input_provenance)) "supplied or explicit local snapshot; not live refresh" else "upstream CSV pinned at recorded immutable Git commit",
    discovery_mode = discovery, sample_originals = sample_n, legacy_import = legacy, n_pairs = nrow(flora),
    n_originals = n_distinct(flora$doi_o_norm), n_dois = nrow(unique_dois),
    started_at = format(start, tz = "UTC", usetz = TRUE),
    git_head = system2("git", c("-C", shQuote(root), "rev-parse", "HEAD"), stdout = TRUE),
    incremental_metered_cost_usd = 0, status = "started",
    query_coverage = if (discovery == "inventory") "complete main-namespace doi.org/subdomain HTTP/HTTPS link inventory; URL-decoded DOI exact match" else if (legacy) "archived HTTPS doi.org raw/encoded only" else "HTTP/HTTPS doi.org and dx.doi.org; raw and slash-encoded",
    source_md5 = as.list(setNames(tools::md5sum(dir_ls(file.path(root, "R"), glob = "*.R")),
      basename(dir_ls(file.path(root, "R"), glob = "*.R")))),
    scope_md5 = unname(tools::md5sum(file.path(DATA_DIR, "scope.csv"))),
    offline = OFFLINE)
  execution_manifest <- file.path(OUTPUT_DIR, paste0("execution-",
    format(start, "%Y%m%dT%H%M%OS6", tz = "UTC"), ".json"))
  write_json(manifest, manifest_path, auto_unbox = TRUE, pretty = TRUE)
  write_json(manifest, execution_manifest, auto_unbox = TRUE, pretty = TRUE)
  if (legacy) {
    for (f in c("exturlusage_en.parquet", "wikitext_meta.parquet")) {
      target <- file.path(DATA_DIR, f)
      if (!file_exists(target)) file_copy(file.path(root, "data", f), target)
    }
    dir_create(file.path(WIKITEXT_DIR, "en"))
    files <- dir_ls(file.path(root, "cache/wikitext/en"), glob = "*.txt")
    for (f in files) {
      target <- file.path(WIKITEXT_DIR, "en", basename(f))
      if (!file_exists(target)) file_copy(f, target)
    }
  }
  source(file.path(root, "R/03_wikitext.R"), local = TRUE)
  source(file.path(root, "R/05_audit.R"), local = TRUE)
  if (discovery == "inventory") source(file.path(root, "R/02_inventory.R"), local = TRUE)
  hits_path <- file.path(DATA_DIR, paste0("exturlusage_", lang, ".parquet"))
  if (OFFLINE) {
    if (!file_exists(hits_path)) stop("Offline discovery cache missing")
    hits <- read_parquet(hits_path)
    if (any(hits$lang != lang) || length(setdiff(unique_dois$doi, hits$doi_query)))
      stop("Discovery cache incomplete; resume online first")
  } else if (discovery == "inventory") hits <- run_inventory(unique_dois$doi, lang, hits_path)
  else hits <- run_exturlusage(unique_dois$doi, lang, hits_path, log_every = 5)
  hits <- hits |> filter(doi_query %in% unique_dois$doi)
  # Prevent pages from a previous broader scope entering the selected audit.
  write_parquet(hits, hits_path)
  fetch_all_wikitext(hits)
  audit <- build_audit()
  contexts <- build_contexts()
  source(file.path(root, "R/06_analysis.R"), local = TRUE)
  source(file.path(root, "R/10_review.R"), local = TRUE)
  manifest$status <- "complete"
  manifest$elapsed_seconds <- as.numeric(difftime(Sys.time(), start, units = "secs"))
  manifest$completed_at <- format(Sys.time(), tz = "UTC", usetz = TRUE)
  manifest$successful_discovery_dois <- n_distinct(hits$doi_query)
  manifest$candidate_pages <- n_distinct(hits$pageid[!is.na(hits$pageid)])
  manifest$packages <- as.list(vapply(c("httr2", "dplyr", "stringr", "nanoparquet"),
    function(p) if (requireNamespace(p, quietly = TRUE)) as.character(packageVersion(p)) else "not installed", character(1)))
  write_json(manifest, manifest_path, auto_unbox = TRUE, pretty = TRUE)
  write_json(manifest, execution_manifest, auto_unbox = TRUE, pretty = TRUE)
  # Append measured runs instead of overwriting live timing on an offline rerun.
  write_csv(tibble(completed_at = manifest$completed_at, offline = OFFLINE,
    elapsed_seconds = manifest$elapsed_seconds, cost_usd = 0),
    file.path(OUTPUT_DIR, "timings.csv"), append = file_exists(file.path(OUTPUT_DIR, "timings.csv")))
  cat(sprintf("\nCompleted %s: %.2f seconds; incremental metered cost US$0\nOutputs: %s\n",
              lang, manifest$elapsed_seconds, OUTPUT_DIR))

}
main()
