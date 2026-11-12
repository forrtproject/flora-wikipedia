#!/usr/bin/env python3
"""Render the identical drafting prompt (used by every route).

page_prompt: all items on one Wikipedia page (brief v3 onwards; v6 adds where each replication is cited).
prompt: one item on its own, for the single-card CLI routes.
Usage: make_prompt.py PAGEID OUT_DIR [EVIDENCE_DIR]
"""
import json
import sys

from common import RUN
from prefilter import on_page_index

import pathlib

HERE = pathlib.Path(__file__).resolve().parent
HOW = {'doi': 'cited on the page (DOI found)', 'title': 'cited on the page (title found)',
       None: 'not found on the page by DOI or title'}


def _render(items, out_dir, evidence_dir):
    found = on_page_index({str(pk['page']['pageid']) for pk in items})
    lines = []
    for pk in items:
        pid = str(pk['page']['pageid'])
        reps = ''.join(f"\n  - replication doi:{r['doi']}: {HOW[found.get((pid, r['doi'].lower()))]}"
                       for r in pk['replications'])
        lines.append(f"- item `{pk['card_id']}`: {pk['original']['flora_title']} (doi:{pk['original']['doi']}); "
                     f"packet {RUN / evidence_dir / pk['card_id'] / 'packet.md'}{reps}")
    brief = (HERE / 'drafting_brief.md').read_text()
    schema = (HERE / 'suggestion.schema.json').read_text()
    return brief.format(item_list='\n'.join(lines), run_dir=RUN, schema_path=HERE / 'suggestion.schema.json',
                        schema_summary=schema.strip(), out_dir=out_dir)


def _packet(card_id, evidence_dir):
    path = RUN / evidence_dir / card_id / 'packet.json'
    if not path.exists():
        raise SystemExit(f'no evidence packet for {card_id} in {evidence_dir}/')
    return json.loads(path.read_text())


def prompt(card_id, out_dir, evidence_dir='evidence'):
    pk = _packet(card_id, evidence_dir)
    return _render([pk], out_dir, evidence_dir) + f"\nThe card_id is `{card_id}`. Write 1 file.\n"


def page_prompt(pageid, out_dir, evidence_dir='evidence'):
    """Prompt for drafting all items on one page; returns the prompt and the item IDs in order."""
    items = []
    for d in sorted((RUN / evidence_dir).iterdir()):
        if not (d / 'packet.json').exists():
            continue
        pk = json.loads((d / 'packet.json').read_text())
        if str(pk['page']['pageid']) == str(pageid):
            items.append(pk)
    if not items:
        raise SystemExit(f'no evidence packets for page {pageid} in {evidence_dir}/')
    items.sort(key=lambda pk: [i['packet_id'] for i in pk.get('page_items', [])].index(pk['card_id'])
               if pk.get('page_items') else 0)
    return _render(items, out_dir, evidence_dir) + \
        f"\nPage: {items[0]['page']['title']} (page ID {pageid}). Write {len(items)} file(s).\n", [pk['card_id'] for pk in items]


if __name__ == '__main__':
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    sys.stdout.write(page_prompt(sys.argv[1], sys.argv[2], *(sys.argv[3:4]))[0])
