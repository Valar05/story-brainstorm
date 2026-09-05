#!/usr/bin/env python3
"""Minimal stdlib validator for scaffold readiness and schema envelopes."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from story_brainstorm import validate_works,validate_cards
print(json.dumps({"works":validate_works(),"cards":validate_cards()},indent=2,sort_keys=True))
raise SystemExit(0 if validate_works()["state"]=="READY" and validate_cards()["state"]=="READY" else 2)
