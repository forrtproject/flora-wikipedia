#!/usr/bin/env python3
"""Build private handover outputs; serve only the output directory."""
import argparse,csv,html,json,pathlib,re,shutil,subprocess,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
STYLE='body{font:17px/1.6 system-ui,sans-serif;max-width:1080px;margin:40px auto;padding:0 24px;color:#19313b;background:#f8faf9}h1,h2,h3{line-height:1.2}a{color:#075c82}table{border-collapse:collapse;width:100%;margin:24px 0}td,th{text-align:left;padding:10px;border-bottom:1px solid #ccd7da}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#eaf0f1;padding:20px;font-size:14px}code{overflow-wrap:anywhere}.lead{padding:20px;background:#e1eef0}details{margin:16px 0}article{padding:20px;border:1px solid #ccd7da;margin:20px 0;background:white}'
def e(x):return html.escape(str(x))
def load(p):return json.loads(p.read_text())
def page(title,body):return f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)}</title><style>{STYLE}</style>{body}</html>'
def prose(text):
    # Plain markdown paragraphs with linked policy URLs; no external JS or fonts.
    result=[]
    for paragraph in text.split('\n\n'):
        if paragraph.startswith('# '):result.append('<h1>'+e(paragraph[2:])+'</h1>');continue
        escaped=e(paragraph)
        escaped=re.sub(r'https://[^\s;<]+',lambda m:f'<a href="{m[0]}">{m[0]}</a>',escaped)
        result.append('<p>'+escaped.replace('\n','<br>')+'</p>')
    return ''.join(result)
def copy_tree_files(source,destination):
    destination.mkdir(parents=True,exist_ok=True)
    for p in source.iterdir():
        if p.is_file():shutil.copy2(p,destination/p.name)
def bundle_run(out,name,base):
    with zipfile.ZipFile(out/name,'w',zipfile.ZIP_DEFLATED) as z:
        for p in base.rglob('*'):
            if p.is_file() and '.lock' not in p.parts:z.write(p,p.relative_to(ROOT))
        for p in (ROOT/'runs/inputs').glob('flora-latest-2026100*.csv*'):z.write(p,p.relative_to(ROOT))
def main(out,plan_only=False):
    out=out.resolve()
    if out==ROOT.parent or out.is_relative_to(ROOT.parent) or (out/'.git').exists():raise ValueError('Serve only a dedicated directory outside the checkout')
    out.mkdir(parents=True,exist_ok=True)
    for name in ['opus-review','wikidata-sample','editathon-review','verification']:
        copy_tree_files(ROOT/'runs'/name,out/name)
    shutil.copy2(ROOT/'runs/inputs/flora-latest-20261005.csv.provenance.json',out/'github-input-check-20261005.json')
    plan=(ROOT.parent/'docs/editathon-plan.md').read_text()
    wd=load(ROOT/'runs/wikidata-sample/summary.json')
    wdrows=list(csv.DictReader((ROOT/'runs/wikidata-sample/reconciliation.csv').open()))
    table='<table><tr><th>Article</th><th>Topic item</th><th>Role / DOI</th><th>Paper item</th></tr>'+''.join(f'<tr><td>{e(r["article"])}</td><td>{e(r["article_qid"])}</td><td>{e(r["role"])}<br>{e(r["doi"])}</td><td>{e(r["paper_qid"] or r["match_status"])}</td></tr>' for r in wdrows)+'</table>'
    schedule='<table><tr><th>When</th><th>Work</th><th>Release gate / output</th></tr><tr><td>11 November</td><td>Policy training and ~20 mixed calibration packets</td><td>Report independent classification/decision agreement before releasing day-two packets</td></tr><tr><td>12 November</td><td>Claim-focused reading and source collection; modest 30–50 packets if resources allow</td><td>Specific-study match, secondary coverage, due weight, sources and second review; defer unresolved disagreements</td></tr><tr><td>13 November</td><td>Reconcile decisions and assemble a small checked backlog</td><td>Retain/drop/defer ledger, no-change record, COI flags and read-only Wikidata identity queue</td></tr><tr><td>Early 2027</td><td>Separately authorised manual edit-a-thons with experienced local editors</td><td>Refresh revisions and policies; individual human decisions, disclosed COI requests, no mass insertion workflow</td></tr><tr><td>30 / 90 days later</td><td>Check accuracy, acceptance and objections</td><td>Quality and retention findings; no automatic restoration</td></tr></table>'
    body=prose(plan).replace('</h1>','</h1>'+schedule,1)+'<h2>Read-only Wikidata demonstration</h2>'+f'<p>{wd["matched_dois"]}/{wd["unique_dois"]} sampled DOI keys matched existing paper items across four Spanish articles. {wd["duplicate_doi_items"]} queried DOI keys had multiple items. This is an identity sample, not a coverage estimate or evidence of acknowledgement. Both main and scholarly graphs were queried; main-only queries missed these scholarly matches. <a href="https://www.wikidata.org/wiki/Wikidata:SPARQL_query_service/WDQS_graph_split">Wikidata graph-split documentation</a>.</p>'+table+'<p>For Automaticidad, the graph already records the Doyen paper (Q21089914) citing the Bargh paper (Q28287465) through P2860. This is a citation edge, not a replication verdict or evidence about the article’s wording.</p><ul>'+''.join('<li>'+e(x)+'</li>' for x in wd['limitations'])+'</ul><p><a href="opus-review/review.md">First Opus review</a> · <a href="opus-review/confirm.md">Explicit approval after revision</a> · <a href="opus-review/cost-ledger.json">Cost ledger</a> · <a href="wikidata-sample/reconciliation.csv">Wikidata identity CSV</a> · <a href="wikidata-sample/summary.json">Sample scope and limitations</a> · <a href="editathon-review/decisions.csv">Editable decision ledger</a> · <a href="editathon-review/calibration.json">Mixed calibration set</a> · <a href="editathon-review/packets.json">Evidence packets</a> · <a href="editathon-review/active-packets.json">Active queue</a> · <a href="handover.html">Full audit handover</a></p>'
    if plan_only and not (out/'handover.html').exists():
        body=body.replace('<a href="handover.html">Full audit handover</a>', '<a href="english-progress.json">English live progress</a>')
    (out/'editathon-plan.html').write_text(page('Opus-reviewed FLoRA edit-a-thon plan',body))
    if plan_only:return
    bases={'en':ROOT/'runs/english-full-gh/en','es':ROOT/'runs/spanish-full-latest/es'}
    summaries={l:load(b/'output/summary.json') for l,b in bases.items()}
    validations={l:load(b/'output/full-validation.json') for l,b in bases.items()}
    if not all(v['passed'] for v in validations.values()):raise ValueError('Both completed full runs must pass verification')
    for l,b in bases.items():
        if load(b/'output/manifest.json')['status']!='complete':raise ValueError('Incomplete audit')
        copy_tree_files(b/'output',out/('full-'+l))
    bundle_run(out,'english-full-products.zip',bases['en'])
    bundle_run(out,'programme-products.zip',ROOT/'runs/editathon-review')
    with zipfile.ZipFile(out/'programme-products.zip','a',zipfile.ZIP_DEFLATED) as z:
        for folder in ['wikidata-sample','opus-review','spanish-sample/es','english-live-sample/en']:
            for f in (ROOT/'runs'/folder).rglob('*'):
                if f.is_file():z.write(f,f.relative_to(ROOT))
    patch=subprocess.check_output(['git','diff','--binary'],cwd=ROOT)
    (out/'tracked-changes.patch').write_bytes(patch)
    with zipfile.ZipFile(out/'code-and-docs.zip','w',zipfile.ZIP_DEFLATED) as z:
        for folder in ['R','tests','scripts','docs']:
            for f in (ROOT/folder).rglob('*'):
                if f.is_file() and '__pycache__' not in f.parts:z.write(f,f.relative_to(ROOT))
        for f in ['README.md','output/REPORT.md']:z.write(ROOT/f,f)
        z.write(ROOT.parent/'.gitignore','.gitignore')
        z.write(out/'tracked-changes.patch','tracked-changes.patch')
    fields=[('scope_pairs','Usable original–replication pairs'),('scope_originals','Distinct originals in scope'),('discovery_dois','Distinct DOI keys'),('candidate_pages','Candidate pages, either role'),('original_citing_pages','Pages with a detected original DOI'),('originals_detected','Detected original studies'),('originals_with_any_co_citing_page','Originals with any co-citing page'),('article_original_combinations','Distinct article–original combinations'),('article_original_combinations_with_any_replication_doi','Combinations with any paired replication DOI')]
    metrics='<table><tr><th>Measure</th><th>English</th><th>Spanish</th></tr>'+''.join('<tr><th>'+e(label)+'</th>'+''.join('<td>'+e(summaries[l][key])+'</td>' for l in ['en','es'])+'</tr>' for key,label in fields)+'</table>'
    denoms=''
    for l,s in summaries.items():
        n=s['originals_with_any_co_citing_page'];d=s['originals_detected'];a=s['article_original_combinations_with_any_replication_doi'];b=s['article_original_combinations']
        denoms+=f'<p>{"English" if l=="en" else "Spanish"}: {n}/{d} ({100*n/d:.1f}%) detected originals had any co-citing page; separately, {a}/{b} ({100*a/b:.1f}%) article–original combinations contained a paired replication DOI. Neither measure is a percentage of individual citations or substantive acknowledgement.</p>'
    overlaps={l:{r['doi_o_norm'] for r in csv.DictReader((b/'output/adjudication_pairs.csv').open())} for l,b in bases.items()}
    shared=sorted(overlaps['en'] & overlaps['es'])
    (out/'current-cross-language-dois.json').write_text(json.dumps(dict(shared_original_dois=shared,count=len(shared),meaning='Shared study DOI keys, not translated article pairs or independent evidence.'),indent=2))
    timing='<table><tr><th>Run</th><th>Live elapsed seconds</th><th>Offline rerun seconds</th><th>Inventory chunks / link rows</th></tr>'+''.join(f'<tr><td>{l}</td><td>{v["full_initial_to_completion_wall_seconds"]:.2f}</td><td>{v["offline_latest_seconds"]:.2f}</td><td>{v["inventory_chunks"]} / {v["inventory_link_rows"]:,}</td></tr>' for l,v in validations.items())+'</table>'
    links='<ul>'+''.join(f'<li>{l}: <a href="full-{l}/summary.json">denominators</a> · <a href="full-{l}/manifest.json">manifest and package versions</a> · <a href="full-{l}/full-validation.json">verification</a> · <a href="full-{l}/timings.csv">times</a> · <a href="full-{l}/adjudication_pairs.csv">all pairs and frozen revisions</a> · <a href="full-{l}/citation_contexts.csv">raw contexts</a> · <a href="full-{l}/flora_wikipedia_audit.csv">audit</a></li>' for l in ['en','es'])+'</ul>'
    commands='''Rscript R/run_audit.R --lang=en --run=english-full-gh --input=runs/inputs/flora-latest-20261003.csv --discovery=inventory
Rscript R/run_audit.R --lang=es --run=spanish-full-latest --input=runs/inputs/flora-latest-20261003.csv --discovery=inventory
# Reuse each frozen namespace without any network access:
Rscript R/run_audit.R --lang=en --run=english-full-gh --discovery=inventory --offline
Rscript R/run_audit.R --lang=es --run=spanish-full-latest --discovery=inventory --offline
bash scripts/verify.sh'''
    body='<h1>FLoRA Wikipedia: full English and Spanish handover</h1><p class="lead">Both editions use the same pinned current GitHub input: 3,056 CSV rows, 2,745 usable DOI pairs, 2,567 originals and 4,826 DOI keys. The GitHub file checked on 5 October is byte-identical to the 3 October pin. Article snapshots are sequential and differ in date: Spanish 3 October, English 5 October. DOI co-citation screens for human review; it does not establish acknowledgement, neglect or a required edit.</p>'+metrics+denoms+f'<p>{len(shared)} detected original DOI keys overlap between these current-input runs. <a href="current-cross-language-dois.json">Shared keys</a> are not translated-page matches. The archived pilot remains separate: 54/422 counted originals with any co-citing page, while 66/847 counted article–original combinations.</p><h2>Implementation and verification</h2><p>Parameterised Wikimedia endpoints, isolated language/run namespaces, immutable CSV provenance, serial cached discovery and revision retrieval, resumable continuation/retries, single-writer locks and deterministic offline stages. Complete inventories are required before materialising negative matches. Zero-hit rows’ inherited queried_at field records local derivation time, not a dedicated DOI request; retained inventory chunk/state timestamps define discovery provenance. The archived English regression remains unchanged. DOI extraction preserves inherited English contracts and Unicode Spanish text. New review-ledger tests verify that drops preserve evidence and require reasons; the retired generator refuses to run.</p>'+timing+'<p>Five principal offline audit products were checked byte-for-byte after rerunning. Full validators recompute scope and denominators, verify every candidate revision sidecar, completed continuation, input checksum and normalised DOI inventory. <a href="verification/validation.json">Regression and pipeline verification</a> · <a href="verification/adjudication-tests.log">Review-ledger tests</a> · <a href="verification/citation-format-tests.log">Author-formatting test</a>.</p><h2>Review programme and limitations</h2><p><a href="editathon-plan.html">Opus-approved private preparation plan, source gates, drop decisions and Wikidata sample</a>. Automatic outcome-to-edit advice is retired locally. The existing public GitHub Pages demo still shows the old suggestions and must be corrected or retired through a separately authorised deployment before programme use. This session makes no Wikipedia/Wikidata edits or external messages.</p><p>Coverage is limited to usable DOI pairs and main-namespace resolver-link discovery. 311 rows missing either DOI were excluded; DOI-free citations, publisher-only links, secondary-source acknowledgement, content accuracy, citation histories and substantive replication interpretation remain unaudited. Complex DOI punctuation and encoded raw-wikitext suffixes retain extractor limits; resolver query/fragment stripping can also miss literal question-mark/hash suffixes. DOIs may occur in comments, bibliographies or examples rather than supporting a visible claim. Context occurrences can repeat across pairs; they are not independent citations. FLoRA outcome labels are preserved screening metadata, never proposed wording. Cross-language comparisons reflect source matching and dated snapshots, not causal differences in editorial quality. Raw Wikipedia text is subject to its CC BY-SA/GFDL licences; revision links retain attribution.</p><h2>Reproduce and review</h2><pre>'+e(commands)+'</pre>'+links+'<p><a href="english-full-products.zip">English full input, products and resumable caches</a> · <a href="spanish-full-products.zip">Spanish full input, products and resumable caches</a> · <a href="programme-products.zip">Decision queue, Wikidata raw caches, Opus reviews and offline sample fixtures</a> · <a href="code-and-docs.zip">Clearly diffed code/docs and tests</a> · <a href="tracked-changes.patch">Tracked-file patch</a> · <a href="opus-review/cost-ledger.json">Cost ledger</a> · <a href="github-input-check-20261005.json">Latest GitHub provenance check</a> · <a href="spanish-full.html">Spanish examples</a> · <a href="index.html">Earlier pilot review</a></p><p>Incremental metered API cost: US$0 cumulative. Opus 5.5 used the existing Max subscription; its reported nominal cumulative rate-equivalent session cost was US$0.4271, not an incremental bill. Free Wikimedia/GitHub read endpoints were used. The server serves only a dedicated private output directory and remains available for review.</p>'
    (out/'handover.html').write_text(page('Full English / Spanish FLoRA audit and programme',body))
    index=out/'index.html'
    if index.exists() and 'href="handover.html"' not in index.read_text():
        index.write_text(index.read_text().replace('<h1>', '<p><a href="handover.html">Completed full English and Spanish audits and Opus-reviewed programme</a></p><h1>',1))
    shutil.copy2(ROOT/'README.md',out/'README.md')
    print(out/'handover.html')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output-dir',required=True,type=pathlib.Path);p.add_argument('--plan-only',action='store_true');a=p.parse_args();main(a.output_dir,a.plan_only)
