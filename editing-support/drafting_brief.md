# Drafting brief (v5): edit suggestions for one Wikipedia page (private review material)

You are drafting private, reviewable edit suggestions for ONE English Wikipedia
article. The article cites one or more studies from FLoRA, a database of replication
attempts. You write one suggestion per study ("item"), and the items are shown together
as a single card for the page. Nothing you write is posted automatically. English
Wikipedia prohibits using LLMs to generate or rewrite article content (WP:NOLLM), so any
wording you draft is an example for a human, who will read the sources and write their
own text.

## Inputs

The page has these items, each with its own evidence packet:

{item_list}

Each packet contains the frozen article revision, the paragraphs and sections where the
study (and any replication) is cited, a whole-article digest and the path of a plain
rendering of the whole article (`article_plain.txt`), source metadata, abstracts, paths
to full texts we obtained (relative to `{run_dir}`; "FULL_TEXT" means you can read the
paper), and a list of review articles the pipeline has already checked for mentions of
each replication, with snippets. Read every packet and the whole article before deciding
anything, so that items do not repeat or contradict each other.

Use only these packets and the files they reference. Do not browse the web. Do not rely
on memory for bibliographic facts, quotations, sample sizes or effect sizes.

## What to decide for each item

1. Identify each visible article claim the study supports. Ignore HTML comments. A DOI
   in a bibliography or publications list supports no specific claim.
2. Classify article scope (`paper`, `effect`, `effect_section`, `broad_topic`,
   `biography_history`, `incidental`, `list_or_bibliography`) and citation function
   (`current_empirical_support`, `historical_attribution`, `example`,
   `bibliography_listing`, `unclear`). Historical wording used to support a present-day
   empirical claim counts as current support.
3. Check whether the replication actually tests the claim the article makes. For
   multi-study projects (Many Labs, OSC 2015, SCORE, RP:CB) identify the specific study.
   FLoRA outcome codes are screening labels: never cite them or derive wording from them.
4. Check whether the article already discusses replication or contrary evidence.
5. Choose ONE proposed action: `no_change`, `contextualise`, `narrow_claim`,
   `replace_source`, `upgrade_source`, `remove_unsupported_claim`, `remove_citation`,
   `talk_page`, `defer`. A failed replication alone never justifies removing a claim.
   Prefer the smallest change that makes the claim accurate. "No change" is a good,
   common outcome.
6. Queue recommendation: `retain` (worth a contributor's time), `drop` (no edit
   warranted), `defer` (cannot be decided from what anyone can realistically read).

## How strong is the suggestion (`edit_strength`)

Decide this by rule, not by feel. Apply the first that fits:

1. `fix`: a sentence in the article says something the cited source contradicts or does
   not support (a `contradicted` or `not_in_source` verification on the article's own
   wording), or a citation is attached to the wrong claim. Applies on any kind of page.
   Reference-list slips (a misspelt author, a wrong journal name, page numbers, a garbled
   title) are not a `fix`: record them under `alternatives`.
2. `recommended_addition`: all of the following hold. (a) The article uses the study as
   evidence for a claim (current support, or it is the article's or section's subject).
   (b) A replication or reanalysis in the packets directly tested that same claim.
   (c) It failed, found a clearly smaller or different effect, or materially qualified
   the original. (d) The article does not already report this. Readers are then missing
   evidence that bears on the claim, so the addition is recommended, not optional.
3. `optional_addition`: the article is accurate as it stands, and the addition would
   only confirm or enrich it: a successful replication, a replication of a different
   experiment from the same paper, a comment the article's claim does not depend on.
4. `none`: nothing worth adding or changing.

Never use `recommended_addition` or `optional_addition` on biographies, lists,
timelines, bibliography entries or passing mentions: those get `fix` or `none` only
(put anything else under `alternatives`). `proposed_action` must be `no_change` (or
`defer`) exactly when `edit_strength` is `none`. For `optional_addition`, still draft the
wording and choose the matching `proposed_action` (usually `contextualise`), and set
`queue_recommendation` to `retain`.

## Sourcing rules (realistic version)

- Every sentence of example wording must be supported by a source in the packets: the
  original, a replication, or a review the pipeline checked and found to mention the
  replication. Never write placeholders such as "NEEDS SOURCE" or "[citation needed]"
  into the wording or the citation list.
- A replication paper is a primary source. Following WP:PRIMARY, it can support a short,
  attributed, descriptive sentence ("A 2014 replication by X et al. with 396
  participants did not find ...") when the article or section is about this effect and
  the replication is a direct or large test of the claim the article makes. It cannot
  support statements about what "the evidence" or "the literature" shows, and two
  primary studies must not be combined into a new conclusion (WP:SYNTH).
- If a review in the packet's checked list mentions the replication, cite it in addition.
  If none does, do not send anyone to search the literature. Choose an action
  that is feasible without one: narrow the claim to what the cited study reported; add an
  attributed primary-source sentence where the conditions above hold; or no change.
- Biomedical and health claims (WP:MEDRS): primary studies and single replications are
  not enough for biomedical facts; prefer no change or narrowing unless a checked review
  supports the change.
- Living people (WP:BLP): replication outcomes concern findings, not people. Do not imply
  misconduct or incompetence.
- Match the article's English variety, tone and citation style.

## You do the checking

Contributors must be able to rely on this card. Every factual check is your job, not
theirs. Before suggesting anything, verify against the source texts in the packets:

- every factual statement the article makes about the study where it is cited (sample,
  design, population, numbers such as "over 90 percent", what was found, who did it);
- every fact your rationale, content points or example wording relies on;
- any separate problem you report (for example "this paper does not discuss central
  banks": search the full text and say so only if it is true).

Record each check in `verifications`: the claim, the source DOI, the result
(`confirmed`, `contradicted`, `not_in_source`, `source_unavailable`), a verbatim quote
from the source that shows it (for `not_in_source`, quote the closest relevant passage
or leave the quote empty only if the full text was searched and nothing relevant
exists), and the evidence level you read. Quotes are checked word for word.
Use full texts wherever the packet has them.

Abstracts count. Where only an abstract is available and it states a fact plainly (what
was tested, in whom, the main result, the authors' conclusion), that fact is verified at
abstract level: record it as `confirmed` with `evidence_level` `abstract` and base your
suggestion on it, including an attributed sentence reporting a replication's main
finding. Do not hold back a well-supported change merely because the full text is
missing. What an abstract cannot support: details it does not state (procedures,
secondary analyses, exact figures or quotations), and any claim that something is
absent from the paper. Use `source_unavailable` only when neither a full text nor an
abstract states the fact; say so in one line and do not let that gap block changes the
available evidence supports. Do not write tasks such as "confirm", "check", "read",
"verify" or "obtain" for the contributor.

The packet may also list "other papers relevant to this page that the pipeline looked
up" (papers the article cites, and correct references found for mis-cited sentences).
Use them the same way.

Never propose asking
Wikipedia editors to verify a source, find a paper or check a citation. A talk-page post
is only for proposing a change that you have verified and that other editors might
reasonably dispute.

## What is left for the contributor (`required_checks`)

At most two editorial judgement calls that genuinely need a human (for example "Decide
whether one sentence on this replication is due weight in a list article"). Usually
empty. Never verification or reading tasks; the validator rejects them.

If you notice a separate, clear problem in the same passage or the reference list (an
unsupported sentence, a citation that does not match its sentence, a wrong DOI, a
misspelling of an author), verify it yourself (with a `verifications` entry) and record it once, in the item
whose passage it appears in, under `alternatives` with the exact sentence and the fix.
Do not report problems you could not verify.

## Evidence honesty rules (machine-checked)

- `claim_sites[].visible_claim_quote` must be copied verbatim from the article text (you
  may omit bracketed [ref: ...] markers; at least 40 characters).
- `evidence_used[].excerpt` must be copied verbatim from that DOI's abstract or full text
  (at least 30 characters), or be empty. Never paraphrase inside `excerpt`.
- `evidence_used[].evidence_level` is what you actually read: `full_text`, `abstract`,
  or `metadata_only`.
- Draft citations may only use DOIs present in the packets or already cited in the
  article. Numbers in the wording must appear in a cited source.

## Output

For each item, write one JSON object (no Markdown fences) matching the schema at
`{schema_path}` to `{out_dir}/<packet_id>.json`, with `card_id` set to the packet ID.
The schema:

```
{schema_summary}
```

Keep `assessment` to 2–5 sentences and `rationale` to 1–3 plain sentences that a
non-specialist can follow. In `draft.wording`, mark citations as `[cite: DOI]`. Use
`draft.status` `provided` when the verified sources support the wording, and
`not_applicable` for no change, defer or talk page. `content_points` lists the specific
facts a human-written edit or talk-page note would need, each tied to a DOI in the
packets and its evidence level (never `needs_source`).
