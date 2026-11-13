# Drafting brief v6: review and pilot

Prepared on 2026-11-12 for issue #9. It covers the changes from brief v5 to v6, what the
three model reviews changed, and a pilot on 20 of the 52 coded articles. The plan is in
[`brief-v6-review.md`](brief-v6-review.md).

## Findings

- **The three hand-made calls now follow from the coding.** In both pilot runs, Jan Eeckhout
  becomes a judgement call from the AI's coded fields alone. Functional accounts of emotion
  and Lise Vesterlund now get edit suggestions in both runs, so they surface without a tier.
  For Functional accounts, the AI finds that the replicated experiment bears indirectly on the
  sentence (optional addition in one run, recommended in the other). For Vesterlund, the
  original paper says overconfidence explains only part of the gap, so the sentence "as they
  tend to be overconfident" needs a fix. With v6 drafts, `label_overrides.json` is no longer
  needed; it stays only for the v5 drafts still shown.
- **The two runs agree more.** They agree on the action class and tier for 32 of 34 studies.
  Under v5 the same 34 studies agreed on edit strength for 32, but that did not cover the
  tiers. The two v6 disagreements are Functional accounts of emotion (optional vs recommended
  addition) and List of common misconceptions (likely no change vs judgement call). Both v5
  disagreements in the pilot (Moral agency, Bad News 2019) now agree.
- **19 of the 25 no-change studies with a call in #9 match it in both runs**, and one more in
  one run (39 of 50 run-level calls). All 11 intended judgement calls are flagged for people
  in both runs, as a judgement call or an edit. Of the 14 intended non-judgement items, 11 stay
  out of the review lists in both runs; the exceptions are listed under *Disagreements*.
- **Every pilot draft validates.** All 68 drafts (34 studies × 2 runs) pass with no errors;
  4 warnings remain, each a draft citing a DOI that the Wikipedia article already cites.
- **5 of the 52 articles cite all their replications, not the 4 in the plan** (none is dropped;
  see decision 2 below). More Guns, Less Crime,
  Red dress effect and Facial feedback hypothesis cite all their replications. Priming
  (psychology) does not: only 1 of its 4 replications is cited, so it stays in coding.
  Door-in-the-face technique (title match; I checked the citation) and Multiculturalism cite
  theirs as well.
- **Cost:** US$0 metered. All runs used subscriptions or OAuth logins (ledger entry 13).

## What changed in v6

| Area | v5 | v6 |
|---|---|---|
| Replications | One match and one acknowledgement per study | `replications_assessed[]`, one entry per replication: `method`, `tested_result`, `bears_on_article_claim` (direct, indirect, none, unclear), `result_vs_article_claim`, `already_on_page`, `page_quote`, `report_accurate`, note |
| Article use | `citation_function` only | `article_use.states_finding` (as fact, attributed, reported as disputed, no) and `relies_as_evidence`; sharper definitions of each citation function |
| No-change reason | `confidence` (29 of 31 rated high) | `confidence` removed; `no_change_basis` with a priority order |
| Minor notes | Free text | Typed: reference slip, wording, optional reference, belongs elsewhere (with `target_article`), other |
| Priming | "'No change' is a good, common outcome." | Removed: "Choose what the evidence supports." The facts are recorded whatever the action |
| Strength rules | Rule 3 and the page-type ban collided | The ban limits the proposal only; the evidence relation is still coded. WP:MEDRS added to the ban; a confirming replication on a topic page is an optional addition |
| Packets | Showed FLoRA outcome codes | Drafting copies (`blind_packets.py`) leave them out; detection by DOI or title is shown instead |
| Wording | The build rewrote "the article" | The brief asks for "the Wikipedia article"; the validator warns, and v6 cards are not rewritten |
| Tiers | `replication_bears_on_claim` plus three overrides | `no_change_tier` from the coded fields (below); FLoRA codes are not used |
| Two runs | Tier taken from the shown run | Between two no-change runs, the card shows the more cautious tier |

**Tier rule** (`build_site.py`, `no_change_tier`, for v6 no-change suggestions). A replication
is *relevant* if it bears on the Wikipedia article (`bears_on_article_claim` is not `none`) or
its tested result is unclear.

1. Any inaccurate report of a replication on the page: **judgement call**.
2. **Already covered:** every relevant replication is reported accurately on the page (or, if
   none is relevant, at least one is), each with a verbatim page quote.
3. **Likely no change:** no replication is relevant; or the article neither states the finding
   nor relies on it; or it cites the paper for history, as an example or in a list, does not
   rely on it, and every relevant replication confirms what it says.
4. Otherwise **judgement call**.

The validator checks the new fields for consistency. It requires the replication list to
match the packet in order, a verbatim page quote whenever a replication is coded as on the
page, and `report_accurate` to be null exactly when it is not. Source quotes must now come from
the named source; only claims that start with "Wikipedia article:" may quote the article. It
also warns where the coding and the chosen strength or reason disagree. v5 drafts are still
validated against the v5 schema, kept with the earlier briefs and schemas in the run
directory (`suggestion.schema.v5.json`, `drafting_brief.v5.md`).

## Model reviews: what I adopted

Three models reviewed the brief, schema, rule and validator independently, with the memo and
the issue discussion: Claude Opus 5.5, `gpt-6.1-sol` (Codex, high) and Gemini 4 Argon High
(Antigravity). Their reviews raised 38 findings, many overlapping.

| Finding (reviewers) | Decision |
|---|---|
| "Confirms" was judged against the original, so Vesterlund's replicated gap with a different explanation could read as confirming (Opus, Sol) | Adopted: `result_vs_article_claim`, compared with the result *and explanation* the article states |
| The related/unrelated boundary and `tests` mixed design with relevance (all three) | Adopted: split into `method` and `tested_result`; relevance only in `bears_on_article_claim`, defined by whether the result would change a reader's trust in a sentence |
| Unknown relevance was forced into `none`, which produced *likely no change* (Sol, Opus) | Adopted: `unclear` relevance, treated as relevant |
| Vacuous and inaccurate *already covered* (all three) | Adopted: step 1 and the stricter step 2 above |
| The history shortcut ignored reliance (Sol, Opus) | Adopted: the shortcut requires `relies_as_evidence` false; citation functions redefined |
| *Already covered* hides cards but had the loosest definition (Opus, Argon) | Adopted: verbatim `page_quote`; `reported_via_other_source` limited to sources that discuss this replication |
| FLoRA outcome codes in the packet anchor the AI's reading (Opus) | Adopted for drafting copies; validation and the build still read the original packets |
| The two-run tier came from the shown run only (Opus, Argon) | Adopted: the more cautious tier is shown, with `tier_agree` |
| Pre-filter matched DOIs in comments, DOI prefixes and generic titles (all three) | Adopted: comments stripped, exact DOI match, titles of at least 40 characters and six words, apostrophes normalised |
| Verification quotes could be satisfied by the Wikipedia text (Sol, Argon); empty `not_in_source` quotes were rejected although the brief allows them (Sol, Argon) | Adopted for v6 drafts |
| `make_prompt.prompt` crashed on the page-level brief (all three) | Fixed |
| The article reported a result only as retracted or disputed (Argon); prize-row paraphrases (Argon) | Adopted: `reported_as_disputed`, treated like `no`; prize citations count as `no` |
| `confirms_claim` contradicted rule 3; MEDRS missing from the strength rules (Opus, Argon) | Adopted |
| Priority order for `no_change_basis`; a value for page-type and policy limits (Argon) | Adopted (`scope_or_policy_limit`); order adjusted after the pilot, below |
| Undefined schema values (`conditional`, `withheld`, `needs_source`) (Sol, Argon) | Removed from the v6 schema |
| Derive `specific_study_match` and `existing_acknowledgement` in the build (all three) | Not adopted: the site shows their notes. A consistency check was added instead |
| Drop `queue_recommendation` (Opus) | Not adopted: outside the tiers, so no change for now |
| Hard error for a bare "the article" (Opus) | Adopted as a warning, with quoted spans exempt |
| Ban additions where the citation function is `example` (Argon) | Not adopted: it would push Functional accounts back to no change |
| Code `bears_on_article_claim` `none` when the study is unidentifiable (Argon) | Not adopted: it conflicts with the unclear-relevance fix |
| Link each replication to a claim site (Sol) | Not adopted: extra load; the claim comparison now sits in `result_vs_article_claim` |
| Compact schema in the prompt (Argon) | Not adopted: the descriptions carry definitions |
| Stop drafting archived wording (Sol) | Not adopted: outside the agreed scope (wording is already kept off the cards) |

**Changes after the pilot.** The pilot drafts showed three problems with my own wording,
fixed in the final brief. The drafts were not re-run (see *Needs your decision*).

- A wrong citation in the same paragraph is a `fix` again, as in v5. My v6 wording had
  turned it into a minor note, which demoted Robert F. Stambaugh from *fix* in both v5 runs
  to *judgement call* in both v6 runs.
- `confirms_claim` now comes before `scope_or_policy_limit` in the priority order. Otherwise
  it could never apply on lists.
- The warning "cited result but no bearing" no longer fires when the article states no result.
  It fired on 12 of the 68 drafts, all correctly coded.

## Pilot

**Articles.** The 15 named in the plan, plus Moral agency (broad topic; v5 runs disagreed),
Bad News (video game) (central effect; three studies, one already cited), Robert F. Stambaugh
(biography; fix), Religiosity and intelligence (co-cited; fix and no change) and Positive
illusions (list or bibliography; two optional additions). That is 20 articles and 34 studies.
Twelve Claude Opus 5.5 sub-agents drafted them twice, independently, into
`drafts/claude_v6a` and `drafts/claude_v6b`, from packets without outcome codes
(`evidence_v6`).

**Per study.** Strength is shown as run A / run B. A tier is given for no-change
suggestions; edits and optional additions are shown by class. "#9 call" is the tier implied
by the card-by-card table and the three-tier proposal in #9.

| Article | Original study | v5 strength | v6 strength | v6 tier or class | #9 call | Match |
|---|---|---|---|---|---|---|
| Bad News (video game) | Roozenbeek & van der Linden 2019 | none / optional | none / none | Already covered | – | – |
| Bad News (video game) | Basol et al. 2020 | optional / optional | optional / optional | Optional | – | – |
| Bad News (video game) | Roozenbeek & van der Linden 2018 | fix / fix | fix / fix | Edit | – | – |
| C-Raf | Hatzivassiliou et al. 2010 | none / none | none / none | Judgement call | Judgement call | yes |
| CASS4 | EADI et al. 2013 | none / none | none / none | Likely no change | Covered or likely | yes |
| Deniz Başkent | Bhargava et al. 2014 | none / none | none / none | Likely no change | Likely no change | yes |
| Functional accounts of emotion | van Dijk et al. 2008 | none / none | optional / recommended | Optional / Edit | Judgement call | flagged (as an edit) |
| Heejung Kim | Kim & Markus 1999 | none / none | none / none | Likely no change | Likely no change | yes |
| Jan Eeckhout | Eeckhout 2004 | none / none | none / none | Judgement call | Judgement call | yes |
| Lise Vesterlund | Niederle & Vesterlund 2007 | none / none | fix / fix | Edit | Judgement call | flagged (as an edit) |
| List of Ig Nobel Prize winners | Piff et al. 2012 | none / none | none / none | Likely no change | Likely no change | yes |
| List of Ig Nobel Prize winners | Wansink et al. 2005 | none / none | none / none | Likely no change | Likely no change | yes |
| List of Ig Nobel Prize winners | Pennycook et al. 2015 | none / none | none / none | Likely no change | Likely no change | yes |
| List of Ig Nobel Prize winners | Strack et al. 1988 | none / none | none / none | Likely no change | Already covered | no |
| List of cognitive biases | Baron & Hershey 1988 | none / none | none / none | Judgement call | Judgement call | yes |
| List of cognitive biases | Adams et al. 2021 | none / none | none / none | Judgement call | Judgement call | yes |
| List of cognitive biases | Hsee & Zhang 2004 | none / none | none / none | Judgement call | Judgement call | yes |
| List of cognitive biases | Tversky & Kahneman 1981 | none / none | none / none | Judgement call | Judgement call | yes |
| List of cognitive biases | Milgram 1963 | fix / fix | fix / fix | Edit | – | – |
| List of cognitive biases | Kruger 1999 | none / none | none / none | Judgement call | Judgement call | yes |
| List of cognitive biases | Walker & Vul 2014 | none / none | none / none | Judgement call | Judgement call | yes |
| List of common misconceptions about arts and culture | Rauscher et al. 1993 | none / none | none / none | Likely no change / Judgement call | Covered or likely | one run |
| Moral agency | Gray & Wegner 2009 | fix / none | fix / fix | Edit | – | – |
| National accounts | Mankiw et al. 1992 | none / none | none / none | Likely no change | Likely no change | yes |
| Outgroup favoritism | Axt et al. 2018 | none / none | optional / optional | Optional | Likely no change | no |
| Oxytocin | Hurlemann et al. 2010 | none / none | none / none | Judgement call | Judgement call | yes |
| Positive illusions | Alicke 1985 | optional / optional | optional / optional | Optional | – | – |
| Positive illusions | Kruger 1999 | optional / optional | optional / optional | Optional | – | – |
| Positive illusions | Nuttin 1987 | none / none | none / none | Likely no change | Likely no change | yes |
| Protection motivation theory | Herath & Rao 2009 | none / none | none / none | Likely no change | Likely no change | yes |
| Religiosity and intelligence | Camerer et al. 2018 | none / none | none / none | Likely no change | Likely no change | yes |
| Religiosity and intelligence | Gervais & Norenzayan 2012 | fix / fix | recommended / recommended | Edit | – | – |
| Robert F. Stambaugh | Pástor & Stambaugh 2003 | fix / fix | none / none | Judgement call | – | – |
| TCF7L2 | Grant et al. 2006 | none / none | none / none | Judgement call | Likely no change | no |

**Disagreements, inspected.** I read both drafts' coding and reasons for each of these.

- *Outgroup favoritism* (optional addition in both runs; #9: likely no change). Both runs code
  the cited sentence as relying on the paper. They find that the SCORE reproduction re-ran 13
  analyses, including the implicit outgroup-favouritism results behind it, and all reproduced.
  Under the v6 rule a confirming replication on a topic page is an optional addition. #9 kept
  it as no change because the re-run reuses the same data. This is a rule question, not a
  coding error (see *Needs your decision*).
- *TCF7L2* (judgement call in both runs; #9: likely no change). Both runs read "Grant et al.
  localised the signal to TCF7L2" as current evidence that the gene matters, which the brief
  now says historical wording can be. This errs on the side of review.
- *Strack et al. 1988 on the Ig Nobel list* (likely no change; #9: already covered). Both runs
  find that the row reports the 2016 Registered Replication Report accurately. However, Noah
  et al. (2018) is not on the page and qualifies "it does not", so coverage is partial. Both
  tiers keep the card out of the review lists.
- *List of common misconceptions* (one run each way). Run B reads the 2010 replication as
  qualifying the entry's mood-and-arousal explanation; run A reads it as confirming. The card
  shows the more cautious tier.
- *Religiosity and intelligence* (fix in v5, recommended addition in v6). The v5 fix concerned
  the authors' 2018 letter; v6 moves that to the same edit and adds the unreported Finley et al.
  (2015) replication of the correlational study. The card still proposes an edit.
- *Robert F. Stambaugh* (fix in v5, judgement call in v6). This was caused by my brief wording
  on minor notes and is fixed in the final brief (above).

**Pilot build.** I built the site from a copy of the run directory with the pilot drafts
(output in scratch, not deployed). It gave 73 cards with no validation failures; 12 no-change
studies are flagged as judgement calls. I checked one card (Jan Eeckhout) in a headless
browser: it renders the v6 fields correctly with no console errors.

## Not yet done

- **Site display of the tiers.** The build assigns `no_change_tier`, and judgement calls
  already show as such. Taking *already covered* cards out of the review lists, and labelling
  *likely no change*, still needs a site change.
- **Display overrides.** `text_overrides.json` and `gist_overrides.json` were written for v5
  drafts and are skipped for v6 cards. After the full re-run they need a fresh pass or can be
  dropped.
- **The full re-run.** It needs `blind_packets.py` for all packets, the pre-filter, and route
  assignment updates (the build now accepts a per-card `second_runs` map).

## Decisions before the full re-run

All five are settled (Lukas agreed to the suggestions in 3–5 on 2026-11-13). The full re-run waits until the
hackathon group has finished its review of the cards.

1. **Confirming reanalyses of the same data (decided).** The group agreed (#9, 2026-11-13)
   that a reproduction that re-runs the original analyses on the original data and confirms
   them is *likely no change*. The brief now codes it as `method: reproduction`, its strength
   is `none` with `no_change_basis: reproduction_confirms`, and the tier rule gives *likely no
   change* when every replication that bears on the claim is a confirming reproduction.
2. **The pre-filter's reach (decided).** No article is dropped before coding (Lukas, #9,
   2026-11-13). The cards' *Adds a replication* filter already leaves out articles that cite
   every replication, and coding them still finds fixes, such as the misdescribed original
   study on Door-in-the-face technique. `prefilter.py` now only reports which replications
   each article cites, ignoring Further reading (the group's call: a replication listed only
   there is not yet in the article).
3. **Historical wording for a present-day claim** (TCF7L2). Both runs read it as current
   evidence, which makes the card a judgement call where #9 had *likely no change*. I suggest
   accepting this, because it errs towards review.
4. **Partial coverage** (Strack on the Ig Nobel list). When the page reports one replication
   but not another that also bears on the row, the rule gives *likely no change* rather than
   *already covered*. Both keep the card out of the review lists; only findability differs.
5. **Proceed without re-piloting the post-pilot fixes?** The three brief fixes after the pilot
   (wrong citations in the paragraph, the basis order, one warning) are small. I suggest
   running the full set with the final brief rather than re-piloting.

## Decisions to review

- **FLoRA outcome codes are no longer shown to the drafting model.** This follows Opus's
  review: the codes anchored the AI's own reading of each replication, which now drives the
  tier. It changes the model's inputs relative to v5, so part of the v5–v6 difference may come
  from it rather than from the brief.
- **The tier rule does not use FLoRA outcome codes at all**, not even as a tie-breaker, which
  the agreed design allowed. The AI's own reading (`result_vs_article_claim`) made this
  unnecessary in the pilot.
- **`confidence` is dropped** rather than redefined.
