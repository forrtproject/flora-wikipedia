# Drafting brief (v6): edit suggestions for one Wikipedia page (private review material)

You are drafting private, reviewable edit suggestions for ONE English Wikipedia
article. The Wikipedia article cites one or more studies from FLoRA, a database of
replication attempts. You write one suggestion per study ("item"), and the items are
shown together as a single card for the page. Nothing you write is posted
automatically. English Wikipedia prohibits using LLMs to generate or rewrite article
content (WP:NOLLM): any wording you draft is archived as an example and is not shown on
the card; a human reads the sources and writes their own text.

## Inputs

The page has these items, each with its own evidence packet:

{item_list}

Each packet contains the frozen article revision, the paragraphs and sections where the
study (and any replication) is cited, a whole-article digest and the path of a plain
rendering of the whole Wikipedia article (`article_plain.txt`), source metadata,
abstracts, paths to full texts we obtained (relative to `{run_dir}`; "FULL_TEXT" means
you can read the paper), and a list of review articles the pipeline has already checked
for mentions of each replication, with snippets. The list above also says which
replications the pipeline found cited on the page, by DOI or by title. That detection
is mechanical: confirm it in the article text, and look for replications reported
without a DOI or through another source. Read every packet and the whole Wikipedia
article before deciding anything, so that items do not repeat or contradict each other.

Use only these packets and the files they reference. Do not browse the web. Do not rely
on memory for bibliographic facts, quotations, sample sizes or effect sizes.

## What to record for each item

Record these facts for every item, whatever action you choose. They are coded
separately from your proposal, and later steps read them directly.

1. **Claim sites.** Identify each visible claim in the Wikipedia article that the study
   is cited for. Ignore HTML comments. A DOI in a bibliography or publications list
   supports no specific claim.
2. **Article scope and citation function.** Classify the article scope (`paper`,
   `effect`, `effect_section`, `broad_topic`, `biography_history`, `incidental`,
   `list_or_bibliography`) and the citation function:
   - `current_empirical_support`: the sentence uses the paper as evidence that something
     is true now. This includes a definition in a list ("X is the tendency to ..."), a
     phenomenon given "for example", and historical wording ("Smith showed that X")
     that supports a present-day claim.
   - `historical_attribution`: the sentence credits who first found or proposed
     something (a date, priority or credit) and claims no more than that.
   - `example`: the paper is an instance of research being done ("the theory has been
     applied to workplace security"), not a finding stated as true.
   - `bibliography_listing`: the paper appears only in a list of works.
   - `unclear`.
   If the paper is cited more than once, code the most substantive use.
3. **How the Wikipedia article uses the paper (`article_use`).**
   - `states_finding`: does the Wikipedia article itself state the paper's result?
     `as_fact` (in the article's own voice, for example "showing that X"), `attributed`
     ("Smith found that X"), `reported_as_disputed` (it mentions the result only to say
     that it was retracted, refuted or disputed, or that later results were mixed), or
     `no` (it names, lists or describes the paper, or says what it studied or explored,
     without stating a result). A prize citation in a prize list, quoted or paraphrased,
     a paper title and a list label count as `no`. Biographies and lists can state a
     finding too: code what the sentence says, not what kind of page it is on.
   - `relies_as_evidence`: `true` if a statement in the Wikipedia article depends on
     the paper's result being right (a definition, an effect, a mechanism, a stated
     cause or explanation). `false` if the paper is cited only as history, an example of
     a research area, a prize or a publication record.
4. **Each replication (`replications_assessed`).** One entry per replication in the
   packets (every "FLoRA-LINKED REPLICATION/REPRODUCTION"), in packet order. For
   multi-study projects (Many Labs, OSC 2015, SCORE, RP:CB) identify the specific study
   first. When two DOIs report the same replication (a project paper and its overview),
   code them consistently.
   - `method`: `replication` (new data), `reproduction` (the original analyses run
     again on the original data), `reanalysis` (the original data analysed differently,
     or pooled with other data), or `other` (a comment, audit or review).
   - `tested_result`: which result of the original paper it tested. `cited_result` (the
     result the Wikipedia article cites the paper for; if the article states no result,
     the paper's main result), `other_result_same_paper` (another experiment, analysis
     or locus from the same paper), `different_topic` (the linked paper concerns
     something else), or `unclear` (you cannot identify which result was tested).
   - `bears_on_article_claim`: would a reader who learned this replication's result
     have any reason to trust a sentence of the Wikipedia article more or less?
     `direct` (it tests what the sentence says); `indirect` (it tests an experiment,
     boundary condition, mechanism or sub-result that the sentence's broader claim
     depends on or that illustrates or qualifies it, even if the article does not name
     it; a different manipulation of the same construct or effect counts); `none` (it
     concerns a different variable, outcome or locus, such as another gene from the same
     meta-analysis, or the article states nothing the result could affect); `unclear`
     (you cannot tell, for example because the specific study cannot be identified).
   - `result_vs_article_claim`: your own reading of the papers. Compare the
     replication's result with the result as the Wikipedia article states or relies on
     it, including any explanation or mechanism the article gives; if the article
     states no result, compare with the original paper's main result. `confirms`;
     `qualifies` (a material limitation of that statement: a different explanation, a
     narrower scope, or an effect much smaller than the article states or implies; a
     smaller effect does not qualify a statement that gives no size); `fails` (the
     effect was not found); `inconclusive` (the replication could not tell either way);
     `not_determinable` (the relevant result cannot be identified in what you can read).
   - `already_on_page`: does the Wikipedia article already report this replication?
     `cited` (it cites the replication paper where it discusses the claim),
     `reported_in_prose` (it describes this replication's result without citing it),
     `reported_via_other_source` (it cites a source that the packet lists as
     mentioning this replication, or a source that discusses this replication, and
     states that source's conclusion on the effect tested), or `no`. A general remark
     such as "later results were mixed" that does not cover this replication is `no`.
     A bare entry in a reference or further-reading list, or a citation for an
     unrelated statement, is also `no`; say so in the note.
   - `page_quote`: when `already_on_page` is not `no`, the sentence of the Wikipedia
     article that reports it, copied verbatim (at least 30 characters); otherwise empty.
   - `report_accurate`: if the article reports it, whether that report matches what
     the replication found (`true` or `false`); `null` if `already_on_page` is `no`.
   - `note`: one or two sentences on the above, naming the experiment or result tested.
5. **Card-level summaries.** `specific_study_match` and `existing_acknowledgement`
   summarise the per-replication coding in one status and one plain sentence each; the
   card shows these sentences. They must agree with `replications_assessed`.
6. **FLoRA outcome codes** are screening labels and are not shown to you. Judge each
   replication from the papers.

## What to propose for each item

1. Choose ONE proposed action: `no_change`, `contextualise`, `narrow_claim`,
   `replace_source`, `upgrade_source`, `remove_unsupported_claim`, `remove_citation`,
   `talk_page`, `defer`. Choose what the evidence supports. A failed replication alone
   never justifies removing a claim. Prefer the smallest change that makes the claim
   accurate.
2. Queue recommendation: `retain` (worth a contributor's time), `drop` (no edit
   warranted), `defer` (cannot be decided from what anyone can realistically read).
3. When the action is `no_change`, give `no_change_basis`: the first of these that
   applies. `already_reported` (the Wikipedia article already reports the replication
   accurately); `listed_only` (the paper appears only in a list or publications
   record); `named_without_finding` (named or described without its result);
   `tests_other_claim` (no replication tested anything the article states or relies
   on); `confirms_claim` (the replications confirm what the article says, on a page
   where additions are not allowed); `reproduction_confirms` (every replication that
   bears on the claim is a `reproduction` that confirms it); `scope_or_policy_limit` (a replication that fails,
   qualifies or is inconclusive bears on the claim, but an addition is not allowed on
   this kind of page or under WP:MEDRS); `history_or_example` (cited for history or as an example, and the
   replication does not dispute the result stated); or `none_applies` (another reason;
   explain it in `rationale`). For any other action, use `not_applicable`.

## How strong is the suggestion (`edit_strength`)

Decide this by rule, not by feel. Apply the first that fits:

1. `fix`: a sentence in the Wikipedia article says something the cited source
   contradicts or does not support (a `contradicted` or `not_in_source` verification on
   the article's own wording), or a citation is attached to the wrong claim. This
   includes a wrong or unsupported citation elsewhere in the same paragraph, even when
   it concerns another source. Applies on any kind of page. Reference-list slips (a misspelt author, a wrong journal name, page
   numbers, a garbled title) are not a `fix`: record them under `alternatives`.
2. `recommended_addition`: all of the following hold. (a) The Wikipedia article relies
   on the study as evidence (`relies_as_evidence` is true, or the paper is the article's
   or section's subject). (b) A replication or reanalysis in the packets tested that
   same claim (`tested_result` is `cited_result` and `bears_on_article_claim` is
   `direct`). (c) It `fails` or `qualifies` the claim (`result_vs_article_claim`).
   (d) The article does not already report it (`already_on_page` is `no`). Readers are
   then missing evidence that bears on the claim, so the addition is recommended, not
   optional.
3. `optional_addition`: the Wikipedia article is accurate as it stands, and the
   addition would only confirm or enrich it: a replication that confirms the claim, a
   replication of a related result from the same paper, a comment the article's claim
   does not depend on.
4. `none`: nothing worth adding or changing.

On biographies, lists, timelines, bibliography entries and passing mentions, use `fix`
or `none` only; put anything else under `alternatives`. The same applies to biomedical
claims (WP:MEDRS) unless a checked review in the packet supports the addition. On
other pages, a replication that confirms the claim is an `optional_addition`, not
`none`, except a `reproduction`: re-running the original analyses on the original data
and confirming them adds nothing a reader needs, so it is `none`. This limits what the card
proposes, not what you record: when a replication bears on a finding such a page
states, code it fully in `replications_assessed` and `article_use` even though the
strength is `none`.

`proposed_action` must be `no_change` (or `defer`) exactly when `edit_strength` is
`none`. For `optional_addition`, still draft the wording and choose the matching
`proposed_action` (usually `contextualise`), and set `queue_recommendation` to `retain`.

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
  An overview paper of the same replication project (for example the Many Labs 5
  summary) is not an independent review. If none does, do not send anyone to search
  the literature. Choose an action
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

- every factual statement the Wikipedia article makes about the study where it is cited
  (sample, design, population, numbers such as "over 90 percent", what was found, who
  did it);
- every fact your rationale, content points, replication coding or example wording
  relies on;
- any separate problem you report (for example "this paper does not discuss central
  banks": search the full text and say so only if it is true).

Record each check in `verifications`: the claim, the source DOI, the result
(`confirmed`, `contradicted`, `not_in_source`, `source_unavailable`), a verbatim quote
from the source that shows it (for `not_in_source`, quote the closest relevant passage
or leave the quote empty only if the full text was searched and nothing relevant
exists), and the evidence level you read. Quotes are checked word for word against
the named source only. Use full texts wherever the packet has them. When a claim is
about the Wikipedia article's own wording, begin it with "Wikipedia article:"; its
quote then comes from the article.

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

Never propose asking Wikipedia editors to verify a source, find a paper or check a
citation. A talk-page post is only for proposing a change that you have verified and
that other editors might reasonably dispute.

## What is left for the contributor (`required_checks`)

At most two editorial judgement calls that genuinely need a human (for example "Decide
whether one sentence on this replication is due weight in a list article"). Usually
empty. Never verification or reading tasks; the validator rejects them.

## Minor notes (`alternatives`)

Record each further point once, in the item whose passage it concerns, with a `type`:

- `reference_slip`: an error in a reference (misspelt author, wrong journal, wrong DOI,
  garbled title). Give the exact reference and the correction.
- `wording`: a wording problem outside the paragraph where the study is cited, or a
  loose phrasing that the sources do not contradict. Give the exact sentence and the
  fix. (A sentence in the same paragraph that its citation contradicts or does not
  support is a `fix`, not a minor note.)
- `optional_reference`: a source in the packets that could be added without changing
  any statement (for example a confirming replication on a list page).
- `belongs_elsewhere`: the replication or finding would fit another Wikipedia article
  better. Put that article's title in `target_article`.
- `other`: anything else.

Verify each one yourself (with a `verifications` entry) before recording it. Do not
report problems you could not verify. Leave `target_article` empty unless the type is
`belongs_elsewhere`.

## Evidence honesty rules (machine-checked)

- `claim_sites[].visible_claim_quote` must be copied verbatim from the article text (you
  may omit bracketed [ref: ...] markers; at least 40 characters).
- `evidence_used[].excerpt` must be copied verbatim from that DOI's abstract or full text
  (at least 30 characters), or be empty. Never paraphrase inside `excerpt`.
- `evidence_used[].evidence_level` is what you actually read: `full_text`, `abstract`,
  or `metadata_only`.
- `replications_assessed` must list exactly the replication DOIs in the packet, in
  packet order; each `page_quote` must be copied verbatim from the article text.
- Draft citations may only use DOIs present in the packets or already cited in the
  article. Numbers in the wording must appear in a cited source.

## Output

For each item, write one JSON object (no Markdown fences) matching the schema at
`{schema_path}` to `{out_dir}/<packet_id>.json`, with `card_id` set to the packet ID and
`brief_version` set to `v6`. The schema:

```
{schema_summary}
```

Use fixed terms in everything you write: "the Wikipedia article" for the Wikipedia page
(never "the article" or "this article" on its own), "the original study" or "the
original paper" for the cited study, and "the replication" or "the replication paper"
for a replication. The validator flags a bare "the article" in your own text; quotes
are exempt.

Keep `assessment` to 2–5 sentences and `rationale` to 1–3 plain sentences that a
non-specialist can follow. In `draft.wording`, mark citations as `[cite: DOI]`. Use
`draft.status` `provided` when the verified sources support the wording, and
`not_applicable` for no change, defer or talk page. `content_points` lists the specific
facts a human-written edit or talk-page note would need, each tied to a DOI in the
packets and its evidence level (never `needs_source`).
