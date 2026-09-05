import json, tempfile, unittest
from pathlib import Path
from tools.audit_bibliography import audit
class AuditTests(unittest.TestCase):
 def base(self,**kw):
  x={"work_id":"w1","title":"Alpha","author":"Doe, Jane","first_publication_year":1920,"first_publication_evidence_url":"https://example.org/catalog/w1","source_edition":{"item_id":"1","url":"https://www.gutenberg.org/ebooks/1","language":"en","raw_title":"Alpha","raw_creator":"Doe, Jane"},"rights":{"status":"PD_US_CONFIRMED","jurisdiction":"US","basis":"published before 1931","verification_refs":["https://www.copyright.gov/circs/circ15a.pdf"]}};x.update(kw);return {"schema_version":"1.0","works":[x],"reserves":[]}
 def test_search_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"s.json";p.write_text(json.dumps(self.base(first_publication_evidence_url="https://loc.gov/books/?q=Alpha")));self.assertEqual(audit(p)["fail"],1)
 def test_missing_item_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"s.json";p.write_text(json.dumps(self.base(source_edition={"url":"https://www.gutenberg.org/ebooks/1","language":"en","raw_title":"Alpha","raw_creator":"Doe"})));self.assertEqual(audit(p)["fail"],1)
if __name__=="__main__":unittest.main()
