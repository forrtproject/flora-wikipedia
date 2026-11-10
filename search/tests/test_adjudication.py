import csv,importlib.util,json,pathlib,tempfile,unittest
root=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('queue',root/'scripts/prepare_adjudication.py');q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)
class QueueTests(unittest.TestCase):
 def test_drop_retains_evidence_and_requires_reason(self):
  with tempfile.TemporaryDirectory() as td:
   out=pathlib.Path(td)/'queue'; packets=q.prepare([root/'runs/spanish-full-latest/es'],out)
   self.assertTrue(any('Penalización' in p['page_title'] for p in packets))
   self.assertTrue(any(c['paragraph'] for p in packets for c in p['raw_contexts']))
   self.assertTrue(all(p['review']['queue_decision']=='unreviewed' for p in packets))
   self.assertEqual(sum(len(p['pairs']) for p in packets),len(q.rows(root/'runs/spanish-full-latest/es/output/adjudication_pairs.csv')))
   ledger=q.rows(out/'decisions.csv');ledger[0]['queue_decision']='drop'
   q.write(out/'decisions.csv',ledger,q.FIELDS)
   with self.assertRaisesRegex(ValueError,'reason'): q.prepare([root/'runs/spanish-full-latest/es'],out,out/'decisions.csv')
   ledger[0]['reason']='Historical attribution; no current claim requiring change'
   q.write(out/'decisions.csv',ledger,q.FIELDS)
   again=q.prepare([root/'runs/spanish-full-latest/es'],out,out/'decisions.csv')
   self.assertEqual(len(again),len(packets));self.assertEqual(len(json.loads((out/'active-packets.json').read_text())),len(packets)-1)
   self.assertEqual(again[0]['pairs'],packets[0]['pairs'])
   self.assertEqual(q.prepare([root/'runs/spanish-full-latest/es'],out)[0]['review']['queue_decision'],'drop')
   ledger=q.rows(out/'decisions.csv');ledger[0]['reviewed_revision_id']='obsolete';q.write(out/'decisions.csv',ledger,q.FIELDS)
   with self.assertRaisesRegex(ValueError,'revision differs'):q.prepare([root/'runs/spanish-full-latest/es'],out)
 def test_large_project_retain_requires_specific_match(self):
  with tempfile.TemporaryDirectory() as td:
   run=pathlib.Path(td)/'run'; (run/'output').mkdir(parents=True)
   (run/'output/manifest.json').write_text('{"status":"complete"}')
   fields=['lang','pageid','doi_o_norm','page_title','title_o','revision_url','revid','revision_timestamp','retrieved_at','pair_id','doi_r_norm','title_r','outcome','assessment','source']
   r={k:'' for k in fields};r.update(lang='es',pageid='1',doi_o_norm='10.1/a',page_title='Ejemplo',source='SCORE')
   q.write(run/'output/adjudication_pairs.csv',[r],fields)
   out=pathlib.Path(td)/'review';p=q.prepare([run],out)[0];d=p['review'];d.update(queue_decision='retain',reason='Relevant current claim')
   q.write(out/'decisions.csv',[d],q.FIELDS)
   with self.assertRaisesRegex(ValueError,'specific study'):q.prepare([run],out,out/'decisions.csv')
   d['specific_study_match']='Verified exact study and claim scope';q.write(out/'decisions.csv',[d],q.FIELDS)
   self.assertEqual(q.prepare([run],out,out/'decisions.csv')[0]['review']['queue_decision'],'retain')
 def test_legacy_generator_is_retired(self):
  import subprocess
  result=subprocess.run(['Rscript',str(root/'R/09_recommendations.R')],capture_output=True,text=True)
  self.assertNotEqual(result.returncode,0);self.assertIn('retired',result.stderr)
if __name__=='__main__': unittest.main()
