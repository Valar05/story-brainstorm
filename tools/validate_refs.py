#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from story_brainstorm import validate_cards,build_index,read_cards
r=validate_cards(Path(sys.argv[1]) if len(sys.argv)>1 else Path("data/primitive_cards.json")); print(r); raise SystemExit(0 if r["state"]=="READY" else 2)
