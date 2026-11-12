# Drafting brief v6: review of v5 and pilot plan

Prepared on 2026-11-12 from issue #9 and the card-by-card review of the 31
no-change items (PR #20 and the issue comments). This file is the starting
brief for the v6 revision and pilot; it is not the brief itself.

## Agreed design (issue #9)

No-change suggestions fall into three tiers, assigned by a fixed build rule, not by
the AI choosing a label:

1. **Already covered:** the Wikipedia article already cites or accurately reports the
   replication. These cards are taken out of the review lists but stay findable.
   Articles that cite every FLoRA replication we hold are dropped before coding.
2. **Likely no change:** only clear cases. The paper is only listed; a biography or list
   names it without stating its finding; it is cited for history or as an example; or
   the replication tested something the article does not rely on.
3. **Judgement call:** every other no-change item. This is the default.

FLoRA outcome codes may decide which cards are flagged for people. They never shape
card wording.

## What the v5 coding could not support

- **Missing facts for the rule.** Three of today's tier calls had to be made by hand
  (`editing-support/label_overrides.json`).
  - *Jan Eeckhout* and *Lise Vesterlund* are biographies that state the paper's finding.
    v5 has no field recording whether the article states a finding, as opposed to
    naming or listing the paper.
  - *Functional accounts of emotion*: the replication tested another experiment from
    the same paper, and that experiment bears on the article's broader claim. v5's
    `specific_study_match` has `mismatch` for both this case and for unrelated
    results, such as other gene loci in CASS4 or a scarcity audit in Religiosity and
    intelligence.
- **The confidence field does not discriminate.** 29 of the 31 no-change items are
  rated `high`. Either define it operationally or drop it; do not base a tier on it.
- **Priming in the brief itself.** Step 5 says '"No change" is a good, common outcome.'
  That is the priming the group objected to in the label. Replace it with a neutral
  instruction: choose what the evidence supports, and record the evidence relation
  even when you choose no change.
- **The strength rules collide.** Rule 3 makes "a replication of a different experiment
  from the same paper" an `optional_addition`. A later rule bans additions on
  biographies, lists and passing mentions. The AI resolved the collision by choosing
  `none`, which hid the fact that the replication bears on the claim (van Dijk on
  Functional accounts of emotion). Keep the ban on additions for those page types, but
  record the evidence relation separately, so that the build can still flag the card.
- **One judgement for several replications.** Cards with several replications (Piff:
  three; Tversky & Kahneman: four) get one item-level match and acknowledgement. Code
  each replication separately.
- **"Already reported" is coarse.** The tier needs to know how the article reports a
  replication: cited by DOI or reference, described in prose, or covered through
  another source (CASS4, Strack). It also needs to know whether that report is accurate.
- **Unstructured minor notes.** `alternatives` mixes reference-list slips, wording
  fixes, optional extra references and notes that the replication "belongs in the X
  article". Give each note a type, and give the target article where one is named:
  those are leads for other pages.
- **Wording that the build rewrites.** The build rewrites "the article" to "the
  Wikipedia article" and the "Article:" prefix in verifications. Ask for that wording
  directly.

## Proposed changes for v6 (for the reviewers to improve)

1. Add per-replication coding, for example `replications_assessed[]`, each with:
   - `doi`;
   - `tests`: `same_claim` | `same_paper_related_result` | `same_paper_unrelated_result`
     | `reanalysis_same_data` | `different_topic` | `unclear`;
   - `bears_on_article_claim`: `direct` | `indirect` | `none`, with a note;
   - `result_vs_original`, the AI's reading of the papers: `confirms` | `qualifies` |
     `fails` | `inconclusive`;
   - `already_on_page`: `cited` | `reported_in_prose` | `reported_via_other_source` |
     `no`, with `report_accurate` (true, false or null).
2. Add article-use fields: `states_finding` (whether the article states the paper's
   result, attributed or as fact) and `relies_as_evidence` (boolean). Keep
   `article_scope` and `citation_function`.
3. Replace `confidence`, or keep it and add `no_change_basis` with the values
   `listed_only` | `named_without_finding` | `history_or_example` | `tests_other_claim`
   | `already_reported` | `confirms_claim` | `none_applies`.
4. Type each `alternatives` entry: `reference_slip` | `wording` | `optional_reference` |
   `belongs_elsewhere` (with `target_article`) | `other`.
5. Remove the "No change is a good, common outcome" sentence. Resolve the collision
   between rule 3 and the page-type ban as described above.
6. Show the AI, in the packet, which replications the page already cites (the packet
   already has `doi_detected_on_page`). Extend the detection beyond DOIs to title
   matches if that is cheap.
7. Write "the Wikipedia article" directly.

Candidate build rule, to replace `replication_bears_on_claim` and the overrides. It
applies only when the AI proposes no change:

- **Already covered:** every replication with `bears_on_article_claim` ≠ `none` has
  `already_on_page` ≠ `no` and `report_accurate` ≠ false.
- **Likely no change:** no replication bears on the claim (all `none`), or the article
  neither states the finding nor relies on the paper as evidence, and no `fix`.
- **Judgement call:** everything else.

Optionally, keep the FLoRA screening flag only as a tie-breaker. The pilot should
check whether the v6 tiers reproduce the hand calls in PR #20 without any overrides.

## Pilot

- **Articles:** 20 of the 52 coded articles.
  - Include: Functional accounts of emotion, Jan Eeckhout, Lise Vesterlund, C-Raf,
    List of cognitive biases, Oxytocin, Deniz Başkent, Outgroup favoritism, National
    accounts, Protection motivation theory, List of Ig Nobel Prize winners, TCF7L2,
    CASS4, Heejung Kim, List of common misconceptions about arts and culture.
  - Add five edit, optional or two-run-disagreement articles across strata, as a
    regression check.
  - More Guns, Less Crime, Red dress effect, Priming (psychology) and Facial feedback
    hypothesis cite all their replications by DOI. Use them to test the pre-filter, not
    for drafting.
- **Runs:** two independent runs per article, as in v5.
- **Compare:** v6 against v5, per study. Report action, strength, tier, agreement between
  the two runs, and agreement with the per-card calls in the #9 comment.
