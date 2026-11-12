#!/usr/bin/env python3
"""Run the drafting prompt for selected cards through a subscription-backed CLI route.

Routes:
  codex  OpenAI Codex CLI, ChatGPT-subscription login, read-only sandbox, user
         plugins/MCP disabled, web search disabled.
  agy    Antigravity CLI (Google OAuth login), read-only workspace, sandboxed.
Claude sub-agent drafts are produced through Claude Code's Agent tool and are
written to drafts/claude/ by the orchestrating session using the same prompt.

Each route writes only to drafts/<route>/; metered-key variables are removed
from the child environment so no route can fall back to a pay-per-token API.
Existing outputs that parse as JSON are skipped (restartable).
"""
import argparse
import datetime
import json
import os
import subprocess
import time

from common import RUN
from make_prompt import prompt

METERED_ENV = ['OPENROUTER_API_KEY', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'GEMINI_API_KEY', 'GOOGLE_API_KEY']
MODELS = {'codex': 'gpt-6.1-sol', 'agy': 'Gemini 3.8 Flash (High)'}


def child_env():
    env = dict(os.environ)
    for k in METERED_ENV:
        env.pop(k, None)
    return env


def run_card(route, card, model, effort):
    out = RUN / 'drafts' / route
    out.mkdir(parents=True, exist_ok=True)
    target = out / f'{card}.json'
    if target.exists():
        try:
            json.loads(target.read_text())
            return 'cached'
        except ValueError:
            pass
    ptext = prompt(card, out)
    (out / f'{card}.prompt.txt').write_text(ptext)
    raw = out / f'{card}.raw.txt'
    log = out / f'{card}.log'
    t0 = time.time()
    if route == 'codex':
        cmd = ['codex', 'exec', '--skip-git-repo-check', '--ignore-user-config', '--sandbox', 'read-only',
               '-m', model, '-c', f'model_reasoning_effort="{effort}"', '-c', 'web_search="disabled"',
               '-C', str(RUN), '--json', '-o', str(raw), '-']
        with open(log, 'w') as lf:
            proc = subprocess.run(cmd, input=ptext, text=True, stdout=lf, stderr=subprocess.STDOUT,
                                  env=child_env(), timeout=1800)
    elif route == 'agy':
        cmd = ['agy', '-p', ptext + '\nPut your whole result in your reply; do not create files or run commands.',
               '--model', model, '--print-timeout', '20m', '--sandbox',
               '--add-dir', str(RUN), '--add-dir', str(RUN.parent.parent)]
        with open(raw, 'w') as rf, open(log, 'w') as lf:
            proc = subprocess.run(cmd, stdout=rf, stderr=lf, env=child_env(), timeout=1800)
    else:
        raise SystemExit(f'unknown route {route}')
    secs = round(time.time() - t0, 1)
    text = raw.read_text() if raw.exists() else ''
    status = 'no_json'
    start, end = text.find('{'), text.rfind('}')
    if start >= 0 and end > start:
        try:
            obj = json.loads(text[start:end + 1])
            target.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
            status = 'ok'
        except ValueError:
            status = 'invalid_json'
    meta = dict(route=route, model=model, effort=effort, card_id=card, seconds=secs, exit_code=proc.returncode,
                status=status, finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
                billing='subscription-backed CLI login; metered key variables removed from child environment',
                incremental_metered_cost_usd=0)
    (out / f'{card}.meta.json').write_text(json.dumps(meta, indent=2) + '\n')
    return f'{status} {secs}s'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--route', required=True, choices=list(MODELS))
    ap.add_argument('--model')
    ap.add_argument('--effort', default='high')
    ap.add_argument('cards', nargs='+')
    a = ap.parse_args()
    for card in a.cards:
        print(card, run_card(a.route, card, a.model or MODELS[a.route], a.effort), flush=True)


if __name__ == '__main__':
    main()
