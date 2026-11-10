import importlib.util,json,pathlib,tempfile,unittest,unittest.mock,urllib.parse
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('wd',ROOT/'scripts/reconcile_wikidata.py');wd=importlib.util.module_from_spec(spec);spec.loader.exec_module(wd)
class WikidataTests(unittest.TestCase):
 def test_graph_split_duplicate_and_topic_identity(self):
  calls=[]
  def fixture(url,cache,offline=False):
   calls.append(url)
   if '/sparql?' in url:
    qid='Q1' if 'query.wikidata.org' in url else 'Q2'
    body={'results':{'bindings':[{'doi':{'value':'10.1/A'},'work':{'value':'http://www.wikidata.org/entity/'+qid}}]}}
   elif 'wbgetentities' in url:
    body={'entities':{q:{'labels':{'en':{'value':'A paper'}},'claims':{'P356':[{'mainsnak':{'datavalue':{'value':'10.1/a'}}}]}} for q in ['Q1','Q2']}}
   else:body={'query':{'pages':{'8':{'pageprops':{'wikibase_item':'Q999'}}}}}
   return {'body':body,'retrieved_at':'fixture'}
  packet={'page_title':'Ejemplo','pageid':'8','language':'es','revision_id':'123','original_doi':'10.1/a','pairs':[{'doi_r_norm':'10.1/b'}]}
  with tempfile.TemporaryDirectory() as td,unittest.mock.patch.object(wd,'get_json',fixture):
   rows=wd.reconcile([packet],pathlib.Path(td),True,1)
   originals=[r for r in rows if r['role']=='original'];self.assertEqual(len(originals),2)
   self.assertTrue(all(r['match_status']=='multiple_items' and r['doi_verified'] for r in originals))
   self.assertTrue(all(r['article_qid']=='Q999' for r in rows));self.assertEqual(rows[-1]['match_status'],'no_exact_case_variant_match')
   self.assertTrue(any('query-scholarly.wikidata.org' in u for u in calls));self.assertTrue(any('query.wikidata.org' in u for u in calls))
 def test_uncached_offline_request_is_not_negative(self):
  with tempfile.TemporaryDirectory() as td:
   with self.assertRaisesRegex(RuntimeError,'Uncached'):wd.get_json('https://example.invalid/',pathlib.Path(td),True)
if __name__=='__main__':unittest.main()
