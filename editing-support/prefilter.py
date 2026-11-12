#!/usr/bin/env python3
"""Pre-filter (brief v6): find articles that already cite every FLoRA replication we hold.

Detection reads the visible frozen wikitext of each page (HTML comments removed): a
replication counts as cited when its DOI appears exactly (not as the prefix of a longer
DOI), or when its title appears (normalised; at least 40 characters and six words, so
that generic titles such as "Registered Replication Report" do not match). A citation
anywhere counts, including further reading. Articles where every replication of every
FLoRA original on the page is cited are dropped before coding (#9). Articles that report
a replication only in prose, or through another source, are not caught here; the
drafting model codes those (`already_on_page`).

Usage: prefilter.py [--pages PAGEID ...] [--out report.json]   (default: the selected pages)
"""
import argparse
import json
import re
import sys
import unicodedata

from common import PACKETS, RUN, wikitext

MIN_TITLE, MIN_WORDS = 40, 6
COMMENT = re.compile(r'<!--.*?-->', re.S)


def _flat(s):
    s = re.sub(r"['’‘‛`]", '', s or '')  # straight and curly apostrophes alike
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r'<[^>]+>|&[a-z]+;', ' ', s)
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()


def detect(doi, title, text, flat_text=None):
    """'doi', 'title' or None: how the replication is cited in the wikitext `text`."""
    if doi and re.search(r'(?<![\w./])' + re.escape(doi.lower()) + r'(?![\w/]|\.\w)', text.lower()):
        return 'doi'
    t = _flat(title)
    if len(t) >= MIN_TITLE and len(t.split()) >= MIN_WORDS and f' {t} ' in f' {flat_text if flat_text is not None else _flat(text)} ':
        return 'title'
    return None


def page_report(pageid, packets):
    """Per-study and per-page detection for one page, from every English packet on it."""
    text = COMMENT.sub(' ', wikitext(pageid))
    flat = _flat(text)
    studies = []
    for p in packets:
        if str(p['pageid']) != str(pageid) or p['language'] != 'en':
            continue
        reps = [dict(doi=q['doi_r_norm'], title=q['title_r'], detected=detect(q['doi_r_norm'], q['title_r'], text, flat))
                for q in p['pairs']]
        studies.append(dict(packet_id=p['packet_id'], original_doi=p['original_doi'], replications=reps,
                            all_cited=bool(reps) and all(r['detected'] for r in reps)))
    title = next((p['page_title'] for p in packets if str(p['pageid']) == str(pageid)), '')
    return dict(pageid=str(pageid), title=title, studies=studies,
                drop=bool(studies) and all(s['all_cited'] for s in studies))


def on_page_index(pageids=None, packets=None):
    """{(pageid, replication DOI): 'doi' | 'title' | None} for the prompt's item list (only `pageids` if given)."""
    packets = packets if packets is not None else [p for p in json.loads(PACKETS.read_text()) if p['language'] == 'en']
    want = {str(x) for x in pageids} if pageids is not None else None
    out, cache = {}, {}
    for p in packets:
        pid = str(p['pageid'])
        if want is not None and pid not in want:
            continue
        if pid not in cache:
            try:
                t = COMMENT.sub(' ', wikitext(pid))
            except FileNotFoundError:
                continue
            cache[pid] = (t, _flat(t))
        t, f = cache[pid]
        for q in p['pairs']:
            out[(pid, q['doi_r_norm'].lower())] = detect(q['doi_r_norm'], q['title_r'], t, f)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--pages', nargs='*')
    ap.add_argument('--out')
    a = ap.parse_args()
    packets = [p for p in json.loads(PACKETS.read_text()) if p['language'] == 'en']
    pages = a.pages or list(dict.fromkeys(str(s['pageid']) for s in json.loads((RUN / 'selection.json').read_text())['pages']))
    rep = [page_report(pid, packets) for pid in pages]
    for r in rep:
        n = sum(len(s['replications']) for s in r['studies'])
        k = sum(bool(x['detected']) for s in r['studies'] for x in s['replications'])
        print(f"{'DROP' if r['drop'] else 'code':4} {r['title'][:45]:45} {k}/{n} replications cited", file=sys.stderr)
    text = json.dumps(dict(pages=rep, dropped=[r['title'] for r in rep if r['drop']]), indent=1, ensure_ascii=False)
    if a.out:
        open(a.out, 'w').write(text + '\n')
    else:
        print(text)


if __name__ == '__main__':
    main()
