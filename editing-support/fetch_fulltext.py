#!/usr/bin/env python3
"""Try the download-paper skill for every non-full-text source in the card sample.

Free routes only: OpenRouter/OpenAlex/CORE/Elsevier key variables are removed or
blanked for the child process; there is no SerpAPI key and the Chrome step is
macOS-only, so it is skipped here. Serial, one DOI at a time, results appended to
ft-skill/results.jsonl (restartable). PDFs stay in the skill's private cache;
extracted text goes to cache/fulltext_skill/ and is not redistributed.
"""
import datetime, json, os, subprocess, time
from common import RUN
from evidence import slug

SKILL = os.path.expanduser('~/.claude/skills/download-paper/download_paper.py')
OUT = RUN / 'ft-skill' / 'results.jsonl'
TXT = RUN / 'cache' / 'fulltext_skill'

def env():
    e = {k: v for k, v in os.environ.items() if k not in ('OPENROUTER_API_KEY', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY',
                                                          'GEMINI_API_KEY', 'SERPAPI_API_KEY', 'SERPAPI_API_KEYS')}
    e.update(OPENALEXAPIKEY='', OPENALEX_API_KEY='', COREAPIKEY='', CORE_API_KEY='', ELSEVIER_TDM_API_KEY='',
             ELSEVIER_API_KEY='', SERPAPI_API_KEY='', SERPAPI_API_KEYS='', EMAIL='unpaywall@impactstory.org')
    e.pop('RESEARCHER_EMAIL', None)
    return e

def _done():
    return {json.loads(l)['doi'].lower(): json.loads(l) for l in OUT.open()} if OUT.exists() else {}


def fetch_one(doi, cards=()):
    """Try the skill once per DOI (results cached in results.jsonl); return the result record."""
    prev = _done().get(doi.lower())
    if prev:
        return prev
    TXT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    try:
        p = subprocess.run([SKILL, '--doi', doi, '--no-browser'], capture_output=True, text=True, env=env(), timeout=600)
        code, stdout, stderr = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        code, stdout, stderr = 124, '', 'timeout'
    rec = dict(doi=doi, cards=list(cards), exit=code, seconds=round(time.time() - t0, 1),
               at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'), log_tail=stderr[-1500:])
    path = stdout.strip().splitlines()[-1] if code == 0 and stdout.strip() else ''
    if path and os.path.exists(path):
        text = subprocess.run(['pdftotext', '-layout', path, '-'], capture_output=True, text=True, timeout=120).stdout
        rec.update(pdf=path, chars=len(text), pages=text.count('\f'))
        if len(text) > 3000:
            (TXT / f"{slug(doi)}.txt").write_text(text)
            rec['text_path'] = str((TXT / f"{slug(doi)}.txt").relative_to(RUN))
        else:
            rec['note'] = 'PDF text too short (scanned or empty)'
    with OUT.open('a') as f:
        f.write(json.dumps(rec) + '\n')
    print('  fetched', doi, code, rec.get('chars'), rec['seconds'], flush=True)
    time.sleep(1)
    return rec


def main():
    for t in json.load(open(RUN / 'ft-skill' / 'targets.json')):
        fetch_one(t['doi'], t['cards'])


if __name__ == '__main__':
    main()
