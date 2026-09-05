#!/usr/bin/env python3
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from story_brainstorm import validate_works,validate_cards
r={"works":validate_works(),"cards":validate_cards()}; print(json.dumps(r,indent=2,sort_keys=True)); raise SystemExit(0 if all(x["state"]=="READY" for x in r.values()) else 2)
