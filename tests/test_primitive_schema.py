import json,unittest
from pathlib import Path
try: import jsonschema
except ImportError: raise RuntimeError('jsonschema is required for primitive schema tests')
from story_brainstorm import primitive_id
S=json.loads(Path('schemas/primitive_card.json').read_text());E=json.loads(Path('schemas/evidence_ref.json').read_text())
def card(f='story'):
 x={'primitive_id':'sha256:'+'a'*64,'family':f,'name':'n','summary':'s','observation':'o','inference':'i','pattern':{'setup':'a','pressure':'b','turn':'c','residue':'d'},'evidence':[{'work_id':'w','edition_url':'https://x/item/1','location':'p.1','short_excerpt':'short','excerpt_words':1}],'rights_basis':'PD_US_CONFIRMED','confidence':'accepted','schema_version':'1.0'}
 if f=='contextual':x['subtype']='setting'
 return x
class T(unittest.TestCase):
 def v(self,x):
  if jsonschema: jsonschema.Draft202012Validator(S, resolver=jsonschema.RefResolver.from_schema(S)).validate(x)
 def test_families(self):
  for f in ['story','speech','character','conflict','structure','contextual']:self.v(card(f))
 def test_required(self):
  for k in ['observation','inference','pattern']:
   x=card();x.pop(k);self.assertRaises(Exception,self.v,x)
 def test_contextual(self):
  x=card('contextual');x.pop('subtype');self.assertRaises(Exception,self.v,x)
  x=card();x['subtype']='setting';self.assertRaises(Exception,self.v,x)
 def test_invalid_contextual_subtype(self):
  x=card('contextual');x['subtype']='bad';self.assertRaises(Exception,self.v,x)
 def test_malformed_primitive_id(self):
  x=card();x['primitive_id']='bad';self.assertRaises(Exception,self.v,x)
 def test_engine_hash_compatibility(self):
  x=card();x['primitive_id']=primitive_id(x);self.v(x)
 def test_pattern_extra(self):
  x=card();x['pattern']['extra']='x';self.assertRaises(Exception,self.v,x)
 def test_long_excerpt(self):
  x=card();x['evidence'][0]['excerpt_words']=26;self.assertRaises(Exception,self.v,x)
 def test_extra(self):
  x=card();x['extra']=1;self.assertRaises(Exception,self.v,x)
if __name__=='__main__':unittest.main()
