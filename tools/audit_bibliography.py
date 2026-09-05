#!/usr/bin/env python3
import argparse,json,re,time,urllib.parse,urllib.request,tempfile
from pathlib import Path
import xml.etree.ElementTree as ET
D="http://purl.org/dc/terms/";P="http://www.gutenberg.org/2009/pgterms/";R="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
def atomic_bytes(path,raw):
 path.parent.mkdir(parents=True,exist_ok=True)
 if path.exists() and path.read_bytes()==raw:return False
 with tempfile.NamedTemporaryFile('wb',dir=path.parent,delete=False) as f:f.write(raw);tmp=Path(f.name)
 tmp.replace(path);return True
def atomic_json(path,obj):return atomic_bytes(path,(json.dumps(obj,sort_keys=True,ensure_ascii=False)+"\n").encode())
def norm(s): return re.sub(r"[^a-z0-9]","",str(s or "").casefold())
def eq(a,b):
 a,b=norm(a),norm(b)
 if a==b:return True
 if ',' in str(b):
  z=[x.strip() for x in str(b).split(',',1)];return norm(' '.join(z[::-1]))==a
 return False
def title_eq(a,b):
 if norm(a)==norm(b):return True
 primary=lambda value: norm(re.split(r"\s*(?::|;|\bor\b)\s*",str(value or ""),maxsplit=1,flags=re.I)[0])
 pa,pb=primary(a),primary(b)
 return len(pa)>=6 and pa==pb
def fetch_json(url):
 for n in range(3):
  try:
   req=urllib.request.Request(url,headers={"User-Agent":"story-brainstorm-auditor/1.0","Accept":"application/json"})
   return json.loads(urllib.request.urlopen(req,timeout=15).read())
  except Exception:
   if n==2:raise
   time.sleep(.2*(n+1))
def rdf(item,cache,live):
 f=cache/f"{item}.rdf" if cache else None;raw=None;fetched=False
 if f and f.exists():
  try: raw=f.read_bytes();ET.fromstring(raw)
  except Exception:
   if not live:raise
   raw=None
 if raw is None and live:
  for n in range(3):
   try: raw=urllib.request.urlopen(urllib.request.Request(f"https://www.gutenberg.org/cache/epub/{item}/pg{item}.rdf",headers={"User-Agent":"story-brainstorm-auditor/1.0"}),timeout=15).read();ET.fromstring(raw);fetched=True;break
   except Exception:
    if n==2:raise
    time.sleep(.2*(n+1))
 if raw is None:raise FileNotFoundError(item)
 if fetched and f:atomic_bytes(f,raw)
 root=ET.fromstring(raw); q=lambda tag: root.findtext('.//{'+D+'}'+tag) or ''
 lang=''
 for e in root.findall('.//{'+D+'}language'):
  resource=e.get('{'+R+'}resource','')
  nested=e.findtext('.//{'+R+'}value') or ''
  lang=(resource.rsplit('/',1)[-1] if resource else nested).strip()
  if lang:break
 c=root.find('.//{'+D+'}creator//{'+P+'}name'); creator=c.text.strip() if c is not None and c.text else q('creator').strip()
 return {'title':q('title').strip(),'creator':creator,'language':lang,'copyright':q('rights').strip(),'digital_release_date':q('issued').strip(),'item_id':str(item)}

def ev_ok(u):
 return bool(re.match(r'^https?://[^/?#]+/(?:item/[^/?#]+|details/[^/?#]+|record/[^/?#]+)(?:[/?#].*)?$',u or ''))
def evidence(url,expected_title,expected_year,cache=None,live=False):
 m=re.match(r"^https://openlibrary\.org/works/(OL[0-9]+W)(?:/[^?#]+)?$",url or "")
 if not m or "?" in (url or "") or "#" in (url or ""): return {"error":"invalid Open Library work URL","checks":{"url_exact":False}}
 item=m.group(1); f=cache/f"{item}.json" if cache else None
 try:
  raw=None
  if f and f.exists():
   try: raw=json.loads(f.read_text())
   except Exception:
    if not live:raise
  if raw is None and live:
   raw=fetch_json(f"https://openlibrary.org/works/{item}.json")
   if f:atomic_json(f,raw)
  if raw is None:raise FileNotFoundError(item)
 except Exception as ex: return {"error":"publication catalog fetch failed: "+type(ex).__name__,"checks":{"url_exact":True,"fetch":False}}
 title=str(raw.get("title", "")); date=None;year=None;source="exact_key_search";exact_key=False
 sf=cache/f"{item}.search.json" if cache else None
 try:
  search=None
  if sf and sf.exists():
   try: search=json.loads(sf.read_text())
   except Exception:
    if not live:raise
  if search is None and live:
   query=urllib.parse.urlencode({"q":f"key:/works/{item}","fields":"key,title,first_publish_year","limit":"2"})
   search=fetch_json("https://openlibrary.org/search.json?"+query)
   if sf:atomic_json(sf,search)
  if search is None:raise FileNotFoundError(item+".search")
  docs=search.get("docs",[])
  exact_key=search.get("numFound")==1 and len(docs)==1 and docs[0].get("key")==f"/works/{item}" and title_eq(docs[0].get("title"),title)
  if exact_key:
   date=docs[0].get("first_publish_year");year=date if isinstance(date,int) else None
 except Exception:
  exact_key=False
 checks={"url_exact":True,"fetch":True,"title_match":title_eq(title,expected_title),"catalog_date_source_exact":exact_key,"first_publish_date_present":year is not None,"catalog_pre_1930":year is not None and year<=1929,"claimed_not_after_catalog":isinstance(expected_year,int) and year is not None and expected_year<=year}
 return {"item_id":item,"title":title,"first_publish_date":date,"first_publication_year":year,"date_source":source,"checks":checks,"error":None if all(checks.values()) else "publication metadata mismatch"}
def audit(path,cache=None,live=False,evidence_cache=None):
 d=json.loads(Path(path).read_text()); rows=d.get('accepted_works',d.get('works',[]))+d.get('reserves',[]); seen={};out=[]
 for w in rows:
  e=w.get('source_edition',{}); item=str(e.get('item_id',''));u=e.get('url',''); errs=[]
  for k in ('work_id','title','author','first_publication_year','first_publication_evidence_url','source_edition','rights'):
   if not w.get(k):errs.append('missing '+k)
  if not isinstance(w.get('first_publication_year'),int) or w.get('first_publication_year',1930)>1929:errs.append('post-1929 or invalid first publication year')
  pub=evidence(w.get('first_publication_evidence_url'),w.get('title'),w.get('first_publication_year'),evidence_cache or cache,live)
  if not all(pub.get('checks',{}).values()):errs.append(pub.get('error') or 'publication evidence mismatch')
  if not re.match(r'^https?://[^/?#]+/(?:ebooks/[^/?#]+|item/[^/?#]+|details/[^/?#]+)(?:[/?#].*)?$',u or ''):errs.append('invalid source item URL')
  if item in seen:errs.append('duplicate item_id')
  if u in seen.values():errs.append('duplicate source URL')
  if norm(w.get('title')) in [norm(x.get('title')) for x in rows[:rows.index(w)]]:errs.append('duplicate title')
  seen[item]=u
  rw={};
  try: rw=rdf(item,cache,live)
  except Exception as ex: errs.append('catalog fetch failed: '+type(ex).__name__)
  checks={'title_match':eq(e.get('raw_title'),rw.get('title')) and eq(w.get('title'),rw.get('title')),'creator_match':eq(e.get('raw_creator'),rw.get('creator')) and eq(w.get('author'),rw.get('creator')),'language_match':e.get('language')=='en' and rw.get('language')=='en','rights_match':w.get('rights',{}).get('status')=='PD_US_CONFIRMED' and w.get('rights',{}).get('jurisdiction')=='US' and bool(w.get('rights',{}).get('verification_refs')) and rw.get('copyright')=='Public domain in the USA.','first_year_ok':isinstance(w.get('first_publication_year'),int) and w['first_publication_year']<=1929,'evidence_exact':all(pub.get('checks',{}).values()),'item_match':bool(item) and bool(re.search(r'/ebooks/'+re.escape(item)+r'(?:$|[?#])',u)),'stored_raw_fields':e.get('raw_title')==rw.get('title') and e.get('raw_creator')==rw.get('creator') and e.get('language')=='en'}
  derivative=bool(e.get('translator') or e.get('editor') or e.get('translation_required') or e.get('derivative'))
  checks['translation_rights']=not derivative or (bool(e.get('translator') or e.get('editor')) and e.get('translation_rights_status')=='PD_US_CONFIRMED')
  if not checks['translation_rights']:errs.append('missing translator/editor rights')
  if not all(checks.values()):errs += [k for k,v in checks.items() if not v]
  out.append({'work_id':w.get('work_id'),'raw_catalog':rw,'publication_catalog':pub,'expected':{'title':w.get('title'),'author':w.get('author'),'first_publication_year':w.get('first_publication_year'),'source_item_id':item},'checks':checks,'errors':sorted(set(errs)),'status':'PASS' if not errs else 'FAIL'})
 return {'schema_version':'1.0','records':len(out),'pass':sum(x['status']=='PASS' for x in out),'fail':sum(x['status']=='FAIL' for x in out),'rows':out,'state':'READY' if out and all(x['status']=='PASS' for x in out) else 'NOT_READY'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--shard',required=True);p.add_argument('--out',required=True);p.add_argument('--rdf-cache',type=Path);p.add_argument('--live',action='store_true');p.add_argument('--evidence-cache',type=Path);a=p.parse_args();r=audit(a.shard,a.rdf_cache,a.live,a.evidence_cache);dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True);text=json.dumps(r,indent=2,sort_keys=True)+'\n';old=dest.read_text() if dest.exists() else None
 if old!=text:
  with tempfile.NamedTemporaryFile('w',dir=dest.parent,delete=False,encoding='utf8') as f:f.write(text);tmp=Path(f.name)
  tmp.replace(dest)
 print(json.dumps({k:r[k] for k in ('state','records','pass','fail')},sort_keys=True));return 0 if r['state']=='READY' else 2
if __name__=='__main__':raise SystemExit(main())
