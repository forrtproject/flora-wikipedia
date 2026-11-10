#!/usr/bin/env python3
"""Render the identical drafting prompt for one card (used by every route)."""
import pathlib
import sys

from common import RUN

HERE = pathlib.Path(__file__).resolve().parent


def prompt(card_id, evidence_dir='evidence'):
    ev = RUN / evidence_dir / card_id
    brief = (HERE / 'drafting_brief.md').read_text()
    schema = (HERE / 'suggestion.schema.json').read_text()
    return brief.format(packet_md=ev / 'packet.md', packet_json=ev / 'packet.json', run_dir=RUN,
                        schema_path=HERE / 'suggestion.schema.json', schema_summary=schema.strip()) + \
        f'\nThe card_id is `{card_id}`.\n'


def page_prompt(pageid, out_dir, evidence_dir='evidence'):
    """Prompt for drafting all items on one page (brief v3)."""
    import json
    items = []
    for d in sorted((RUN / evidence_dir).iterdir()):
        pk = json.loads((d / 'packet.json').read_text())
        if str(pk['page']['pageid']) == str(pageid):
            items.append(pk)
    items.sort(key=lambda pk: [i['packet_id'] for i in pk.get('page_items', [])].index(pk['card_id'])
               if pk.get('page_items') else 0)
    item_list = '\n'.join(f"- item `{pk['card_id']}`: {pk['original']['flora_title']} (doi:{pk['original']['doi']}); "
                           f"packet {RUN / evidence_dir / pk['card_id'] / 'packet.md'}" for pk in items)
    brief = (HERE / 'drafting_brief.md').read_text()
    schema = (HERE / 'suggestion.schema.json').read_text()
    return brief.format(item_list=item_list, run_dir=RUN, schema_path=HERE / 'suggestion.schema.json',
                        schema_summary=schema.strip(), out_dir=out_dir) + \
        f"\nPage: {items[0]['page']['title']} (page ID {pageid}). Write {len(items)} file(s).\n", [pk['card_id'] for pk in items]


if __name__ == '__main__':
    sys.stdout.write(prompt(sys.argv[1], *(sys.argv[2:3])))
