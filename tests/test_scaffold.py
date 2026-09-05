import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from story_brainstorm import atomic_write,stable_hash,validate_works,validate_cards
class ScaffoldTests(unittest.TestCase):
 def test_empty_data_is_honestly_not_ready(self):
  self.assertEqual(validate_works()['state'],'NOT_READY'); self.assertEqual(validate_cards()['state'],'NOT_READY')
 def test_timestamps_excluded(self):
  self.assertEqual(stable_hash({'x':1,'generated_at':'a'}),stable_hash({'x':1,'generated_at':'b'}))
 def test_atomic_write_noop(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x'; self.assertTrue(atomic_write(p,'a')); self.assertFalse(atomic_write(p,'a')); self.assertTrue(atomic_write(p,'b'))
 def test_doc_path_boundary(self):
  from tools.doc_server import safe_path
  with self.assertRaises((FileNotFoundError,ValueError)): safe_path('/../README.md')
if __name__=='__main__': unittest.main()
