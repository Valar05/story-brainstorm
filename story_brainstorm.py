#!/usr/bin/env python3
"""Deterministic source-first narrative primitive research engine."""
from __future__ import annotations
import argparse, hashlib, json, re, sys, tempfile
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parent
RIGHTS={"PD_US_CONFIRMED"}
FAMILIES=("story","speech","character","conflict","structure","contextual")
QUOTAS={"story":300,"speech":200,"character":200,"conflict":100,"structure":100,"contextual":100}
VOLATILE={"created_at","generated_at","updated_at","retrieved_at"}
def normalize_for_hash(v:Any)->Any:
    if isinstance(v,dict): return {k:normalize_for_hash(x) for k,x in v.items() if k not in VOLATILE}
    if isinstance(v,list): return [normalize_for_hash(x) for x in v]
    return v
def stable_hash(v:Any)->str:
    raw=json.dumps(normalize_for_hash(v),sort_keys=True,ensure_ascii=False,separators=(",",":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
def primitive_id(card:dict[str,Any])->str:
    body={k:v for k,v in card.items() if k!="primitive_id"}
    return "sha256:"+stable_hash(body)
def atomic_write(path:Path,text:str)->bool:
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8")==text: return False
    with tempfile.NamedTemporaryFile("w",encoding="utf-8",dir=path.parent,delete=False) as f:
        f.write(text); tmp=Path(f.name)
    tmp.replace(path); return True
def write_json(path:Path,obj:Any)->bool:
    return atomic_write(path,json.dumps(obj,indent=2,sort_keys=True,ensure_ascii=False)+"\n")
def load(path:Path)->dict[str,Any]: return json.loads(path.read_text(encoding="utf-8"))
def _valid_item_url(value:Any)->bool:
    if not isinstance(value,str) or not value.startswith(("https://","http://")): return False
    low=value.lower()
    return not any(x in low for x in ("/search", "?q=", "?query=", "search?") )
def _errors_works(works:list[dict[str,Any]])->list[str]:
    errors=[]; ids=set()
    for w in works:
        wid=w.get("work_id")
        if not isinstance(wid,str) or not wid: errors.append("missing work_id")
        elif wid in ids: errors.append(f"duplicate work_id: {wid}")
        ids.add(wid)
        first=w.get("first_publication_year",w.get("publication_year"))
        if not isinstance(first,int) or first>1929: errors.append(f"post-1929 first publication: {wid}")
        ed=w.get("source_edition",{}); rights=w.get("rights",{})
        for key in ("item_id","url","language","raw_title","raw_creator"):
            if not ed.get(key): errors.append(f"missing edition {key}: {wid}")
        if ed.get("language")!="en": errors.append(f"non-English edition: {wid}")
        if not _valid_item_url(ed.get("url")): errors.append(f"unstable/search edition URL: {wid}")
        if not w.get("first_publication_evidence_url") or not _valid_item_url(w.get("first_publication_evidence_url")):
            errors.append(f"missing first-publication evidence: {wid}")
        if rights.get("status") not in RIGHTS: errors.append(f"unaccepted rights: {wid}")
        if rights.get("jurisdiction")!="US" or not rights.get("basis") or not rights.get("verification_refs"): errors.append(f"incomplete rights verification: {wid}")
        if ed.get("translator") is not None or ed.get("editor") is not None:
            if not ed.get("translator") and not ed.get("editor"): errors.append(f"unidentified translation/editor: {wid}")
            if ed.get("translation_rights_status")!="PD_US_CONFIRMED": errors.append(f"translation/editor rights not confirmed: {wid}")
    return errors
def validate_works(path:Path=ROOT/"data/works.json",required:int=100)->dict[str,Any]:
    try: works=load(path).get("works",[])
    except Exception as e: return {"state":"NOT_READY","accepted_works":0,"required_works":required,"errors":[str(e)]}
    errors=_errors_works(works)
    if len(works)!=required: errors.append(f"expected exactly {required} works, got {len(works)}")
    return {"state":"READY" if not errors else "NOT_READY","accepted_works":len(works),"required_works":required,"errors":errors}
def _card_errors(cards:list[dict[str,Any]],required:int=1000,quotas:dict[str,int]|None=None)->tuple[list[str],dict[str,int]]:
    quotas=quotas or QUOTAS; errors=[]; ids=set(); counts={f:0 for f in FAMILIES}
    for c in cards:
        cid=c.get("primitive_id"); fam=c.get("family")
        if not isinstance(cid,str) or not cid: errors.append("missing primitive_id")
        elif cid in ids: errors.append(f"duplicate primitive_id: {cid}")
        ids.add(cid)
        if fam not in FAMILIES: errors.append(f"invalid family: {fam}")
        else: counts[fam]+=1
        if c.get("confidence")!="accepted": errors.append(f"non-accepted card: {cid}")
        if not c.get("observation"): errors.append(f"missing observation: {cid}")
        if not c.get("inference"): errors.append(f"missing inference: {cid}")
        if not c.get("evidence"): errors.append(f"missing evidence: {cid}")
        for e in c.get("evidence",[]):
            if not e.get("location"): errors.append(f"missing evidence location: {cid}")
            if not e.get("edition_url"): errors.append(f"missing evidence edition_url: {cid}")
            excerpt=e.get("short_excerpt","")
            if e.get("excerpt_words",0)>25 or len(excerpt.split())>25: errors.append(f"excerpt too long: {cid}")
            if e.get("excerpt_words",0)<1: errors.append(f"missing excerpt_words: {cid}")
        expected=primitive_id(c)
        if isinstance(cid,str) and cid.startswith("sha256:") and cid!=expected: errors.append(f"primitive hash mismatch: {cid}")
    if len(cards)!=required: errors.append(f"expected exactly {required} cards, got {len(cards)}")
    for fam,n in quotas.items():
        if counts.get(fam,0)!=n: errors.append(f"family {fam}: expected {n}, got {counts.get(fam,0)}")
    return errors,counts
def validate_cards(path:Path=ROOT/"data/primitive_cards.json",required:int=1000,quotas:dict[str,int]|None=None)->dict[str,Any]:
    try: cards=load(path).get("cards",[])
    except Exception as e: return {"state":"NOT_READY","accepted_cards":0,"required_cards":required,"family_counts":{f:0 for f in FAMILIES},"errors":[str(e)]}
    errors,counts=_card_errors(cards,required,quotas)
    return {"state":"READY" if not errors else "NOT_READY","accepted_cards":len(cards),"required_cards":required,"family_counts":counts,"errors":errors}
def read_cards(path:Path)->list[dict[str,Any]]: return load(path).get("cards",[])
def merge_shards(shard_dir:Path)->list[dict[str,Any]]:
    cards=[]
    for p in sorted(shard_dir.glob("*.json")):
        cards.extend(read_cards(p))
    return cards
def build_index(cards:list[dict[str,Any]],out:Path)->dict[str,Any]:
    refs=[]
    for c in sorted(cards,key=lambda x:x.get("primitive_id","")):
        for e in c.get("evidence",[]):
            refs.append({"record_type":"primitive_ref","primitive_id":c.get("primitive_id"),"family":c.get("family"),"name":c.get("name"),"observation":c.get("observation"),"inference":c.get("inference"),"work_id":e.get("work_id"),"location":e.get("location"),"evidence":e.get("short_excerpt"),"edition_url":e.get("edition_url"),"rights_basis":c.get("rights_basis"),"confidence":c.get("confidence")})
    out.mkdir(parents=True,exist_ok=True); text="".join(json.dumps(x,sort_keys=True,ensure_ascii=False)+"\n" for x in refs); atomic_write(out/"primitive_refs.jsonl",text)
    byfam={f:sum(1 for c in cards if c.get("family")==f) for f in FAMILIES}; bywork={}
    for r in refs: bywork[r.get("work_id","")]=bywork.get(r.get("work_id",""),0)+1
    summary={"record_count":len(refs),"card_count":len(cards),"by_family":byfam,"by_work":dict(sorted(bywork.items()))}
    write_json(out/"primitive_index_summary.json",summary)
    lines=["# Story Brainstorm Primitive Index","",f"- Cards: {len(cards)}",f"- Evidence records: {len(refs)}","","## Families",""]+[f"- {f}: {byfam[f]}" for f in FAMILIES]
    atomic_write(out/"primitive_index_report.md","\n".join(lines)+"\n"); return summary
def cmd_validate_works(a): result=validate_works(Path(a.path)); print(json.dumps(result,indent=2,sort_keys=True)); return 0 if result["state"]=="READY" else 2
def cmd_validate_cards(a): result=validate_cards(Path(a.path)); print(json.dumps(result,indent=2,sort_keys=True)); return 0 if result["state"]=="READY" else 2
def main()->int:
    p=argparse.ArgumentParser(description="Story Brainstorm narrative primitive research")
    sub=p.add_subparsers(dest="command",required=True)
    w=sub.add_parser("works"); ws=w.add_subparsers(dest="action",required=True); v=ws.add_parser("validate"); v.add_argument("--path",default=str(ROOT/"data/works.json")); v.set_defaults(fn=cmd_validate_works)
    c=sub.add_parser("primitives"); cs=c.add_subparsers(dest="action",required=True); cl=cs.add_parser("list"); cl.add_argument("--family",choices=FAMILIES); cl.set_defaults(fn=lambda a:(print(json.dumps({"state":"NOT_READY","items":[]})),2)[1]); cv=cs.add_parser("validate"); cv.add_argument("--path",default=str(ROOT/"data/primitive_cards.json")); cv.set_defaults(fn=cmd_validate_cards)
    ix=sub.add_parser("index"); ixs=ix.add_subparsers(dest="action",required=True); ib=ixs.add_parser("build"); ib.add_argument("--cards",default=str(ROOT/"data/primitive_cards.json")); ib.add_argument("--shards",default=""); ib.add_argument("--out-dir",default=str(ROOT/"generated/primitive_refs")); ib.set_defaults(fn=lambda a:(print(json.dumps(build_index(merge_shards(Path(a.shards)) if a.shards else read_cards(Path(a.cards)),Path(a.out_dir)),indent=2,sort_keys=True)),0)[1])
    si=sub.add_parser("search-index"); si.add_argument("query",nargs="?",default=""); si.add_argument("--index",default=str(ROOT/"generated/primitive_refs/primitive_refs.jsonl")); si.add_argument("--family",default=""); si.add_argument("--work",default=""); si.add_argument("--limit",type=int,default=20)
    si.set_defaults(fn=lambda a: search(a))
    co=sub.add_parser("compose"); co.add_argument("--query",default=""); co.add_argument("--count",type=int,default=1); co.add_argument("--seed",type=int,default=0); co.add_argument("--index",default=str(ROOT/"generated/primitive_refs/primitive_refs.jsonl")); co.set_defaults(fn=lambda a: compose(a))
    rp=sub.add_parser("report"); rp.add_argument("--index",default=str(ROOT/"generated/primitive_refs/primitive_refs.jsonl")); rp.set_defaults(fn=lambda a:(print(json.dumps(index_summary(Path(a.index)),indent=2,sort_keys=True)),0)[1])
    rc=sub.add_parser("receipts"); rcs=rc.add_subparsers(dest="action",required=True); rv=rcs.add_parser("validate"); rv.add_argument("path"); rv.set_defaults(fn=lambda a: receipt_validate(Path(a.path)))
    sv=sub.add_parser("serve"); sv.set_defaults(fn=lambda a:(print("Use tools/doc_server.py"),0)[1])
    a=p.parse_args(); return a.fn(a)
def search(a):
    terms=set(re.findall(r"[a-z0-9]+",a.query.lower())); n=0
    try: rows=[json.loads(x) for x in Path(a.index).read_text().splitlines() if x.strip()]
    except OSError as e: print(json.dumps({"state":"NOT_READY","error":str(e)})); return 2
    for r in rows:
        hay=json.dumps(r).lower()
        if terms and not all(t in hay for t in terms): continue
        if a.family and r.get("family")!=a.family: continue
        if a.work and r.get("work_id")!=a.work: continue
        print(json.dumps(r,sort_keys=True)); n+=1
        if n>=a.limit: break
    return 0
def compose(a):
    import random
    rows=[json.loads(x) for x in Path(a.index).read_text().splitlines() if x.strip()]; tokens=set(re.findall(r"[a-z0-9]+",a.query.lower())); scored=[r for r in rows if not tokens or all(t in json.dumps(r).lower() for t in tokens)]; rng=random.Random(a.seed); rng.shuffle(scored); print(json.dumps({"query":a.query,"seed":a.seed,"items":scored[:a.count]},indent=2,sort_keys=True)); return 0
def index_summary(path):
    rows=[json.loads(x) for x in path.read_text().splitlines() if x.strip()]; return {"record_count":len(rows),"by_family":{f:sum(r.get("family")==f for r in rows) for f in FAMILIES}}
def receipt_validate(path):
    required={"owner","status","commit","changed","checks","result","blockers","dependencies_unlocked","proposals"}
    try: obj=load(path); missing=sorted(required-set(obj)); result={"state":"READY" if not missing else "NOT_READY","missing":missing}
    except Exception as e: result={"state":"NOT_READY","missing":[str(e)]}
    print(json.dumps(result,indent=2,sort_keys=True)); return 0 if result["state"]=="READY" else 2
if __name__=="__main__": raise SystemExit(main())
