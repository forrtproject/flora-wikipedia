#!/usr/bin/env python3
"""Spot-check a cross-role sample of cards against live Wikipedia and Crossref.

For each sampled card: fetch the current revision (read API, cached by revid),
confirm the focal claim quote is still present, confirm the original DOI is still
cited, and compare Crossref titles of the original and replications with FLoRA
titles. Orchestrator notes from manual reading are merged from MANUAL below.
Writes runs/edit-prototype-en/manual-inspection.json.
"""
import datetime
import difflib
import json
import re

from common import RUN, dump_json, load_json
from evidence import live_revisions, live_wikitext
from validate import norm
import wikitext_render as wr

SAMPLE = {  # title: role checked
    'Power posing': 'central effect, historical attribution',
    'Romeo and Juliet effect': 'central effect, false "not replicated" claim',
    'Helminthiasis': 'broad topic, health framing (MEDRS)',
    'Francesca Gino': 'biography (BLP), retracted-paper list',
    'Lise Vesterlund': 'biography (BLP), narrowed summary',
    'C-Raf': 'biomedical, RP:CB preprint',
    'CASS4': 'biomedical list context, internal inconsistency',
    'List of Ig Nobel Prize winners': 'list/historical record',
    'Lara Aknin': 'bibliography entry only',
    'Big Five personality traits and culture': 'large-project (OSC 2015) match',
    'Religiosity and intelligence': 'co-cited, multi-study original',
    'More Guns, Less Crime': 'co-cited, reference-list repair',
}
MANUAL = {
    'Power posing': 'Read lead and Initial claims; confirmed citations are attributions and replication coverage is extensive. Agree no change; uncited "lasting hormonal changes" sentence is a real check.',
    'Romeo and Juliet effect': 'Confirmed sentence "While Driscoll\'s study has not been replicated" and that Sinclair et al. (2014) title/abstract describe a replication of Driscoll et al. (1972). Agree contextualise; fallback deletion of the false clause is minimal.',
    'Helminthiasis': 'Compared "improve school attendance by 25 percent" with the abstract ("reduced school absenteeism ... by one-quarter"). Different quantity; agree narrow.',
    'Francesca Gino': 'Confirmed the DOI sits in a bulleted list of retracted papers with {{Retracted}}. Agree no change; adding the replication would risk implying misconduct from a replication outcome.',
    'Lise Vesterlund': 'Compared article sentence (overconfidence only) with abstract (overconfidence and preferences for competing). Agree narrow.',
    'C-Raf': 'Confirmed the replication DOI is a bioRxiv posted-content record. Agree no change; MEDRS.',
    'CASS4': 'Confirmed prose "not found predictive" and table "Odds ratio 0.8888; p-value 1.75 ×10−7" both cite Ruiz_2014. Inconsistency is real; talk-page route appropriate.',
    'List of Ig Nobel Prize winners': 'Prize record; agree no change.',
    'Lara Aknin': 'Publications list only; agree no change.',
    'Big Five personality traits and culture': 'Replication is the OSC 2015 project paper; specific-study match cannot be established from the packet. Agree no change.',
    'Religiosity and intelligence': 'Confirmed "Noernzayan" misspelling and that Sanchez et al. (2017) title/abstract concern a replication of the Thinker prime. Agree narrow.',
    'More Guns, Less Crime': 'Confirmed duplicated DOI/s2cid identifiers across different references. Agree no change to focal citation; retain for citation repair.',
}


def title_sim(a, b):
    return round(difflib.SequenceMatcher(None, norm(a), norm(b)).ratio(), 2)


def main():
    sel = {s['page_title']: s for s in load_json(RUN / 'selection.json')['pages']}
    live = live_revisions([sel[t]['pageid'] for t in SAMPLE], refresh=True)
    out = []
    for title, role in SAMPLE.items():
        s = sel[title]
        cid = s['packet_id']
        pk = load_json(RUN / 'evidence' / cid / 'packet.json')
        draft = load_json(RUN / 'drafts' / 'claude' / f'{cid}.json')
        lv = live[s['pageid']]
        text = live_wikitext(s['pageid'], lv['live_revid'])
        live_plain = norm(wr.plain(text, wr.named_refs(text)))
        quotes = [c['visible_claim_quote'] for c in draft['claim_sites'] if c['is_visible_claim']]
        present = [norm(q) in live_plain for q in quotes]
        orig = pk['original']
        rec = dict(page=title, card_id=cid, role=role,
                   frozen_revid=pk['page']['frozen_revid'], live_revid=lv['live_revid'], live_checked_at=lv['checked_at'],
                   original_doi_in_live=orig['doi'].lower() in text.lower(),
                   claim_quotes_in_live=f'{sum(present)}/{len(present)}',
                   original_title_match=title_sim(orig['flora_title'], (orig['source'].get('crossref') or {}).get('title', '')),
                   replication_title_match=[title_sim(r['flora_title'], (r['source'].get('crossref') or {}).get('title', ''))
                                            for r in pk['replications']],
                   orchestrator_reading=MANUAL[title])
        ok = rec['original_doi_in_live'] and all(present) and rec['original_title_match'] >= 0.8 and \
            all(x >= 0.8 for x in rec['replication_title_match'])
        rec['verified'] = ('live passage and DOI present; Crossref titles match FLoRA titles; '
                           if ok else 'see fields: ' + ', '.join(k for k, v in [
                               ('DOI missing in live', not rec['original_doi_in_live']),
                               ('claim quote changed in live', not all(present)),
                               ('title mismatch', rec['original_title_match'] < 0.8 or any(x < 0.8 for x in rec['replication_title_match']))] if v))
        rec['outcome'] = 'agree with card' if ok else 'agree with card; mechanical check needs human look'
        out.append(rec)
        print(title, rec['claim_quotes_in_live'], rec['original_doi_in_live'], rec['original_title_match'], rec['replication_title_match'])
    n_ok = sum(r['outcome'] == 'agree with card' for r in out)
    dump_json(RUN / 'manual-inspection.json', dict(
        checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
        summary=(f'The orchestrator read {len(out)} cards across roles against the article text and sources, and '
                 f're-checked each against the live article and Crossref. {n_ok}/{len(out)} passed every mechanical '
                 'check (claim still present in the live revision, original DOI still cited, Crossref titles match '
                 'FLoRA titles at similarity ≥ 0.8); the remainder are listed with the failing check. This is model '
                 'review by the orchestrating model, not independent human adjudication.'),
        inspected=out))


if __name__ == '__main__':
    main()
