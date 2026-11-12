#!/usr/bin/env python3
"""Write drafting copies of evidence packets without FLoRA outcome codes (brief v6).

FLoRA outcome codes are screening labels. The drafting model codes its own reading of each
replication (`result_vs_article_claim`), so the drafting copies leave the codes out to avoid
anchoring it. The copies also replace the DOI-only "detected on page" note with the pre-filter's
DOI-or-title detection. Source texts, article text and paths are unchanged; validation and the
build keep reading the original packets in evidence/.

Usage: blind_packets.py OUT_DIR CARD_ID ...   (OUT_DIR is created under the run directory)
"""
import json
import re
import sys

from common import RUN, dump_json
from prefilter import on_page_index

CODE = re.compile(r'; FLoRA outcome code: [^;\[]*\[screening input only, not citable\]')
DETECTED = re.compile(r'; DOI detected on page: (True|False)\)')
HOW = {'doi': 'yes (DOI found)', 'title': 'yes (title found)', None: 'not found by DOI or title'}


def blind(card_id, out_name, found):
    src, dst = RUN / 'evidence' / card_id, RUN / out_name / card_id
    dst.mkdir(parents=True, exist_ok=True)
    pk = json.loads((src / 'packet.json').read_text())
    pid = str(pk['page']['pageid'])
    for r in pk['replications']:
        r.pop('flora_outcome', None)
    for r in pk.get('replications_not_fetched', []):
        r.pop('flora_outcome', None)
    dump_json(dst / 'packet.json', pk)
    md = (src / 'packet.md').read_text()
    md = CODE.sub('', md)
    md = re.sub(r',?\s*"flora_outcome":\s*"[^"]*"', '', md)  # the 'further FLoRA pairs' list
    md = re.sub(r'(## FLoRA-LINKED REPLICATION/REPRODUCTION: doi:(\S+) .*?); DOI detected on page: (?:True|False)\)',
                lambda m: f"{m.group(1)}; cited on page: {HOW[found.get((pid, m.group(2).lower()))]})", md)
    if 'outcome code' in md or 'flora_outcome' in md or DETECTED.search(md):
        raise SystemExit(f'{card_id}: outcome code or old detection note left in packet.md')
    (dst / 'packet.md').write_text(md)
    for f in src.iterdir():
        if f.name not in ('packet.json', 'packet.md') and not (dst / f.name).exists():
            (dst / f.name).symlink_to(f.resolve())


if __name__ == '__main__':
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    found = on_page_index({json.loads((RUN / 'evidence' / c / 'packet.json').read_text())['page']['pageid'] for c in sys.argv[2:]})
    for cid in sys.argv[2:]:
        blind(cid, sys.argv[1], found)
    print(f'{len(sys.argv) - 2} packets written to {RUN / sys.argv[1]}')
