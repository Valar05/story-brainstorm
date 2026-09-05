#!/usr/bin/env python3
"""Fail-closed bibliography shard auditor (stdlib only)."""
import argparse,json,re,time,urllib.request,urllib.error
from pathlib import Path

def norm(s): return re.sub(r"[^a-z0-9]", "", (s or "").casefold())
def same(a,b):
 a,b=norm(a),norm(b)
 if a==b:return True
 # harmless catalog inversion: Last, First
 return norm(" ".join((b.split()[-1:],b.split()[:-1])))==a if b else False
def load_rdf(item,cache,live):
 fn=cache/f"{item}.rdf" if cache else None
 if fn and fn.exists(): data=fn.read_bytes()
 elif live:
  url=f"https://www.gutenberg.org/cache/epub/{item}/pg{item}.rdf"
  for n in range(3):
   try:
    req=urllib.request.Request(url,headers={"User-Agent":"story-brainstorm-auditor/1.0"});data=urllib.request.urlopen(req,timeout=12).read();break
   except Exception:
    if n==2: raise
    time.sleep(.2*(n+1))
 else: raise FileNotFoundError(f"missing RDF cache for item {item}")
 text=data.decode("utf-8","replace")
 def tag(pattern):
  m=re.search(pattern,text,re.I|re.S);return re.sub(r"<[^>]+>"," ",m.group(1)).strip() if m else ""
 title=tag(r"<dcterms:title[^>]*>(.*?)</dcterms:title>")
 creator=tag(r"<pgterms:name[^>]*>(.*?)</pgterms:name>")
 rights=tag(r"<dcterms:rights[^>]*>(.*?)</dcterms:rights>")
 issued=tag(r"<dcterms:issued[^>]*>(.*?)</dcterms:issued>")
 lang= "en" if re.search(r"rdf:resource=[\"']http://purl.org/dc/terms/LISO-639-2/en[\"']",text) or re.search(r"rdf:resource=[\"'][^\"']*/en[\"']",text) else ""
 return {"title":title,"creator":creator,"language":lang,"copyright":rights,"digital_release_date":issued,"item_id":str(item),"rdf_url":f"https://www.gutenberg.org/cache/epub/{item}/pg{item}.rdf"}
def audit(shard,cache=None,live=False):
 data=json.loads(Path(shard).read_text()); rows=data.get("works",[])+data.get("reserves",[]); out=[]; ids=set();titles=set();urls=set()
 for w in rows:
  e=w.get("source_edition",{}); item=str(e.get("item_id", "")); url=e.get("url",""); errs=[]
  if not item: errs.append("missing item_id")
  if "?" in url or "/search" in url or "/books/" in url: errs.append("publication evidence/source URL must be exact item, not search")
  if not w.get("first_publication_evidence_url") or "?" in w.get("first_publication_evidence_url","") or "/search" in w.get("first_publication_evidence_url",""): errs.append("missing exact first-publication evidence URL")
  if item in ids: errs.append("duplicate item_id"); ids.add(item)
  else: ids.add(item)
  if norm(w.get("title")) in titles: errs.append("duplicate title")
  titles.add(norm(w.get("title"))); 
  if url in urls: errs.append("duplicate source URL")
  urls.add(url)
  try: raw=load_rdf(item,cache,live)
  except Exception as ex: raw={};errs.append("catalog fetch failed: "+type(ex).__name__)
  checks={"title_match":same(w.get("title"),raw.get("title")),"creator_match":same(w.get("author"),raw.get("creator")),"language_en":raw.get("language")=="en","us_pd":raw.get("copyright")=="Public domain in the USA.","first_year_le_1929":isinstance(w.get("first_publication_year"),int) and w["first_publication_year"]<=1929,"source_item_match":item and bool(re.search(r"/ebooks/"+re.escape(item)+r"(?:$|[?#])",url)),"exact_pub_evidence":bool(w.get("first_publication_evidence_url")) and "?" not in w.get("first_publication_evidence_url","") and "/search" not in w.get("first_publication_evidence_url","")}
  if e.get("translation_required") and (not e.get("translator") or e.get("translation_rights_status")!="PD_US_CONFIRMED"): errs.append("missing translator or translation rights")
  checks["translation_identity_rights"]=not e.get("translation_required") or (bool(e.get("translator")) and e.get("translation_rights_status")=="PD_US_CONFIRMED")
  if not all(checks.values()): errs.extend(k for k,v in checks.items() if not v)
  out.append({"work_id":w.get("work_id"),"raw_catalog":raw,"expected":{"title":w.get("title"),"author":w.get("author"),"first_publication_year":w.get("first_publication_year"),"source_item_id":item},"checks":checks,"errors":sorted(set(errs)),"status":"PASS" if not errs else "FAIL"})
 summary={"schema_version":"1.0","records":len(out),"pass":sum(x["status"]=="PASS" for x in out),"fail":sum(x["status"]=="FAIL" for x in out),"rows":out,"state":"READY" if out and all(x["status"]=="PASS" for x in out) else "NOT_READY"}
 return summary
def main():
 p=argparse.ArgumentParser();p.add_argument("--shard",required=True);p.add_argument("--out",required=True);p.add_argument("--rdf-cache",type=Path);p.add_argument("--live",action="store_true");a=p.parse_args();r=audit(a.shard,a.rdf_cache,a.live);Path(a.out).write_text(json.dumps(r,indent=2,sort_keys=True)+"\n");print(json.dumps({k:r[k] for k in ("state","records","pass","fail")},sort_keys=True));return 0 if r["state"]=="READY" else 2
if __name__=="__main__":raise SystemExit(main())
