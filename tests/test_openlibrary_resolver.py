import json,tempfile,unittest,hashlib,urllib.parse
from pathlib import Path
from tools.resolve_openlibrary import resolve_row,cache_key
class ResolverTests(unittest.TestCase):
 def row(self,**k):
  x={'work_id':'w1','title':'Alpha','author':'Doe, Jane','first_publication_year':1920};x.update(k);return x
 def put(self,row,docs):
  d=Path(tempfile.mkdtemp());q=cache_key(row['work_id'],row['title'],row['author']);(d/(q+'.json')).write_text(json.dumps({'numFound':len(docs),'docs':docs}));return d
 def test_unique(self):
  r=self.row();d=self.put(r,[{'key':'/works/OL1W','title':'Alpha','author_name':['Doe, Jane'],'first_publish_year':1920}]);self.assertEqual(resolve_row(r,d,False)['status'],'RESOLVED')
 def test_surname_order(self):
  r=self.row(author='Jane Doe');d=self.put(r,[{'key':'/works/OL1W','title':'Alpha','author_name':['Doe, Jane'],'first_publish_year':1920}]);self.assertEqual(resolve_row(r,d,False)['status'],'RESOLVED')
 def test_author_mismatch(self):
  r=self.row();d=self.put(r,[{'key':'/works/OL1W','title':'Alpha','author_name':['Other'],'first_publish_year':1920}]);self.assertEqual(resolve_row(r,d,False)['status'],'REVIEW_REQUIRED')
 def test_title_mismatch(self):
  r=self.row();d=self.put(r,[{'key':'/works/OL1W','title':'Beta','author_name':['Doe, Jane'],'first_publish_year':1920}]);self.assertEqual(resolve_row(r,d,False)['status'],'REVIEW_REQUIRED')
 def test_year_boundaries(self):
  r=self.row();d=self.put(r,[{'key':'/works/OL1W','title':'Alpha','author_name':['Doe, Jane'],'first_publish_year':1930}]);self.assertEqual(resolve_row(r,d,False)['status'],'REVIEW_REQUIRED');r['first_publication_year']=1921;d=self.put(r,[{'key':'/works/OL1W','title':'Alpha','author_name':['Doe, Jane'],'first_publish_year':1920}]);self.assertEqual(resolve_row(r,d,False)['status'],'REVIEW_REQUIRED')
 def test_multiple_zero(self):
  r=self.row();d=self.put(r,[{'key':'/works/OL1W','title':'Alpha','author_name':['Doe, Jane'],'first_publish_year':1920},{'key':'/works/OL2W','title':'Alpha','author_name':['Doe, Jane'],'first_publish_year':1920}]);self.assertEqual(resolve_row(r,d,False)['status'],'REVIEW_REQUIRED')
 def test_cache_miss(self):self.assertEqual(resolve_row(self.row(),Path(tempfile.mkdtemp()),False)['status'],'BLOCKED')
 def test_unsafe_work_id_stays_in_cache(self):
  d=Path(tempfile.mkdtemp());r=self.row(work_id='../../escape');self.assertEqual(resolve_row(r,d,False)['status'],'BLOCKED');self.assertEqual(list(d.rglob('*')),[])
 def test_atomic_noop(self):
  import time
  from tools.resolve_openlibrary import atomic
  d=Path(tempfile.mkdtemp())/'out.json';self.assertTrue(atomic(d,{'x':1}));t=d.stat().st_mtime_ns;time.sleep(.01);self.assertFalse(atomic(d,{'x':1}));self.assertEqual(t,d.stat().st_mtime_ns)

if __name__=='__main__':unittest.main()
