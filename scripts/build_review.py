#!/usr/bin/env python3
"""Build a self-contained private report in a dedicated directory (never publish)."""
import argparse, csv, html, json, pathlib, shutil, subprocess, zipfile
root = pathlib.Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument('--output-dir', required=True)
args = p.parse_args()
out = pathlib.Path(args.output_dir).resolve()
if out == root or (out / '.git').exists():
    raise SystemExit('Choose a dedicated output directory, not a repository')
out.mkdir(parents=True, exist_ok=True)
def esc(x): return html.escape(str(x if x is not None else ''))
def rows(path):
    with path.open(encoding='utf-8', newline='') as f: return list(csv.DictReader(f))
def load(run, lang):
    d = root / 'runs' / run / lang / 'output'
    return d, json.loads((d / 'summary.json').read_text()), rows(d / 'timings.csv')
esdir, es, estimes = load('spanish-sample', 'es')
endir, en, entimes = load('english-regression', 'en')
livedir, live, livetimes = load('english-live-sample', 'en')
for name, directory in [('spanish', esdir), ('english-regression', endir), ('english-live', livedir)]:
    dest = out / name; dest.mkdir(exist_ok=True)
    for f in directory.iterdir():
        if f.is_file(): shutil.copy2(f, dest / f.name)
shutil.copy2(root / 'README.md', out / 'README.md')
shutil.copy2(root / 'output/REPORT.md', out / 'corrected-pilot-report.md')
verification = root / 'runs/verification'
if not (verification / 'validation.json').exists():
    raise SystemExit('Run verification first; missing runs/verification/validation.json')
validation = json.loads((verification / 'validation.json').read_text())
if not validation.get('passed'): raise SystemExit('Verification has not passed')
for f in verification.iterdir():
    if f.is_file(): shutil.copy2(f, out / f.name)
# Full cached products, including frozen raw Spanish pages and revisions.
with zipfile.ZipFile(out / 'audit-products.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    for run in ['spanish-sample', 'english-regression', 'english-live-sample']:
        for f in (root / 'runs' / run).rglob('*'):
            if f.is_file() and '.lock' not in f.parts: z.write(f, f.relative_to(root))
with zipfile.ZipFile(out / 'code-and-docs.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    for sub in ['R', 'tests', 'scripts']:
        for f in (root / sub).rglob('*'):
            if f.is_file() and '__pycache__' not in f.parts: z.write(f, f.relative_to(root))
    for f in ['README.md', '.gitignore', 'output/REPORT.md']:
        z.write(root / f, f)
examples = rows(esdir / 'adjudication_pairs.csv')
contexts = rows(esdir / 'citation_contexts.csv')
notes = {
 '7511921': 'Both paired DOI strings occur in Características. Review whether the surrounding wording represents the replication accurately; co-presence alone does not establish this.',
 '11468441': 'The original appears among several sources in the introduction. The paired replication DOI was not detected. Check the other sources and the replication’s scope before considering a change.',
 '832526': 'The original is cited as the historical origin of the Stroop effect. The page also cites review sources. DOI absence does not establish a problem with this historical use.',
 '11595699': 'The original appears in Historia. Check the paired replication, broader clinical literature, and other references. The DOI audit does not adjudicate the medical claim.',
}
cards = []
for pid, note in notes.items():
    ex = [r for r in examples if r['pageid'] == pid]
    if not ex: continue
    r = ex[0]
    blocks = []
    seen = set()
    for c in contexts:
        if c['pageid'] != pid: continue
        key = (c['doi'], c['match_pos'])
        if key in seen: continue
        seen.add(key)
        blocks.append(f'<details><summary>{esc(c["doi_role"])} DOI {esc(c["doi"])} · section {esc(c["section"])}</summary><p>Raw ref block</p><pre>{esc(c["ref_block"])}</pre><p>Full raw paragraph (not translated)</p><pre lang="es">{esc(c["paragraph"])}</pre></details>')
    pair_list = ''.join(f'<li>{esc(x["title_r"])} ({esc(x["year_r"])}) · <code>{esc(x["doi_r_norm"])}</code> · {esc(x["outcome"])} (FLoRA label) · {esc(x["assessment"])}</li>' for x in ex)
    cards.append(f'<article><h3>{esc(r["page_title"])}</h3><p>{esc(note)}</p><p><a href="{esc(r["revision_url"])}">Frozen revision {esc(r["revid"])}</a> · revision UTC {esc(r["revision_timestamp"])} · retrieved {esc(r["retrieved_at"])}</p><p>Original: {esc(r["title_o"])} ({esc(r["year_o"])}) · <code>{esc(r["doi_o_norm"])}</code></p><ul>{pair_list}</ul><p lang="es">{esc(r["review_prompt"])}</p>{"".join(blocks)}</article>')
metric_rows = ''.join(f'<tr><th>{label}</th><td>{es[key]}</td><td>{en[key]}</td></tr>' for key, label in [
 ('scope_originals','Originals in scope'),('scope_pairs','Replication pairs in scope'),
 ('discovery_dois','DOIs in discovery scope'),('candidate_pages','Candidate pages (either role)'),
 ('original_citing_pages','Pages with scoped original DOI'),('originals_detected','Detected originals'),
 ('originals_with_any_co_citing_page','Originals with any co-citing page'),
 ('article_original_combinations','Article–original combinations'),
 ('article_original_combinations_with_any_replication_doi','Combinations with any paired replication DOI')])
es_first = next(t for t in estimes if t['offline'] == 'FALSE')
en_live_first = next(t for t in livetimes if t['offline'] == 'FALSE')
overlap = rows(esdir / 'cross_language_doi_overlap.csv')
common = len({r['doi_o_norm'] for r in overlap})
page_keys = len({(r['pageid'], r['doi_o_norm']) for r in overlap})
check_list = ''.join(f'<li>{esc(x)}</li>' for x in validation['checks'])
report = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>FLoRA Wikipedia · English and Spanish audit review</title>
<style>body{{font:17px/1.55 system-ui,sans-serif;max-width:1050px;margin:40px auto;padding:0 24px;color:#182b32;background:#f8faf9}}h1,h2,h3{{line-height:1.2}}h1{{font-size:2.25rem}}a{{color:#075c82}}table{{border-collapse:collapse;width:100%;margin:20px 0}}th,td{{padding:10px;border-bottom:1px solid #c7d3d5;text-align:left}}article{{padding:22px;border:1px solid #c7d3d5;background:white;margin:24px 0}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;padding:16px;background:#edf2f2;font-size:14px}}code{{overflow-wrap:anywhere}}details{{margin:14px 0}}summary{{cursor:pointer;font-weight:600}}.intro{{padding:20px;background:#e4eff1}}.muted{{color:#506168}}</style>
<h1>FLoRA Wikipedia: English replay and Spanish pilot</h1><p class="muted">Private review · 3 October 2026 · no edits, messages, or public publication · incremental metered API cost US$0</p>
<p class="intro">Language support and a safe one-command runner are implemented. English audit rows and summaries reproduce exactly. Spanish discovery, revision retrieval, DOI matching, raw contexts, and adjudication exports completed on a selected live sample. Missing DOI co-citation remains a screening observation, not a judgement about acknowledgement.</p>
<h2>Scope and denominators</h2><table><tr><th>Measure</th><th>Spanish live sample</th><th>English archived replay</th></tr>{metric_rows}</table>
<p>The Spanish sample selects the top 12 originals by archived English page count, with DOI as the tie-breaker, and includes all their 15 pairs (27 unique DOIs). It deliberately tests likely hits and is not representative of Spanish Wikipedia. Ten of 12 originals were detected; 1/10 had any co-citing page. Separately, 1/16 article–original combinations contained a paired replication DOI. No edition-wide rate is inferred.</p>
<p>The corrected English pilot rate is <strong>54/422 originals (12.8%) with any co-citing page</strong>. It is not a citation-level percentage. The distinct article–original rate is <strong>66/847 (7.8%)</strong>. The 798 candidate pages include DOI hits for either role; only 700 contain a detected scoped original. The discovery file’s 1,041 page–DOI hit rows are also a different denominator.</p>
<h2>Implementation and rerunning</h2><p>The runner locates its checkout from the script path and pins the supplied FLoRA CSV. Separate run/language directories isolate outputs, caches, and overlapping page IDs. It records scope hashes, code hashes, package versions, input source, completion status, and timing. Atomic DOI checkpoints include successful zero-hit queries; failed requests remain pending. Cached page sidecars preserve revision IDs, revision UTC times, and retrieval UTC times across interruption. Offline mode prohibits network requests, and a directory lock prevents concurrent writers to one namespace.</p>
<p>Live discovery queries HTTP/HTTPS, doi.org/dx.doi.org, and literal/slash-encoded forms, follows continuation, uses maxlag, and retries 429/5xx and relevant Wikimedia errors. Final pacing is serial with a one-request bucket refilled every 0.5 seconds. The initial live sample preceded this stricter burst-capacity setting; final pacing was exercised in the actual HTTP retry test. No paid translations or OpenAlex enrichment were run. Existing English outputs and scientific labels are preserved; report interpretation was corrected.</p>
<pre>Rscript R/setup.R
Rscript R/run_audit.R --lang=en --run=english-regression --legacy --offline
Rscript R/run_audit.R --lang=es --run=spanish-sample --sample=12
Rscript R/run_audit.R --lang=es --run=spanish-sample --sample=12 --offline
Rscript tests/test_pipeline.R
Rscript tests/test_english_regression.R</pre>
<p>Repeat an identical command to resume. Use a new run name to change scope or retrieve fresh revisions. The supplied CSV is frozen; new data acquisition requires an explicit new snapshot and run. Legacy OpenAlex, title-search, and insertion-sentence stages are optional and outside this runner. The Spanish packet supplies a Spanish review prompt and original metadata rather than an automatic insertion sentence. Archived recommendations have not been substantively adjudicated.</p>
<h2>Verification and measured time</h2><ul>{check_list}</ul>
<p>Spanish live sample: {float(es_first['elapsed_seconds']):.2f} seconds. Latest Spanish offline rerun: {float(estimes[-1]['elapsed_seconds']):.2f} seconds. English replay: {float(entimes[0]['elapsed_seconds']):.2f} seconds initially and {float(entimes[-1]['elapsed_seconds']):.2f} seconds on the latest rerun. English live sample: {live['discovery_dois']} DOIs, {live['candidate_pages']} pages, {float(en_live_first['elapsed_seconds']):.2f} seconds. Timing logs retain all measured reruns.</p>
<h2>Spanish examples for adjudication</h2><p>These are review candidates. Open a frozen revision and compare the original, paired replication, other sources, and article context. FLoRA outcome labels are inherited and do not themselves justify article wording. The expandable blocks retain full raw Spanish paragraphs and refs, with DOI occurrences deduplicated for display.</p>{''.join(cards)}
<h2>Coverage and remaining uncertainty</h2><p>All {common} detected Spanish original DOI keys also occur in the archived English audit ({page_keys} Spanish article–original combinations). The overlap CSV joins studies by DOI and can have several English pages per Spanish row. These are not independent studies, and DOI overlap does not establish translation links. Wikipedia text provenance: CC BY-SA/GFDL as applicable; revision links identify each source.</p>
<p>The sample leaves 1,785 FLoRA originals and most Spanish Wikipedia pages outside scope. Main-namespace external-link discovery misses publisher-only links, DOI-free references, and some encodings. The inherited DOI extractor expects a literal registrant slash and has known limits for SICI/parenthesised DOI suffixes. Presence alone does not prove citation relevance. Raw wikitext preserves Spanish cite templates and named-ref reuse; named-ref rendering, title/author/year search, secondary-source quality, substantive acknowledgement, and citation-addition histories remain unaudited. Pages were retrieved sequentially. Archived English revision IDs are available, but their retrieval/revision timestamps were not recorded. New Spanish caches retain both.</p>
<p>Full Spanish discovery has not run. At final pacing, 3,256 DOIs × up to eight ordinary requests × 0.5 seconds requires about 3.6 hours before retries, continuation, and page retrieval. It remains a concrete, resumable next step, with no paid API requirement:</p><pre>Rscript R/run_audit.R --lang=es --run=spanish-full</pre>
<h2>Review files and handover</h2><ul>
<li><a href="README.md">Reproducible commands and pipeline documentation</a> · <a href="corrected-pilot-report.md">Corrected English pilot report</a></li>
<li><a href="spanish/adjudication_pairs.csv">Spanish adjudication pairs</a> · <a href="spanish/citation_contexts.csv">Full raw Spanish contexts</a> · <a href="spanish/cross_language_doi_overlap.csv">Cross-language DOI overlap</a></li>
<li><a href="spanish/manifest.json">Spanish provenance manifest</a> · <a href="spanish/summary.json">Spanish denominators</a> · <a href="spanish/timings.csv">Spanish timings</a></li>
<li><a href="english-regression/summary.json">English replay denominators</a> · <a href="english-regression/manifest.json">English replay provenance</a> · <a href="english-live/manifest.json">English live sample provenance</a></li>
<li><a href="pipeline-tests.log">Pipeline tests</a> · <a href="regression-tests.log">Exact English regression</a> · <a href="validation.json">Verification and cost record</a></li>
<li><a href="code-and-docs.zip">Code, tests, and docs</a> · <a href="audit-products.zip">Complete frozen run products including raw caches</a></li>
</ul><p>The original checkout contains clearly diffed edits, with no push. Keep the private product archive or local runs for the 11–13 November replication hackathon and the planned early 2027 edit-a-thon. Place the archive’s runs folder in the checkout to use the offline commands. Sharing this tailnet report does not publish it publicly.</p></html>'''
(out / 'index.html').write_text(report, encoding='utf-8')
print(f'Report and handover files built in {out}')
