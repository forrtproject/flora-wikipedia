#!/usr/bin/env python3
"""Fetch, cache and assemble evidence packets for the selected pages.

Free read-only services only: Wikipedia API (live revision check), Crossref
(metadata), Europe PMC (abstracts and open-access full text), OpenAlex
(anonymous free allowance; abstracts, OA links, citing reviews), and open PDFs.
Every response is cached with its retrieval time, so reruns are offline unless
`--refresh-live` is passed. Requests are serial and paced per host.
"""
import argparse
import csv
import datetime
import html
import json
import re
import subprocess
import urllib.parse

from common import RUN, PACKETS, dump_json, http_get, load_json, wikitext, wikitext_meta
import wikitext_render as wr

CACHE = RUN / 'cache'
EVID = RUN / 'evidence'
MAX_REPLICATIONS = 4
MAX_FULLTEXT_CHARS = 400_000
LOG = CACHE / 'requests.jsonl'
MENTION = re.compile(r'replicat|reproduc|meta-analy|failed to|could not be|did not find|criticis|controvers|disput', re.I)


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')


def slug(doi):
    return re.sub(r'[^a-z0-9]+', '_', doi.lower()).strip('_')[:120]


def logged_get(url, params=None, interval=1.0, accept='application/json', retries=4):
    rec = dict(url=url, params=params, at=now())
    try:
        body = http_get(url, params, host_interval=interval, accept=accept, retries=retries)
        rec['status'] = 200
        return body
    except Exception as e:  # recorded, not hidden
        rec['status'] = getattr(e, 'code', None) or type(e).__name__
        raise
    finally:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open('a') as f:
            f.write(json.dumps(rec) + '\n')


def strip_jats(s):
    s = re.sub(r'<jats:title>.*?</jats:title>', '', s or '', flags=re.S)
    return html.unescape(re.sub(r'<[^>]+>', ' ', s)).strip()


def inverted_to_text(inv):
    if not inv:
        return ''
    words = sorted((i, w) for w, idx in inv.items() for i in idx)
    return ' '.join(w for _, w in words)


def jats_to_text(xml):
    xml = re.sub(r'<ref-list.*?</ref-list>', '', xml, flags=re.S)
    xml = re.sub(r'<(title)>(.*?)</title>', lambda m: f'\n\n## {m.group(2)}\n', xml, flags=re.S)
    xml = re.sub(r'</p>', '\n\n', xml)
    text = html.unescape(re.sub(r'<[^>]+>', '', xml))
    return re.sub(r'\n{3,}', '\n\n', re.sub(r'[ \t]+', ' ', text)).strip()


# Files the download-paper skill returned that are supplementary material only (judged and verified on
# 2026-10-06); they are offered to drafters but do not raise the evidence level.
SUPPLEMENT_ONLY = {'10.1038/ng.2802', '10.1038/nature08833', '10.1038/s41562-018-0399-z', '10.1037/edu0000141'}


def _hunt_results():
    out = {}
    for f in sorted((RUN / 'hunt').glob('results_*.jsonl')) if (RUN / 'hunt').exists() else []:
        for line in f.open():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get('found') and r.get('text_path'):
                out[r['doi'].lower()] = r
    return out


HUNT = _hunt_results()


EXTRA = load_json(RUN / 'hunt' / 'extra_sources.json', {'abstracts': {}, 'by_page': {}})


def with_skill_fulltext(rec):
    """Attach text obtained via the download-paper skill (cache/fulltext_skill), if any."""
    found = EXTRA['abstracts'].get(rec['doi'].lower())
    if found and not rec.get('abstract'):
        rec = dict(rec, abstract=found['abstract'], abstract_source=found['abstract_source'])
        if rec.get('evidence_level') == 'metadata_only':
            rec['evidence_level'] = 'abstract'
    p = CACHE / 'fulltext_skill' / f"{slug(rec['doi'])}.txt"
    hunted = CACHE / 'fulltext_hunt' / f"{slug(rec['doi'])}.txt"
    if not rec.get('fulltext_path') and not p.exists() and hunted.exists():
        info = HUNT.get(rec['doi'].lower(), {})
        return dict(rec, fulltext_path=str(hunted.relative_to(RUN)), evidence_level='full_text',
                    fulltext_source=(f"PDF supplied by the {info['supplied_by']} ({info.get('version', 'version unrecorded')})"
                                     if info.get('supplied_by') else
                                     f"Free copy found by source search ({info.get('version', 'version unrecorded')}): {info.get('url', '')}"))
    if rec.get('fulltext_path') or not p.exists():
        return rec
    rec = dict(rec, fulltext_path=str(p.relative_to(RUN)))
    if rec['doi'].lower() in SUPPLEMENT_ONLY:
        rec['fulltext_source'] = 'Supplementary material only (via download-paper skill); the article itself was not read'
    else:
        rec['fulltext_source'] = 'PDF via download-paper skill (fetchpdf open-access chain); may be a preprint or author manuscript'
        rec['evidence_level'] = 'full_text'
    return rec


def fetch_source(doi):
    """Return cached source record for a DOI; fetch on first use."""
    path = CACHE / 'sources' / f'{slug(doi)}.json'
    rec = load_json(path)
    if rec:
        return with_skill_fulltext(rec)
    rec = dict(doi=doi, retrieved_at=now(), errors=[])
    q = urllib.parse.quote(doi, safe='')
    try:
        m = json.loads(logged_get(f'https://api.crossref.org/works/{q}'))['message']
        rec['crossref'] = dict(
            title=(m.get('title') or [''])[0], container=(m.get('container-title') or [''])[0],
            type=m.get('type'), year=(m.get('issued', {}).get('date-parts') or [[None]])[0][0],
            authors=[' '.join(x for x in [a.get('given'), a.get('family')] if x) or a.get('name', '')
                     for a in m.get('author', [])],
            volume=m.get('volume'), issue=m.get('issue'), page=m.get('page'),
            relation=m.get('relation', {}), update_to=m.get('update-to', []))
        if m.get('abstract'):
            rec['abstract'], rec['abstract_source'] = strip_jats(m['abstract']), 'Crossref deposited abstract'
    except Exception as e:
        rec['errors'].append(f'crossref: {e}')
    try:
        r = json.loads(logged_get('https://www.ebi.ac.uk/europepmc/webservices/rest/search',
                                  dict(query=f'DOI:"{doi}"', resultType='core', format='json')))
        hits = r.get('resultList', {}).get('result', [])
        if hits:
            h = hits[0]
            rec['europepmc'] = {k: h.get(k) for k in ['id', 'source', 'pmid', 'pmcid', 'isOpenAccess', 'title', 'pubYear']}
            if h.get('abstractText') and not rec.get('abstract'):
                rec['abstract'], rec['abstract_source'] = strip_jats(h['abstractText']), 'Europe PMC abstract'
            if h.get('pmcid') and h.get('isOpenAccess') == 'Y':
                xml = logged_get(f"https://www.ebi.ac.uk/europepmc/webservices/rest/{h['pmcid']}/fullTextXML",
                                 accept='application/xml').decode('utf-8', 'replace')
                save_fulltext(rec, jats_to_text(xml), f"Europe PMC open-access full text ({h['pmcid']})")
    except Exception as e:
        rec['errors'].append(f'europepmc: {e}')
    try:
        o = json.loads(logged_get(f'https://api.openalex.org/works/doi:{doi}', dict(
            select='id,title,type,publication_year,open_access,best_oa_location,abstract_inverted_index,cited_by_count,is_retracted')))
        rec['openalex'] = {k: o.get(k) for k in ['id', 'type', 'publication_year', 'cited_by_count', 'is_retracted']}
        rec['openalex']['oa_status'] = (o.get('open_access') or {}).get('oa_status')
        loc = o.get('best_oa_location') or {}
        rec['openalex']['oa_pdf'] = loc.get('pdf_url')
        rec['openalex']['oa_landing'] = loc.get('landing_page_url')
        if not rec.get('abstract') and o.get('abstract_inverted_index'):
            rec['abstract'], rec['abstract_source'] = inverted_to_text(o['abstract_inverted_index']), 'OpenAlex reconstructed abstract'
        if not rec.get('fulltext_path') and loc.get('pdf_url'):
            try_pdf(rec, loc['pdf_url'])
    except Exception as e:
        rec['errors'].append(f'openalex: {e}')
    rec['evidence_level'] = ('full_text' if rec.get('fulltext_path') else
                             'abstract' if rec.get('abstract') else 'metadata_only')
    dump_json(path, rec)
    return with_skill_fulltext(rec)


def save_fulltext(rec, text, source):
    if len(text) < 2000:
        rec['errors'].append(f'fulltext too short from {source}')
        return
    p = CACHE / 'fulltext' / f"{slug(rec['doi'])}.txt"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text[:MAX_FULLTEXT_CHARS])
    rec['fulltext_path'] = str(p.relative_to(RUN))
    rec['fulltext_source'] = source
    rec['fulltext_chars'] = len(text)


def try_pdf(rec, url):
    try:
        body = logged_get(url, interval=2.0, accept='application/pdf', retries=1)
        if not body.startswith(b'%PDF') or len(body) > 30_000_000:
            rec['errors'].append(f'oa pdf not a PDF or too large: {url}')
            return
        tmp = CACHE / 'pdf' / f"{slug(rec['doi'])}.pdf"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(body)
        text = subprocess.run(['pdftotext', '-layout', str(tmp), '-'], capture_output=True, text=True,
                              timeout=120).stdout
        save_fulltext(rec, text, f'open-access PDF via OpenAlex best_oa_location ({url})')
    except Exception as e:
        rec['errors'].append(f'oa pdf: {e}')


def secondary_candidates(orig, reps):
    """Reviews citing the original, and any works citing both original and a replication.

    These are leads for human source-finding, metadata/abstract only.
    """
    oid = (orig.get('openalex') or {}).get('id', '').rsplit('/', 1)[-1]
    if not oid:
        return []
    key = CACHE / 'secondary' / f"{slug(orig['doi'])}.json"
    cached = load_json(key)
    if cached is not None:
        return cached
    out, seen = [], set()
    queries = [('review citing original', f'cites:{oid},type:review')]
    for r in reps:
        rid = (r.get('openalex') or {}).get('id', '').rsplit('/', 1)[-1]
        if rid:
            queries.append((f"cites original and replication {r['doi']}", f'cites:{oid},cites:{rid}'))
    for why, flt in queries[:3]:
        try:
            res = json.loads(logged_get('https://api.openalex.org/works', dict(
                filter=flt, sort='cited_by_count:desc', per_page=5,
                select='id,doi,title,type,publication_year,cited_by_count,abstract_inverted_index')))['results']
        except Exception as e:
            out.append(dict(error=str(e), query=flt))
            continue
        for w in res:
            if w['id'] in seen:
                continue
            seen.add(w['id'])
            out.append(dict(why=why, openalex=w['id'], doi=(w.get('doi') or '').replace('https://doi.org/', ''),
                            title=w.get('title'), type=w.get('type'), year=w.get('publication_year'),
                            cited_by=w.get('cited_by_count'),
                            abstract=inverted_to_text(w.get('abstract_inverted_index'))[:2500],
                            evidence_level='abstract' if w.get('abstract_inverted_index') else 'metadata_only',
                            retrieved_at=now(), status='candidate lead; not inspected or verified for this claim'))
    dump_json(key, out)
    return out


def live_revisions(pageids, refresh):
    path = CACHE / 'live_revisions.json'
    data = load_json(path, {})
    todo = [p for p in pageids if refresh or p not in data]
    for i in range(0, len(todo), 50):
        chunk = todo[i:i + 50]
        r = json.loads(logged_get('https://en.wikipedia.org/w/api.php', dict(
            action='query', prop='revisions', pageids='|'.join(chunk), rvprop='ids|timestamp',
            format='json', formatversion=2, maxlag=5), interval=1.0))
        for pg in r['query']['pages']:
            rev = (pg.get('revisions') or [{}])[0]
            data[str(pg['pageid'])] = dict(title=pg.get('title'), live_revid=rev.get('revid'),
                                           live_timestamp=rev.get('timestamp'), checked_at=now())
    dump_json(path, data)
    return data


def live_wikitext(pageid, revid):
    path = CACHE / 'live_wikitext' / f'{pageid}_{revid}.txt'
    if path.exists():
        return path.read_text()
    r = json.loads(logged_get('https://en.wikipedia.org/w/api.php', dict(
        action='query', prop='revisions', revids=revid, rvprop='content', rvslots='main',
        format='json', formatversion=2, maxlag=5)))
    text = r['query']['pages'][0]['revisions'][0]['slots']['main']['content']
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return text


def norm_ws(s):
    return re.sub(r'\s+', ' ', s).strip()


def build_packet(sel, packet, live):
    pid = packet['pageid']
    text = wikitext(pid)
    meta = wikitext_meta(pid)
    refs = wr.named_refs(text)
    reps = packet['pairs'][:MAX_REPLICATIONS]
    rep_dois = [q['doi_r_norm'] for q in packet['pairs']]
    occurrences, seen_par = [], set()
    sites = [(int(c['match_pos']), c['doi'], c['doi_role']) for c in packet['raw_contexts']]
    for d, role in [(packet['original_doi'], 'original')] + [(x, 'replication') for x in rep_dois]:
        for name in wr.ref_names_with(text, d):
            sites += [(p, d, role + ' (named-reference reuse)') for p in wr.named_ref_reuses(text, name)]
    for pos, doi, role in sorted(sites, key=lambda x: (not x[2].startswith('original'), x[0])):
        c = dict(doi=doi, doi_role=role)
        name, s0, s1 = wr.section_bounds(text, pos)
        par = wr.paragraph_at(text, pos)
        if (c['doi_role'], par) in seen_par:
            continue
        seen_par.add((c['doi_role'], par))
        before = text[:pos]
        sec_text = text[s0:s1]
        if len(sec_text) > 12000:
            off = pos - s0
            sec_text = sec_text[max(0, off - 6000): off + 6000]
        occurrences.append(dict(
            doi=c['doi'], doi_role=c['doi_role'], match_pos=pos, section=name,
            in_comment=before.rfind('<!--') > before.rfind('-->'),
            paragraph_wikitext=par,
            paragraph_plain=wr.plain(par, refs, [packet['original_doi']], rep_dois),
            section_plain=wr.plain(sec_text, refs, [packet['original_doi']], rep_dois)))
    lv = live.get(pid, {})
    changed = bool(lv.get('live_revid')) and str(lv['live_revid']) != str(packet['revision_id'])
    live_check = dict(frozen_revid=packet['revision_id'], **lv, changed_since_frozen=changed)
    if changed:
        lt = live_wikitext(pid, lv['live_revid'])
        lowered = lt.lower()
        live_check['original_doi_still_present'] = packet['original_doi'].lower() in lowered
        live_check['focal_paragraphs_unchanged'] = all(
            norm_ws(o['paragraph_wikitext']) in norm_ws(lt) for o in occurrences if o['doi_role'] == 'original')
    article_plain = wr.plain(text, refs, [packet['original_doi']], rep_dois)
    mentions = [par.strip() for par in article_plain.split('\n\n')
                if MENTION.search(par) and len(par) > 80][:25]
    orig = fetch_source(packet['original_doi'])
    rsrc = [fetch_source(q['doi_r_norm']) for q in reps]
    return dict(
        card_id=packet['packet_id'], stratum=sel['stratum'], screening_flags=dict(
            page_kind_heuristic=sel['page_kind'], context_kind=sel['context_kind'],
            living_person_category=sel['living_person'], health_term_flag=sel['health_flag'],
            co_cited=sel['co_cited'], large_project=sel['large_project'],
            flora_originals_on_page=sel['originals_on_page']),
        page=dict(title=packet['page_title'], pageid=pid, frozen_revid=packet['revision_id'],
                  frozen_timestamp=meta.get('revision_timestamp'), retrieved_at=meta.get('retrieved_at'),
                  frozen_url=f"https://en.wikipedia.org/w/index.php?oldid={packet['revision_id']}",
                  live_url='https://en.wikipedia.org/wiki/' + urllib.parse.quote(packet['page_title'].replace(' ', '_')),
                  talk_url='https://en.wikipedia.org/wiki/Talk:' + urllib.parse.quote(packet['page_title'].replace(' ', '_')),
                  lead_plain=wr.plain(wr.lead(text), refs, [packet['original_doi']], rep_dois)[:3500], outline=wr.outline(text)[:60],
                  categories=re.findall(r'\[\[\s*Category\s*:\s*([^\]|]+)', text)[:30]),
        live_check=live_check,
        original=dict(doi=packet['original_doi'], flora_title=packet['original_title'], source=orig),
        replications=[dict(pair_id=q['pair_id'], doi=q['doi_r_norm'], flora_title=q['title_r'],
                           flora_outcome=q['outcome'], flora_source=q['source'],
                           doi_detected_on_page='Both DOI' in q['assessment'], source=s)
                      for q, s in zip(reps, rsrc)],
        replications_not_fetched=[dict(doi=q['doi_r_norm'], flora_title=q['title_r'], flora_outcome=q['outcome'])
                                  for q in packet['pairs'][MAX_REPLICATIONS:]],
        occurrences=occurrences,
        article_plain=article_plain,
        replication_mentions=mentions,
        secondary_leads=secondary_candidates(orig, rsrc),
        audit=dict(run='runs/english-full-gh/en', packet_source='runs/editathon-review/packets.json'))


def render_md(pk):
    """Agent- and human-readable packet text (evidence only, no instructions)."""
    L = [f"# Evidence packet {pk['card_id']}: {pk['page']['title']}", '',
         f"Frozen revision: {pk['page']['frozen_revid']} ({pk['page']['frozen_timestamp']}); {pk['page']['frozen_url']}",
         f"Live check: {json.dumps(pk['live_check'])}", '',
         f"Screening flags (heuristic, unverified): {json.dumps(pk['screening_flags'])}", '',
         '## Article lead (plain rendering, approximate)', pk['page']['lead_plain'], '',
         '## Article outline', '\n'.join(pk['page']['outline']), '',
         '## Categories', '; '.join(pk['page']['categories']), '']
    for i, o in enumerate(pk['occurrences'], 1):
        L += [f"## Occurrence {i}: {o['doi_role']} DOI {o['doi']} in section '{o['section']}'"
              + (' (INSIDE HTML COMMENT, not visible)' if o['in_comment'] else ''), '',
              '### Paragraph (plain rendering; [FOCAL REF] = original study, [PAIRED REF] = FLoRA replication)',
              o['paragraph_plain'], '', '### Paragraph (raw wikitext)', '```', o['paragraph_wikitext'][:6000], '```', '',
              '### Full section (plain rendering)', o['section_plain'][:9000], '']

    L += ['## Whole-article digest: paragraphs mentioning replication, reproduction, meta-analysis or criticism',
          f"(Full plain rendering of the whole article: {pk['card_id']}/article_plain.txt in the evidence directory.)", '']
    L += [f'- {m[:1500]}' for m in pk['replication_mentions']] or ['- (none found by keyword scan)']
    L += ['']

    def src(label, s, extra=''):
        c = s.get('crossref') or {}
        out = [f"## {label}: doi:{s['doi']} {extra}",
               f"Crossref: {c.get('title')} | {', '.join((c.get('authors') or [])[:6])}{' et al.' if len(c.get('authors') or []) > 6 else ''} | {c.get('container')} | {c.get('year')} | type {c.get('type')}",
               f"Updates/relations (Crossref): {json.dumps(c.get('update_to') or [])} {json.dumps(c.get('relation') or {})[:300]}",
               f"OpenAlex: {json.dumps(s.get('openalex') or {})}",
               f"Evidence level available to you: {s['evidence_level'].upper()}"
               + (f" — full text file: {s['fulltext_path']} ({s['fulltext_source']})" if s.get('fulltext_path') else ''),
               f"Retrieved: {s['retrieved_at']}"]
        if s.get('abstract'):
            out += [f"### Abstract ({s['abstract_source']})", s['abstract']]
        return out + ['']
    L += src('ORIGINAL STUDY', pk['original']['source'], f"(FLoRA title: {pk['original']['flora_title']})")
    for r in pk['replications']:
        L += src('FLoRA-LINKED REPLICATION/REPRODUCTION', r['source'],
                 f"(FLoRA title: {r['flora_title']}; FLoRA outcome code: {r['flora_outcome']} [screening input only, not citable]; "
                 f"DOI detected on page: {r['doi_detected_on_page']})")
    if pk['replications_not_fetched']:
        L += ['## Further FLoRA pairs (metadata only, not fetched)', json.dumps(pk['replications_not_fetched']), '']
    if len(pk.get('page_items', [])) > 1:
        L += ['## Other database studies cited on this same page (each has its own packet; drafted together)']
        L += [f"- {i['packet_id']}: {i['original_title']} (doi:{i['original_doi']})" for i in pk['page_items']
              if i['packet_id'] != pk['card_id']] + ['']
    if pk.get('secondary_checked'):
        L += ['## Review articles checked by the pipeline for mentions of the replication(s)',
              'Each was searched (full text where we could get it, otherwise abstract) for the replication authors and year.']
        for r in pk['secondary_checked']:
            L += [f"- doi:{r['doi']} | {r['title']} | {r['year']} | read: {r['evidence_level']} | mentions replication: "
                  f"{r['mentions']}" + (f" | file: {r['text_path']}" if r.get('text_path') else '')]
            L += [f"  Snippet: {x}" for x in r.get('snippets', [])[:2]]
        L += ['']
    if pk.get('extra_sources'):
        L += ['## Other papers relevant to this page that the pipeline looked up']
        for x in pk['extra_sources']:
            L += [f"- doi:{x['doi']} | {x['title']} | {x['kind']} | read: {x['evidence_level']}"
                  + (f" | {x['note']}" if x.get('note') else '')]
            if x.get('abstract'):
                L += [f"  Abstract ({x['abstract_source']}): {x['abstract']}"]
        L += ['']
    L += ['## Other secondary-source leads from OpenAlex (NOT inspected; metadata/abstract only)']
    for s in pk['secondary_leads']:
        if 'error' in s:
            continue
        L += [f"- [{s['why']}] doi:{s['doi']} | {s['title']} | {s['year']} | {s['type']} | cited_by {s['cited_by']}",
              f"  Abstract: {s['abstract'][:1200] or '(none)'}"]
    return '\n'.join(L) + '\n'


def page_packets(sel, packets):
    """All English packets on each selected page: the selected (focal) packet first, then by title."""
    by_page = {}
    for p in packets.values():
        if p['language'] == 'en':
            by_page.setdefault(p['pageid'], []).append(p)
    feats = {r['packet_id']: r for r in csv.DictReader((RUN / 'packet_features.csv').open())}
    out = []
    for s in sel:
        items = sorted(by_page[s['pageid']], key=lambda p: (p['packet_id'] != s['packet_id'], p['original_title'].lower()))
        for p in items:
            f = feats[p['packet_id']]
            row = dict(s if p['packet_id'] == s['packet_id'] else
                       dict(f, stratum=s['stratum'], living_person=f['living_person'] == 'True',
                            health_flag=f['health_flag'] == 'True', co_cited=f['co_cited'] == 'True',
                            large_project=f['large_project'] == 'True', originals_on_page=int(f['originals_on_page'])))
            row['page_items'] = [dict(packet_id=q['packet_id'], original_title=q['original_title'], original_doi=q['original_doi'])
                                 for q in items]
            out.append((row, p))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--refresh-live', action='store_true', help='re-query current revision IDs')
    ap.add_argument('--only', nargs='*', help='card IDs to (re)build')
    a = ap.parse_args()
    sel = load_json(RUN / 'selection.json')['pages']
    packets = {p['packet_id']: p for p in json.loads(PACKETS.read_text())}
    live = live_revisions([s['pageid'] for s in sel], a.refresh_live)
    for s, packet in page_packets(sel, packets):
        if a.only and packet['packet_id'] not in a.only:
            continue
        pk = build_packet(s, packet, live)
        pk['page_items'] = s['page_items']
        pk['extra_sources'] = EXTRA['by_page'].get(pk['page']['title'], [])
        pk['secondary_checked'] = load_json(CACHE / 'reviews_checked' / f"{pk['card_id']}.json", [])
        d = EVID / pk['card_id']
        (d).mkdir(parents=True, exist_ok=True)
        (d / 'article_plain.txt').write_text(pk['article_plain'])
        dump_json(d / 'packet.json', pk)
        (d / 'packet.md').write_text(render_md(pk))
        lv = pk['live_check']
        print(f"{pk['card_id']} {pk['page']['title'][:40]:40} orig={pk['original']['source']['evidence_level']:13} "
              f"reps={[r['source']['evidence_level'][:4] for r in pk['replications']]} changed={lv['changed_since_frozen']}"
              f" leads={len(pk['secondary_leads'])}", flush=True)


if __name__ == '__main__':
    main()
