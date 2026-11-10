# FLoRA on Wikipedia

Many Wikipedia articles cite psychology studies that have since been replicated, often
unsuccessfully, without mentioning the replication. This project uses
[FLoRA](https://github.com/forrtproject/FReD-data/blob/main/output/flora.csv), the FORRT
Library of Reproduction and Replication Attempts, to find those citations and to help editors decide
whether and how an article should change.

It has two parts:

| Folder | What it does | Status |
|---|---|---|
| [`search/`](search/) | Finds Wikipedia articles that cite a FLoRA original study by DOI and checks whether the paired replication is cited on the same page (English and Spanish). | Full English and Spanish audits complete (October 2026) |
| [`editing-support/`](editing-support/) | Turns the English audit into one review card per article: what the article claims, what the original and replication found, and whether an edit is warranted. | Work-in-progress prototype at **https://forrt.org/flora-wikipedia/** |

## Editing support: review cards

The prototype covers 52 English Wikipedia articles and the 73 FLoRA studies they cite.
Each card shows the passage that cites the study, the original and replication sources
with the evidence we could read, and a suggested action with its strength (fix,
recommended addition, optional addition or no change). A suggested edit says where a
change could go, which points to cover and which sources to cite. It gives no
ready-made wording, because English Wikipedia does not allow AI-generated article text
([WP:NOLLM](https://en.wikipedia.org/wiki/Wikipedia:Writing_articles_with_large_language_models)):
contributors read the sources and write their own text.

AI suggests a change for 42 of the 73 studies and no change for 31. Each study was
assessed twice, independently; where the two assessments disagree (7 of 73), the card
shows both as a judgement call. Nobody has yet checked the cards, and the dashboard
cannot edit Wikipedia.

See [`editing-support/README.md`](editing-support/README.md) for the pipeline, grounding
checks and rebuild commands, and
[`editing-support/docs/contributor-workflow.md`](editing-support/docs/contributor-workflow.md)
for how contributors should use a card.

## Search: DOI co-citation audit

The audit lists every Wikipedia article whose wikitext contains a FLoRA original DOI and
records whether the paired replication DOI also occurs there. Against the 2,745 usable
pairs in FLoRA (October 2026):

| | English | Spanish |
|---|---|---|
| Originals cited on at least one article | 586 of 2,567 | 159 of 2,567 |
| … with the replication cited on the same article | 65 of 586 | 12 of 159 |
| Article–original combinations with a replication DOI | 80 of 1,193 | 13 of 201 |

These are counts of DOI strings. A missing replication DOI does not show that an article
ignores replication evidence: articles can cite reviews or DOI-free sources, and a DOI
can sit in a bibliography without supporting any claim. Deciding that requires reading
the article, which is what the review cards do.

See [`search/README.md`](search/README.md) for setup, commands, outputs and limitations.

## Repository layout

```
search/            R audit pipeline, review-queue scripts, tests, archived May 2026 pilot
editing-support/   review-card prototype: evidence packets, drafting brief, site builder, tests
docs/              edit-a-thon programme plan, shared by both parts
```

Each part keeps its run products in its own `runs/` folder (`search/runs/`,
`editing-support/runs/`). These are large, ignored by Git and shared as private archives.
The editing support reads the English audit from `search/runs/english-full-gh/` and the
review queue from `search/runs/editathon-review/`.

Neither part edits Wikipedia or Wikidata or sends messages. The earlier static demo
pages are in
[LukasWallrich/flora-wikipedia-demo](https://github.com/LukasWallrich/flora-wikipedia-demo).
