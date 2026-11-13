## Status
This page describes build `ac7997cf0f14` (2026-11-13T11:45:53+00:00). It has 52 cards, one for each English Wikipedia article, covering 73 studies. The cards were prepared with AI and nobody has checked them yet, so contributors need to check them before acting. This is research material shared for review, not for publication. The dashboard does not edit Wikipedia or Wikidata, post messages or copy text into an editor.

A card shows where an edit might help, which points it could cover and which sources to read. It gives no ready-made wording: contributors decide whether to edit, and write their own text from sources they have read.

For 42 of the 73 studies the AI suggests changing the article and for 31 no change. We show the no-change suggestions too: in most of them the citation is accurate in context.

11 articles cite more than one study. Studies on the same article were assessed together, so that the suggestions for one article do not repeat or contradict each other. 21 articles have at least one suggested edit, not counting judgement calls.

Each suggestion has one of four strengths, set by a fixed rule:

- **Fix:** the article says something its cited source contradicts or does not support, or a citation sits on the wrong claim.
- **Recommended addition:** the article uses the study as evidence, a replication or reanalysis tested that claim directly and failed, found a clearly smaller effect or substantially qualified it, and the article does not say so.
- **Optional addition:** the article is accurate, and the extra information would only confirm or enrich it.
- **None:** no change is suggested.

Additions are not suggested on biographies, lists, timelines or passing mentions.

Each study was assessed twice, independently, by the same AI system. The two assessments agreed on the broad category (edit, optional addition or no change) for 66 of 73 studies. The other 7 are shown as judgement calls with both views; the card leads with the view that suggests more change. Agreement does not mean an assessment is right.

Where both assessments suggest no change, the card is still shown as a judgement call if a replication tested a claim the article relies on, the article does not report it and the replication did not plainly confirm the original (6 studies). The replication database's outcome codes only decide which cards are flagged this way; they never shape what a card says. "No change needed" is kept where no edit has a point: the paper is only listed, a biography or list mentions it in passing, the article already reports the replication, or the replication tests something the article does not rely on.

We searched for legitimate free copies of every paper we had only as an abstract: on author and lab pages, in university repositories and on preprint and working-paper servers. The AI then checked each fact a suggestion relies on against the papers, and the card lists these checks with the passages quoted. An automatic check confirms that each quote appears word for word in the source; it cannot confirm that the AI read it correctly. Papers we could not obtain are listed in `papers-not-obtained.csv` in the downloads.

For each replication we also looked for review articles: first works that cite both the original and the replication, then reviews of the original. We searched their text for the replication. Suggestions cite only sources that were read, and each point names a specific sentence, source or fact. Where no review covers a replication, the suggestion stays within what exists: narrowing the claim to the cited study, an attributed sentence about the replication on an article about that effect, or no change.

| Suggested action | Studies |
|---|---|
| Add context | 22 |
| Narrow a claim | 16 |
| No change | 31 |
| Remove a citation | 2 |
| Remove an unsupported claim | 1 |
| Replace a source | 1 |

| AI recommendation | Studies |
|---|---|
| Leave out of review | 30 |
| Keep for review | 43 |

## Inputs and freshness
The cards build on the complete English citation audit `search/runs/english-full-gh/en` (FLoRA file commit `717fbaf0a35dc662e276d5860dba7faaf7142f93`, SHA-256 `28748e8c…`) and the citation contexts it recorded. In that audit, 586 of the 2,567 original FLoRA studies in scope had their DOI on at least one English article (979 articles and 1,193 article–study pairs in all). These are counts of DOI strings: they do not show that an article discusses a study or mentions its replication.

On 6 October 2026 we saved the current upstream FLoRA file as `search/runs/inputs/flora-latest-20261006.csv` (commit `19012dfaabd54432955d2b1d39cd43da6c76f7c3`). It differs from the audited copy in a single field (one journal name changed from “OSF” to blank). Study pairs, DOIs and outcomes are identical, so we did not repeat the citation inventory.

Article text comes from the revisions saved in the audit. On 2026-10-06 we checked the current revision of each selected article: 1 of 52 had changed since the snapshot. For a changed article, the card records whether the original DOI and the relevant paragraph are still there. Every card links to the snapshot, the current article and the difference between them.

## How articles were selected
Selection ignored replication outcomes. Each article–study pair was classified from the saved article text: the type of article; whether the DOI sits in prose, a list, a bibliography or a hidden comment; and whether the article concerns a living person or health. One study was chosen per article, preferring citations in prose, and each article group was then filled in a fixed pseudo-random order (SHA-256 of `flora-en-edit-prototype-20261006` plus the article–study ID). A test checks that swapping failed and successful replication labels leaves the selection unchanged.

| Article group | Target | Selected | Articles of this kind in the audit |
|---|---|---|---|
| Effect or study article | 16 | 16 | 32 |
| Broad topic article | 13 | 13 | 760 |
| Biography | 7 | 7 | 152 |
| Biomedical (gene, drug or protein) | 4 | 4 | 25 |
| History, timeline or list article | 4 | 4 | 10 |
| Bibliography or list entry only | 3 | 3 | n/a (set by citation context) |
| Original and replication both cited | 5 | 5 | n/a (set by citation context) |

858 of the 979 audited articles cite an original study in prose. Article types come from simple rules (an effect article, for example, is one whose title appears in a study title). The AI then reclassified each article and the role of each citation, and the filters use those classifications. The sample is small and spread across article types on purpose, so its counts describe this sample, not English Wikipedia as a whole. Citations without a DOI were outside the audit, and so are outside the sample.

## Available evidence
For each study we saved Crossref, Europe PMC and OpenAlex records, the abstract and any free full text (Europe PMC XML or a PDF), with the time each was retrieved. Requests were sent one at a time and paced for each service. Review articles suggested by OpenAlex are leads: a listed review has not necessarily been read.

| Source and what was available | Count |
|---|---|
| Original: Abstract only | 18 |
| Original: Full text | 52 |
| Original: Title and details only | 3 |
| Replication: Abstract only | 15 |
| Replication: Full text | 82 |

A paper is counted once for each study it is attached to. Read the full paper before relying on it, especially where only the abstract was available.

## Earlier experiment: does full text change the suggestions?
We ran this experiment on the first build, so its numbers do not describe the current cards.

We searched free sources for the 90 papers we then had only as an abstract or as publication details. Usable text came back for 21 (8 of 47 originals and 13 of 43 replications) in 13 minutes. Most failures were paywalled APA, SAGE, Elsevier and Wiley papers; we did not try institutional access, because that step only works on macOS. Four of the files were supplementary material rather than the article, and several were working papers or author manuscripts. The identity check let these through because their titles matched.

Before any full text was read, GPT-6.1 Sol predicted from the abstracts which assessments the full text would change. Claude then reassessed 20 studies twice: once with the full text and once, as a control, without it. GPT-6.1 Sol compared each pair against the full-text files, and Claude Opus 5.5 checked four of its verdicts. No person reviewed this comparison.

Full text made a meaningful difference to 13 of the 20 studies. Most changes settled or sharpened a check: the C-Raf structure citation, for example, turned out to be supported by the paper's supplement. One study changed its suggested action: for Door-in-the-face, the replication tested a different study from the one the article describes. For Facial feedback, the suggested edit no longer needed a condition. Repeating an assessment without new evidence also changed the action for 2 studies, about as often as full text did. The predictions from abstracts missed 7 of the meaningful changes, including both of these.

**What follows.** Get the full text of every source behind a suggestion that is kept or still uncertain, starting with the replications, which hold the detail needed to match the exact study. Check that each file is the article, not a supplement. Institutional access should reach most of the papers still missing.

## Earlier comparison of AI systems
Three AI systems were given the same instructions and evidence for five pilot articles: Power posing (central effect; co-cited); Daydreaming (broad topic; current support); Francesca Gino (BLP; retracted paper list); C-Raf (biomedical; RP:CB preprint); Lara Aknin (BLP; publications list). Each result was scored from 0 to 2 on five criteria: factual support, fit to the article, specific advice, traceable sources and stated uncertainty. Claude Opus 5.5 did the scoring after reading the evidence, so the comparison may favour Claude. No person scored the results.

| AI system | Access | Mean seconds per study | Score out of 50 |
|---|---|---|---|
| Claude | Claude subscription | 72.7 | 50 |
| Codex | ChatGPT subscription | 96.0 | 47 |
| Gemini | Google sign-in | 222.6 | 41 |

Claude used Opus 5.5, Codex used GPT-6.1 Sol and Gemini used 3.8 Flash, the last two with high reasoning effort. Full settings and scores are in `route_comparison.json`.

All five Claude results passed the automatic checks first time. Codex passed four, and all five once we fixed a check that wrongly rejected DOIs already cited in the article. Gemini passed three: one result had an unexpected field, and one attempt returned nothing and worked on a retry. On two pilot articles, Gemini also stated facts or study matches that the evidence did not support.

We chose Claude for the full set because it scored highest, was fastest and most reliably spotted other problems in the article. Codex assessed the first 52 selected studies independently, as a comparison; Gemini was not used after the pilot. The instructions were then extended: the AI now sees the whole article, follows rules on secondary sources and on other problems in the article, and may not state anything from memory. All current assessments were made by Claude.

In that comparison, Claude and Codex agreed on the broad action (edit, no change or wait) for 36 of the 52 studies. Codex more often suggested waiting, usually because it could not get the sources. Most other differences were between adding context and narrowing a claim, so both suggested an edit. Codex took 114.9 seconds per study on average. Claude Opus 5.5 reviewed the substantive disagreements; its notes are in the downloads.

## Earlier spot checks
On 2026-10-06, Claude Opus 5.5 checked 12 assessments against the article text, the sources, the current revisions and Crossref. All quoted claims and original DOIs were still in the articles, and the Crossref and FLoRA titles matched closely (similarity of at least 0.8). These were AI checks of an earlier version, so they do not show that the current cards are right.

| Article | Citation context | Outcome |
|---|---|---|
| Power posing | central effect, historical attribution | agrees with card |
| Romeo and Juliet effect | central effect, false "not replicated" claim | agrees with card |
| Helminthiasis | broad topic, health framing (MEDRS) | agrees with card |
| Francesca Gino | biography (BLP), retracted-paper list | agrees with card |
| Lise Vesterlund | biography (BLP), narrowed summary | agrees with card |
| C-Raf | biomedical, RP:CB preprint | agrees with card |
| CASS4 | biomedical list context, internal inconsistency | agrees with card |
| List of Ig Nobel Prize winners | list/historical record | agrees with card |
| Lara Aknin | bibliography entry only | agrees with card |
| Big Five personality traits and culture | large-project (OSC 2015) match | agrees with card |
| Religiosity and intelligence | co-cited, multi-study original | agrees with card |
| More Guns, Less Crime | co-cited, reference-list repair | agrees with card |

The detailed readings are in `manual-inspection.json`.

## Writing and Wikipedia policies
Write your own text from sources you have read; the [contributor workflow](guide.html) explains how.

On 6 October 2026 we read [Writing articles with large language models](https://en.wikipedia.org/wiki/Wikipedia:Writing_articles_with_large_language_models) (revision 1378473005, 4 October 2026), the talk page guidelines (revision 1378840295) and the bot policy (revision 1372438517). They advise against AI-generated article text and talk-page comments, and against repetitive edits worked through from a list. Pressing save does not make generated wording your own. Policies change, so check them again before an event.

## Cost
Metered API charges: **US$0.00** (cap US$1.00). Every AI system was used through a subscription or a Google sign-in, so no metered API key was needed, and OpenAlex queries stayed within its free allowance. Subscription fees are not included. The cost record is in the downloads.

## Reproduce
For organisers rebuilding the dashboard:

```sh
bash editing-support/build.sh                 # offline rebuild from saved evidence and assessments
bash editing-support/build.sh --refresh-live  # also check current Wikipedia revision IDs
python3 editing-support/tests/test_edit_prototype.py
```

`editing-support/run_route.py` reruns the AI assessments. It can resume, and skips saved results that already parse. The instructions, settings and full AI outputs, including the earlier draft wording, are archived in `editing-support/runs/edit-prototype-en` (instruction files in `drafts/claude/*.prompt.txt`, everything else in `archive/`) and are not part of the downloads.

## What still needs people
- Read the article, its talk page and the full sources before acting, and check every fact your edit relies on.
- Read secondary sources before saying anything about the overall state of the evidence.
- Confirm that a replication tested the exact study and claim, especially where its abstract does not name the original.
- Apply the rules on biographies of living people and on medical sources where they are relevant.
- Before giving participants a review list, have two people independently check each decision to keep, leave out or defer a suggestion.
- Check policies and the current article revisions again close to any event.
