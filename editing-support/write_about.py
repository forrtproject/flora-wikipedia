"""Generate the method and coverage page from recorded products."""
import collections
import csv

from common import RUN, load_json

STRATUM = {'central_effect': 'Effect or study article', 'broad_topic': 'Broad topic article', 'biography': 'Biography',
           'biomedical': 'Biomedical (gene, drug or protein)', 'history_list': 'History, timeline or list article',
           'list_or_bibliography': 'Bibliography or list entry only', 'co_cited': 'Original and replication both cited'}
ACTION = {'contextualise': 'Add context', 'narrow_claim': 'Narrow a claim', 'replace_source': 'Replace a source',
          'remove_unsupported_claim': 'Remove an unsupported claim', 'remove_citation': 'Remove a citation',
          'no_change': 'No change', 'defer': 'Wait for more evidence', 'talk_page': 'Discuss on the talk page'}
EVIDENCE = {'full_text': 'Full text', 'abstract': 'Abstract only', 'metadata_only': 'Title and details only'}


def table(header, rows):
    out = ['| ' + ' | '.join(header) + ' |', '|' + '---|' * len(header)]
    out += ['| ' + ' | '.join(str(x) for x in r) + ' |' for r in rows]
    return '\n'.join(out)


def about_md(data):
    c = data['counts']
    sel = load_json(RUN / 'selection.json')
    rc = load_json(RUN / 'route_comparison.json')
    ledger = load_json(RUN / 'cost-ledger.json', {})
    manual = load_json(RUN / 'manual-inspection.json', {})
    feats = list(csv.DictReader((RUN / 'packet_features.csv').open()))
    pages_by_kind = collections.Counter()
    seen = set()
    for f in feats:
        if f['pageid'] not in seen:
            seen.add(f['pageid'])
            pages_by_kind[f['page_kind']] += 1
    inline_pages = len({f['pageid'] for f in feats if f['context_kind'] == 'inline'})
    cards = data['cards']  # Study assessments; the dashboard groups these by article.
    pages = data['pages']
    selected_by_kind = collections.Counter(p['stratum'] for p in pages)
    revised_pages = sum(bool(p['live_check'].get('changed_since_frozen')) for p in pages)
    src_levels = collections.Counter()
    for card in cards:
        src_levels['Original: ' + EVIDENCE[card['original']['evidence_level']]] += 1
        for r in card['replications']:
            src_levels['Replication: ' + EVIDENCE[r['evidence_level']]] += 1
    n = c['items']
    nochange = c['proposed_action'].get('no_change', 0)
    defer = c['proposed_action'].get('defer', 0)
    edits = n - nochange - defer - c['proposed_action'].get('talk_page', 0)
    actions = (f"For {edits} of the {n} studies the AI suggests changing the article"
               + ''.join(f", for {v} {label}" for v, label in ((c['proposed_action'].get('talk_page', 0), 'raising it on the talk page'),
                                                               (defer, 'waiting for more evidence')) if v)
               + f" and for {nochange} no change.")
    disagree = c['two_runs'] - c['two_runs_agree']
    L = ['## Status',
         f"This page describes build `{data['build_id']}` ({data['built_at']}). It has {len(pages)} cards, one for each "
         f"English Wikipedia article, covering {n} studies. The cards were prepared with AI and nobody has checked "
         'them yet, so contributors need to check them before acting. This is private research material, not for '
         'publication. The dashboard does not edit Wikipedia or Wikidata, post messages or copy text into an editor.', '',
         'A card shows where an edit might help, which points it could cover and which sources to read. It gives no '
         'ready-made wording: contributors decide whether to edit, and write their own text from sources they have '
         'read.', '',
         f"{actions} We show the no-change suggestions too: in most of them the "
         'citation is accurate in context.', '',
         f"{c['pages_with_several_studies']} articles cite more than one study. Studies on the same article were "
         'assessed together, so that the suggestions for one article do not repeat or contradict each other. '
         f"{c['pages_with_edit']} articles have at least one suggested edit, not counting judgement calls."
         + (f" {c['pages_with_adjacent']} also list other problems found in the article." if c['pages_with_adjacent'] else ''), '',
         'Each suggestion has one of four strengths, set by a fixed rule:', '',
         '- **Fix:** the article says something its cited source contradicts or does not support, or a citation sits on the wrong claim.',
         '- **Recommended addition:** the article uses the study as evidence, a replication or reanalysis tested that '
         'claim directly and failed, found a clearly smaller effect or substantially qualified it, and the article does not say so.',
         '- **Optional addition:** the article is accurate, and the extra information would only confirm or enrich it.',
         '- **None:** no change is suggested.', '',
         'Additions are not suggested on biographies, lists, timelines or passing mentions.', '',
         f"Each study was assessed twice, independently, by the same AI system. The two assessments agreed on the "
         f"broad category (edit, optional addition or no change) for {c['two_runs_agree']} of {c['two_runs']} studies. "
         f"The other {disagree} are shown as judgement calls with both views; the card leads with the view that "
         'suggests more change. Agreement does not mean an assessment is right.', '',
         f"Where both assessments suggest no change, the card is still shown as a judgement call if a replication "
         'tested a claim the article relies on, the article does not report it and the replication did not plainly '
         f"confirm the original ({c.get('no_change_flagged', 0)} studies). The replication database's outcome codes "
         'only decide which cards are flagged this way; they never shape what a card says. "No change needed" is '
         'kept where no edit has a point: the paper is only listed, a biography or list mentions it in passing, the '
         'article already reports the replication, or the replication tests something the article does not rely on.', '',
         'We searched for legitimate free copies of every paper we had only as an abstract: on author and lab pages, '
         'in university repositories and on preprint and working-paper servers. The AI then checked each fact a '
         'suggestion relies on against the papers, and the card lists these checks with the passages quoted. An '
         'automatic check confirms that each quote appears word for word in the source; it cannot confirm that the '
         'AI read it correctly. Papers we could not obtain are listed in `papers-not-obtained.csv` in the downloads.', '',
         'For each replication we also looked for review articles: first works that cite both the original and the '
         'replication, then reviews of the original. We searched their text for the replication. Suggestions cite '
         'only sources that were read, and each point names a specific sentence, source or fact. Where no review '
         'covers a replication, the suggestion stays within what exists: narrowing the claim to the cited study, an '
         'attributed sentence about the replication on an article about that effect, or no change.', '',
         table(['Suggested action', 'Studies'],
               [(ACTION.get(k, k), v) for k, v in sorted(c['proposed_action'].items())]), '',
         table(['AI recommendation', 'Studies'],
               [({'retain': 'Keep for review', 'drop': 'Leave out of review', 'defer': 'Wait'}.get(k, k), v)
                for k, v in sorted(c['queue_recommendation'].items())]), '']
    L += ['## Inputs and freshness',
          'The cards build on the complete English citation audit `search/runs/english-full-gh/en` (FLoRA file commit '
          '`717fbaf0a35dc662e276d5860dba7faaf7142f93`, SHA-256 `28748e8c…`) and the citation contexts it recorded. '
          'In that audit, 586 of the 2,567 original FLoRA studies in scope had their DOI on at least one English '
          'article (979 articles and 1,193 article–study pairs in all). These are counts of DOI strings: they do not '
          'show that an article discusses a study or mentions its replication.', '',
          'On 6 October 2026 we saved the current upstream FLoRA file as '
          '`search/runs/inputs/flora-latest-20261006.csv` (commit `19012dfaabd54432955d2b1d39cd43da6c76f7c3`). '
          'It differs from the audited copy in a single field (one journal name changed from “OSF” to blank). '
          'Study pairs, DOIs and outcomes are identical, so we did not repeat the citation inventory.', '',
          f"Article text comes from the revisions saved in the audit. On {cards[0]['live_check']['checked_at'][:10]} "
          f"we checked the current revision of each selected article: {revised_pages} of {len(pages)} had changed since "
          'the snapshot. For a changed article, the card records whether the original DOI and the relevant paragraph '
          'are still there. Every card links to the snapshot, the current article and the difference between them.', '']
    L += ['## How articles were selected',
          'Selection ignored replication outcomes. Each article–study pair was classified from the saved article '
          'text: the type of article; whether the DOI sits in prose, a list, a bibliography or a hidden comment; and '
          'whether the article concerns a living person or health. One study was chosen per article, preferring '
          'citations in prose, and each article group was then filled in a fixed pseudo-random order (SHA-256 of '
          f"`{sel['salt']}` plus the article–study ID). A test checks that swapping failed and successful "
          'replication labels leaves the selection unchanged.', '',
          table(['Article group', 'Target', 'Selected', 'Articles of this kind in the audit'],
                [(STRATUM[k], q, selected_by_kind.get(k, 0), pages_by_kind.get(k, 'n/a (set by citation context)'))
                 for k, q in sel['quotas'].items()]), '',
          f"{inline_pages} of the 979 audited articles cite an original study in prose. Article types come from "
          'simple rules (an effect article, for example, is one whose title appears in a study title). The AI then '
          'reclassified each article and the role of each citation, and the filters use those classifications. The '
          'sample is small and spread across article types on purpose, so its counts describe this sample, not '
          'English Wikipedia as a whole. Citations without a DOI were outside the audit, and so are outside the sample.', '']
    L += ['## Available evidence',
          'For each study we saved Crossref, Europe PMC and OpenAlex records, the abstract and any free full text '
          '(Europe PMC XML or a PDF), with the time each was retrieved. Requests were sent one at a time and paced '
          'for each service. Review articles suggested by OpenAlex are leads: a listed review has not necessarily '
          'been read.', '',
          table(['Source and what was available', 'Count'], sorted(src_levels.items())), '',
          'A paper is counted once for each study it is attached to. Read the full paper before relying on it, '
          'especially where only the abstract was available.', '']
    ft = load_json(RUN / 'ft-skill' / 'summary.json')
    if ft:
        r = ft['results']
        frac = lambda s: s.replace('/', ' of ')
        L += ['## Earlier experiment: does full text change the suggestions?',
              'We ran this experiment on the first build, so its numbers do not describe the current cards.', '',
              f"We searched free sources for the {ft['targets']} papers we then had only as an abstract or as publication "
              f"details. Usable text came back for {ft['usable_text']} ({frac(ft['usable_by_role']['original'])} originals "
              f"and {frac(ft['usable_by_role']['replication'])} replications) in {ft['wall_clock_seconds'] // 60} minutes. "
              'Most failures were paywalled APA, SAGE, Elsevier and Wiley papers; we did not try institutional access, '
              'because that step only works on macOS. Four of the files were supplementary material rather than the '
              'article, and several were working papers or author manuscripts. The identity check let these through '
              'because their titles matched.', '',
              'Before any full text was read, GPT-6.1 Sol predicted from the abstracts which assessments the full text '
              f"would change. Claude then reassessed {ft['cards_gaining_full_text']} studies twice: once with the full "
              'text and once, as a control, without it. GPT-6.1 Sol compared each pair against the full-text files, and '
              'Claude Opus 5.5 checked four of its verdicts. No person reviewed this comparison.', '',
              f"Full text made a meaningful difference to {r['meaningful_change_attributable_to_full_text']} of the "
              f"{ft['cards_gaining_full_text']} studies. Most changes settled or sharpened a check: the C-Raf structure "
              "citation, for example, turned out to be supported by the paper's supplement. One study changed its "
              'suggested action: for Door-in-the-face, the replication tested a different study from the one the article '
              'describes. For Facial feedback, the suggested edit no longer needed a condition. Repeating an assessment '
              f"without new evidence also changed the action for {r['rerun_noise_action_flips']} studies, about as often "
              f"as full text did. The predictions from abstracts missed {ft['triage']['false_negative']} of the meaningful "
              'changes, including both of these.', '',
              '**What follows.** Get the full text of every source behind a suggestion that is kept or still uncertain, '
              'starting with the replications, which hold the detail needed to match the exact study. Check that each '
              'file is the article, not a supplement. Institutional access should reach most of the papers still missing.', '']
    routes = rc['routes']
    names = {'claude': 'Claude', 'codex': 'Codex', 'agy': 'Gemini'}
    L += ['## Earlier comparison of AI systems',
          'Three AI systems were given the same instructions and evidence for five pilot articles: '
          + '; '.join(rc['pilot_cards'].values()) + '. Each result was scored from 0 to 2 on five criteria: factual '
          'support, fit to the article, specific advice, traceable sources and stated uncertainty. Claude Opus 5.5 did '
          'the scoring after reading the evidence, so the comparison may favour Claude. No person scored the results.', '',
          table(['AI system', 'Access', 'Mean seconds per study', 'Score out of 50'],
                [(names[k], {'claude': 'Claude subscription', 'codex': 'ChatGPT subscription', 'agy': 'Google sign-in'}[k],
                  v['mean_seconds'], v['total']) for k, v in routes.items()]), '',
          'Claude used Opus 5.5, Codex used GPT-6.1 Sol and Gemini used 3.8 Flash, the last two with high reasoning '
          'effort. Full settings and scores are in `route_comparison.json`.', '',
          'All five Claude results passed the automatic checks first time. Codex passed four, and all five once we '
          'fixed a check that wrongly rejected DOIs already cited in the article. Gemini passed three: one result had '
          'an unexpected field, and one attempt returned nothing and worked on a retry. On two pilot articles, Gemini '
          'also stated facts or study matches that the evidence did not support.', '',
          'We chose Claude for the full set because it scored highest, was fastest and most reliably spotted other '
          'problems in the article. Codex assessed the first 52 selected studies independently, as a comparison; '
          'Gemini was not used after the pilot. The instructions were then extended: the AI now sees the whole '
          'article, follows rules on secondary sources and on other problems in the article, and may not state '
          'anything from memory. All current assessments were made by Claude.', '']
    if rc.get('full_run'):
        fr = rc['full_run']
        L += [f"In that comparison, Claude and Codex agreed on the broad action (edit, no change or wait) for "
              f"{fr['same_category_edit_nochange_defer']} of the {fr['cards']} studies. Codex more often suggested "
              'waiting, usually because it could not get the sources. Most other differences were between adding '
              f"context and narrowing a claim, so both suggested an edit. Codex took {fr['codex_mean_seconds']} seconds "
              'per study on average. Claude Opus 5.5 reviewed the substantive disagreements; its notes are in the downloads.', '']
    if manual:
        inspected = manual.get('inspected', [])
        L += ['## Earlier spot checks',
              f"On {manual['checked_at'][:10]}, Claude Opus 5.5 checked {len(inspected)} assessments against the article "
              'text, the sources, the current revisions and Crossref. All quoted claims and original DOIs were still in '
              'the articles, and the Crossref and FLoRA titles matched closely (similarity of at least 0.8). These were '
              'AI checks of an earlier version, so they do not show that the current cards are right.', '',
              table(['Article', 'Citation context', 'Outcome'],
                    [(m['page'], m['role'], m['outcome'].replace('agree with', 'agrees with')) for m in inspected]), '',
              'The detailed readings are in `manual-inspection.json`.', '']
    L += ['## Writing and Wikipedia policies',
          'Write your own text from sources you have read; the [contributor workflow](guide.html) explains how.', '',
          'On 6 October 2026 we read [Writing articles with large language models]'
          '(https://en.wikipedia.org/wiki/Wikipedia:Writing_articles_with_large_language_models) (revision 1378473005, '
          '4 October 2026), the talk page guidelines (revision 1378840295) and the bot policy (revision 1372438517). '
          'They advise against AI-generated article text and talk-page comments, and against repetitive edits worked '
          'through from a list. Pressing save does not make generated wording your own. Policies change, so check '
          'them again before an event.', '']
    if ledger:
        L += ['## Cost',
              f"Metered API charges: **US${ledger['cumulative_task_metered_api_cost_usd']:.2f}** "
              f"(cap US${ledger['cap_usd']:.2f}). Every AI system was used through a subscription or a Google sign-in, "
              'so no metered API key was needed, and OpenAlex queries stayed within its free allowance. Subscription '
              'fees are not included. The cost record is in the downloads.', '']
    L += ['## Reproduce',
          'For organisers rebuilding the dashboard:', '',
          '```sh', 'bash editing-support/build.sh                 # offline rebuild from saved evidence and assessments',
          'bash editing-support/build.sh --refresh-live  # also check current Wikipedia revision IDs',
          'python3 editing-support/tests/test_edit_prototype.py', '```', '',
          '`editing-support/run_route.py` reruns the AI assessments. It can resume, and skips saved results that already '
          'parse. The instructions, settings and full AI outputs, including the earlier draft wording, are archived '
          'in `editing-support/runs/edit-prototype-en` (instruction files in `drafts/claude/*.prompt.txt`, everything else in '
          '`archive/`) and are not part of the downloads.', '',
          '## What still needs people',
          '- Read the article, its talk page and the full sources before acting, and check every fact your edit relies on.',
          '- Read secondary sources before saying anything about the overall state of the evidence.',
          '- Confirm that a replication tested the exact study and claim, especially where its abstract does not name the original.',
          '- Apply the rules on biographies of living people and on medical sources where they are relevant.',
          '- Before giving participants a review list, have two people independently check each decision to keep, leave out or defer a suggestion.',
          '- Check policies and the current article revisions again close to any event.']
    return '\n'.join(L) + '\n'
