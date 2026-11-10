# Editing support: review cards for English Wikipedia

This prototype turns the English FLoRA audit in [`../search/`](../search/) into one
review card per Wikipedia article. A card covers every FLoRA study the article cites and,
for each, shows:

- the passage that cites the study, from a saved revision, with links to the current
  article and the changes since;
- what the article uses the study for, and the original and replication sources with the
  level of evidence we could read (full text or abstract);
- a suggested action (for example add context, narrow a claim, replace a source or no
  change) and its strength;
- a suggested edit: where the change could go, the points it could cover and the sources
  it could cite, with the facts it relies on checked against quoted passages;
- review articles we searched for mentions of the replication, uncertainties and
  judgement calls left to the editor.

The work-in-progress dashboard is at **https://forrt.org/flora-wikipedia/**. It covers
52 articles and 73 studies; AI suggests a change for 42 studies and no change for 31.
Nobody has yet checked the cards.

## Principles

- **No generated wording.** English Wikipedia prohibits AI-generated article text
  ([WP:NOLLM](https://en.wikipedia.org/wiki/Wikipedia:Writing_articles_with_large_language_models)).
  Cards say what to change and which sources to read; contributors write their own text.
  Earlier draft wording is archived in `runs/edit-prototype-en/archive/` and kept out of
  the site and downloads. See [`docs/contributor-workflow.md`](docs/contributor-workflow.md).
- **The pipeline does the legwork.** It finds sources, hunts for legitimate free copies
  of paywalled papers, searches review articles for the replication and checks facts, so
  that the questions left to people are editorial judgement calls rather than chores.
- **Strength follows a fixed rule.** *Fix*: the article says something its source
  contradicts or does not support. *Recommended addition*: a replication directly tested
  a claim the article relies on and failed, found a clearly smaller effect or
  substantially qualified it. *Optional addition*: the article is accurate and the
  addition would only enrich it. *None*: no change. Additions are not suggested on
  biographies, lists, timelines or passing mentions.
- **Outcome-blind selection.** Articles were sampled across article types in a fixed
  pseudo-random order; a test checks that swapping replication outcomes leaves the
  selection unchanged. FLoRA outcome codes never generate wording; this replaces the
  retired generator in
  [`../search/docs/archive/09_recommendations.R.txt`](../search/docs/archive/09_recommendations.R.txt).
- **Two independent assessments.** Each article was drafted twice from the same
  evidence. They agreed on the broad category for 66 of 73 studies; the other 7 are
  shown as judgement calls with both views. Repeating a run changes about one action in
  ten, so a single assessment is low-precision.
- **Read-only.** Nothing here edits Wikipedia or Wikidata, posts messages or copies text
  into an editor.

## Pipeline

Products are written to `runs/edit-prototype-en/` (ignored by Git). The pipeline reads
the full English audit (`../search/runs/english-full-gh/en`) and the review queue
(`../search/runs/editathon-review/packets.json`) and never writes to them.

| Step | Script | Output (under `runs/edit-prototype-en/`) | Network |
|---|---|---|---|
| Screen and select articles (outcome-blind strata) | `select_pages.py` | `packet_features.csv`, `selection.json` | none |
| Build evidence packets | `evidence.py` | `evidence/<card>/packet.{md,json}`, `article_plain.txt`, `cache/` | first run only: Wikipedia read API, Crossref, Europe PMC, OpenAlex, open PDFs (serial, paced, cached) |
| Find full texts and check reviews | `fetch_fulltext.py`, `check_reviews.py` | `cache/fulltext_skill/`, `cache/reviews_checked/`, `ft-skill/` | free routes only |
| Draft | `make_prompt.py` with `drafting_brief.md`; Claude sub-agents, or `run_route.py` for Codex | `drafts/<route>/<card>.json` | subscription CLIs only |
| Validate | `validate.py`, `validate_all.py` | `validation-report.json` | none |
| Orchestrator review | `review/<card>.json` | verdicts and overrides | none |
| Live spot-check | `inspect_sample.py` | `manual-inspection.json` | Wikipedia read API |
| Build site | `build_site.py` (+ `write_about.py`) | static site outside the repository | none |

Grounding checks are mechanical: claim quotes must occur in the reviewed revision,
source quotes must occur verbatim in the cached abstract or full text, evidence levels
cannot exceed what was cached, cited DOIs must come from the packet or the article, and
FLoRA/FORRT may not appear as a source. The validator also rejects placeholder citations
and checks left to contributors that the pipeline should have done ("confirm", "check",
"read").

Card text is cleaned at build time without touching the raw drafts.
`text_overrides.json` holds exact replacements and `gist_overrides.json` the reviewed
one-line summaries, each tied to a hash of the text it replaces; the build fails if a
draft changes underneath an override.

## Commands

Run from the repository root.

```sh
# Offline rebuild of selection, packets, validation and site
bash editing-support/build.sh
# Also re-check current revision IDs (one batched Wikipedia read request) and fetch
# Crossref/DataCite details for newly cited sources without a cached author and year
bash editing-support/build.sh --refresh-live
# Tests
python3 editing-support/tests/test_edit_prototype.py
# Re-draft cards through a CLI route (restartable; skips parsed outputs)
python3 editing-support/run_route.py --route codex <card_id> ...
```

The site is written to `../flora-wikipedia-edit-prototype-20261006` next to the
checkout (override with `PROTOTYPE_OUTPUT_DIR`). To serve it privately over the tailnet:

```sh
systemd-run --user --unit=flora-wikipedia-edit-prototype-20261006 --property=Restart=on-failure \
  /usr/bin/python3 -m http.server 8771 --bind "$(tailscale ip -4)" \
  --directory ../flora-wikipedia-edit-prototype-20261006
```

To publish, stage a copy with `stage_public.py`, which rewrites "private" wording to
"shared for review" and fails if draft wording or a local archive slipped in. `--wip` adds the work-in-progress banner used
for the FORRT copy, which is published as a one-commit `gh-pages` branch:

```sh
python3 editing-support/stage_public.py ../flora-wikipedia-edit-prototype-20261006 STAGING_DIR --wip
```

Reviewer decisions are kept in the browser (localStorage), bound to each card's reviewed
revision, and export to CSV/JSON; imports skip records whose revision differs from the
card's. A "Re-check live revision" button compares the current revision ID with the
reviewed one.

## Models and cost

Three drafting routes were compared on five pilot pages with identical prompts and
evidence (`route_comparison.json`). Claude sub-agents became the primary route and Codex
(`gpt-6.1-sol`) an independent second route; Gemini 3.8 Flash (agy) was used in the pilot
only. All routes ran through subscription or OAuth logins with metered API keys removed
from child processes. Incremental metered spend was US$0 (`cost-ledger.json`).
