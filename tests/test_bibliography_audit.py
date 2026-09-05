import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tools.audit_bibliography import audit
FIX=Path(__file__).parent/'fixtures/catalog'
PUB=Path(__file__).parent/'fixtures/publication_catalog'
class T(unittest.TestCase):
 def rec(self,**kw):
  x={"work_id":"w1","title":"Alpha","author":"Doe, Jane","first_publication_year":1920,"first_publication_evidence_url":"https://openlibrary.org/works/OL1W","source_edition":{"item_id":"1","url":"https://www.gutenberg.org/ebooks/1","language":"en","raw_title":"Alpha","raw_creator":"Doe, Jane"},"rights":{"status":"PD_US_CONFIRMED","jurisdiction":"US","basis":"old","verification_refs":["https://copyright.gov"]}};x.update(kw);return {"schema_version":"1","accepted_works":[x],"reserves":[]}
 def evaluate(self,x):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'s.json';p.write_text(json.dumps(x));return audit(p,FIX,False,PUB)
 def test_valid_native(self):self.assertEqual(self.evaluate(self.rec())['pass'],1)
 def test_wrong_id_title(self):self.assertEqual(self.evaluate(self.rec(source_edition={"item_id":"2","url":"https://www.gutenberg.org/ebooks/2","language":"en","raw_title":"Alpha","raw_creator":"Doe, Jane"}))['fail'],1)
 def test_wrong_language_catalog_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'s.json'; x=self.rec(title='Beta',source_edition={"item_id":"2","url":"https://www.gutenberg.org/ebooks/2","language":"en","raw_title":"Beta","raw_creator":"Doe, Jane"});p.write_text(json.dumps(x));self.assertEqual(audit(p,FIX)['fail'],1)
 def test_query_rejected(self):self.assertEqual(self.evaluate(self.rec(first_publication_evidence_url='https://loc.gov/books/?q=Alpha'))['fail'],1)
 def test_root_rejected(self):self.assertEqual(self.evaluate(self.rec(first_publication_evidence_url='https://loc.gov/'))['fail'],1)
 def test_unknown_rights(self):self.assertEqual(self.evaluate(self.rec(rights={"status":"UNKNOWN","jurisdiction":"US","basis":"x","verification_refs":["x"]}))['fail'],1)
 def test_post_year(self):self.assertEqual(self.evaluate(self.rec(first_publication_year=1930))['fail'],1)
 def test_duplicate(self):
  x=self.rec();x['reserves']=[dict(x['accepted_works'][0])];self.assertEqual(self.evaluate(x)['fail'],1)
 def test_missing_translation(self):
  e=dict(self.rec()['accepted_works'][0]);e['source_edition']=dict(e['source_edition'],translation_required=True);self.assertEqual(self.evaluate({"accepted_works":[e],"reserves":[]})['fail'],1)

 def test_stored_raw_title_creator_mismatch_rejected(self):
  e=dict(self.rec()['accepted_works'][0]);e['source_edition']=dict(e['source_edition'],raw_title='Wrong',raw_creator='Wrong');self.assertEqual(self.evaluate({'accepted_works':[e],'reserves':[]})['fail'],1)
 def test_historical_translation_passes(self):
  e=dict(self.rec()['accepted_works'][0]);e['source_edition']=dict(e['source_edition'],translation_required=True,translator='Translator Name',translation_rights_status='PD_US_CONFIRMED');self.assertEqual(self.evaluate({'accepted_works':[e],'reserves':[]})['pass'],1)
 def test_duplicate_row_fails(self):
  e=self.rec();e['reserves']=[dict(e['accepted_works'][0])];self.assertEqual(self.evaluate(e)['fail'],1)
 def test_cli_output_mtime_noop(self):
  import subprocess,time
  with tempfile.TemporaryDirectory() as d:
   shard=Path(d)/'s.json';out=Path(d)/'o.json';shard.write_text(json.dumps(self.rec()));cmd=['python','tools/audit_bibliography.py','--shard',str(shard),'--out',str(out),'--rdf-cache',str(FIX),'--evidence-cache',str(PUB)];subprocess.run(cmd,check=False);t=out.stat().st_mtime_ns;time.sleep(.01);subprocess.run(cmd,check=False);self.assertEqual(t,out.stat().st_mtime_ns)

 def test_deterministic(self):self.assertEqual(self.evaluate(self.rec()),self.evaluate(self.rec()))
 def test_title_mismatch_publication(self):
  e=self.rec(title='Wrong');self.assertEqual(self.evaluate(e)['fail'],1)
 def test_year_mismatch_publication(self):
  e=self.rec(first_publication_year=1921);self.assertEqual(self.evaluate(e)['fail'],1)
 def test_missing_publication_date(self):
  self.assertEqual(self.evaluate(self.rec(first_publication_evidence_url='https://openlibrary.org/works/OL404W'))['fail'],1)
 def test_exact_key_search_fallback(self):
  result=self.evaluate(self.rec(first_publication_year=1920,first_publication_evidence_url='https://openlibrary.org/works/OL2W'))
  self.assertEqual(result['pass'],1);self.assertEqual(result['rows'][0]['publication_catalog']['date_source'],'exact_key_search')
 def test_exact_key_search_claimed_after_rejected(self):
  self.assertEqual(self.evaluate(self.rec(first_publication_year=1926,first_publication_evidence_url='https://openlibrary.org/works/OL2W'))['fail'],1)
 def test_ambiguous_exact_key_search_rejected(self):
  self.assertEqual(self.evaluate(self.rec(first_publication_evidence_url='https://openlibrary.org/works/OL3W'))['fail'],1)
 def test_edition_subtitle_matches_anchored_work_title(self):
  self.assertEqual(self.evaluate(self.rec(title='Kwaidan: Stories and Studies of Strange Things',first_publication_year=1899,first_publication_evidence_url='https://openlibrary.org/works/OL4W',source_edition={'item_id':'1','url':'https://www.gutenberg.org/ebooks/1','language':'en','raw_title':'Alpha','raw_creator':'Doe, Jane'}))['fail'],1)
  from tools.audit_bibliography import evidence
  self.assertTrue(evidence('https://openlibrary.org/works/OL4W','Kwaidan: Stories and Studies of Strange Things',1899,PUB)['checks']['title_match'])
  self.assertFalse(evidence('https://openlibrary.org/works/OL4W','Kwaito Music',1899,PUB)['checks']['title_match'])
 def test_live_evidence_cache_resumes_offline(self):
  from tools.audit_bibliography import evidence
  work={'key':'/works/OL9W','title':'Alpha'};search={'numFound':1,'docs':[{'key':'/works/OL9W','title':'Alpha','first_publish_year':1920}]}
  with tempfile.TemporaryDirectory() as d:
   cache=Path(d)
   with patch('tools.audit_bibliography.fetch_json',side_effect=[work,search]) as fetch:
    self.assertIsNone(evidence('https://openlibrary.org/works/OL9W','Alpha',1919,cache,True)['error']);self.assertEqual(fetch.call_count,2)
   with patch('tools.audit_bibliography.fetch_json',side_effect=AssertionError('network used')):
    self.assertIsNone(evidence('https://openlibrary.org/works/OL9W','Alpha',1919,cache,False)['error'])
 def test_malformed_live_cache_is_recovered(self):
  from tools.audit_bibliography import evidence
  work={'key':'/works/OL9W','title':'Alpha'};search={'numFound':1,'docs':[{'key':'/works/OL9W','title':'Alpha','first_publish_year':1920}]}
  with tempfile.TemporaryDirectory() as d:
   cache=Path(d);(cache/'OL9W.json').write_text('{bad');(cache/'OL9W.search.json').write_text('{bad')
   with patch('tools.audit_bibliography.fetch_json',side_effect=[work,search]):self.assertIsNone(evidence('https://openlibrary.org/works/OL9W','Alpha',1919,cache,True)['error'])
   json.loads((cache/'OL9W.json').read_text());json.loads((cache/'OL9W.search.json').read_text())
if __name__=='__main__':unittest.main()
