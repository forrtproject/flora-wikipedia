#!/usr/bin/env python3
"""Copy the built site to a staging directory for the shared review deployment.

Rewrites "private" wording to "shared for review" and checks that no draft
wording or local archive is included. Fails if any expected text has moved,
so the staged copy never silently keeps the private wording.

    python3 prototype/stage_public.py ../flora-wikipedia-edit-prototype-20261006 STAGING_DIR
"""
import pathlib
import shutil
import sys

HDR = ('prototype · private review material', 'prototype · review material')
REWRITES = {
    'index.html': [('(private prototype)', '(prototype for review)'),
                   ('A private prototype, prepared', 'A prototype shared for review, prepared')],
    'guide.html': [HDR, ('The cards are private research material', 'The cards are research material shared for review,')],
    'about.html': [HDR, ('This is private research material, not for publication.',
                         'This is research material shared for review, not for publication.')],
    'downloads/about.md': [('This is private research material, not for publication.',
                            'This is research material shared for review, not for publication.')],
    'downloads/contributor-workflow.md': [('The cards are private research\nmaterial',
                                           'The cards are research material\nshared for review,')],
    'downloads/README.txt': [('Private research material. Not for publication.',
                              'Research material shared for review. Not for publication.')],
    'downloads/index.html': [('Private research material. Not for publication.',
                              'Research material shared for review. Please do not circulate further.')],
}


def main(src, dst):
    src, dst = pathlib.Path(src).resolve(), pathlib.Path(dst).resolve()
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    for name, subs in REWRITES.items():
        p = dst / name
        s = p.read_text()
        for old, new in subs:
            if old not in s:
                sys.exit(f'{name}: expected text not found: {old!r}')
            s = s.replace(old, new)
        p.write_text(s)
    leftovers = [str(p.relative_to(dst)) for p in dst.rglob('*') if p.suffix in ('.html', '.md', '.txt')
                 and 'private' in p.read_text().lower()]
    if leftovers:
        sys.exit(f'"private" still appears in: {leftovers}')
    if '"wording"' in (dst / 'data' / 'suggestions.json').read_text() or list(dst.rglob('drafts-all-routes.zip')):
        sys.exit('draft wording found in the staged copy')
    print(dst)


if __name__ == '__main__':
    main(*sys.argv[1:3])
