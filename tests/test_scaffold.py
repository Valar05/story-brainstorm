import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from story_brainstorm import atomic_write,stable_hash,validate_works,validate_cards
class ScaffoldTests(unittest.TestCase):
 def test_empty_data_is_honestly_not_ready(self):
  with tempfile.TemporaryDirectory() as d:
   works=Path(d)/'works.json';cards=Path(d)/'cards.json'
   works.write_text(json.dumps({'works':[]}));cards.write_text(json.dumps({'cards':[]}))
   self.assertEqual(validate_works(works)['state'],'NOT_READY'); self.assertEqual(validate_cards(cards)['state'],'NOT_READY')
 def test_candidate_rights_fail_closed(self):
  import tempfile
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'works.json'; p.write_text(json.dumps({'works':[{'work_id':'candidate_work','title':'T','author':'A','publication_year':1920,'source_edition':{'edition_year':1920,'url':'https://example.test/t','locator':'p.1'},'rights':{'status':'PUBLIC_DOMAIN_CANDIDATE','jurisdiction':'US','basis':'old','verification_refs':['ref']}}]}))
   self.assertEqual(validate_works(p)['state'],'NOT_READY')

 def test_timestamps_excluded(self):
  self.assertEqual(stable_hash({'x':1,'generated_at':'a'}),stable_hash({'x':1,'generated_at':'b'}))
 def test_atomic_write_noop(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x'; self.assertTrue(atomic_write(p,'a')); self.assertFalse(atomic_write(p,'a')); self.assertTrue(atomic_write(p,'b'))
 def test_doc_path_boundary(self):
  from tools.doc_server import safe_path
  with self.assertRaises((FileNotFoundError,ValueError)): safe_path('/../README.md')
if __name__=='__main__': unittest.main()
