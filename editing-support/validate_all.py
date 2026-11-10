#!/usr/bin/env python3
"""Validate every draft from every route and write validation-report.json."""
import glob
import json

from common import RUN, dump_json, load_json
from validate import check

report = {}
for path in sorted(glob.glob(str(RUN / 'drafts' / '*' / '*.json'))):
    if path.endswith('.meta.json'):
        continue
    route = path.split('/')[-2]
    try:
        d = json.loads(open(path).read())
        evdir = 'evidence_ft' if route.endswith('_ft') else 'evidence'
        pk = load_json(RUN / evdir / d['card_id'] / 'packet.json')
        errors, warnings = check(d, pk)
    except Exception as e:  # unreadable output is a recorded failure
        errors, warnings = [f'unreadable: {e}'], []
    report.setdefault(route, {})[path.split('/')[-1][:-5]] = dict(errors=errors, warnings=warnings)
summary = {r: dict(drafts=len(v), failing=sum(bool(x['errors']) for x in v.values())) for r, v in report.items()}
dump_json(RUN / 'validation-report.json', dict(summary=summary, details=report))
print(json.dumps(summary))
