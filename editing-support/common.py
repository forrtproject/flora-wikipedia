"""Shared paths and helpers for the English edit-suggestion prototype.

The prototype reads the frozen full English audit and its claim-review packets.
It never writes to those namespaces, to Wikipedia, or to Wikidata.
"""
import hashlib
import json
import pathlib
import re
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent  # editing-support/
SEARCH = ROOT.parent / 'search'
AUDIT = SEARCH / 'runs/english-full-gh/en'
WIKITEXT = AUDIT / 'cache/wikitext/en'
PACKETS = SEARCH / 'runs/editathon-review/packets.json'
RUN = ROOT / 'runs/edit-prototype-en'
UA = 'FLoRA-Wikipedia-Edit-Prototype/0.1 (private research prototype; https://github.com/forrtproject/flora-wikipedia)'

LIST_SECTIONS = {'further reading', 'references', 'selected publications', 'bibliography',
                 'publications', 'sources', 'articles', 'external links', 'works', 'selected works',
                 'notes', 'literature', 'selected bibliography', 'books', 'papers'}
HEALTH_TERMS = re.compile(r'disorder|disease|therap|clinical|medic|psychiatr|depress|anxiety|autis|drug|'
                          r'symptom|patient|treatment|cancer|diet|obesity|health|placebo|vaccin|surgery|'
                          r'pharma|syndrome|schizo|dementia|alzheimer|nutrition|mental illness', re.I)


def sha(text, n=20):
    return hashlib.sha256(text.encode()).hexdigest()[:n]


def load_json(path, default=None):
    path = pathlib.Path(path)
    return json.loads(path.read_text()) if path.exists() else default


def dump_json(path, obj):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
    tmp.rename(path)


def wikitext(pageid):
    return (WIKITEXT / f'{pageid}.txt').read_text(encoding='utf-8')


def wikitext_meta(pageid):
    return json.loads((WIKITEXT / f'{pageid}.txt.json').read_text())


def categories(text):
    return re.findall(r'\[\[\s*Category\s*:\s*([^\]|]+)', text, re.I)


def is_biography(text):
    cats = ' '.join(categories(text)).lower()
    return bool(re.search(r'\b(\d{3,4}s? births|living people|\d{4} deaths)\b', cats)) or \
        bool(re.search(r'\{\{\s*infobox (scientist|person|academic|philosopher|economist)', text, re.I))


def is_living(text):
    return any(c.strip().lower() == 'living people' for c in categories(text))


class Throttle:
    """Serial pacing for free services (default one request per second)."""

    def __init__(self, interval=1.0):
        self.interval, self.last = interval, 0.0

    def wait(self):
        delta = time.monotonic() - self.last
        if delta < self.interval:
            time.sleep(self.interval - delta)
        self.last = time.monotonic()


_THROTTLES = {}


def http_get(url, params=None, host_interval=1.0, accept='application/json', retries=4,
             max_seconds=90, max_bytes=40_000_000):
    """GET with per-host pacing and polite retry on 429/5xx; returns bytes."""
    if params:
        url = url + ('&' if '?' in url else '?') + urllib.parse.urlencode(params)
    host = urllib.parse.urlparse(url).netloc
    throttle = _THROTTLES.setdefault(host, Throttle(host_interval))
    for attempt in range(retries):
        throttle.wait()
        req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': accept})
        try:
            deadline = time.monotonic() + max_seconds
            with urllib.request.urlopen(req, timeout=30) as r:
                chunks, size = [], 0
                while True:
                    chunk = r.read(65536)
                    if not chunk:
                        return b''.join(chunks)
                    chunks.append(chunk)
                    size += len(chunk)
                    if time.monotonic() > deadline or size > max_bytes:
                        raise TimeoutError(f'download exceeded {max_seconds}s or {max_bytes} bytes')
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(float(e.headers.get('Retry-After') or 2 ** (attempt + 1)))
                continue
            raise
        except TimeoutError:
            raise
        except urllib.error.URLError:
            if attempt < retries - 1:
                time.sleep(2 ** (attempt + 1))
                continue
            raise
