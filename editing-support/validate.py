#!/usr/bin/env python3
"""Schema and grounding validation for drafted suggestions.

Grounding checks (all machine-verifiable; they do not judge quality):
- claim quotes occur verbatim (whitespace-normalised) in the packet's article text;
- source excerpts occur verbatim in the cached abstract/full text of that DOI;
- the claimed evidence level does not exceed what was cached;
- draft citations reference packet DOIs (or are flagged NEEDS SOURCE);
- replace/modify targets occur in the article text;
- FLoRA outcome codes are not used as sources.
"""
import json
import pathlib
import re
import sys
import unicodedata

import jsonschema

from common import RUN, wikitext

HERE = pathlib.Path(__file__).parent
SCHEMA = json.loads((HERE / 'suggestion.schema.json').read_text())  # brief v6
SCHEMA_V5 = json.loads((HERE / 'suggestion.schema.v5.json').read_text())  # drafts written before v6
LEVEL = {'metadata_only': 0, 'abstract': 1, 'full_text': 2}
HUMAN_CHORE = re.compile(r'^\s*(confirm|check|verify|read|obtain|look up|open|find|search|consult|compare|see whether|ensure)\b', re.I)
DELEGATED = re.compile(r'(raise|ask|note|query|post)[^.;]{0,40}talk page (whether|if|to check|asking)|'
                       r'editor(s)? with access|ask(ing)? (an? |other )?editors? to (check|verify|confirm|find|obtain)', re.I)
GENERIC_CHECK = re.compile(r'\b(find|search( for)?|look for|locate|identify|seek)\b[^.;]{0,60}\b(review|meta-analy|secondary source|textbook|literature)', re.I)


def norm(s):
    s = unicodedata.normalize('NFKC', s or '')
    s = s.replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"')
    s = s.replace('–', '-').replace('—', '-').replace('­', '').replace('−', '-')
    s = re.sub(r'\s*\[(?:FOCAL REF|PAIRED REF|ref)[^\]]*\]', ' ', s)
    s = re.sub(r'-\s*\n\s*', '', s)  # PDF hyphenation
    return re.sub(r'\s+', ' ', s).strip().lower()


def article_texts(pk):
    parts = [pk['page']['lead_plain'], pk.get('article_plain', '')]
    for o in pk['occurrences']:
        parts += [o['paragraph_plain'], o['section_plain'], o['paragraph_wikitext']]
    return norm('\n'.join(parts))


def source_texts(pk):
    out = {}
    recs = [pk['original']['source']] + [r['source'] for r in pk['replications']]
    for s in recs:
        text = s.get('abstract') or ''
        if s.get('fulltext_path'):
            text += '\n' + (RUN / s['fulltext_path']).read_text(errors='replace')
        out[s['doi'].lower()] = (norm(text), s['evidence_level'])
    for r in pk.get('secondary_checked', []):  # reviews the pipeline checked, with text where obtained
        text = (RUN / r['text_path']).read_text(errors='replace') if r.get('text_path') else ''
        lead = next((l for l in pk.get('secondary_leads', []) if l.get('doi') == r['doi']), {})
        out.setdefault(r['doi'].lower(), (norm(text + '\n' + lead.get('abstract', '')), r['evidence_level']))
    for x in pk.get('extra_sources', []):  # article-cited papers and DOI look-ups
        out.setdefault(x['doi'].lower(), (norm((x.get('abstract') or '') + '\n' + (x.get('note') or '')), x['evidence_level']))
    for lead in pk.get('secondary_leads', []):
        if lead.get('doi'):
            out.setdefault(lead['doi'].lower(), (norm(lead.get('abstract', '')), lead['evidence_level']))
    return out


def check(draft, pk):
    errors, warnings = [], []
    v6 = 'brief_version' in draft
    try:
        jsonschema.validate(draft, SCHEMA if v6 else SCHEMA_V5)
    except jsonschema.ValidationError as e:
        return [f'schema: {e.message} at {list(e.absolute_path)}'], warnings
    if draft['card_id'] != pk['card_id']:
        errors.append('card_id mismatch')
    art = article_texts(pk)
    for c in draft['claim_sites']:
        q = norm(c['visible_claim_quote'])
        if c['is_visible_claim'] and len(q) < 40:
            errors.append(f'claim quote too short: {c["visible_claim_quote"]!r}')
        elif q and q not in art:
            errors.append(f'claim quote not found in article text: {c["visible_claim_quote"][:80]!r}')
    src = source_texts(pk)
    page_raw = wikitext(pk['page']['pageid']).lower()  # DOIs cited anywhere in the reviewed revision
    for e in draft['evidence_used']:
        doi = e['doi'].lower().replace('https://doi.org/', '')
        if doi not in src:
            if doi in page_raw and e['evidence_level'] == 'metadata_only' and not e['excerpt']:
                warnings.append(f'{doi}: cited in the article but not fetched; content uninspected')
            else:
                errors.append(f'evidence DOI not in packet: {doi}')
            continue
        text, level = src[doi]
        if LEVEL[e['evidence_level']] > LEVEL[level]:
            errors.append(f'{doi}: claims {e["evidence_level"]} but cache has {level}')
        if e['excerpt']:
            x = norm(e['excerpt'])
            if len(x) < 30:
                errors.append(f'{doi}: excerpt shorter than 30 characters')
            elif x not in text:
                errors.append(f'{doi}: excerpt not verbatim in cached source: {e["excerpt"][:80]!r}')
    d = draft['draft']
    if d['status'] in ('provided', 'conditional'):
        if not d['wording'].strip():
            errors.append('draft provided without wording')
        for cit in d['citations']:
            c = cit.lower().replace('https://doi.org/', '').strip()
            if c == 'needs source':
                warnings.append('draft relies on a source not yet found (NEEDS SOURCE)')
            elif c not in src:
                (warnings if c in page_raw else errors).append(f'draft cites DOI outside fetched packet sources: {cit}')
        for c in re.findall(r'\[cite:\s*([^\]]+)\]', d['wording']):
            c = c.strip().lower()
            if c != 'needs source' and c not in src and c not in page_raw:
                errors.append(f'draft wording cites DOI outside packet: {c}')
        cited = [c.lower().replace('https://doi.org/', '').strip() for c in d['citations']]
        pool = ' '.join(src[c][0] for c in cited if c in src) + ' ' + art
        prose = re.sub(r'\[cite:[^\]]*\]|<ref[^>]*>.*?</ref>|\{\{[^}]*\}\}', ' ', d['wording'])
        flat = pool.replace(',', '')
        for num in set(re.findall(r'(?<![\w.])\d[\d,]*(?:\.\d+)?', prose)):
            n = num.replace(',', '')
            alt = n[1:] if n.startswith('0.') else n
            if len(n) >= 2 and n not in flat and alt not in flat and not re.fullmatch(r'(19|20)\d\d', n):
                warnings.append(f'number {num} in draft wording not found in cited source text or article (check)')
        if d['operation'] in ('replace', 'modify', 'remove') and d['target_text'] and norm(d['target_text']) not in art:
            errors.append('draft target_text not found in article text')
    if 'needs source' in (d.get('wording', '') + ' '.join(d.get('citations', []))).lower():
        errors.append('placeholder citation (NEEDS SOURCE) in draft wording or citations')
    es = draft.get('edit_strength')
    if es is not None:
        idle = draft['proposed_action'] in ('no_change', 'defer')
        if (es == 'none') != idle:
            errors.append(f'edit_strength {es} inconsistent with proposed_action {draft["proposed_action"]}')
        if es in ('recommended_addition', 'optional_addition') and draft['article_scope'] in (
                'biography_history', 'list_or_bibliography', 'incidental'):
            errors.append(f'{es} is not allowed on a {draft["article_scope"]} page (use fix or none)')
        if es == 'fix' and not any(x['result'] in ('contradicted', 'not_in_source') for x in draft.get('verifications', [])):
            warnings.append('fix without a contradicted or not-in-source verification')
    for vf in draft.get('verifications', []):
        src_doi = vf['source'].lower().replace('https://doi.org/', '').replace('doi:', '').strip()
        if vf['result'] == 'source_unavailable':
            continue
        if not vf['quote'].strip():
            if not (v6 and vf['result'] == 'not_in_source' and vf['evidence_level'] == 'full_text'):
                errors.append(f'verification without a quote: {vf["claim"][:70]}')
            continue
        pool_text, level = src.get(src_doi, ('', None))
        # v6: a source quote must come from the named source; only claims about the article's wording quote the article.
        about_article = re.match(r'\s*(wikipedia )?article:', vf['claim'], re.I)
        allowed = (pool_text + ' ' + art) if (not v6 or about_article) else pool_text
        if src_doi not in src and src_doi not in page_raw:
            errors.append(f'verification source not in packet: {vf["source"]}')
        elif level and LEVEL[vf['evidence_level']] > LEVEL[level]:
            errors.append(f'verification claims {vf["evidence_level"]} but cache has {level}: {src_doi}')
        elif norm(vf['quote']) not in allowed:
            errors.append(f'verification quote not verbatim in source: {vf["quote"][:70]!r}')
    for chk in draft['required_checks']:
        if HUMAN_CHORE.search(chk):
            errors.append(f'left a verification chore for humans (do it yourself): {chk[:80]}')
    texts = [draft['rationale'], draft['assessment']] + draft['required_checks'] + \
        [a['action'] + ' ' + a['when'] for a in draft['alternatives']]
    for t in texts:
        if DELEGATED.search(t):
            warnings.append(f'delegates checking to Wikipedia editors: {t[:90]}')
    for chk in draft['required_checks']:
        if GENERIC_CHECK.search(chk):
            warnings.append(f'open-ended literature task in required_checks: {chk[:90]}')
    if re.search(r'\bFLoRA\b|FORRT', d.get('wording', ''), re.I):
        errors.append('draft wording mentions FLoRA/FORRT (not a citable source for article text)')
    for p in draft['content_points']:
        s = p['source'].lower().replace('https://doi.org/', '').strip()
        if p['evidence_level'] != 'needs_source' and s not in src and s not in page_raw and not s.startswith('needs'):
            warnings.append(f'content point source not in packet: {p["source"]}')
    if v6:
        e6, w6 = check_v6(draft, pk)
        errors += e6
        warnings += w6
    if draft['proposed_action'] == 'no_change' and draft['queue_recommendation'] == 'retain':
        warnings.append('no_change with retain queue decision: check consistency')
    if pk['screening_flags']['living_person_category'] and not draft['flags']['blp']:
        warnings.append('page is in Living people but blp flag is false')
    return errors, warnings


BARE_ARTICLE = re.compile(r'(?<!Wikipedia )\b(the|this)( live)? article\b|^Article:', re.I)
ADDITIONS_BANNED = ('biography_history', 'list_or_bibliography', 'incidental')
QUOTED = re.compile(r'"[^"]*"|“[^”]*”|‘[^’]*’|(?<!\w)\'[^\']*\'(?!\w)')


def ai_prose(draft):
    """The model's own sentences, with quoted spans removed."""
    out = [draft['assessment'], draft['rationale'], draft['article_use']['note'],
           draft['specific_study_match']['note'], draft['existing_acknowledgement']['note']]
    out += [r['note'] for r in draft['replications_assessed']] + draft['uncertainties'] + draft['required_checks']
    out += [a['action'] + ' ' + a['when'] for a in draft['alternatives']]
    out += [c['note'] for c in draft['claim_sites']] + [p['point'] for p in draft['content_points']]
    out += [e['what_it_supports'] for e in draft['evidence_used']]
    out += [v['claim'] for v in draft['verifications'] if not re.match(r'\s*Wikipedia article:', v['claim'])]
    return [QUOTED.sub('', t) for t in out]


def relevant(r):
    """A replication that bears, or may bear, on what the Wikipedia article says (shared with the build rule)."""
    return r['bears_on_article_claim'] != 'none' or r['tested_result'] == 'unclear'


def check_v6(draft, pk):
    """Consistency checks for brief v6 fields (the evidence coding that the build's tier rule reads)."""
    errors, warnings = [], []
    want = [r['doi'].lower() for r in pk['replications']]
    got = [r['doi'].lower().replace('https://doi.org/', '').replace('doi:', '').strip() for r in draft['replications_assessed']]
    if got != want:
        errors.append(f'replications_assessed must list the packet replications in order {want}, got {got}')
    art = article_texts(pk)
    for r in draft['replications_assessed']:
        on = r['already_on_page'] != 'no'
        if on != (r['report_accurate'] is not None):
            errors.append(f"{r['doi']}: report_accurate must be null exactly when already_on_page is no")
        if on and (len(norm(r['page_quote'])) < 30 or norm(r['page_quote']) not in art):
            errors.append(f"{r['doi']}: already_on_page {r['already_on_page']} needs a verbatim page_quote (30+ characters)")
        if not on and r['page_quote'].strip():
            errors.append(f"{r['doi']}: page_quote must be empty when already_on_page is no")
        if r['tested_result'] == 'different_topic' and r['bears_on_article_claim'] != 'none':
            warnings.append(f"{r['doi']}: tested_result different_topic but bears_on_article_claim is {r['bears_on_article_claim']}")
        if r['tested_result'] == 'cited_result' and r['bears_on_article_claim'] == 'none' \
                and draft['article_use']['states_finding'] != 'no':
            warnings.append(f"{r['doi']}: tested_result cited_result but bears_on_article_claim is none")
    idle = draft['proposed_action'] == 'no_change'
    if idle != (draft['no_change_basis'] != 'not_applicable'):
        errors.append(f"no_change_basis {draft['no_change_basis']} inconsistent with proposed_action {draft['proposed_action']}")
    for a in draft['alternatives']:
        if (a['type'] == 'belongs_elsewhere') != bool(a['target_article'].strip()):
            errors.append(f"alternative of type {a['type']}: target_article must be set exactly for belongs_elsewhere")
    for t in ai_prose(draft):
        m = BARE_ARTICLE.search(t)
        if m:
            warnings.append(f'say "the Wikipedia article", not "{m.group(0)}": {t[max(0, m.start() - 30):m.end() + 30]!r}')
            break
    reps, use, cf = draft['replications_assessed'], draft['article_use'], draft['citation_function']
    rel = [r for r in reps if relevant(r)]
    on_page = [r for r in reps if r['already_on_page'] != 'no']
    ack = draft['existing_acknowledgement']['status']
    if (ack == 'yes' and len(on_page) < len(reps)) or (ack == 'no' and on_page):
        errors.append(f'existing_acknowledgement {ack} disagrees with already_on_page in replications_assessed')
    if cf == 'current_empirical_support' and not use['relies_as_evidence']:
        warnings.append('current_empirical_support but relies_as_evidence is false')
    if cf == 'bibliography_listing' and (use['states_finding'] in ('as_fact', 'attributed') or use['relies_as_evidence']):
        warnings.append('bibliography_listing but the Wikipedia article states or relies on the finding')
    rule2 = [r['doi'] for r in reps if r['tested_result'] == 'cited_result' and r['bears_on_article_claim'] == 'direct'
             and r['result_vs_article_claim'] in ('fails', 'qualifies') and r['already_on_page'] == 'no']
    es = draft.get('edit_strength')
    if rule2 and use['relies_as_evidence'] and es in ('optional_addition', 'none') \
            and draft['article_scope'] not in ADDITIONS_BANNED and not draft['flags']['medrs']:
        warnings.append(f'recommended_addition conditions appear met ({", ".join(rule2)}) but edit_strength is {es}')
    if es == 'recommended_addition' and not rule2:
        warnings.append('recommended_addition without a direct, unreported replication that fails or qualifies the claim')
    basis = draft['no_change_basis']
    if basis == 'tests_other_claim' and rel:
        warnings.append('no_change_basis tests_other_claim, but a replication is coded as bearing on the claim')
    if basis == 'already_reported' and not (on_page and all(r['already_on_page'] != 'no' and r['report_accurate'] for r in rel)):
        warnings.append('no_change_basis already_reported, but not every relevant replication is reported accurately')
    if basis in ('confirms_claim', 'history_or_example') and any(r['result_vs_article_claim'] != 'confirms' for r in rel):
        warnings.append(f'no_change_basis {basis}, but a relevant replication does not confirm')
    if basis == 'confirms_claim' and draft['article_scope'] not in ADDITIONS_BANNED and not draft['flags']['medrs']:
        warnings.append('no_change_basis confirms_claim on a page where a confirming replication is an optional_addition')
    if basis in ('listed_only', 'named_without_finding') and use['states_finding'] in ('as_fact', 'attributed'):
        warnings.append(f"no_change_basis {basis}, but article_use.states_finding is {use['states_finding']}")
    return errors, warnings


def load_draft(path):
    raw = pathlib.Path(path).read_text()
    m = re.search(r'\{.*\}', raw, re.S)
    return json.loads(m.group(0) if m else raw)


if __name__ == '__main__':
    bad = 0
    import os
    evdir = os.environ.get('EVIDENCE_DIR', 'evidence')
    for path in sys.argv[1:]:
        d = load_draft(path)
        pk = json.loads((RUN / evdir / d['card_id'] / 'packet.json').read_text())
        errs, warns = check(d, pk)
        bad += bool(errs)
        print(f"{path}: {'OK' if not errs else 'FAIL'}")
        for e in errs:
            print('  ERROR', e)
        for w in warns:
            print('  warn ', w)
    sys.exit(1 if bad else 0)
