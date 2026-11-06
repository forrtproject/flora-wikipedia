# English edit-suggestion prototype (private)

This prototype turns the frozen English FLoRA audit into page-specific, reviewable
edit suggestions. Each card covers one English Wikipedia page and one FLoRA
original cited on it: the exact passage, the article's scope and the citation's
function, the original and replication sources with the evidence level we could
read, a proposed action (including no change), model-drafted illustrative
wording where the sources support it, alternatives, uncertainties and required
human checks. It replaces the retired outcome-code-to-sentence generator
(`docs/archive/09_recommendations.R.txt`); no wording is derived from FLoRA
outcome codes, and selection never ranks by outcome.

The cards are private research material and model review, not human
adjudication. English Wikipedia prohibits LLM-generated article text
(WP:NOLLM), so drafts are illustrations for reviewers, and contributors write
their own text from sources they have read (`docs/contributor-workflow.md`).
Nothing here edits Wikipedia or Wikidata.

## Pipeline

| Step | Script | Output (under `runs/edit-prototype-en/`) | Network |
|---|---|---|---|
| Screen and select pages (outcome-blind strata) | `select_pages.py` | `packet_features.csv`, `selection.json` | none |
| Build evidence packets | `evidence.py` | `evidence/<card>/packet.{md,json}`, `article_plain.txt`, `cache/` | first run only: Wikipedia read API, Crossref, Europe PMC, OpenAlex, open PDFs (serial, paced, cached with retrieval times) |
| Draft | `make_prompt.py` + Claude sub-agents; `run_route.py` for Codex/agy | `drafts/<route>/<card>.json` + `.meta.json` | subscription CLIs only |
| Validate | `validate.py`, `validate_all.py` | `validation-report.json` | none |
| Orchestrator review | `review/<card>.json` (written by `review/write_reviews.py`) | verdicts, adjacent opportunities, overrides | none |
| Live spot-check | `inspect_sample.py` | `manual-inspection.json` | Wikipedia read API |
| Build site | `build_site.py` (+ `write_about.py`) | static site in a dedicated directory outside the repo | none |

The one-line summary at the top of each study comes from `gist_overrides.json`: reviewed
rewrites, each tied to a hash of the rationale it summarises, so the build fails if a draft
changes underneath it. Without an entry, the rationale's opening sentence is used.

Grounding checks are mechanical: claim quotes must occur in the reviewed
revision, source excerpts must occur verbatim in the cached abstract or full
text, evidence levels cannot exceed what was cached, cited DOIs must come from
the packet or the article, numbers in draft wording must occur in a cited source
or the article, and FLoRA/FORRT may not appear as a source in draft wording.

## Commands

```sh
# Offline rebuild of selection, packets, validation and site
bash prototype/build.sh
# Also re-query current revision IDs (one batched Wikipedia read request) and fetch
# Crossref/DataCite details for any newly cited source that has no cached author and year
bash prototype/build.sh --refresh-live
# Copy the built site for the shared review deployment ("private" wording rewritten)
python3 prototype/stage_public.py ../flora-wikipedia-edit-prototype-20261006 STAGING_DIR
# The FORRT GitHub Pages copy (https://forrt.org/flora-wikipedia/) adds a work-in-progress
# banner and is published as the gh-pages branch (one commit per publish)
python3 prototype/stage_public.py ../flora-wikipedia-edit-prototype-20261006 STAGING_DIR --wip
# Tests
python3 tests/test_edit_prototype.py
# Re-draft missing cards through a CLI route (restartable; skips parsed outputs)
python3 prototype/run_route.py --route codex <card_id> ...
```

The site is written to `../flora-wikipedia-edit-prototype-20261006` (override
with `PROTOTYPE_OUTPUT_DIR`). It can be served privately over a tailnet with:

```sh
systemd-run --user --unit=flora-wikipedia-edit-prototype-20261006 --property=Restart=on-failure \
  /usr/bin/python3 -m http.server 8771 --bind "$(tailscale ip -4)" \
  --directory "$PROTOTYPE_OUTPUT_DIR"
```

The reviewer ledger lives in the browser (localStorage), bound to each card's
reviewed revision, and exports to CSV/JSON; imports skip records whose revision
differs from the card's. A "Re-check live revision" button compares the current
revision ID with the reviewed one.

## Delegation and cost

Three drafting routes were compared on five pilot pages with an identical prompt
and evidence (`route_comparison.json`). Claude sub-agents became the primary
route and Codex (`gpt-6.1-sol`) an independent second route; agy (Gemini 3.8
Flash High) was used in the pilot only. All model routes ran through
subscription or OAuth logins with metered key variables removed from child
processes; incremental metered spend is recorded in `cost-ledger.json`.
