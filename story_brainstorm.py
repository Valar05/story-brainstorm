#!/usr/bin/env python3
"""Deterministic, source-first narrative primitive research scaffold."""
from __future__ import annotations
import argparse, hashlib, json, os, tempfile
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parent
RIGHTS={"PD_US_CONFIRMED"}
FAMILIES={"story","speech","character","conflict","structure","contextual"}
def normalize_for_hash(value: Any)->Any:
    if isinstance(value,dict): return {k:normalize_for_hash(v) for k,v in value.items() if k not in {"created_at","generated_at","updated_at","retrieved_at"}}
    if isinstance(value,list): return [normalize_for_hash(v) for v in value]
    return value
def stable_hash(value: Any)->str:
    raw=json.dumps(normalize_for_hash(value),sort_keys=True,ensure_ascii=False,separators=(",",":"))
    return hashlib.sha256(raw.encode()).hexdigest()
def atomic_write(path:Path, text:str)->bool:
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8")==text: return False
    with tempfile.NamedTemporaryFile("w",encoding="utf-8",dir=path.parent,delete=False) as f: f.write(text); tmp=Path(f.name)
    tmp.replace(path); return True
def load(path:Path)->dict[str,Any]: return json.loads(path.read_text(encoding="utf-8"))
def validate_works(path:Path=ROOT/"data/works.json")->dict[str,Any]:
    works=load(path).get("works",[]); errors=[]; ids=set()
    for w in works:
        if w.get("work_id") in ids: errors.append("duplicate work_id")
        ids.add(w.get("work_id"))
        if w.get("publication_year",1930)>1929: errors.append(f"post-1929 work: {w.get('work_id')}")
        rights=w.get("rights",{});
        if rights.get("status") not in RIGHTS: errors.append(f"unaccepted rights: {w.get('work_id')}")
        if not rights.get("verification_refs"): errors.append(f"missing rights refs: {w.get('work_id')}")
    ready=not errors and len(works)>=100
    return {"state":"READY" if ready else "NOT_READY","accepted_works":len(works),"required_works":100,"errors":errors}
def validate_cards(path:Path=ROOT/"data/primitive_cards.json")->dict[str,Any]:
    cards=load(path).get("cards",[]); errors=[]; ids=set(); counts={f:0 for f in FAMILIES}
    for c in cards:
        cid=c.get("primitive_id"); fam=c.get("family")
        if cid in ids: errors.append(f"duplicate primitive_id: {cid}")
        ids.add(cid)
        if fam not in FAMILIES: errors.append(f"invalid family: {fam}")
        else: counts[fam]+=1
        if c.get("confidence")!="accepted": errors.append(f"non-accepted card: {cid}")
        if not c.get("evidence"): errors.append(f"missing evidence: {cid}")
        for e in c.get("evidence",[]):
            if e.get("excerpt_words",26)>25: errors.append(f"excerpt too long: {cid}")
    ready=not errors and len(cards)>=1000
    return {"state":"READY" if ready else "NOT_READY","accepted_cards":len(cards),"required_cards":1000,"family_counts":counts,"errors":errors}
def main()->int:
    p=argparse.ArgumentParser(description="Story Brainstorm narrative primitive research")
    sub=p.add_subparsers(dest="command",required=True); w=sub.add_parser("works"); ws=w.add_subparsers(dest="action",required=True); v=ws.add_parser("validate"); v.set_defaults(fn=lambda:validate_works())
    c=sub.add_parser("cards"); cs=c.add_subparsers(dest="action",required=True); cv=cs.add_parser("validate"); cv.set_defaults(fn=lambda:validate_cards())
    ls=sub.add_parser("list"); ls.add_argument("--family",choices=sorted(FAMILIES)); ls.set_defaults(fn=lambda:{"state":"NOT_READY","items":[]})
    args=p.parse_args(); result=args.fn(); print(json.dumps(result,indent=2,sort_keys=True)); return 0 if result.get("state")=="READY" else 2
if __name__=="__main__": raise SystemExit(main())
