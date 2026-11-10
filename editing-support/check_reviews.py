#!/usr/bin/env python3
"""Do the review search for contributors instead of handing them a generic task.

For every packet, take up to five OpenAlex leads (works citing both the original and a
replication first, then reviews citing the original), try to obtain their text with the
download-paper skill (free routes only; see fetch_fulltext.py), fall back to the
abstract, and look for the replication's first author and year within 250 characters
of each other. Results go to cache/reviews_checked/<packet>.json and are shown to
drafters as "review articles checked". Also fetches missing full texts for the
packets' own sources. Restartable: downloads are logged in ft-skill/results.jsonl.
"""
import json
import re

from common import RUN, dump_json, load_json
from fetch_fulltext import fetch_one
from validate import norm

MAX_LEADS = 5


def text_for(doi, abstract):
    rec = fetch_one(doi)
    if rec.get('text_path'):
        return (RUN / rec['text_path']).read_text(errors='replace'), 'full_text', rec['text_path']
    return abstract or '', 'abstract' if abstract else 'metadata_only', ''


def surname(source):
    authors = (source.get('crossref') or {}).get('authors') or []
    return authors[0].split()[-1] if authors and authors[0] else ''


def mentions(text, name, year):
    t = norm(text)
    hits = []
    if not name or not year:
        return hits
    for m in re.finditer(re.escape(name.lower()), t):
        window = t[max(0, m.start() - 250): m.end() + 250]
        if str(year) in window:
            hits.append(window.strip())
    return hits


def main():
    import sys
    out_dir = RUN / 'cache' / 'reviews_checked'
    for d in sorted((RUN / 'evidence').iterdir(), reverse='--reverse' in sys.argv):
        pk = json.loads((d / 'packet.json').read_text())
        for src in [pk['original']['source']] + [r['source'] for r in pk['replications']]:
            if src['evidence_level'] != 'full_text':
                fetch_one(src['doi'])
        if (out_dir / f'{d.name}.json').exists():
            continue
        leads = [l for l in pk['secondary_leads'] if l.get('doi')]
        ordered = [l for l in leads if l['why'].startswith('cites original and replication')] + \
                  [l for l in leads if l['why'] == 'review citing original']
        seen, results = set(), []
        for lead in ordered:
            if lead['doi'] in seen or len(results) >= MAX_LEADS:
                continue
            seen.add(lead['doi'])
            text, level, path = text_for(lead['doi'], lead.get('abstract'))
            found = []
            for r in pk['replications']:
                name, year = surname(r['source']), (r['source'].get('crossref') or {}).get('year')
                for snip in mentions(text, name, year)[:2]:
                    found.append(dict(replication_doi=r['doi'], snippet=snip))
            results.append(dict(doi=lead['doi'], title=lead['title'], year=lead['year'], type=lead['type'],
                                evidence_level=level, text_path=path, mentions=bool(found),
                                mentioned_replications=sorted({f['replication_doi'] for f in found}),
                                snippets=[f['snippet'] for f in found][:3]))
        dump_json(out_dir / f'{d.name}.json', results)
        print(d.name, pk['page']['title'][:35], len(results), sum(r['mentions'] for r in results), flush=True)


if __name__ == '__main__':
    main()
