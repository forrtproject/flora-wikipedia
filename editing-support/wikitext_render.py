"""Minimal wikitext helpers: section extraction and a readable plain rendering.

The plain rendering keeps citation positions as bracketed markers so a reader
can see which sentence a reference supports. It is an approximation of the
rendered article; reviewers must still check the live page.
"""
import re

CITE_FIELD = r'\|\s*{}\s*=\s*([^|}}]+)'


def _field(tpl, name):
    m = re.search(CITE_FIELD.format(name), tpl, re.I)
    return m.group(1).strip() if m else ''


def ref_label(body):
    """Short label for a reference body: Author (year), DOI."""
    author = _field(body, 'last1') or _field(body, 'last') or _field(body, 'author1') or _field(body, 'author')
    ym = re.search(r'\b(1[89]\d\d|20\d\d)\b', _field(body, 'date') or _field(body, 'year'))
    year = ym.group(1) if ym else ''
    doi = _field(body, 'doi')
    title = _field(body, 'title')
    if not (author or doi or title):
        plain = re.sub(r'<[^>]+>|\{\{|\}\}|\[|\]', '', body).strip()
        return plain[:90]
    parts = [p for p in [author, f'({year})' if year else '', f'"{title[:70]}"' if title else ''] if p]
    return ' '.join(parts) + (f' doi:{doi}' if doi else '')


def ref_names_with(text, doi):
    """Names of <ref name=...> definitions whose body contains the DOI."""
    return [n for n, b in named_refs(text).items() if doi.lower() in b.lower()]


def named_ref_reuses(text, name):
    pat = r'<ref\s+name\s*=\s*"?' + re.escape(name) + r'"?\s*/>'
    return [m.start() for m in re.finditer(pat, text, re.I)]


def named_refs(text):
    out = {}
    for m in re.finditer(r'<ref\s+name\s*=\s*"?([^">/]+?)"?\s*>(.*?)</ref>', text, re.S | re.I):
        out.setdefault(m.group(1).strip(), m.group(2))
    return out


def plain(wt, refs=None, focal_dois=(), other_dois=()):
    """Render wikitext to readable text with [ref: ...] markers.

    References containing a focal DOI become [FOCAL REF: ...]; references
    containing a paired replication DOI become [PAIRED REF: ...].
    """
    refs = refs or {}
    focal = [d.lower() for d in focal_dois]
    other = [d.lower() for d in other_dois]

    def mark(body):
        low = body.lower()
        tag = 'FOCAL REF' if any(d in low for d in focal) else 'PAIRED REF' if any(d in low for d in other) else 'ref'
        return f' [{tag}: {ref_label(body)}]'

    def full(m):
        return mark(m.group(2))

    def short(m):
        name = m.group(1).strip()
        return mark(refs.get(name, name))

    s = re.sub(r'<!--.*?-->', '', wt, flags=re.S)
    s = re.sub(r'<ref([^>/]*)>(.*?)</ref>', full, s, flags=re.S | re.I)
    s = re.sub(r'<ref\s+name\s*=\s*"?([^">/]+?)"?\s*/>', short, s, flags=re.I)
    s = re.sub(r'\[\[(?:File|Image|Category):(?:[^\[\]]|\[\[[^\]]*\]\])*\]\]', '', s, flags=re.I)
    s = re.sub(r'\[\[([^\]|]+)\|([^\]]+)\]\]', r'\2', s)
    s = re.sub(r'\[\[([^\]]+)\]\]', r'\1', s)
    for _ in range(4):  # nested templates (links resolved first so their pipes do not split templates)
        s = re.sub(r'\{\{(?:[^{}])*\}\}', _template, s)
    s = re.sub(r'\[https?://\S+ ([^\]]+)\]', r'\1', s)
    s = re.sub(r"'''?", '', s)
    s = re.sub(r'<[^>]+>', '', s)
    s = re.sub(r'[ \t]+', ' ', s)
    s = re.sub(r'\n{3,}', '\n\n', s)
    return s.strip()


def _template(m):
    body = m.group(0)[2:-2]
    name = body.split('|', 1)[0].strip().lower()
    if name.startswith(('cite', 'citation')):
        return f'[{ref_label(body)}]'
    if name in ('quote', 'cquote', 'blockquote', 'quotation', 'quote box', 'centered pull quote'):
        parts = [p for p in body.split('|')[1:] if not re.match(r'\s*(author|source|title|sign|width|align|quote)\s*=', p)]
        q = re.search(r'\|\s*(?:quote|text)\s*=\s*([^|]+)', body)
        return '\n“' + (q.group(1) if q else (parts[0] if parts else '')).strip() + '”\n'
    if name in ('lang', 'nowrap', 'em', 'math', 'mvar'):
        parts = body.split('|')
        return parts[-1]
    if name in ('as of',):
        return 'As of ' + '|'.join(body.split('|')[1:])
    if name.startswith(('citation needed', 'cn', 'fact', 'dubious', 'better source', 'failed verification',
                        'clarify', 'when', 'who', 'by whom', 'vague', 'according to whom')):
        return f' [{{{{{name}}}}}]'
    return ''


def section_bounds(text, pos):
    """Return (heading, start, end) of the lowest-level section containing pos."""
    heads = [(m.start(), len(m.group(1)), m.group(2).strip()) for m in
             re.finditer(r'^(={2,6})\s*(.*?)\s*\1\s*$', text, re.M)]
    start, level, name = 0, 1, '(lead)'
    for h in heads:
        if h[0] <= pos:
            start, level, name = h
        else:
            break
    end = len(text)
    for h in heads:
        if h[0] > pos and h[1] <= level:
            end = h[0]
            break
    return name, start, end


def lead(text):
    m = re.search(r'^==', text, re.M)
    return text[:m.start()] if m else text[:6000]


def outline(text):
    return [('  ' * (len(m.group(1)) - 2)) + m.group(2).strip() for m in
            re.finditer(r'^(={2,6})\s*(.*?)\s*\1\s*$', text, re.M)]


def paragraph_at(text, pos):
    start = text.rfind('\n\n', 0, pos)
    end = text.find('\n\n', pos)
    return text[start + 2 if start >= 0 else 0: end if end >= 0 else len(text)]
