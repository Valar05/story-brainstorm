import json,tempfile,unittest
from pathlib import Path
from tools.audit_bibliography import audit
FIX=Path(__file__).parent/'fixtures/catalog'
class T(unittest.TestCase):
 def rec(self,**kw):
  x={"work_id":"w1","title":"Alpha","author":"Doe, Jane","first_publication_year":1920,"first_publication_evidence_url":"https://loc.gov/item/abc/","source_edition":{"item_id":"1","url":"https://www.gutenberg.org/ebooks/1","language":"en","raw_title":"Alpha","raw_creator":"Doe, Jane"},"rights":{"status":"PD_US_CONFIRMED","jurisdiction":"US","basis":"old","verification_refs":["https://copyright.gov"]}};x.update(kw);return {"schema_version":"1","accepted_works":[x],"reserves":[]}
 def evaluate(self,x):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'s.json';p.write_text(json.dumps(x));return audit(p,FIX)
 def test_valid_native(self):self.assertEqual(self.evaluate(self.rec())['pass'],1)
 def test_wrong_id_title(self):self.assertEqual(self.evaluate(self.rec(source_edition={"item_id":"2","url":"https://www.gutenberg.org/ebooks/2","language":"en","raw_title":"Alpha","raw_creator":"Doe, Jane"}))['fail'],1)
 def test_subject_language(self):self.assertEqual(self.evaluate(self.rec(source_edition={"item_id":"1","url":"https://www.gutenberg.org/ebooks/1","language":"en","raw_title":"Alpha","raw_creator":"Doe, Jane"}))['pass'],1)
 def test_query_rejected(self):self.assertEqual(self.evaluate(self.rec(first_publication_evidence_url='https://loc.gov/books/?q=Alpha'))['fail'],1)
 def test_root_rejected(self):self.assertEqual(self.evaluate(self.rec(first_publication_evidence_url='https://loc.gov/'))['fail'],1)
 def test_unknown_rights(self):self.assertEqual(self.evaluate(self.rec(rights={"status":"UNKNOWN","jurisdiction":"US","basis":"x","verification_refs":["x"]}))['fail'],1)
 def test_post_year(self):self.assertEqual(self.evaluate(self.rec(first_publication_year=1930))['fail'],1)
 def test_duplicate(self):
  x=self.rec();x['reserves']=[dict(x['accepted_works'][0])];self.assertEqual(self.evaluate(x)['fail'],1)
 def test_missing_translation(self):
  e=dict(self.rec()['accepted_works'][0]);e['source_edition']=dict(e['source_edition'],translation_required=True);self.assertEqual(self.evaluate({"accepted_works":[e],"reserves":[]})['fail'],1)
 def test_deterministic(self):self.assertEqual(self.evaluate(self.rec()),self.evaluate(self.rec()))
if __name__=='__main__':unittest.main()
