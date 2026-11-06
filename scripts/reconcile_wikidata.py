#!/usr/bin/env python3
"""Small read-only Wikidata identity sample. DOI identity is not acknowledgement.
Cached GET requests only; unresolved service errors never become no-match claims.
"""
import argparse,csv,datetime,hashlib,json,pathlib,time,urllib.parse,urllib.request,urllib.error
UA='FLoRA-Wikipedia-Audit/0.3 (https://github.com/forrtproject/flora-wikipedia)'
def get_json(url,cache,offline=False):
    path=cache/(hashlib.sha256(url.encode()).hexdigest()+'.json')
    if path.exists(): return json.loads(path.read_text())
    if offline: raise RuntimeError('Uncached request in offline mode')
    last=None
    for attempt in range(4):
        time.sleep(.6)
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/sparql-results+json, application/json'}),timeout=60) as r: body=json.load(r)
            if 'error' in body: raise RuntimeError(str(body['error']))
            record={'request_url':url,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'body':body}
            tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(record,ensure_ascii=False));tmp.replace(path)
            return record
        except urllib.error.HTTPError as e:
            last=e
            if e.code not in {429,500,502,503,504}: raise
            time.sleep(min(30,max(2**attempt,float(e.headers.get('Retry-After','0')))))
        except (urllib.error.URLError,TimeoutError) as e: last=e;time.sleep(2**attempt)
    raise RuntimeError('Request unresolved after retries: '+str(last))
def reconcile(packets,out,offline=False,limit=4):
    out.mkdir(parents=True,exist_ok=True);cache=out/'cache';cache.mkdir(exist_ok=True)
    # Fixed named sample across article roles; not an edition-wide estimate.
    names=['Automaticidad','Efecto de Stroop','Penalización de la maternidad','Racismo médico en Estados Unidos']
    selected=[p for name in names for p in packets if p['page_title']==name][:limit]
    if not selected: selected=packets[:limit]
    dois=sorted({d for p in selected for d in [p['original_doi']]+[r['doi_r_norm'] for r in p['pairs']]})
    literals=' '.join(json.dumps(d.upper())+' '+json.dumps(d.lower()) for d in dois)
    query='SELECT DISTINCT ?doi ?work WHERE { VALUES ?doi { '+literals+' } ?work wdt:P356 ?doi . }'
    records=[get_json(endpoint+'?'+urllib.parse.urlencode({'query':query,'format':'json'}),cache,offline) for endpoint in ['https://query.wikidata.org/sparql','https://query-scholarly.wikidata.org/sparql']]
    record=records[-1]
    matches={d:[] for d in dois}
    for result in records:
        for row in result['body']['results']['bindings']:
            doi=row['doi']['value'].lower();qid=row['work']['value'].rsplit('/',1)[-1]
            if doi in matches and qid not in matches[doi]: matches[doi].append(qid)
    qids=sorted({q for qs in matches.values() for q in qs})
    entities={}
    if qids:
        er=get_json('https://www.wikidata.org/w/api.php?'+urllib.parse.urlencode({'action':'wbgetentities','ids':'|'.join(qids),'props':'labels|claims|info','languages':'en|es','format':'json','maxlag':5}),cache,offline)
        entities=er['body']['entities']
    pages={}
    for lang in sorted({p['language'] for p in selected}):
        ids=[p['pageid'] for p in selected if p['language']==lang]
        pr=get_json(f'https://{lang}.wikipedia.org/w/api.php?'+urllib.parse.urlencode({'action':'query','pageids':'|'.join(ids),'prop':'pageprops','ppprop':'wikibase_item','format':'json','maxlag':5}),cache,offline)
        pages.update({(lang,k):v.get('pageprops',{}).get('wikibase_item','') for k,v in pr['body']['query']['pages'].items()})
    def values(ent,prop):
        return [c.get('mainsnak',{}).get('datavalue',{}).get('value') for c in ent.get('claims',{}).get(prop,[])]
    rows=[]
    for p in selected:
        for role,d in [('original',p['original_doi'])]+[('replication',r['doi_r_norm']) for r in p['pairs']]:
            qs=matches[d]
            if not qs: qs=['']
            for qid in qs:
                ent=entities.get(qid,{})
                rows.append(dict(language=p['language'],article=p['page_title'],article_qid=pages.get((p['language'],p['pageid']),''),article_audit_revision=p['revision_id'],role=role,doi=d,paper_qid=qid,match_status='multiple_items' if len(matches[d])>1 else 'exact_doi_item' if qid else 'no_exact_case_variant_match',paper_label=ent.get('labels',{}).get('en',ent.get('labels',{}).get('es',{})).get('value',''),item_revision=ent.get('lastrevid',''),item_modified=ent.get('modified',''),doi_verified=any(isinstance(v,str) and v.lower()==d for v in values(ent,'P356')),main_subject_qids='|'.join(v['id'] for v in values(ent,'P921') if isinstance(v,dict) and 'id'in v),cites_original_work_qids='|'.join(v['id'] for v in values(ent,'P2860') if isinstance(v,dict) and v.get('id') in matches[p['original_doi']]),discovery_retrieved_at=record['retrieved_at']))
    with (out/'reconciliation.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    (out/'summary.json').write_text(json.dumps(dict(sample_articles=len(selected),unique_dois=len(dois),matched_dois=sum(bool(v) for v in matches.values()),duplicate_doi_items=sum(len(v)>1 for v in matches.values()),read_only=True,incremental_metered_api_cost_usd=0,limitations=['Both main and scholarly WDQS graphs queried for exact upper/lowercase P356 values; mixed-case values and missing/deprecated statements may be missed.','Labels require human bibliographic verification; DOI identity alone does not adjudicate provenance or study scope.','Article QIDs identify topics, not necessarily the cited papers.','P2860 records citations, not replication outcomes or article acknowledgement.','P921 values are supplied metadata, not an inferred replication relation.','Article pageprops retrieved now; audited article wikitext has the separately recorded frozen revision.']),indent=2)+'\n')
    return rows
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--packets',required=True,type=pathlib.Path);p.add_argument('--output',required=True,type=pathlib.Path);p.add_argument('--offline',action='store_true');p.add_argument('--limit',type=int,default=4);a=p.parse_args()
    if not 1<=a.limit<=10:p.error('Use a small sample of 1–10 articles')
    print(f'{len(reconcile(json.loads(a.packets.read_text()),a.output,a.offline,a.limit))} read-only reconciliation rows')
