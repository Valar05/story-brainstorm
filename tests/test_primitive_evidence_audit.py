import json,tempfile,unittest
from pathlib import Path
import importlib.util
from unittest.mock import patch
s=importlib.util.spec_from_file_location("a",Path("tools/audit_primitive_evidence.py")); m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class EvidenceAuditTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory(); self.d=Path(self.t.name); self.cache=self.d/"cache"; self.cache.mkdir(); (self.cache/"11.txt").write_text("*** START OF THE PROJECT GUTENBERG EBOOK ALICE ***\nCHAPTER I\nAlice was beginning to get very tired of sitting by her sister on the bank.\n*** END OF THE PROJECT GUTENBERG EBOOK ALICE ***\n")
  self.w=self.d/"w.json";self.w.write_text(json.dumps({"works":[{"work_id":"w1","source_edition":{"url":"https://www.gutenberg.org/ebooks/11"}}]})); self.c=self.d/"c.json";self.o=self.d/"o.json"
 def tearDown(self):self.t.cleanup()
 def do(self,evidence):self.c.write_text(json.dumps({"cards":[{"evidence":evidence}]}));return m.audit(self.w,self.c,self.cache,self.o)
 def ev(self,**kw):
  x={"work_id":"w1","edition_url":"https://www.gutenberg.org/ebooks/11","location":"Chapter 1","short_excerpt":"Alice was beginning to get very tired","excerpt_words":7};x.update(kw);return x
 def test_exact_pass_and_noop(self):
  r=self.do([self.ev()]);self.assertEqual(r["state"],"READY"); before=self.o.read_bytes();r=m.audit(self.w,self.c,self.cache,self.o);self.assertEqual(before,self.o.read_bytes());self.assertEqual(r["state"],"READY")
 def test_changed_word(self):
  r=self.do([self.ev(short_excerpt="Alice was beginning purple",excerpt_words=4)]);self.assertEqual(r["state"],"NOT_READY");self.assertIn("excerpt not found in source",r["rows"][0]["errors"])
 def test_unknown_work(self):self.assertEqual(self.do([self.ev(work_id="bad")])["state"],"NOT_READY")
 def test_wrong_edition(self):self.assertEqual(self.do([self.ev(edition_url="https://www.gutenberg.org/ebooks/12")])["state"],"NOT_READY")
 def test_count_mismatch(self):self.assertEqual(self.do([self.ev(excerpt_words=8)])["state"],"NOT_READY")
 def test_over_25(self):self.assertEqual(self.do([self.ev(short_excerpt=" ".join(["Alice"]*26),excerpt_words=26)])["state"],"NOT_READY")
 def test_vague_location(self):self.assertEqual(self.do([self.ev(location="chapter")])["state"],"NOT_READY")
 def test_duplicate(self):self.assertEqual(self.do([self.ev(),self.ev()])["state"],"NOT_READY")
 def test_no_evidence(self):self.assertEqual(self.do([])["state"],"NOT_READY")
 def test_missing_source(self):self.assertEqual(self.do([self.ev(edition_url="https://www.gutenberg.org/ebooks/999")])["state"],"NOT_READY")
 def test_fetch_retries_then_caches(self):
  (self.cache/"11.txt").unlink()
  good=b"*** START OF THE PROJECT GUTENBERG EBOOK ALICE ***\nCHAPTER I\nAlice was beginning to get very tired of sitting by her sister on the bank.\n*** END OF THE PROJECT GUTENBERG EBOOK ALICE ***\n"
  class R:
   def read(self): return good
  with patch.object(m.urllib.request,"urlopen",side_effect=[OSError("temporary"),R()]):
   text,source=m.load_text("11",self.cache,True)
  self.assertEqual(source,"live");self.assertEqual(text.count("Alice"),1);self.assertTrue((self.cache/"11.txt").exists())
 def test_malformed_cache(self): (self.cache/"11.txt").write_bytes(b"\xff");self.assertEqual(self.do([self.ev()])["state"],"NOT_READY")
 def test_cache_inside_repo_rejected(self):
  target=Path(__file__).resolve().parents[1]/"tests"/"fixtures"/"cache_guard_target";target.mkdir(exist_ok=True)
  with patch.object(m,"load_text",side_effect=AssertionError("must not call")):
   r=m.audit(self.w,self.c,target,self.o,live=True)
  self.assertEqual(r["state"],"NOT_READY");self.assertEqual(list(target.glob("*.txt")),[])

if __name__=="__main__":unittest.main()
