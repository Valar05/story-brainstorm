#!/usr/bin/env python3
import argparse,hashlib,json,re,tempfile,time,urllib.parse,urllib.request
from pathlib import Path

def norm(s):return re.sub(r"[^a-z0-9]","",str(s or "").casefold())
def eq(a,b):
 ra,rb=str(a or '').casefold().strip(),str(b or '').casefold().strip()
 if norm(ra)==norm(rb):return True
 def parts(x): return [z.strip() for z in x.split(',',1)] if ',' in x else []
 pa,pb=parts(ra),parts(rb)
 return bool(pa and pb and norm(' '.join(pa[::-1]))==norm(' '.join(pb))) or bool(pa and norm(' '.join(pa[::-1]))==norm(rb)) or bool(pb and norm(ra)==norm(' '.join(pb[::-1])))
def cache_key(work_id,title,author):
 q=urllib.parse.urlencode({'title':title,'author':author,'fields':'key,title,author_name,first_publish_year','limit':'5'})
 return hashlib.sha256((str(work_id)+'\0'+q).encode()).hexdigest()[:32]
def title_eq(a,b):
 if norm(a)==norm(b):return True
 cut=lambda x:norm(re.split(r"\s*(?::|;|\bor\b)\s*",str(x or ""),maxsplit=1,flags=re.I)[0])
 return len(cut(a))>=6 and cut(a)==cut(b)
def atomic(path,obj):
 text=json.dumps(obj,sort_keys=True,indent=2,ensure_ascii=False)+"\n";old=path.read_text() if path.exists() else None
 if old==text:return False
 path.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile('w',dir=path.parent,delete=False,encoding='utf8') as f:f.write(text);tmp=Path(f.name)
 tmp.replace(path);return True
def resolve_row(w,cache,live):
 q=urllib.parse.urlencode({'title':w.get('title',''),'author':w.get('author',''),'fields':'key,title,author_name,first_publish_year','limit':'5'})
 h=hashlib.sha256(q.encode()).hexdigest()[:16];fn=cache/(cache_key(w.get('work_id'),w.get('title',''),w.get('author',''))+'.json')
 try:
  if fn.exists():j=json.loads(fn.read_text());source='cache'
  elif live:
   url='https://openlibrary.org/search.json?'+q;last=None
   for n in range(4):
    try:
     req=urllib.request.Request(url,headers={'User-Agent':'story-brainstorm-resolver/1.0'});j=json.loads(urllib.request.urlopen(req,timeout=15).read());atomic(fn,j);break
    except Exception as e:
     last=f'{type(e).__name__}: {e}';
     if n==3:return {'work_id':w.get('work_id'),'status':'BLOCKED','reason':last,'query_hash':h}
     time.sleep(.2*(n+1))
   source='live'
  else:return {'work_id':w.get('work_id'),'status':'BLOCKED','reason':'cache miss (use --live)','query_hash':h}
 except Exception as e:return {'work_id':w.get('work_id'),'status':'BLOCKED','reason':type(e).__name__,'query_hash':h}
 cand=[]
 for d in j.get('docs',[]):
  key=(d.get('key') or '');
  if not re.fullmatch(r'/works/OL[0-9]+W',key):continue
  authors=d.get('author_name') or []
  if not title_eq(w.get('title'),d.get('title')) or not any(eq(w.get('author'),a) for a in authors):continue
  y=d.get('first_publish_year');
  if not isinstance(y,int) or y>1929 or not isinstance(w.get('first_publication_year'),int) or w['first_publication_year']>y:continue
  cand.append({'item_id':key.rsplit('/',1)[-1],'title':d.get('title'),'authors':authors,'first_publish_year':y})
 if len(cand)==1:return {'work_id':w.get('work_id'),'status':'RESOLVED','evidence_url':'https://openlibrary.org/works/'+cand[0]['item_id'],'candidate':cand[0],'query_hash':h,'source':source}
 return {'work_id':w.get('work_id'),'status':'REVIEW_REQUIRED','reason':'zero eligible candidates' if not cand else 'multiple eligible candidates','candidates':cand[:5],'query_hash':h,'source':source}
def main():
 p=argparse.ArgumentParser();p.add_argument('--shard',required=True);p.add_argument('--out',required=True);p.add_argument('--cache-dir',required=True,type=Path);p.add_argument('--live',action='store_true');a=p.parse_args();d=json.loads(Path(a.shard).read_text());rows=d.get('accepted_works',d.get('works',[]))+d.get('reserves',[]);out=[resolve_row(w,a.cache_dir,a.live) for w in rows];out.sort(key=lambda x:str(x.get('work_id')));res={'schema_version':'1.0','records':len(out),'counts':{k:sum(x['status']==k for x in out) for k in ('RESOLVED','REVIEW_REQUIRED','BLOCKED')},'state':'READY' if out and all(x['status']=='RESOLVED' for x in out) else 'NOT_READY','rows':out};atomic(Path(a.out),res);print(json.dumps({'state':res['state'],'records':len(out),'counts':res['counts']},sort_keys=True));return 0 if res['state']=='READY' else 2
if __name__=='__main__':raise SystemExit(main())
