#!/usr/bin/env python3
"""Build the full latest-input Spanish report after a completed run."""
import argparse,csv,html,json,pathlib,shutil,zipfile
root=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--output-dir',required=True);p.add_argument('--run',default='spanish-full-latest');a=p.parse_args()
out=pathlib.Path(a.output_dir).resolve()
if out in (root, root.parent) or (out/'.git').exists(): raise SystemExit('Use a dedicated output directory')
out.mkdir(parents=True,exist_ok=True)
base=root/'runs'/a.run/'es'; d=base/'output'
def read(p): return json.loads(p.read_text())
def rows(p):
 with p.open(encoding='utf-8',newline='') as f: return list(csv.DictReader(f))
def e(s): return html.escape(str(s if s is not None else ''))
m=read(d/'manifest.json'); s=read(d/'summary.json'); v=read(d/'full-validation.json')
if m['status']!='complete' or not v['passed']: raise SystemExit('Full run must complete and pass validation first')
prov=m['input_provenance']; state=read(base/'cache/resolver_inventory/state.json'); times=rows(d/'timings.csv')
initial=next(x for x in times if x['offline']=='FALSE'); offline=[x for x in times if x['offline']=='TRUE'][-1]
for f in d.iterdir():
 if f.is_file():
  dest=out/'spanish-full'/f.name;dest.parent.mkdir(exist_ok=True);shutil.copy2(f,dest)
shutil.copy2(base/'data/flora_source.json',out/'latest-flora-provenance.json')
shutil.copy2(root/'README.md',out/'README.md')
with zipfile.ZipFile(out/'spanish-full-products.zip','w',zipfile.ZIP_DEFLATED) as z:
 for f in base.rglob('*'):
  if f.is_file() and '.lock' not in f.parts: z.write(f,f.relative_to(root))
 for f in (root/'runs/inputs').glob('flora-latest-20261003.csv*'): z.write(f,f.relative_to(root))
with zipfile.ZipFile(out/'code-and-docs.zip','w',zipfile.ZIP_DEFLATED) as z:
 for sub in ['R','tests','scripts']:
  for f in (root/sub).rglob('*'):
   if f.is_file() and '__pycache__' not in f.parts: z.write(f,f.relative_to(root))
 for f in ['README.md','output/REPORT.md']: z.write(root/f,f)
 z.write(root.parent/'.gitignore','.gitignore')
examples=rows(d/'adjudication_pairs.csv');contexts=rows(d/'citation_contexts.csv')
notes={'7511921':'Both paired DOI strings occur here. Inspect whether the wording represents the replication, rather than inferring acknowledgement from co-presence.',
 '11468441':'The article draws on several sources. Check the paired replication, its scope, and the other references before considering a change.',
 '832526':'The original citation describes the historical origin of the effect. Review sources may discuss the evidence without naming this paired replication.',
 '11595699':'Review the article claim, the paired replication, and relevant secondary sources. This DOI audit does not adjudicate the clinical literature.'}
cards=[]
for pid,note in notes.items():
 ex=[r for r in examples if r['pageid']==pid]
 if not ex: continue
 r=ex[0];detail=[];seen=set()
 for c in contexts:
  if c['pageid']!=pid or (c['doi'],c['match_pos']) in seen: continue
  seen.add((c['doi'],c['match_pos']))
  detail.append(f'<details><summary>{e(c["doi_role"])} · {e(c["doi"])} · {e(c["section"])}</summary><p>Raw reference</p><pre>{e(c["ref_block"])}</pre><p>Full raw paragraph</p><pre lang="es">{e(c["paragraph"])}</pre></details>')
 pairs=''.join(f'<li>{e(x["title_r"])} ({e(x["year_r"])}) · <code>{e(x["doi_r_norm"])}</code> · FLoRA outcome: {e(x["outcome"])} · {e(x["assessment"])}</li>' for x in ex)
 cards.append(f'<article><h3>{e(r["page_title"])}</h3><p>{e(note)}</p><p><a href="{e(r["revision_url"])}">Frozen revision {e(r["revid"])}</a> · revision {e(r["revision_timestamp"])} · retrieved {e(r["retrieved_at"])}</p><p>Original: {e(r["title_o"])} ({e(r["year_o"])}) · <code>{e(r["doi_o_norm"])}</code></p><ul>{pairs}</ul><p lang="es">{e(r["review_prompt"])}</p>{"".join(detail)}</article>')
def pct(a,b): return f'{100*a/b:.1f}%' if b else 'undefined'
metrics=[('CSV rows',prov['csv_rows']),('Rows with both DOI fields',s['scope_pairs']),('Rows excluded because either DOI is missing',prov['csv_rows']-s['scope_pairs']),('Unique originals in scope',s['scope_originals']),('Unique DOIs in scope',s['discovery_dois']),('Candidate pages from either role',s['candidate_pages']),('Pages with detected scoped original',s['original_citing_pages']),('Originals detected in wikitext',s['originals_detected']),('Originals with any co-citing page',s['originals_with_any_co_citing_page']),('Article–original combinations',s['article_original_combinations']),('Combinations with any paired replication DOI',s['article_original_combinations_with_any_replication_doi'])]
table=''.join(f'<tr><th>{e(k)}</th><td>{e(x)}</td></tr>' for k,x in metrics)
checks=''.join(f'<li>{e(x)}</li>' for x in v['checks'])
command=f'Rscript R/run_audit.R --lang=es --run={a.run} --input=runs/inputs/flora-latest-20261003.csv --discovery=inventory'
report=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Full Spanish FLoRA audit · latest GitHub snapshot</title><style>body{{font:17px/1.55 system-ui,sans-serif;max-width:1050px;margin:40px auto;padding:0 24px;color:#182b32;background:#f8faf9}}h1,h2,h3{{line-height:1.2}}a{{color:#075c82}}table{{border-collapse:collapse;width:100%;margin:20px 0}}th,td{{padding:10px;border-bottom:1px solid #c7d3d5;text-align:left}}article{{padding:22px;border:1px solid #c7d3d5;background:white;margin:24px 0}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;padding:16px;background:#edf2f2;font-size:14px}}code{{overflow-wrap:anywhere}}details{{margin:14px 0}}summary{{cursor:pointer;font-weight:600}}.intro{{padding:20px;background:#e4eff1}}</style>
<h1>Full Spanish Wikipedia DOI audit</h1><p>Latest GitHub FLoRA snapshot · private review · incremental metered API cost US$0</p><p class="intro">The full audit completed against the latest FLoRA file fetched on 3 October 2026. The earlier sample used the clone snapshot and was not based on the latest upstream file. This report keeps those scopes separate. All usable DOI pairs in the pinned latest input were included.</p>
<h2>Input provenance</h2><p>Source: <a href="{e(prov['source_url'])}">immutable flora.csv</a> at <a href="{e(prov['upstream_commit_url'])}">commit {e(prov['upstream_file_commit'][:12])}</a>, file updated {e(prov['upstream_file_commit_time'])}; retrieved {e(prov['retrieved_at'])}. SHA-256: <code>{e(prov['sha256'])}</code>. The clone had 1,925 usable pairs, 1,797 originals, and 3,256 DOIs; this input has 2,745 pairs, 2,567 originals, and 4,826 DOIs. No clone input or archived English audit tables were overwritten. Two optional replication metadata fields absent upstream remain NA; FLoRA outcome labels were preserved.</p>
<h2>Coverage and denominators</h2><table>{table}</table><p>{s['originals_detected']}/{s['scope_originals']} ({pct(s['originals_detected'],s['scope_originals'])}) scoped originals were detected. Among detected originals, {s['originals_with_any_co_citing_page']}/{s['originals_detected']} ({pct(s['originals_with_any_co_citing_page'],s['originals_detected'])}) had any co-citing page. Separately, {s['article_original_combinations_with_any_replication_doi']}/{s['article_original_combinations']} ({pct(s['article_original_combinations_with_any_replication_doi'],s['article_original_combinations'])}) distinct article–original combinations contained a paired replication DOI.</p><p>These are DOI-based measures. Missing DOI co-citation does not establish missing acknowledgement. The archived English 54/422 rate counts originals with any co-citing page; 66/847 is its article–original measure. That English run used an earlier FLoRA snapshot and earlier article revisions, so these results do not support a direct language comparison.</p>
<h2>Method and service load</h2><p>Rather than issuing thousands of per-DOI queries, the run exhausted main-namespace MediaWiki external-link continuation for doi.org, including dx.doi.org subdomains, over HTTP and HTTPS together. It checkpointed each response and continuation, then matched URL-decoded, case-normalised DOI keys exactly to the pinned FLoRA DOI set. Complete negative matches were materialised only after inventory completion. This inventory contained {v['inventory_link_rows']:,} raw resolver-link rows in {state['chunks']} successful chunks. All {s['candidate_pages']} candidate pages were fetched with revision IDs, revision times, and retrieval times, then processed by the same wikitext DOI extraction and audit/context stages.</p><p>Requests were serial and paced at two per second, with maxlag, retries, and resumable caches. Inventory completion and every candidate revision were verified; case/encoding coverage can exceed the earlier per-DOI query approach. A live separate-versus-combined protocol check and a sample-versus-inventory comparison are included in the validation record. Full elapsed time from the first start through completion, including a cache-preserving restart: {float(v['full_initial_to_completion_wall_seconds']):.2f} seconds. The completion attempt took {float(initial['elapsed_seconds']):.2f} seconds after reusing the completed inventory and saved pages. Offline full rerun: {float(offline['elapsed_seconds']):.2f} seconds. All stages used free endpoints; no translation API, paid model, Wikipedia edits, or messages were used.</p>
<h2>Verification</h2><ul>{checks}</ul><h2>Adjudication examples</h2><p>The following examples retain original Spanish wikitext and frozen revision links. Outcome labels describe the supplied FLoRA rows and do not themselves justify article wording.</p>{''.join(cards)}
<h2>What remains unaudited</h2><p>Full means all usable DOI pairs in this input, not all scientific sources on Spanish Wikipedia. The {prov['csv_rows']-s['scope_pairs']} rows missing one or both DOIs were excluded; alternate identifiers were not substituted. Publisher-only or DOI-free citations, secondary-source acknowledgement, article history, and the substantive treatment of replication evidence remain unaudited. Main-namespace redirects/disambiguation pages can be candidates; DOI presence alone does not establish a substantive citation. The inherited extractor has limitations for complex SICI/parenthesised suffixes and DOI strings encoded inside raw wikitext. Citation contexts are occurrences, may repeat across pairs, and are not independent citations. Additional computational/robustness outcome labels in current FLoRA are preserved; the inherited worst-outcome summary rule does not adjudicate their meaning. Sequential page retrieval is not a simultaneous edition snapshot.</p><p>The overlap export contains {v["common_originals_with_archived_english"]} original DOI keys shared with the archived English pilot. Cross-language overlap uses DOI keys against that earlier run. It indicates shared studies, not translated pages, independent evidence, or comparable coverage denominators. Raw Wikipedia text remains subject to its CC BY-SA/GFDL licences, with revision links providing attribution.</p>
<h2>Reproduce and hand over</h2><pre>{e(command)}
Rscript R/run_audit.R --lang=es --run={e(a.run)} --discovery=inventory --offline
Rscript tests/test_inventory.R</pre><p>The input CSV is included in the cached-product archive; its provenance sidecar is also retained. Keep the frozen run for the 11–13 November replication hackathon and planned early 2027 edit-a-thon. Unzip its runs directory into the checkout to run offline.</p><ul><li><a href="spanish-full-products.zip">Complete full-run products, input, inventory responses, and revision caches</a> · <a href="code-and-docs.zip">Code, tests, and docs</a></li><li><a href="latest-flora-provenance.json">Latest input provenance</a> · <a href="README.md">Rerun documentation</a></li><li><a href="spanish-full/summary.json">Denominators</a> · <a href="spanish-full/manifest.json">Run manifest</a> · <a href="spanish-full/timings.csv">Measured times</a> · <a href="spanish-full/full-validation.json">Verification and cost</a></li><li><a href="spanish-full/adjudication_pairs.csv">All adjudication pairs</a> · <a href="spanish-full/citation_contexts.csv">All raw contexts</a> · <a href="spanish-full/cross_language_doi_overlap.csv">DOI overlap with English archive</a> · <a href="spanish-full/flora_wikipedia_audit.csv">Full paired audit</a></li><li><a href="spanish-full/inventory-tests.log">Inventory tests</a> · <a href="spanish-full/english-regression-tests.log">English regression</a> · <a href="index.html">Earlier sample review</a></li></ul></html>'''
(out/'spanish-full.html').write_text(report,encoding='utf-8')
index=out/'index.html'
if index.exists():
 old=index.read_text()
 if 'href="spanish-full.html"' not in old: index.write_text(old.replace('<h1>', '<p class="intro"><a href="spanish-full.html">Completed full Spanish audit against latest GitHub FLoRA</a></p><h1>',1))
print(out/'spanish-full.html')
