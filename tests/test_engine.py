import json, tempfile, unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from story_brainstorm import primitive_id, stable_hash, validate_cards, validate_works, receipt_validate
class EngineTests(unittest.TestCase):
 def test_hash_changes_with_evidence_and_ignores_time(self):
  c={"family":"speech","name":"x","observation":"o","inference":"i","evidence":[{"work_id":"w","edition_url":"https://x","location":"p.1","short_excerpt":"small","excerpt_words":1}],"confidence":"accepted","rights_basis":"PD_US_CONFIRMED","generated_at":"a"}
  self.assertEqual(stable_hash(c),stable_hash({**c,"generated_at":"b"}))
  self.assertNotEqual(primitive_id(c),primitive_id({**c,"evidence":[{**c["evidence"][0],"location":"p.2"}]}))
 def test_digital_edition_rules(self):
  base={"work_id":"native","title":"T","author":"A","first_publication_year":1920,"first_publication_evidence_url":"https://catalog.example/work","source_edition":{"item_id":"item-1","url":"https://archive.example/item-1","language":"en","raw_title":"T","raw_creator":"A","digital_release_date":"2020-01-01"},"rights":{"status":"PD_US_CONFIRMED","jurisdiction":"US","basis":"item status","verification_refs":["catalog"]}}
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"works.json"
   p.write_text(json.dumps({"works":[base]})); self.assertEqual(validate_works(p,required=1)["state"],"READY")
   for bad in ({**base,"first_publication_year":1930},{**base,"rights":{"status":"UNKNOWN"}}, {**base,"source_edition":{**base["source_edition"],"item_id":""}}, {**base,"source_edition":{**base["source_edition"],"translator":"Unknown"}}):
    p.write_text(json.dumps({"works":[bad]})); self.assertEqual(validate_works(p,required=1)["state"],"NOT_READY")

 def test_missing_location_rejected(self):
  c={"primitive_id":"sha256:"+"0"*64,"family":"speech","observation":"o","inference":"i","confidence":"accepted","evidence":[{"work_id":"w","edition_url":"https://x","short_excerpt":"x","excerpt_words":1}]}
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"cards.json"; p.write_text(json.dumps({"cards":[c]})); self.assertEqual(validate_cards(p,required=1,quotas={"speech":1})["state"],"NOT_READY")
if __name__=="__main__": unittest.main()
