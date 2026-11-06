# FLoRA Wikipedia DOI audit (English and Spanish)

This pipeline audits Wikipedia DOI strings for original–replication pairs in
[FLoRA](https://github.com/forrtproject/FReD-data/blob/main/output/flora.csv).
It finds pages linking to a DOI, retrieves their wikitext, and checks whether
both paired DOI strings occur on the same page. **A missing replication DOI
is not evidence that the article fails to acknowledge replication evidence.**
DOI-free references, secondary sources, historical context, and the substantive
relationship between studies require human adjudication.

The review-card prototype built on this audit (`prototype/`) is published as a
work in progress at https://forrt.org/flora-wikipedia/. The earlier static demo
pages now live in
[LukasWallrich/flora-wikipedia-demo](https://github.com/LukasWallrich/flora-wikipedia-demo).

## Setup and one-command runs

Requires R (verified with R 4.6.1 on Linux) and internet access for live stages.
Run from this checkout, or use the absolute script path from another directory.
No credentials, translation services, or paid APIs are needed.

```sh
Rscript R/setup.R
# Reproduce the complete archived English pilot without network access:
Rscript R/run_audit.R --lang=en --run=english-regression --legacy --offline
# Spanish sample: top 12 originals by archived English page count, all their pairs:
Rscript R/run_audit.R --lang=es --run=spanish-sample --sample=12
# Reanalyse the same frozen Spanish sample without network access:
Rscript R/run_audit.R --lang=es --run=spanish-sample --sample=12 --offline
# Small live English smoke audit:
Rscript R/run_audit.R --lang=en --run=english-live-sample --sample=3
# Pin latest FLoRA at an immutable upstream file commit (explicit acquisition):
python3 scripts/pin_flora.py --output runs/inputs/flora-latest.csv
# Full Spanish audit using a complete DOI-resolver link inventory:
Rscript R/run_audit.R --lang=es --run=spanish-full-latest --input=runs/inputs/flora-latest.csv --discovery=inventory
# Reanalyse the frozen full run offline:
Rscript R/run_audit.R --lang=es --run=spanish-full-latest --discovery=inventory --offline
# Full fresh English discovery:
Rscript R/run_audit.R --lang=en --run=english-fresh
```

Repeat the identical command after interruption to resume. Completed zero-hit
queries are cached; failed or partially paginated DOI queries are not treated
as negative results. Every completed DOI and page is checkpointed. The default per-DOI mode makes up to four discovery requests per ordinary
DOI plus continuation and page retrieval; empty `euprotocol` combines HTTP
and HTTPS, verified against separate queries on a small live comparison.
`--discovery=inventory` instead enumerates all main-namespace doi.org links
(including subdomains such as dx.doi.org), caches each continuation chunk,
and matches URL-decoded, case-normalised DOI keys exactly against FLoRA.
This is more efficient for a full edition audit. It still retrieves wikitext
only for scoped candidate pages and does not assess all Spanish references. Requests are serial, paced at two per second with capacity
one, honour Retry-After, use maxlag, and retry HTTP 429/5xx and Wikimedia
maxlag/rate-limit errors. Do not launch simultaneous full runs.

The clone snapshot was not the latest FLoRA. The October follow-up pins
upstream file commit `717fbaf0a35dc662e276d5860dba7faaf7142f93` (2 October
2026): 3,056 CSV rows, 2,745 usable DOI pairs, 2,567 originals, and 4,826
unique DOIs. The 311 rows missing either DOI remain outside this audit.
`pin_flora.py` records the immutable source URL, commit date, acquisition UTC
time, and SHA-256 in a sidecar. `--input=CSV` copies the chosen snapshot and
its sidecar into a new run. An existing run rejects a different input or
discovery mode. Current FLoRA no longer includes two optional replication
metadata fields; the loader retains those as NA without imputing labels.

New products live under `runs/<run>/<en|es>/{data,cache,output}`. Language
namespaces isolate overlapping page IDs and files. Existing `data/`, `cache/`,
and `output/` are archived pilot products; the new runner never
writes to them. `--legacy` explicitly copies the English archive into a new
namespace and retains its narrower discovery coverage. Legacy individual
stage scripts remain available from the repository root, but can overwrite
legacy products; use `run_audit.R` for safe reruns.

A run directory has one writer, enforced by `.lock`. If the process is killed
without cleanup, confirm the recorded process has stopped before removing
that run's `.lock`. Use a different `--run` for fresh discovery or changed
scope. Scope is pinned by input and selected-pair hashes, and changing the
sample option in an existing namespace is rejected. Cache content is frozen,
not silently refreshed. Keep run directories for the 11–13 November replication
hackathon and early 2027 edit-a-thon; they are ignored by Git, so copy them with
`rsync -a` or archive them for collaborators rather than expecting a clone to
contain them.

## Stages and dependencies

| Stage | Input/service | Cached output | Offline? |
|---|---|---|---|
| Pin and normalise FLoRA | supplied `data/flora.csv` | copied CSV, normalised pairs, scope CSV | yes |
| DOI discovery | selected Wikipedia MediaWiki API | `exturlusage_<lang>.parquet`, query UTC times | after complete cache |
| Candidate article retrieval | selected Wikipedia revision API | UTF-8 `.txt` and revision/time JSON sidecars | after complete cache |
| DOI extraction and paired joins | frozen wikitext and FLoRA | article DOIs, audit, raw contexts | yes |
| Summaries and review packet | preceding products, archived English overlap | summary, adjudication CSV, cross-language DOI overlap | yes |

`R/setup.R` installs missing CRAN packages only. Arrow is optional; nanoparquet
reads/writes the existing Parquet files without compiling Arrow. Both backends
produce Parquet, not a substitute file format. No environment is automatically
installed during an audit. Package versions, source hashes, Git base revision,
input provenance, successful scope, and timings are recorded in each run.

The optional legacy `07_openalex.R` and `08_estimate_misses.R` are outside the
default runner; `09_recommendations.R` is retired and refuses to run. They are not needed to
rerun the DOI audit. OpenAlex is an additional live enrichment, not a required
or free-cost assumption; its existing enrichment is preserved. The old
recommendations ranked candidates and created outcome-based insertion sentences
and cite templates. Those historical sentences were not substantively adjudicated.
For Spanish, `10_review.R` supplies study metadata, revision links, a Spanish
review prompt, and raw contexts; it does **not** translate article text or
generate blanket insertion sentences. Named reference reuse is left in raw
wikitext and may require reading the full page.

## Validation and results

```sh
Rscript tests/test_pipeline.R
Rscript R/run_audit.R --lang=en --run=english-regression --legacy --offline
Rscript tests/test_english_regression.R
# Requires the retained Spanish sample products:
Rscript tests/test_runner.R
```

The archived English audit and per-original summary reproduce exactly:
**54/422 (12.8%)** is the share of detected originals with **any** co-citing
page, not the share of citations. The separate article–original measure is
**66/847 (7.8%)**. The 798 candidate pages include pages found via replication
DOIs; only 700 contain a detected scoped original. See
[`output/REPORT.md`](output/REPORT.md) for corrected pilot interpretation.

The October 2026 live Spanish sample detected 10/12 selected originals on
16 pages; one of the 10 had any co-citing page. At article–original level,
1/16 combinations contained a paired replication DOI. There were 17 candidate
pages. This selected sample is a functionality check, not a Spanish coverage
estimate. The sample completed in 58.45 seconds; its measured offline rerun
took 1.31 seconds. English archived replay took 26.03 seconds initially.
Timings depend on caches and Wikimedia service conditions. The first small
live validations preceded the final capacity-one pacing correction; future
uncached queries use the final stricter pacing. The subsequent full latest-snapshot run uses the more efficient resolver
inventory mode. Its result and measured times are supplied in the private
full-run review report, separately from this archived sample description.

## Outputs and adjudication

Each run's `output/` contains `manifest.json`, append-only `timings.csv`,
`summary.json`, per-execution provenance JSON, paired audit CSV/Parquet, per-original summary, raw context
CSV/Parquet, `adjudication_pairs.csv`, and `cross_language_doi_overlap.csv`.
The manifest separates candidates, analysed originals, and input scope.
`summary.json` distinguishes original-level and article–original denominators.
DOI occurrences in the context file can repeat within a paragraph and across
replication pairs; they are not independent citations. Cross-language overlap
joins by original DOI against the English pilot; it does not establish that
pages are translations or independent evidence.

Useful Spanish examples include **Automaticidad** (both Bargh 1996 and Doyen
2012 DOI strings detected), **Penalización de la maternidad** (Correll 2007
present; paired replication DOI not detected), and **Efecto de Stroop**
(historical original citation alongside review sources). Revision links and
full raw context in the run products let editors judge relevance before any
change. No Wikipedia edits or messages are sent by the pipeline.

Limitations: discovery searches main-namespace external DOI resolver links,
not all Wikipedia text. Raw and slash-encoded `doi.org` and `dx.doi.org` links
are queried over HTTP/HTTPS; publisher-only links, some complex SICI DOIs,
other encodings, and DOI-free citations can be missed. The inherited DOI
extractor expects a literal registrant slash and may truncate parentheses or
special punctuation. DOI presence alone does not prove a substantive citation.
Current revisions are snapshots retrieved sequentially, not one simultaneous
edition state. Archived English revision IDs exist, but revision/retrieval
timestamps were not recorded. New Spanish pages have both. Revision history,
secondary-source quality, author/title matching, and absence of substantive
acknowledgement remain unaudited. FLoRA's supplied pair/outcome decisions are
preserved, including the inherited worst-outcome summary rule.

## Private review report

With the three retained validation runs present, rebuild the report and its
download bundles into a dedicated directory:

```sh
bash scripts/verify.sh
python3 scripts/build_review.py --output-dir ../flora-wikipedia-review-20261003
```

The builder does not start a server or publish anything. When sharing privately, serve
only that output directory over the current `tailscale ip -4` address. The
verified private review URL and running service are recorded in
`runs/verification/server.json`. Do not serve the checkout itself.

The inventory implementation is tested with:

```sh
Rscript tests/test_inventory.R
```

This tests exact DOI matching, encoding/aliases, complete negative results,
continuation checkpointing, interruption/resume, language isolation, offline
reuse, and missing optional columns in current FLoRA. DOI inventory matches
may detect additional case/encoding variants compared with the older per-DOI
queries. The inherited wikitext extractor's complex DOI limits still apply.

## Full Spanish results against current FLoRA (3 October 2026)

The completed `spanish-full-latest` run includes all 2,745 usable DOI pairs
in the pinned latest CSV: 2,567 originals and 4,826 distinct DOIs. The full
resolver inventory contains 350,962 rows in 775 continuation chunks. It led
to 182 candidate revisions, of which 167 contain a scoped original DOI.
We detected 159/2,567 originals (6.2%); 12/159 detected originals (7.5%)
had any co-citing page. Separately, 13/201 article–original combinations
(6.5%) contained a paired replication DOI. These are DOI-based screening
measures and do not assess substantive acknowledgement.

Elapsed time from the first start through successful completion, including
a cache-preserving restart, was 1,019 seconds (about 17 minutes). The full
offline rerun took 13.29 seconds and left audit, summary, context, and
adjudication files byte-identical. The inventory recovers all 19 page–DOI
hits from the earlier 27-DOI Spanish sample. Current schema/inventory tests
and exact English regression checks passed. Cumulative incremental metered
API cost is US$0. The 311 CSV rows missing either DOI, DOI-free sources,
and substantive acknowledgement remain outside this audit.

Full-run validation and the report can be rebuilt from retained products:

```sh
Rscript scripts/validate_full_run.R spanish-full-latest
python3 scripts/build_full_review.py --output-dir ../flora-wikipedia-review-20261003
```

## Full English on the same current GitHub input

The 5 October 2026 upstream check produced `runs/inputs/flora-latest-20261005.csv`, byte-identical (SHA-256 `28748e8c6f02c428e06c98bd8ec0df4905c04324506b787691fa8639a36557d9`) to the 3 October pin used for Spanish. The new file commit is `fe14eb96731f3ee9016e6fa65c73599a0f1b7bc7`; both provenance sidecars are retained. The full English audit deliberately uses the same 3 October pin.

```bash
Rscript R/run_audit.R --lang=en --run=english-full-gh --input=runs/inputs/flora-latest-20261003.csv --discovery=inventory
Rscript R/run_audit.R --lang=en --run=english-full-gh --discovery=inventory --offline
Rscript scripts/validate_full_run.R english-full-gh en
```

English and Spanish article snapshots were collected on different days. Common DOI keys are shared studies, not independent replications, translated-page pairs or substantive acknowledgement.

## Review decisions and edit-a-thons

`R/09_recommendations.R` is retired and stops on entry. Its historical source is retained as non-executable `docs/archive/09_recommendations.R.txt`; existing outputs remain unchanged. The local archived web UI suppresses insertion sentences, citation-copy and edit-mode links and defaults to article order. The existing public Pages demo still exposes old suggestions: changing that deployment requires separate authorisation, and it must not be used for the proposed programme until corrected or retired.

[The Opus-reviewed programme](docs/editathon-plan.md) separates article scope from citation function. It requires specific study matching, current sources, due weight and individual judgement. FLoRA outcome codes never provide citable wording. Retain/drop/defer decisions describe our queue, not whether a Wikipedia citation should be removed. Citation removal or claim narrowing require source-supported reasons.

```bash
python3 scripts/prepare_adjudication.py --run-dir runs/english-full-gh/en --run-dir runs/spanish-full-latest/es --output runs/editathon-review
# Edit a COPY of decisions.csv: complete scope, citation function, reason, sources and review fields.
# Reapply the ledger; dropped/deferred candidates leave active-packets.json, but remain in packets.json.
python3 scripts/prepare_adjudication.py --run-dir runs/english-full-gh/en --run-dir runs/spanish-full-latest/es --output runs/editathon-review --decisions path/to/reviewed-decisions.csv
```

No outcome ranking or automatic retain decision is produced. `wikidata_only` means queue for **read-only reconciliation**, never permission to write. For OSC/Many Labs/SCORE, retain decisions require an explicit specific-study match. Claims that use historical attribution to support a current empirical assertion must be reviewed as current support. Current revision checks are still required at the event.

```bash
python3 scripts/reconcile_wikidata.py --packets runs/editathon-review/packets.json --output runs/wikidata-sample
python3 scripts/reconcile_wikidata.py --packets runs/editathon-review/packets.json --output runs/wikidata-sample --offline
```

This deliberately small four-article sample searches both main and scholarly Wikidata query graphs for exact DOI case variants and retains raw responses. Paper QIDs, article-topic QIDs, P2860 citations and P921 subjects are distinct. Missing or ambiguous identity is recorded; no outcome properties, item creation or Wikimedia writes are performed. The sample does not estimate Wikidata coverage.

Packets group article–original matches for screening and include unmodified raw contexts. When a paper supports several claims, review each claim separately and record distinct claim notes; a retain/drop decision is not a blanket verdict on the article. DOI strings in comments or bibliographies may support no visible claim.

For inventory discovery, positive rows retain the response chunk retrieval time. The inherited `queried_at` field on materialised zero-hit rows records the local derivation time, not a dedicated DOI query or an edition snapshot time. Use `resolver_inventory/state.json` and the retained chunk timestamps for the discovery interval; negative-row derivation timestamps can change on offline replay. The five principal audit products are the deterministic replay contract.

Resolver URL matching strips query/fragment components after decoding. Literal question marks or hash characters in a DOI suffix can therefore be ambiguous and missed. This adds to the inherited raw-wikitext punctuation/encoding limits; absence is not a substantive judgement.

For an offline handover on another machine, extract `code-and-docs.zip` into a checkout at the run manifest’s base commit, then both full-product archives and `programme-products.zip`. The programme archive includes the small English/Spanish live sample caches used by full validation and CLI tests; archived English regression is rebuilt from the repository’s original tracked products. Install the documented R dependencies first. No network requests occur during `--offline` replay.

Queue rebuilds automatically preserve an existing decision ledger. Non-unreviewed decisions are tied to `reviewed_revision_id`; applying them to a changed revision is refused until re-review, including previously dropped candidates. Keep downloaded reviewer ledgers as immutable records and reconcile them explicitly.

The legacy-named `cross_language_doi_overlap.csv` emitted by `10_review.R` always compares a run with the archived May English baseline: it is historical same-language overlap for a new English run and historical cross-language overlap for Spanish. Use the handover’s `current-cross-language-dois.json` for the two current-input full runs. Neither export identifies translated article pairs or independent evidence.

## English edit-suggestion prototype (6 October 2026)

`prototype/` builds private, page-specific edit-suggestion cards for about 50
English pages from the frozen full English audit, with source-grounded model
drafts, an independent second drafting route, orchestrator review and a
browser-based reviewer ledger. It replaces the retired outcome-sentence
generator and writes only to `runs/edit-prototype-en/` and a dedicated site
directory outside the checkout. See `prototype/README.md` for the pipeline,
commands, grounding checks and the policy limits on using generated text.
