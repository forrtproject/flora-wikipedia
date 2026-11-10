# Search: FLoRA DOI co-citation audit (English and Spanish)

This pipeline audits Wikipedia DOI strings for original–replication pairs in
[FLoRA](https://github.com/forrtproject/FReD-data/blob/main/output/flora.csv).
It finds pages linking to a DOI, retrieves their wikitext, and checks whether
both paired DOI strings occur on the same page. **A missing replication DOI
is not evidence that the article fails to acknowledge replication evidence.**
DOI-free references, secondary sources, historical context, and the substantive
relationship between studies require human adjudication; the review cards in
[`../editing-support/`](../editing-support/) build on this audit for that step.

All commands below are run from this `search/` folder. The R runner also works from any
directory when given its absolute path. No Wikipedia edits or messages are sent.

## Results

| Run | Scope | Originals detected | … with a co-citing page | Article–original combinations with a replication DOI |
|---|---|---|---|---|
| `english-full-gh` (5 Oct 2026) | 2,745 pairs, 2,567 originals | 586 | 65 | 80/1,193 |
| `spanish-full-latest` (3 Oct 2026) | 2,745 pairs, 2,567 originals | 159 (6.2%) | 12 (7.5%) | 13/201 (6.5%) |
| Archived English pilot (May 2026) | 1,925 pairs | 422 | 54 (12.8%) | 66/847 (7.8%) |
| `spanish-sample` (Oct 2026) | top 12 originals | 10 | 1 | 1/16 |

The original-level measure counts originals with **any** co-citing page; it is not the
share of citations. The article–original measure counts distinct page–original
combinations. Both are DOI-based screening measures. The Spanish sample is a
functionality check, not a coverage estimate.

**Full runs.** Both full runs use the same FLoRA pin: upstream file commit
`717fbaf0a35dc662e276d5860dba7faaf7142f93` (2 October 2026), with 3,056 CSV rows,
2,745 usable DOI pairs, 2,567 originals and 4,826 unique DOIs. The 311 rows missing
either DOI are outside the audit. A 5 October check
(`runs/inputs/flora-latest-20261005.csv`, file commit
`fe14eb96731f3ee9016e6fa65c73599a0f1b7bc7`) was byte-identical (SHA-256
`28748e8c6f02c428e06c98bd8ec0df4905c04324506b787691fa8639a36557d9`). English and Spanish
article snapshots were collected on different days; shared DOI keys are shared studies,
not translated page pairs or independent evidence.

For Spanish, the resolver inventory held 350,962 rows in 775 continuation chunks and led
to 182 candidate revisions, of which 167 contain a scoped original DOI. The run took
1,019 seconds (about 17 minutes) including a cache-preserving restart; the offline rerun
took 13.29 seconds and left audit, summary, context and adjudication files
byte-identical. The inventory recovers all 19 page–DOI hits from the earlier Spanish
sample.

**Archived pilot.** The 798 candidate pages include pages found via replication DOIs;
700 contain a detected scoped original. See [`output/REPORT.md`](output/REPORT.md) for
the corrected pilot interpretation.

Useful Spanish examples include **Automaticidad** (both Bargh 1996 and Doyen 2012 DOI
strings detected), **Penalización de la maternidad** (Correll 2007 present; paired
replication DOI not detected) and **Efecto de Stroop** (historical original citation
alongside review sources).

Incremental metered API cost for all runs: US$0.

## Setup and commands

Requires R (verified with R 4.6.1 on Linux) and internet access for live stages.
No credentials, translation services or paid APIs are needed.

```sh
Rscript R/setup.R
# Pin the latest FLoRA at an immutable upstream file commit:
python3 scripts/pin_flora.py --output runs/inputs/flora-latest.csv
# Full audit from a complete DOI-resolver link inventory (as used for both full runs):
Rscript R/run_audit.R --lang=en --run=english-full-gh --input=runs/inputs/flora-latest-20261003.csv --discovery=inventory
Rscript R/run_audit.R --lang=es --run=spanish-full-latest --input=runs/inputs/flora-latest-20261003.csv --discovery=inventory
# Reanalyse a frozen run without network access, and validate it:
Rscript R/run_audit.R --lang=en --run=english-full-gh --discovery=inventory --offline
Rscript scripts/validate_full_run.R english-full-gh en
Rscript scripts/validate_full_run.R spanish-full-latest
# Reproduce the archived English pilot offline:
Rscript R/run_audit.R --lang=en --run=english-regression --legacy --offline
# Spanish sample (top 12 originals by archived English page count) and a small English smoke test:
Rscript R/run_audit.R --lang=es --run=spanish-sample --sample=12
Rscript R/run_audit.R --lang=en --run=english-live-sample --sample=3
```

Repeat the identical command after an interruption to resume.

## How runs work

**Discovery.** `--discovery=inventory` enumerates all main-namespace doi.org links
(including subdomains such as dx.doi.org), caches each continuation chunk, and matches
URL-decoded, case-normalised DOI keys exactly against FLoRA. It retrieves wikitext only
for scoped candidate pages. The default per-DOI mode instead makes up to four discovery
requests per DOI (raw and slash-encoded, HTTP and HTTPS) plus continuation and page
retrieval; it suits small samples.

**Politeness and resumption.** Requests are serial, paced at two per second with
capacity one, honour Retry-After, use maxlag, and retry HTTP 429/5xx and Wikimedia
maxlag or rate-limit errors. Do not launch simultaneous full runs. Completed zero-hit
queries are cached; failed or partially paginated queries are not treated as negative.
Every completed DOI and page is checkpointed.

**Run directories.** Products live under `runs/<run>/<en|es>/{data,cache,output}`;
language namespaces isolate overlapping page IDs. A run has one writer, enforced by
`.lock`; if a process is killed, confirm it has stopped before removing that run's
`.lock`. Scope is pinned by input and selected-pair hashes: an existing run rejects a
different input, discovery mode or sample size, so use a new `--run` name for changed
scope. Cache content is frozen, not silently refreshed. `--input=CSV` copies the snapshot
and its provenance sidecar (source URL, commit date, acquisition time, SHA-256) into the
run.

`runs/` is ignored by Git. Keep run directories for the replication hackathon and the
early 2027 edit-a-thon, and share them as archives (`rsync -a` or zip).

**Archived pilot.** The tracked `data/`, `cache/` and `output/` folders are the May 2026
English pilot products; `run_audit.R` never writes to them. `--legacy` copies that
archive into a new namespace and keeps its narrower discovery coverage. The legacy
stage scripts in `R/` can overwrite the archive if run directly; use `run_audit.R`.

| Stage | Input/service | Cached output | Offline? |
|---|---|---|---|
| Pin and normalise FLoRA | supplied CSV | copied CSV, normalised pairs, scope CSV | yes |
| DOI discovery | Wikipedia MediaWiki API | `exturlusage_<lang>.parquet`, query times | after complete cache |
| Article retrieval | Wikipedia revision API | UTF-8 `.txt` and revision/time JSON sidecars | after complete cache |
| DOI extraction and paired joins | frozen wikitext and FLoRA | article DOIs, audit, raw contexts | yes |
| Summaries and review packet | preceding products | summary, adjudication CSV, DOI overlap | yes |

`R/setup.R` installs missing CRAN packages only. Arrow is optional; nanoparquet reads and
writes the Parquet files. Package versions, source hashes, Git revision, input
provenance, scope and timings are recorded in each run.

## Outputs

Each run's `output/` contains `manifest.json`, append-only `timings.csv`,
`summary.json`, per-execution provenance JSON, the paired audit (CSV/Parquet), a
per-original summary, raw contexts (CSV/Parquet), `adjudication_pairs.csv` and
`cross_language_doi_overlap.csv`. `summary.json` distinguishes original-level and
article–original denominators. DOI occurrences in the context file can repeat within a
paragraph and across pairs; they are not independent citations.

`cross_language_doi_overlap.csv` always compares a run with the archived May English
pilot, so for a new English run it is historical same-language overlap. Use the
handover's `current-cross-language-dois.json` to compare the two full runs.

For inventory discovery, the `queried_at` field on zero-hit rows records local
derivation time, not a DOI query; use `resolver_inventory/state.json` and chunk
timestamps for the discovery interval. The five principal audit products are the
deterministic replay contract.

## Review queue and Wikidata sample

```sh
python3 scripts/prepare_adjudication.py --run-dir runs/english-full-gh/en --run-dir runs/spanish-full-latest/es --output runs/editathon-review
# Edit a COPY of decisions.csv (scope, citation function, reason, sources, review fields), then reapply it:
python3 scripts/prepare_adjudication.py --run-dir runs/english-full-gh/en --run-dir runs/spanish-full-latest/es --output runs/editathon-review --decisions path/to/reviewed-decisions.csv
python3 scripts/reconcile_wikidata.py --packets runs/editathon-review/packets.json --output runs/wikidata-sample [--offline]
```

The queue groups article–original matches into packets with unmodified raw contexts,
ordered by language and article, never by outcome. Retain/drop/defer decisions describe
our queue, not whether a Wikipedia citation should be removed. Decisions are tied to
`reviewed_revision_id`; applying them to a changed revision is refused until re-review.
Queue rebuilds preserve an existing ledger. When a paper supports several claims, review
each separately. For OSC, Many Labs and SCORE, retain decisions require an explicit
specific-study match. `wikidata_only` means read-only reconciliation, never permission to
write. The editing support reads `runs/editathon-review/packets.json`.

The Wikidata sample covers four articles. It searches both main and scholarly query
graphs for exact DOI case variants and keeps raw responses; it creates no items and
writes nothing. It does not estimate Wikidata coverage.

The programme for using these queues is in [`../docs/editathon-plan.md`](../docs/editathon-plan.md).
FLoRA outcome codes never provide citable wording. `R/09_recommendations.R`, the
retired outcome-to-sentence generator, stops on entry; its source is kept as
[`docs/archive/09_recommendations.R.txt`](docs/archive/09_recommendations.R.txt).
`07_openalex.R` and `08_estimate_misses.R` are optional legacy enrichments outside the
default runner.

## Tests and private reports

```sh
bash scripts/verify.sh                  # all tests below plus English replay; logs to runs/verification
Rscript tests/test_pipeline.R
Rscript tests/test_inventory.R          # exact matching, encodings, resume, language isolation
Rscript tests/test_english_regression.R # after the english-regression replay
Rscript tests/test_runner.R             # needs the retained sample runs
python3 -m unittest discover -s tests -p 'test_*.py'
```

The archived English pilot reproduces exactly (54/422 and 66/847).

The `scripts/build_*review.py` builders write private review reports and download
bundles into a dedicated directory outside the checkout; they never start a server or
publish. For example:

```sh
python3 scripts/build_full_review.py --output-dir ../../flora-wikipedia-review-20261003
```

Serve only that directory, over the `tailscale ip -4` address. For an offline handover,
extract `code-and-docs.zip` into a checkout at the run manifest's base commit, then the
product archives; `--offline` replay makes no network requests.

## Limitations

- Discovery covers main-namespace DOI resolver links, not all Wikipedia text.
  Publisher-only links, some complex SICI DOIs, other encodings and DOI-free citations
  can be missed.
- The inherited DOI extractor expects a literal registrant slash and may truncate
  parentheses or special punctuation. Resolver matching strips query and fragment
  components, so literal `?` or `#` in a DOI suffix can be missed.
- DOI presence does not prove a substantive citation: DOIs can sit in comments or
  bibliographies and support no visible claim.
- Revisions are retrieved sequentially, not as one simultaneous edition state. The
  archived English pilot has revision IDs but no retrieval timestamps.
- Revision history, secondary-source quality, author/title matching and substantive
  acknowledgement are not audited. FLoRA's pair and outcome decisions are kept as
  supplied, including its worst-outcome summary rule; two optional replication metadata
  fields absent from current FLoRA stay NA.
