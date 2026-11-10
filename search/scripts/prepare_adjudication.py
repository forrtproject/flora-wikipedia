#!/usr/bin/env python3
"""Offline claim-review queue; never generates prose or writes to Wikimedia.
One packet per article–original, with all supplied pairs (not failure-ranked).
Decisions are kept separately; drops filter the active queue, never the evidence.
"""
import argparse, csv, hashlib, json, pathlib
SCOPES={'unreviewed','paper','effect','effect_section','broad_topic','biography_history','incidental'}
ROLES={'unreviewed','current_empirical_support','historical_attribution','example','unclear'}
DECISIONS={'unreviewed','retain','drop','defer'}
ACTIONS={'unreviewed','no_change','contextualise','narrow_claim','replace_source','remove_unsupported_claim','remove_citation','talk_request','wikidata_only'}
FIELDS=['packet_id','reviewed_revision_id','article_scope','citation_function','claim_quote','specific_study_match','queue_decision','reason','proposed_action','supporting_sources','source_quote','due_weight_note','coi_flag','second_review','review_notes']
def rows(path):
    with path.open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
def write(path, records, fields):
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(records)
def prepare(runs,out,decisions=None):
    grouped={}
    for run in runs:
        manifest=json.loads((run/'output/manifest.json').read_text())
        if manifest['status']!='complete': raise ValueError('Incomplete audit cannot form a queue')
        context_path=run/'output/citation_contexts.csv'
        contexts=rows(context_path) if context_path.exists() else []
        for row in rows(run/'output/adjudication_pairs.csv'):
            key=(row['lang'],row['pageid'],row['doi_o_norm'])
            packet=grouped.setdefault(key,dict(packet_id=hashlib.sha256('|'.join(key).encode()).hexdigest()[:20],language=key[0],pageid=key[1],page_title=row['page_title'],original_doi=key[2],original_title=row['title_o'],revision_url=row['revision_url'],revision_id=row['revid'],revision_timestamp=row['revision_timestamp'],retrieved_at=row['retrieved_at'],audit_run=str(run),raw_contexts=[{k:c[k] for k in ['doi','doi_role','match_pos','section','ref_block','paragraph']} for c in contexts if c['lang']==key[0] and c['pageid']==key[1] and c['pair_doi_o']==key[2]],pairs=[]))
            packet['pairs'].append({k:row[k] for k in ['pair_id','doi_r_norm','title_r','outcome','assessment','source']})
    for packet in grouped.values():
        packet['raw_contexts']=list({(c['doi'],c['match_pos'],c['doi_role']):c for c in packet['raw_contexts']}.values())
    packets=sorted(grouped.values(),key=lambda x:(x['language'],x['page_title'].casefold(),x['original_doi']))
    ledger={}
    if decisions is None and (out/'decisions.csv').exists(): decisions=out/'decisions.csv'
    if decisions:
        for row in rows(decisions):
            if row['packet_id'] in ledger: raise ValueError('Duplicate decision packet ID')
            for field,valid in [('article_scope',SCOPES),('citation_function',ROLES),('queue_decision',DECISIONS),('proposed_action',ACTIONS)]:
                if row[field] not in valid: raise ValueError('Invalid '+field)
            if row['queue_decision']!='unreviewed' and not row['reason'].strip(): raise ValueError('Decision requires a reason')
            ledger[row['packet_id']]=row
        if set(ledger)-{p['packet_id'] for p in packets}: raise ValueError('Decision refers to unknown packet')
    for packet in packets:
        default={f:'' for f in FIELDS};default.update(packet_id=packet['packet_id'],reviewed_revision_id=packet['revision_id'],article_scope='unreviewed',citation_function='unreviewed',queue_decision='unreviewed',proposed_action='unreviewed')
        recorded=ledger.get(packet['packet_id'])
        if recorded and recorded['queue_decision']!='unreviewed' and recorded.get('reviewed_revision_id')!=packet['revision_id']: raise ValueError('Decision revision differs; re-review refreshed packet before reusing decisions')
        packet['review']={**default,**(recorded or {})}
        if packet['review']['queue_decision']=='unreviewed': packet['review']['reviewed_revision_id']=packet['revision_id']
        if packet['review']['queue_decision']=='retain' and any(p['source'].upper() in {'COS','SCORE','OSC','MANY LABS'} or any(t in p['title_r'].casefold() for t in ['many labs','reproducibility of psychological science']) for p in packet['pairs']) and not packet['review']['specific_study_match'].strip(): raise ValueError('Large-project retain decision requires a specific study match')
        packet['review_prompt']='Historical attribution that supports a current empirical claim must be reviewed as current support. Verify specific study identity, DOI-free coverage, secondary sources and due weight. wikidata_only means a read-only reconciliation queue.'
    out.mkdir(parents=True,exist_ok=True)
    # Audits and contexts remain in their original namespaces, untouched.
    (out/'packets.json').write_text(json.dumps(packets,ensure_ascii=False,indent=2)+'\n')
    write(out/'decisions.csv',[p['review'] for p in packets],FIELDS)
    active=[p for p in packets if p['review']['queue_decision'] not in {'drop','defer'}]
    (out/'active-packets.json').write_text(json.dumps(active,ensure_ascii=False,indent=2)+'\n')
    (out/'queue-summary.json').write_text(json.dumps(dict(packets=len(packets),active=len(active),decisions={d:sum(p['review']['queue_decision']==d for p in packets) for d in sorted(DECISIONS)},incremental_metered_api_cost_usd=0),indent=2)+'\n')
    return packets
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run-dir',action='append',required=True,type=pathlib.Path);p.add_argument('--output',required=True,type=pathlib.Path);p.add_argument('--decisions',type=pathlib.Path);a=p.parse_args()
    if a.output.resolve() in {r.resolve() for r in a.run_dir} or any(a.output.resolve().is_relative_to(r.resolve()) for r in a.run_dir): p.error('Keep review decisions outside frozen run namespaces')
    print(f'{len(prepare(a.run_dir,a.output,a.decisions))} packets retained in evidence ledger')
