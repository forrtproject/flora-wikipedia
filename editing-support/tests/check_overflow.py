#!/usr/bin/env python3
"""Rendered check: no card content spills past the card or is clipped, in any layout.

Opens every card with all folds and tabs open and reports elements whose right edge passes
the card, elements that clip their own content, and horizontal page scroll.

    uv run -q --with playwright python editing-support/tests/check_overflow.py http://HOST:PORT/ [--widths 1500,1150,400] [--layouts current]

Exits 1 if anything overflows.
"""
import argparse
import asyncio
import json
import sys
import urllib.request

from playwright.async_api import async_playwright

PROBE = r"""() => {
  document.querySelectorAll('#detail details').forEach(d => d.open = true);
  const det = document.getElementById('detail'), R = det.getBoundingClientRect(), out = [];
  for (const el of det.querySelectorAll('*')) {
    if (el.closest('[hidden]')) continue;
    const r = el.getBoundingClientRect();
    if (!r.width) continue;
    const name = el.tagName.toLowerCase() + (typeof el.className === 'string' && el.className ? '.' + el.className.split(' ').join('.') : '');
    if (r.right > R.right + 1) out.push(`past the card: ${name} by ${Math.round(r.right - R.right)}px`);
    const ox = getComputedStyle(el).overflowX;
    if (el.clientWidth && el.scrollWidth > el.clientWidth + 1 && !['auto', 'scroll'].includes(ox))
      out.push(`clipped: ${name} ${el.scrollWidth}>${el.clientWidth}`);
  }
  if (document.documentElement.scrollWidth > innerWidth + 1) out.push('horizontal page scroll');
  return [...new Set(out)];
}"""


async def main(base, widths, layouts):
    ids = [p['page_id'] for p in json.load(urllib.request.urlopen(base + 'data/suggestions.json'))['pages']]
    problems, errors = [], []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        for w in widths:
            await page.set_viewport_size({'width': w, 'height': 950})
            for lay in layouts:
                for pid in ids:
                    # A unique query string forces a reload (a hash-only change would not).
                    await page.goto(f'{base}?layout={lay}&welcome=0&c={lay}{w}{pid}#{pid}')
                    await page.wait_for_selector('#detail .item', timeout=10000)
                    for tab in (['papers', 'article', 'plan'] if lay == 'tabs' else ['']):
                        if tab:
                            await page.evaluate('t => document.querySelectorAll(`[data-tab="${t}"]`).forEach(x => x.click())', tab)
                        problems += [f'{w}px {lay} #{pid} {tab}: {p}' for p in await page.evaluate(PROBE)]
        await browser.close()
    for line in problems + [f'page error: {e}' for e in errors]:
        print(line)
    print(f'{len(ids)} cards × {len(layouts)} layouts × {len(widths)} widths: {len(problems)} overflow, {len(errors)} page errors')
    return 1 if problems or errors else 0


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('base')
    ap.add_argument('--widths', default='1500,1150,400')
    ap.add_argument('--layouts', default='current,brief,tabs,desk')
    a = ap.parse_args()
    sys.exit(asyncio.run(main(a.base.rstrip('/') + '/', [int(x) for x in a.widths.split(',')], a.layouts.split(','))))
