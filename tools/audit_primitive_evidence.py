#!/usr/bin/env python3
"""Verify primitive-card evidence against caller-supplied Gutenberg text cache."""
import argparse, hashlib, json, re, tempfile, urllib.request, time
from pathlib import Path

def norm(s): return re.sub(r"\s+", " ", str(s or "")).strip().casefold()
def words(s): return len(re.findall(r"\S+", str(s or "")))
def item_id(url):
 m=re.fullmatch(r"https?://www\.gutenberg\.org/ebooks/([0-9]+)",str(url or "")); return m.group(1) if m else None
def valid_locator(s):
 s=str(s or "").strip(); low=s.casefold()
 if not s:return False
 return bool(re.search(r"\b(?:chapter|act|scene|book|part|section|poem|stanza)\s+[a-z0-9][a-z0-9 .:_-]*",low) or re.search(r"\bpage\s+\d+",low))
def body_only(text):
 start=re.search(r"\*+\s*START OF (?:THE )?PROJECT GUTENBERG EBOOK[^\n]*",text,re.I); end=re.search(r"\*+\s*END OF (?:THE )?PROJECT GUTENBERG EBOOK[^\n]*",text,re.I)
 if not start or not end or end.start()<=start.end(): raise ValueError("missing or reversed Gutenberg body markers")
 body=text[start.end():end.start()]
 return body
def atomic(path,data):
 path.parent.mkdir(parents=True,exist_ok=True)
 if path.exists() and path.read_bytes()==data:return False
 with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as f:f.write(data);tmp=Path(f.name)
 tmp.replace(path);return True
def load_text(item,cache,live):
 p=cache/(item+'.txt')
 if p.exists(): return p.read_text(encoding='utf-8'), 'cache'
 if not live: raise FileNotFoundError(item)
 req=urllib.request.Request(f'https://www.gutenberg.org/cache/epub/{item}/pg{item}.txt',headers={'User-Agent':'story-brainstorm-evidence-auditor/1.0'})
 last=None
 for attempt in range(3):
  try:
   data=urllib.request.urlopen(req,timeout=15).read(); text=data.decode('utf-8')
   atomic(p,data); return text,'live'
  except (OSError, UnicodeError) as exc:
   last=exc
   if attempt<2: time.sleep(0.1*(attempt+1))
 raise last
def audit(works_path,cards_path,cache,out_path,live=False):
 errors=[]; rows=[]
 try:wrows=json.loads(Path(works_path).read_text()).get('works',[]); crows=json.loads(Path(cards_path).read_text()).get('cards',[])
 except Exception as e:return {'state':'NOT_READY','cards':0,'refs':0,'errors':['input parse: '+type(e).__name__]}
 repo=Path(__file__).resolve().parent.parent
 try:
  cache.resolve().relative_to(repo)
  result={'schema_version':'1.0','state':'NOT_READY','cards':len(crows),'refs':0,'errors':['text cache must be outside repository'],'rows':[]}
  atomic(Path(out_path),(json.dumps(result,indent=2,sort_keys=True)+'\n').encode())
  return result
 except ValueError:
  pass
 workmap={w.get('work_id'):w for w in wrows}; seen=set()
 for ci,c in enumerate(crows):
  evs=c.get('evidence') or []
  if not evs: rows.append({'card_index':ci,'status':'FAIL','errors':['missing evidence']});continue
  for ei,e in enumerate(evs):
   er=[]; wid=e.get('work_id'); w=workmap.get(wid); url=e.get('edition_url'); ex=e.get('short_excerpt',''); stored=e.get('excerpt_words'); iid=item_id(url)
   if not w: er.append('unknown work')
   expected=w.get('source_edition',{}).get('url') if w else None
   if not expected or url!=expected: er.append('edition URL mismatch')
   if not valid_locator(e.get('location')): er.append('vague or missing location')
   actual=words(ex)
   if not isinstance(stored,int) or stored!=actual or not 1<=actual<=25: er.append('excerpt word count invalid')
   key=(wid,url,e.get('location'),norm(ex))
   if key in seen: er.append('duplicate evidence reference')
   seen.add(key)
   txt=None; source=None
   if iid and not er:
    try: txt,source=load_text(iid,cache,live); 
    except Exception as x: er.append('source unavailable: '+type(x).__name__)
   if txt is not None:
    try: body=body_only(txt)
    except Exception as x: er.append(str(x)); body=''
    if body and norm(ex) not in norm(body): er.append('excerpt not found in source')
    if body and len(re.findall(re.escape(norm(ex)),norm(body)))!=1: er.append('excerpt occurrence is not unique')
    if re.search(r'(project gutenberg|license|credits:|produced by|transcrib)',ex,re.I): er.append('boilerplate excerpt rejected')
   rows.append({'card_index':ci,'evidence_index':ei,'work_id':wid,'status':'PASS' if not er else 'FAIL','errors':sorted(set(er)),'source':source})
 result={'schema_version':'1.0','state':'READY' if not errors and rows and all(r['status']=='PASS' for r in rows) else 'NOT_READY','cards':len(crows),'refs':len(rows),'errors':errors,'rows':rows}
 atomic(Path(out_path),(json.dumps(result,indent=2,sort_keys=True)+'\n').encode()); return result
def main():
 p=argparse.ArgumentParser();p.add_argument('--works',required=True);p.add_argument('--cards',required=True);p.add_argument('--out',required=True);p.add_argument('--text-cache',required=True,type=Path);p.add_argument('--live',action='store_true');a=p.parse_args(); r=audit(a.works,a.cards,a.text_cache,Path(a.out),a.live); print(json.dumps({k:r[k] for k in ('state','cards','refs')})); return 0 if r['state']=='READY' else 2
if __name__=='__main__':raise SystemExit(main())
