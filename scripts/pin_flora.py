#!/usr/bin/env python3
"""Acquire the latest upstream FLoRA file at an immutable Git commit."""
import argparse, csv, datetime, hashlib, io, json, pathlib, urllib.request
p = argparse.ArgumentParser(); p.add_argument('--output', required=True); a=p.parse_args()
out = pathlib.Path(a.output); out.parent.mkdir(parents=True, exist_ok=True)
if out.exists(): raise SystemExit('Refusing to overwrite a pinned input; use a new path')
def get(url):
    req=urllib.request.Request(url, headers={'User-Agent':'FLoRA-Wikipedia-Audit/0.2 (https://github.com/forrtproject/flora-wikipedia)'})
    with urllib.request.urlopen(req, timeout=60) as r: return r.read()
api='https://api.github.com/repos/forrtproject/FReD-data/commits?path=output/flora.csv&per_page=1'
commit=json.loads(get(api))[0]
sha=commit['sha']; url=f'https://raw.githubusercontent.com/forrtproject/FReD-data/{sha}/output/flora.csv'
content=get(url)
rows=list(csv.DictReader(io.StringIO(content.decode('utf-8-sig'))))
if not rows or not {'doi_o','doi_r','outcome','type','source'}.issubset(rows[0]):
    raise SystemExit('Upstream CSV schema does not contain required fields')
pairs=[r for r in rows if r['doi_o'] not in ('','NA') and r['doi_r'] not in ('','NA')]
provenance={'source_url':url,'upstream_file_commit':sha,
 'upstream_file_commit_time':commit['commit']['committer']['date'],
 'upstream_commit_url':commit['html_url'],
 'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'sha256':hashlib.sha256(content).hexdigest(),'csv_rows':len(rows),'doi_pairs':len(pairs),
 'originals':len({r['doi_o'].lower() for r in pairs}),
 'unique_dois':len({r[k].lower() for r in pairs for k in ('doi_o','doi_r')}),
 'incremental_metered_api_cost_usd':0}
tmp=out.with_suffix('.csv.tmp'); tmp.write_bytes(content); tmp.rename(out)
pathlib.Path(str(out)+'.provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
print(json.dumps(provenance,indent=2))
