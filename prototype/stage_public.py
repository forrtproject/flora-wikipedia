#!/usr/bin/env python3
"""Copy the built site to a staging directory for the shared review deployment.

Rewrites "private" wording to "shared for review" and checks that no draft
wording or local archive is included. Fails if any expected text has moved,
so the staged copy never silently keeps the private wording.

    python3 prototype/stage_public.py ../flora-wikipedia-edit-prototype-20261006 STAGING_DIR [--wip]

--wip adds a work-in-progress banner across the top of every page (used for the FORRT GitHub Pages copy).
"""
import argparse
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
                              'Research material shared for review; not a finished publication.')],
    'downloads/index.html': [('Private research material. Not for publication.',
                              'Research material shared for review; not a finished publication.')],
}
WIP = ('<div class="wip-banner" role="note"><strong>Work in progress.</strong> A prototype shared for feedback: '
       'the cards were prepared with AI help and have not yet been checked by people. Read the sources before acting '
       'on anything here.</div>')


def main(src, dst, wip=False):
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
    if wip:
        for p in [dst / 'index.html', dst / 'guide.html', dst / 'about.html', dst / 'downloads' / 'index.html']:
            s = p.read_text()
            if '<body>' in s:
                s = s.replace('<body>', '<body class="has-wip">\n' + WIP, 1)
            else:  # the downloads page has no <body> tag
                s = s.replace('<div class="prose">', WIP + '<div class="prose">', 1)
            p.write_text(s)
        (dst / '.nojekyll').write_text('')
    leftovers = [str(p.relative_to(dst)) for p in dst.rglob('*') if p.suffix in ('.html', '.md', '.txt')
                 and 'private' in p.read_text().lower()]
    if leftovers:
        sys.exit(f'"private" still appears in: {leftovers}')
    if '"wording"' in (dst / 'data' / 'suggestions.json').read_text() or list(dst.rglob('drafts-all-routes.zip')):
        sys.exit('draft wording found in the staged copy')
    print(dst)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('src')
    ap.add_argument('dst')
    ap.add_argument('--wip', action='store_true')
    a = ap.parse_args()
    main(a.src, a.dst, a.wip)
