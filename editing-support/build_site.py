#!/usr/bin/env python3
"""Assemble the private review site and download bundles from cached products.

Offline: reads selection, evidence packets, drafts, orchestrator reviews and the
route assignment from runs/edit-prototype-en and writes a static site to a
dedicated output directory outside the repository. Presentation (site/) is kept
separate from data (data/suggestions.json).
"""
import argparse
import csv
import datetime
import hashlib
import html
import re
import io
import json
import pathlib
import shutil
import subprocess
import zipfile

from common import PACKETS, ROOT, RUN, dump_json, load_json
from validate import check
from write_about import about_md

HERE = pathlib.Path(__file__).resolve().parent
ROUTE_LABEL = {k: 'Claude' for k in ('claude', 'claude_ft', 'claude_v4', 'claude_v41', 'claude_v5a', 'claude_v5b')}
ROUTE_LABEL.update(codex='Codex', agy='Gemini', orchestrator='Claude')
LEVEL = {'metadata_only': 0, 'abstract': 1, 'full_text': 2}


def _clean(t):
    return re.sub(r'<[^>]+>', '', html.unescape(t or '')).strip()


def cite(s):
    c = dict(s.get('crossref') or {})
    c['title'] = _clean(c.get('title'))
    a = c.get('authors') or []
    names = ', '.join(a[:3]) + (' et al.' if len(a) > 3 else '')
    return f"{names or 'Unknown authors'} ({c.get('year') or 'n.d.'}). {c.get('title') or s.get('doi')}. {c.get('container') or ''}".strip()


PARTICLES = {'van', 'von', 'de', 'der', 'den', 'da', 'di', 'du', 'le', 'la', 'del', 'dos', 'ten', 'ter'}


SUFFIXES = {'jr', 'jr.', 'sr', 'sr.', 'ii', 'iii', 'iv'}


def family(name):
    """Family name from 'Given Family', keeping lower-case particles: 'Jan C. van Ours' -> 'van Ours'.

    Drops suffixes ('John R. Lott, Jr.' -> 'Lott'), uses a group's abbreviation ('… Initiative (EADI)' -> 'EADI')
    and handles initials written last ('Suresha B.' -> 'Suresha')."""
    m = re.search(r'\(([^()]+)\)\s*$', name)
    if m:
        return m.group(1)
    t = [x.strip(',') for x in name.split() if x.strip(',').lower() not in SUFFIXES]
    while len(t) > 1 and re.fullmatch(r'[A-Z]\.?', t[-1]):
        t.pop()
    i = len(t) - 1
    while i > 0 and t[i - 1] in PARTICLES:
        i -= 1
    return ' '.join(t[i:])


def author_year(c):
    """'Smith (2010)', 'Smith & Jones (2010)' or 'Smith et al. (2010)' from Crossref-style metadata."""
    fam = [family(a) for a in (c.get('authors') or []) if a.strip()]
    who = (fam[0] if len(fam) == 1 else f'{fam[0]} & {fam[1]}' if len(fam) == 2
           else f'{fam[0]} et al.' if fam else 'Unknown authors')
    return f"{who} ({c.get('year') or 'n.d.'})"


def short(s):
    c = dict(s.get('crossref') or {})
    return f"{author_year(c)}: {_clean(c.get('title'))[:80]}"


def src_view(s):
    note = {'full_text': 'Full text available',
            'abstract': 'Abstract only; we could not get the full paper',
            'metadata_only': 'Title and publication details only; no abstract or full text obtained'}[s['evidence_level']]
    return dict(doi=s['doi'], citation=cite(s), short=short(s), evidence_level=s['evidence_level'],
                evidence_note=note, retrieved_at=s['retrieved_at'],
                retracted=(s.get('openalex') or {}).get('is_retracted'))


def merge_occurrences(occs):
    """One display block per distinct paragraph; packet numbering is kept in `numbers`."""
    out = {}
    for i, o in enumerate(occs, 1):
        key = o['paragraph_wikitext']
        if key in out:
            out[key]['numbers'].append(i)
            if o['doi_role'] not in out[key]['doi_role']:
                out[key]['doi_role'] += '; ' + o['doi_role']
            continue
        out[key] = {k: o[k] for k in ['doi', 'doi_role', 'section', 'in_comment', 'paragraph_plain',
                                      'paragraph_wikitext', 'section_plain']}
        out[key]['numbers'] = [i]
    return list(out.values())


def apply_review(draft, review):
    final = json.loads(json.dumps(draft))
    for k, v in (review or {}).get('overrides', {}).items():
        final[k] = v
    return final


STRENGTH_ORDER = {'none': 0, 'optional': 1, 'edit': 2}


def strength_class(draft):
    """edit = fix or recommended addition; optional = optional addition; none = nothing to do."""
    es = draft.get('edit_strength')
    if es in ('fix', 'recommended_addition'):
        return 'edit'
    if es == 'optional_addition':
        return 'optional'
    if es == 'none':
        return 'none'
    return 'none' if draft['proposed_action'] in ('no_change', 'defer') else 'edit'  # drafts written before v5


def adds_replication(draft, pk):
    """Whether the drafted edit would bring in a replication the page does not yet cite, and how strongly."""
    if draft['draft']['status'] not in ('provided', 'conditional'):
        return None
    text = (draft['draft']['wording'] + ' ' + ' '.join(draft['draft']['citations'])).lower()
    new = [r['source']['doi'] for r in pk['replications']
           if r['source']['doi'].lower() in text and not r['doi_detected_on_page']]
    if not new:
        return None
    return dict(dois=new, level='optional' if draft.get('edit_strength') == 'optional_addition' else 'recommended')


def build_items():
    """One item per (page, FLoRA original) on the selected pages."""
    from evidence import page_packets
    sel = load_json(RUN / 'selection.json')['pages']
    assignment = load_json(RUN / 'route_assignment.json', {})
    packets = {p['packet_id']: p for p in json.loads(PACKETS.read_text())}
    review_dir = RUN / assignment.get('review_dir', 'review')
    items, missing = [], []
    for s, p in page_packets(sel, packets):
        cid = p['packet_id']
        route = assignment.get('cards', {}).get(cid, assignment.get('default'))
        two_run = None
        run_b = assignment.get('second_run')
        if run_b and (RUN / 'drafts' / run_b / f'{cid}.json').exists() and (RUN / 'drafts' / str(route) / f'{cid}.json').exists():
            da, db = load_json(RUN / 'drafts' / route / f'{cid}.json'), load_json(RUN / 'drafts' / run_b / f'{cid}.json')
            ka, kb = strength_class(da), strength_class(db)
            if STRENGTH_ORDER[kb] > STRENGTH_ORDER[ka]:  # show the run that proposes more; the other is reported
                route, da, db, ka, kb = run_b, db, da, kb, ka
            two_run = dict(agree=ka == kb, shown=dict(run=route, strength=da.get('edit_strength'), action=da['proposed_action']),
                           other=dict(strength=db.get('edit_strength'), action=db['proposed_action'], rationale=db['rationale']))
        dpath = RUN / 'drafts' / str(route) / f'{cid}.json'
        if not route or not dpath.exists():
            missing.append(dict(card_id=cid, page=p['page_title'], route=route))
            continue
        evdir = 'evidence_ft' if str(route).endswith('_ft') else 'evidence'
        pk = load_json(RUN / evdir / cid / 'packet.json')
        draft = load_json(dpath)
        review = load_json(review_dir / f'{cid}.json')
        final = apply_review(draft, review)
        errors, warnings = check(final, pk)
        meta = load_json(RUN / 'drafts' / route / f'{cid}.meta.json', {})
        ft_note = (load_json(RUN / 'ft-skill' / 'card_notes.json', {}) or {}).get(cid)
        best = max([e['evidence_level'] for e in final['evidence_used']] or ['metadata_only'], key=LEVEL.get)
        items.append(dict(
            card_id=cid, pageid=str(p['pageid']), focal=cid == s['packet_id'], stratum=s['stratum'],
            page=dict(**{k: pk['page'][k] for k in ['title', 'pageid', 'frozen_revid', 'frozen_timestamp', 'frozen_url',
                                                    'live_url', 'talk_url']},
                      diff_url=f"https://en.wikipedia.org/w/index.php?diff=cur&oldid={pk['page']['frozen_revid']}"),
            live_check=pk['live_check'],
            occurrences=merge_occurrences(pk['occurrences']),
            original=src_view(pk['original']['source']),
            replications=[dict(**src_view(r['source']), flora_outcome=r['flora_outcome'],
                               doi_detected_on_page=r['doi_detected_on_page']) for r in pk['replications']],
            replications_not_fetched=pk['replications_not_fetched'],
            reviews_checked=pk.get('secondary_checked', []),
            secondary_leads=[x for x in pk['secondary_leads'] if 'error' not in x],
            suggestion=final, best_evidence=best, two_run=two_run,
            adds_replication=adds_replication(final, pk),
            kind=('judgement' if two_run and not two_run['agree'] else strength_class(final)),
            validation=dict(errors=errors, warnings=warnings),
            provenance=dict(route=route, route_label=ROUTE_LABEL.get(route, 'AI assessment'),
                            model=meta.get('model') or assignment.get('models', {}).get(route, ''),
                            finished_at=meta.get('finished_at', ''), fulltext_update=ft_note,
                            orchestrator=dict(verdict=(review or {}).get('verdict', 'not yet reviewed'),
                                              notes=(review or {}).get('notes', '')))))
    apply_text_overrides(items)
    return items, missing


def apply_text_overrides(cards):
    """Apply display-only rewrites; reject stale paths or source text."""
    by_id = {c['card_id']: c for c in cards}
    for o in json.loads((HERE / 'text_overrides.json').read_text()):
        label = f"{o['card_id']}:{o['field']}"
        try:
            target = by_id[o['card_id']]
            keys = [int(k) if k.isdigit() else k for k in
                    re.split(r'\.|\[|\]', o['field']) if k]
            for key in keys[:-1]:
                target = target[key]
            old = target[keys[-1]]
        except (KeyError, IndexError, TypeError) as e:
            raise ValueError(f'Text override missing card or field: {label}') from e
        if old != o['old']:
            raise ValueError(f'Text override old text mismatch: {label}')
        target[keys[-1]] = o['new']


def build_pages(items):
    """Group items into one card per Wikipedia page; carry over page-level verified problems."""
    pages = {}
    for it in items:
        pg = pages.setdefault(it['pageid'], dict(page_id=it['pageid'], page=it['page'], live_check=it['live_check'],
                                                  stratum=it['stratum'], items=[], adjacent=[]))
        pg['items'].append(it)
    for pg in pages.values():
        seen = set()
        for it in pg['items']:  # verified adjacent problems from the orchestrator's earlier page review
            review_dir = RUN / (load_json(RUN / 'route_assignment.json', {}) or {}).get('review_dir', 'review')
            for a in (load_json(review_dir / f"{it['card_id']}.json") or {}).get('adjacent_opportunities', []):
                if a['sentence'] not in seen:
                    seen.add(a['sentence'])
                    pg['adjacent'].append(a)
    return list(pages.values())


def counts(cards, pages=None):
    def tally(f):
        out = {}
        for c in cards:
            v = f(c)
            out[v] = out.get(v, 0) + 1
        return dict(sorted(out.items()))
    return dict(
        cards=len(cards), items=len(cards), distinct_pages=len({c['page']['pageid'] for c in cards}),
        pages_with_several_studies=sum(len(p['items']) > 1 for p in pages or []),
        pages_with_edit=sum(any(i['kind'] == 'edit' for i in p['items']) for p in pages or []),
        item_kinds=tally(lambda c: c['kind']),
        adds_replication=tally(lambda c: (c['adds_replication'] or {}).get('level', 'no')),
        edit_strength=tally(lambda c: c['suggestion'].get('edit_strength', 'n/a')),
        two_runs=sum(bool(c['two_run']) for c in cards),
        two_runs_agree=sum(bool(c['two_run'] and c['two_run']['agree']) for c in cards),
        pages_with_adjacent=sum(bool(p['adjacent']) for p in pages or []),
        open_literature_tasks=sum(any(w.startswith('open-ended') for w in c['validation']['warnings']) for c in cards),
        proposed_action=tally(lambda c: c['suggestion']['proposed_action']),
        queue_recommendation=tally(lambda c: c['suggestion']['queue_recommendation']),
        draft_status=tally(lambda c: c['suggestion']['draft']['status']),
        stratum=tally(lambda c: c['stratum']),
        article_scope=tally(lambda c: c['suggestion']['article_scope']),
        citation_function=tally(lambda c: c['suggestion']['citation_function']),
        best_evidence=tally(lambda c: c['best_evidence']),
        route=tally(lambda c: c['provenance']['route']),
        orchestrator_verdicts=tally(lambda c: c['provenance']['orchestrator']['verdict']),
        validation_failures=sum(bool(c['validation']['errors']) for c in cards),
        revised_since_frozen=sum(bool(c['live_check'].get('changed_since_frozen')) for c in cards),
        blp=sum(c['suggestion']['flags']['blp'] for c in cards), medrs=sum(c['suggestion']['flags']['medrs'] for c in cards))


def flat_csv(cards):
    buf = io.StringIO()
    cols = ['card_id', 'page_title', 'frozen_revid', 'stratum', 'article_scope', 'citation_function', 'proposed_action',
            'queue_recommendation', 'draft_status', 'confidence', 'blp', 'medrs', 'best_evidence', 'route', 'model',
            'orchestrator_verdict', 'validation_errors', 'original_doi', 'replication_dois', 'rationale']
    w = csv.DictWriter(buf, fieldnames=cols)
    w.writeheader()
    for c in cards:
        s = c['suggestion']
        w.writerow(dict(card_id=c['card_id'], page_title=c['page']['title'], frozen_revid=c['page']['frozen_revid'],
                        stratum=c['stratum'], article_scope=s['article_scope'], citation_function=s['citation_function'],
                        proposed_action=s['proposed_action'], queue_recommendation=s['queue_recommendation'],
                        draft_status=s['draft']['status'], confidence=s['confidence'], blp=s['flags']['blp'],
                        medrs=s['flags']['medrs'], best_evidence=c['best_evidence'], route=c['provenance']['route'],
                        model=c['provenance']['model'], orchestrator_verdict=c['provenance']['orchestrator']['verdict'],
                        validation_errors=len(c['validation']['errors']), original_doi=c['original']['doi'],
                        replication_dois=' '.join(r['doi'] for r in c['replications']), rationale=s['rationale']))
    return buf.getvalue()


def papers_not_obtained(cards):
    """Sources on the cards that we could not read in full, with where the search looked."""
    notes = {}
    for f in sorted((RUN / 'hunt').glob('results_*.jsonl')):
        for line in f.open():
            r = json.loads(line)
            notes[r['doi'].lower()] = r.get('notes', '')
    rows = {}
    for c in cards:
        for role, s in [('original', c['original'])] + [('replication', r) for r in c['replications']]:
            if s['evidence_level'] != 'full_text':
                row = rows.setdefault(s['doi'], dict(doi=s['doi'], citation=s['citation'], level_read=s['evidence_level'],
                                                     pages='', roles='', search_notes=notes.get(s['doi'].lower(), '')))
                row['pages'] = '; '.join(sorted(set(filter(None, row['pages'].split('; ') + [c['page']['title']]))))
                row['roles'] = '; '.join(sorted(set(filter(None, row['roles'].split('; ') + [role]))))
    return sorted(rows.values(), key=lambda r: r['pages'])


def zip_dir(target, sources):
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as z:
        for base, pattern in sources:
            for p in sorted(base.glob(pattern)):
                if p.is_file():
                    z.write(p, p.relative_to(RUN))


LABEL_CACHE = RUN / 'cache' / 'crossref_labels'


def item_dois(it):
    """Every DOI a card shows as a source, in display order."""
    s = it['suggestion']
    found = [it['original']['doi'], *(r['doi'] for r in it['replications']),
             *(v['source'] for v in s.get('verifications', [])), *(c['source'] for c in s['content_points']),
             *s['draft'].get('citations', []), *(e['doi'] for e in s['evidence_used']),
             *(r['doi'] for r in it.get('reviews_checked', []))]
    return [re.sub(r'^doi:', '', d.strip(), flags=re.I).lower() for d in found if d and not re.match(r'needs', d, re.I)]


def source_labels(cards, fetch=False):
    """Map each DOI to a short author-year label and a full citation, from cached Crossref metadata.

    Sources already in the evidence cache are used first; others come from cache/crossref_labels,
    which only --fetch-labels fills (one paced Crossref request per missing DOI)."""
    from common import http_get
    meta = {}
    for f in (RUN / 'cache' / 'sources').glob('*.json'):
        d = load_json(f)
        if d.get('crossref'):
            meta[d['doi'].lower()] = d['crossref']
    LABEL_CACHE.mkdir(exist_ok=True)
    out, missing = {}, []
    for doi in dict.fromkeys(d for c in cards for d in item_dois(c)):
        path = LABEL_CACHE / (re.sub(r'[^a-z0-9]+', '_', doi) + '.json')
        cached = load_json(path) if path.exists() else None
        if doi not in meta and fetch and (not cached or 'error' in cached['crossref']):
            try:
                m = json.loads(http_get(f'https://api.crossref.org/works/{doi}'))['message']
                rec = dict(authors=[' '.join(filter(None, [a.get('given'), a.get('family')])) or a.get('name', '')
                                    for a in m.get('author', [])],
                           year=(m.get('issued', {}).get('date-parts') or [[None]])[0][0],
                           title=(m.get('title') or [''])[0], container=(m.get('container-title') or [''])[0])
            except Exception as e:  # not a Crossref DOI (e.g. OSF): try DataCite, else keep the bare DOI
                try:
                    a = json.loads(http_get(f'https://api.datacite.org/dois/{doi}'))['data']['attributes']
                    rec = dict(authors=[' '.join(filter(None, [x.get('givenName'), x.get('familyName')])) or x.get('name', '')
                                        for x in a.get('creators', [])], year=a.get('publicationYear'),
                               title=(a.get('titles') or [{}])[0].get('title', ''), container=a.get('publisher', ''),
                               registry='datacite')
                except Exception as e2:
                    rec = dict(error=f'{e}; DataCite: {e2}')
            dump_json(path, dict(doi=doi, retrieved_at=datetime.datetime.now(datetime.timezone.utc).isoformat(
                timespec='seconds'), crossref=rec))
        c = meta.get(doi) or (load_json(path) or {}).get('crossref') or {}
        if not c.get('authors') and not c.get('year'):
            missing.append(doi)
            out[doi] = dict(label=f'doi:{doi}', citation=f'doi:{doi}')
            continue
        out[doi] = dict(label=author_year(c), citation=cite(dict(crossref=c, doi=doi)))
    # Same author-year for different papers: add a, b, … in DOI order so labels stay unique.
    by_label = {}
    for doi, v in out.items():
        by_label.setdefault(v['label'], []).append(doi)
    for label, dois in by_label.items():
        if len(dois) > 1 and label.endswith(')'):
            for i, doi in enumerate(sorted(dois)):
                out[doi]['label'] = label[:-1] + 'abcdefghij'[i] + ')'
    return out, missing


SENTENCE_END = re.compile(r'(?<=[.!?])\s+(?=[A-Z“"(])')
NOT_AN_END = re.compile(r'(?:\bet al|\be\.g|\bi\.e|\bvs|\bcf|\bNo|\bpp?|\bDr|\bSt|\b[A-Z])\.$')


def split_gist(text):
    """First sentence of a rationale (the one-line reason on a card) and the rest."""
    parts = SENTENCE_END.split(text.strip())
    sentences, cur = [], ''
    for part in parts:  # re-join splits after abbreviations such as "et al."
        cur = f'{cur} {part}'.strip()
        if not NOT_AN_END.search(cur):
            sentences.append(cur)
            cur = ''
    sentences += [cur] if cur else []
    # A short first sentence often only sets the scene ("The article is accurate."): add the next one.
    n = 2 if len(sentences) > 1 and len(sentences[0]) < 120 else 1
    return ' '.join(sentences[:n]), ' '.join(sentences[n:])


GIST_OVERRIDES = HERE / 'gist_overrides.json'


def rationale_sha(text):
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def card_gist(card):
    """One-line reason for a study: the reviewed rewrite in gist_overrides.json, else the rationale's opening.

    A rewrite is tied to the rationale it summarises; if the drafts change, the build fails rather than
    showing a summary of an older rationale. With a rewrite, the card shows the full rationale below it."""
    rationale = card['suggestion']['rationale']
    o = (load_json(GIST_OVERRIDES, {}) or {}).get(card['card_id'])
    if not o:
        return split_gist(rationale)
    if o['rationale_sha'] != rationale_sha(rationale):
        raise ValueError(f"gist_overrides.json is stale for {card['card_id']}: its rationale has changed")
    return o['gist'], rationale


def pandoc(md, html_out, title):
    subprocess.run(['pandoc', str(md), '-s', '--metadata', f'title={title}', '-c', 'style.css',
                    '--template', str(HERE / 'site' / 'page.template.html'), '-o', str(html_out)], check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir', required=True, type=pathlib.Path)
    ap.add_argument('--fetch-labels', action='store_true',
                    help='fetch Crossref details for sources that have no cached author and year')
    a = ap.parse_args()
    out = a.output_dir.resolve()
    if out == ROOT.parent or ROOT.parent in out.parents:
        ap.error('Output directory must be outside the repository checkout')
    cards, missing = build_items()
    pages = build_pages(cards)
    # Cards give no ready-made wording: archive the AI draft text outside the site, then drop it.
    archive = RUN / 'archive'
    archive.mkdir(exist_ok=True)
    dump_json(archive / 'suggestions-with-draft-wording.json', cards)
    for c in cards:
        c['suggestion']['draft'].pop('wording', None)
        c['gist'], c['rationale_rest'] = card_gist(c)
    sources, unlabelled = source_labels(cards, fetch=a.fetch_labels)
    for c in cards:  # sources the evidence cache has no authors for: use the label cache's details
        for src in [c['original'], *c['replications']]:
            lab = sources.get(src['doi'].lower())
            if src['citation'].startswith('Unknown authors') and lab and not lab['label'].startswith('doi:'):
                src['citation'], src['short'] = lab['citation'], lab['label'] + src['short'][src['short'].index(':'):]
    if unlabelled:
        print(f'{len(unlabelled)} sources have no cached author and year (run with --fetch-labels): {unlabelled}')
    built = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
    data = dict(build_id=hashlib.sha256(json.dumps(cards, sort_keys=True).encode()).hexdigest()[:12], built_at=built,
                status='Private research material, not for publication. Prepared with AI; nobody has checked it yet.',
                counts=counts(cards, pages), missing_drafts=missing, sources=sources, pages=pages)
    (out / 'data').mkdir(parents=True, exist_ok=True)
    (out / 'downloads').mkdir(exist_ok=True)
    for f in ['index.html', 'app.js', 'style.css']:
        shutil.copy2(HERE / 'site' / f, out / f)
    dump_json(out / 'data' / 'suggestions.json', data)
    (RUN / 'about.md').write_text(about_md(dict(data, cards=cards)))
    pandoc(HERE / 'docs' / 'contributor-workflow.md', out / 'guide.html', 'Contributor workflow')
    pandoc(RUN / 'about.md', out / 'about.html', 'Method & coverage')
    dl = out / 'downloads'
    shutil.copy2(out / 'data' / 'suggestions.json', dl / 'suggestions.json')
    (dl / 'suggestions.csv').write_text(flat_csv(cards))
    missing_rows = papers_not_obtained(cards)
    with (dl / 'papers-not-obtained.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(missing_rows[0]) if missing_rows else ['doi'])
        w.writeheader()
        w.writerows(missing_rows)
    if (RUN / 'ft-skill' / 'summary.json').exists():
        shutil.copy2(RUN / 'ft-skill' / 'summary.json', dl / 'fulltext-experiment.json')
    for name in ['selection.json', 'packet_features.csv', 'route_assignment.json', 'route_comparison.json',
                 'cost-ledger.json', 'validation-report.json', 'manual-inspection.json']:
        if (RUN / name).exists():
            shutil.copy2(RUN / name, dl / name)
    shutil.copy2(RUN / 'about.md', dl / 'about.md')
    shutil.copy2(HERE / 'docs' / 'contributor-workflow.md', dl / 'contributor-workflow.md')
    zip_dir(archive / 'drafts-all-routes.zip', [(RUN / 'drafts', '*/*'), (RUN / 'review', '*.json')])
    zip_dir(dl / 'evidence-packets.zip', [(RUN / 'evidence', '*/packet.*')])
    zip_dir(dl / 'source-cache.zip', [(RUN / 'cache', 'sources/*.json'),
                                      (RUN / 'cache', 'secondary/*.json'), (RUN / 'cache', 'live_revisions.json'),
                                      (RUN / 'cache', 'requests.jsonl'), (RUN / 'cache', 'policy/*.json')])
    (dl / 'README.txt').write_text(
        'Private research material. Not for publication.\n\n'
        'The cards were prepared with AI and nobody has checked them yet. Read the articles and sources before '
        'acting, and write any edit in your own words. The earlier AI-written draft wording is not included.\n\n'
        'suggestions.json holds the cards; suggestions.csv has one row per study. about.md describes the method and '
        'coverage, and contributor-workflow.md explains how to review a card and record a decision. '
        'papers-not-obtained.csv lists the papers we could not get in full, with notes on where we looked. '
        'evidence-packets.zip holds the evidence the AI was given for each study. source-cache.zip holds publication '
        'details, abstracts, possible review articles, revision checks, the request log and the saved Wikipedia '
        'policies; a possible review article is a lead, not a checked source. The other files record the selection, '
        'the AI comparisons, the checks and the costs.\n\n'
        'Cached full texts stay in runs/edit-prototype-en/cache/fulltext and are not included here, because some '
        'free-to-read copies have no reuse licence.\n')
    items = sorted(p.name for p in dl.iterdir() if p.name != 'index.html')
    (dl / 'index.html').write_text('<!doctype html><meta charset="utf-8"><meta name="robots" content="noindex">'
                                   '<link rel="stylesheet" href="../style.css"><div class="prose"><h1>Downloads</h1>'
                                   '<p>Private research material. Not for publication. The cards were prepared with AI and nobody has '
                                   'checked them yet: read the sources and write any edit in your own words. '
                                   '<a href="README.txt">README.txt</a> says what each file holds.</p><ul>'
                                   + ''.join(f'<li><a href="{n}">{n}</a> ({(dl / n).stat().st_size // 1024} KB)</li>' for n in items)
                                   + '</ul><p><a href="../index.html">Back to the prototype</a></p></div>')
    print(json.dumps(dict(output=str(out), **data['counts'], missing=len(missing)), indent=1))


if __name__ == '__main__':
    main()
