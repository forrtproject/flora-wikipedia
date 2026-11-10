#!/usr/bin/env python3
"""Stratified, outcome-blind selection of English pages for edit-suggestion cards.

Every English article-original packet receives screening features derived from
the frozen wikitext (page kind, citation location, health/BLP flags). Pages are
then filled into coverage strata in a fixed hash order. The FLoRA outcome is
used only to check that selected pages are not dominated by one outcome; it is
never a ranking key. The output is a candidate list for human-style review,
not a judgement that any page needs an edit.
"""
import argparse
import collections
import csv
import json
import re

from common import (LIST_SECTIONS, HEALTH_TERMS, PACKETS, RUN, categories, dump_json, is_biography,
                    is_living, sha, wikitext)

SALT = 'flora-en-edit-prototype-20261006'
# Strata quotas (pages). Overlap is allowed for flags; each page fills one stratum.
QUOTAS = [('central_effect', 16), ('broad_topic', 13), ('biography', 7), ('biomedical', 4),
          ('history_list', 4), ('list_or_bibliography', 3), ('co_cited', 5)]
EFFECT_WORDS = re.compile(r'\b(effect|bias|phenomenon|hypothesis|heuristic|fallacy|paradox|illusion|theory|technique|'
                          r'experiment|game|penalty|threat|priming|posing)\b', re.I)
BIOMED = re.compile(r'\{\{\s*infobox (gene|protein|drug)|\[\[\s*category:[^\]]*(genes on|proteins|receptors|'
                    r'transcription factors|oncogenes|kinases)', re.I)


def is_central(title, study, lead):
    phrase = re.sub(r'\s*\(.*\)', '', title).lower()
    if not re.search(r'(?<![a-z])' + re.escape(phrase) + r'(?![a-z])', study.lower()):
        return False
    first = re.sub(r"\{\{.*?\}\}|<ref.*?(/>|</ref>)|'''?", '', lead, flags=re.S).strip()[:400]
    return len(phrase.split()) >= 2 and bool(EFFECT_WORDS.search(phrase + ' ' + first)) or bool(EFFECT_WORDS.search(phrase))


def context_kind(packet, text):
    kinds = []
    for c in packet['raw_contexts']:
        if c['doi_role'] != 'original':
            continue
        sec = (c['section'] or '').strip().lower()
        pos = int(c['match_pos'])
        before = text[:pos]
        if before.rfind('<!--') > before.rfind('-->'):
            kinds.append('comment')
        elif sec in LIST_SECTIONS:
            kinds.append('list')
        else:
            prose = re.sub(r'<ref[^>]*?/>|<ref[^>]*>.*?</ref>|\{\{[^{}]*\}\}', '', c['paragraph'] or '', flags=re.S)
            kinds.append('inline' if len(prose.strip()) > 60 and not prose.lstrip().startswith(('*', '#')) else 'list')
    if 'inline' in kinds:
        return 'inline'
    return kinds[0] if kinds else 'unknown'


def features(packets):
    out = []
    by_page = collections.Counter(p['pageid'] for p in packets)
    for p in packets:
        text = wikitext(p['pageid'])
        title = p['page_title']
        study = ' '.join([p['original_title']] + [q['title_r'] for q in p['pairs']])
        lead = text[:4000]
        body = re.sub(r'^(\{\{.*?\}\}\s*)+', '', text, flags=re.S)[:1500]
        central = is_central(title, study, body)
        kind = ('history_list' if re.match(r'^(\d{3,4}s? in |List of |Timeline of )', title) else
                'biography' if is_biography(text) else
                'biomedical' if BIOMED.search(text) else
                'central_effect' if central else 'broad_topic')
        outcomes = sorted({q['outcome'] for q in p['pairs']})
        out.append(dict(
            packet_id=p['packet_id'], pageid=p['pageid'], page_title=title, original_doi=p['original_doi'],
            page_kind=kind, context_kind=context_kind(p, text),
            living_person=is_living(text), health_flag=bool(HEALTH_TERMS.search(title + ' ' + ' '.join(categories(text)) + ' ' + lead[:1500])),
            co_cited=any('Both DOI' in q['assessment'] for q in p['pairs']),
            originals_on_page=by_page[p['pageid']], outcomes='|'.join(outcomes),
            large_project=any(re.search(r'many labs|reproducibility of psychological science|score', q['title_r'], re.I) for q in p['pairs']),
            order=sha(SALT + p['packet_id'])))
    return out


def select(rows, n_pages):
    by_page = collections.defaultdict(list)
    for r in rows:
        by_page[r['pageid']].append(r)
    chosen, seen = [], set()

    def page_rep(pid):
        # The page's focal packet: inline contexts first, then hash order (never outcome).
        return sorted(by_page[pid], key=lambda r: (r['context_kind'] != 'inline', r['order']))[0]

    pool = sorted((page_rep(pid) for pid in by_page), key=lambda r: r['order'])
    for stratum, quota in QUOTAS:
        for r in pool:
            if sum(c['stratum'] == stratum for c in chosen) >= quota:
                break
            if r['pageid'] in seen:
                continue
            if stratum == 'co_cited':
                ok = r['co_cited'] and r['context_kind'] == 'inline'
            elif stratum == 'list_or_bibliography':
                ok = r['context_kind'] in ('list', 'comment')
            else:
                ok = r['page_kind'] == stratum and r['context_kind'] == 'inline'
            if ok:
                chosen.append({**r, 'stratum': stratum})
                seen.add(r['pageid'])
    return chosen[:n_pages]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pages', type=int, default=52)
    a = ap.parse_args()
    packets = [p for p in json.loads(PACKETS.read_text()) if p['language'] == 'en']
    rows = features(packets)
    RUN.mkdir(parents=True, exist_ok=True)
    with (RUN / 'packet_features.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    chosen = select(rows, a.pages)
    dump_json(RUN / 'selection.json', dict(
        salt=SALT, quotas=dict(QUOTAS), rule='Outcome-blind: strata filled in SHA-256 order of salt+packet_id; '
        'focal packet per page prefers inline (visible-claim) contexts.', pages=chosen))
    c = collections.Counter(r['stratum'] for r in chosen)
    print(len(chosen), dict(c))
    print('outcomes', collections.Counter(o for r in chosen for o in r['outcomes'].split('|')))
    print('living', sum(r['living_person'] for r in chosen), 'health', sum(r['health_flag'] for r in chosen))


if __name__ == '__main__':
    main()
