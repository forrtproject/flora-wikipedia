#!/usr/bin/env python3
"""Select a deterministic mixed review set; no inferential centrality labels."""
import argparse,hashlib,json,pathlib
p=argparse.ArgumentParser();p.add_argument('--packets',required=True,type=pathlib.Path);p.add_argument('--output',required=True,type=pathlib.Path);p.add_argument('--count',type=int,default=20);a=p.parse_args()
packets=json.loads(a.packets.read_text());strata={}
for packet in packets:
 both=any(r['assessment'].startswith('Both DOI') for r in packet['pairs'])
 strata.setdefault((packet['language'],both),[]).append(packet)
for items in strata.values():items.sort(key=lambda r:hashlib.sha256(r['packet_id'].encode()).hexdigest())
chosen=[]
while len(chosen)<a.count and any(strata.values()):
 for key in sorted(strata):
  if strata[key] and len(chosen)<a.count:chosen.append(strata[key].pop(0))
a.output.parent.mkdir(parents=True,exist_ok=True)
a.output.write_text(json.dumps(dict(packets=chosen,selection='Deterministic round-robin across language and DOI co-presence; not based on outcomes or presumed scope. Human reviewers classify scope and role independently.',agreement_status='Not yet measured; independent reviewer decisions must be collected and reported before day-two release.',requested=a.count,selected=len(chosen)),ensure_ascii=False,indent=2)+'\n')
print(f'{len(chosen)} calibration packets selected; no reviewer agreement invented')
