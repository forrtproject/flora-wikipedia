#!/usr/bin/env python3
"""Readable display snippets for the review articles checked for a replication.

check_reviews.py decides whether a review mentions the replication, from text that
`pdftotext -layout` extracted and that was lower-cased for matching. In two-column
PDFs, -layout interleaves the columns line by line, so its windows are unreadable.
For display only, this re-extracts the cached PDF in reading order (no -layout),
keeps the original case, skips hits in the reference list and returns the whole
sentence(s) around each in-text citation. The `mentions` result is left unchanged.
"""
import json
import re
import subprocess
from functools import lru_cache

from common import RUN
from evidence import slug

READING = RUN / 'cache' / 'fulltext_reading'
MAX_CHARS = 600


@lru_cache(maxsize=None)
def _pdfs():
    out = {}
    path = RUN / 'ft-skill' / 'results.jsonl'
    if path.exists():
        for line in path.open():
            r = json.loads(line)
            if r.get('pdf'):
                out[r['doi'].lower()] = r['pdf']
    return out


def reading_text(doi, text_path='', fallback=''):
    """Text in reading order: cached, else from the PDF, else the -layout text."""
    cached = READING / f'{slug(doi)}.txt'
    if cached.exists():
        return cached.read_text(errors='replace')
    pdf = _pdfs().get(doi.lower())
    text = ''
    if pdf:
        try:
            text = subprocess.run(['pdftotext', pdf, '-'], capture_output=True, text=True, timeout=120).stdout
        except (OSError, subprocess.TimeoutExpired):
            text = ''
    if len(text) > 3000:
        READING.mkdir(parents=True, exist_ok=True)
        cached.write_text(text)
        return text
    return (RUN / text_path).read_text(errors='replace') if text_path else fallback or ''


def _flat(text):
    text = text.replace('­', '')
    text = re.sub(r'(\w)-\s*\n\s*(\w)', r'\1\2', text)  # hyphenation at line ends
    return re.sub(r'\s+', ' ', text).strip()


REFS_HEAD = re.compile(r'\n\s*(References|REFERENCES|Bibliography|Literature Cited|Works Cited)\s*\n')


def _body_end(text):
    """Offset where the reference list starts (the last such heading), or the end."""
    heads = list(REFS_HEAD.finditer(text))
    return heads[-1].start() if heads and heads[-1].start() > len(text) * 0.4 else len(text)


SENT_END = re.compile(r'(?<=[a-z0-9\)\]][.!?])\s+(?=[A-Z“"(])')


def _sentence_around(flat, start, end):
    """Expand [start, end) to whole sentences, capped at MAX_CHARS."""
    bounds = [0] + [m.end() for m in SENT_END.finditer(flat)] + [len(flat)]
    s = max(b for b in bounds if b <= start)
    e = min((b for b in bounds if b >= end), default=len(flat))
    snippet = flat[s:e].strip()
    if len(snippet) > MAX_CHARS:  # runaway sentence (table, heading run-on): centre on the hit
        mid = (start + end) // 2
        s, e = max(0, mid - MAX_CHARS // 2), min(len(flat), mid + MAX_CHARS // 2)
        snippet = ('…' if s else '') + flat[s:e].strip() + ('…' if e < len(flat) else '')
    return snippet


def snippets(doi, text_path, cited, fallback=''):
    """cited: [(surname, year)] of the replications. Returns (snippets, reference_list_only)."""
    text = reading_text(doi, text_path, fallback)
    if not text:
        return [], False
    body = _flat(text[:_body_end(text)])
    found, in_refs = [], False
    for name, year in cited:
        if not name or not year:
            continue
        # A citation "Name (year)" or "Name et al., year" first; failing that, the looser
        # check_reviews.py rule (year within 250 characters either side).
        for reach in (60, 250):
            for m in re.finditer(rf'\b{re.escape(name)}\b', body):
                lo = m.start() - (reach if reach > 60 else 0)
                y = re.search(rf'\b{year}[a-z]?\b', body[max(0, lo): m.end() + reach])
                if not y:
                    continue
                ys = max(0, lo) + y.start()
                snip = _sentence_around(body, min(m.start(), ys), max(m.end(), ys + 4))
                if snip not in found:
                    found.append(snip)
            if found:
                break
        if not found and re.search(rf'\b{re.escape(name)}\b', _flat(text[_body_end(text):])):
            in_refs = True
    return found[:2], in_refs and not found
