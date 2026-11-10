#!/usr/bin/env python3
"""Copy evidence packets into evidence_ft/, adding full texts obtained via the download-paper skill.

Only sources that lacked full text and now have extracted PDF text are changed; their
evidence level becomes full_text with the skill named as the source. The original
evidence/ packets are left untouched so drafts can be compared with and without.
"""
import json, shutil
from common import RUN, dump_json
from evidence import render_md, slug

def main():
    res = {}
    for line in (RUN / 'ft-skill' / 'results.jsonl').open():
        r = json.loads(line)
        if r.get('text_path'):
            res[r['doi'].lower()] = r
    changed = {}
    for d in sorted((RUN / 'evidence').iterdir()):
        pk = json.loads((d / 'packet.json').read_text())
        new = []
        for src in [pk['original']['source']] + [r['source'] for r in pk['replications']]:
            r = res.get(src['doi'].lower())
            if r and src['evidence_level'] != 'full_text':
                src.update(fulltext_path=r['text_path'], fulltext_chars=r['chars'], evidence_level='full_text',
                           fulltext_source='PDF via download-paper skill (fetchpdf open-access chain), retrieved ' + r['at'])
                new.append(src['doi'])
        if new:
            out = RUN / 'evidence_ft' / d.name
            out.mkdir(parents=True, exist_ok=True)
            shutil.copy2(d / 'article_plain.txt', out / 'article_plain.txt')
            dump_json(out / 'packet.json', pk)
            (out / 'packet.md').write_text(render_md(pk).replace(f"{pk['card_id']}/article_plain.txt", f"evidence_ft/{pk['card_id']}/article_plain.txt"))
            changed[d.name] = new
    dump_json(RUN / 'ft-skill' / 'ft_packets.json', changed)
    print(len(changed), 'cards gain full text;', sum(map(len, changed.values())), 'sources')

if __name__ == '__main__':
    main()
