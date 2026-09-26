#!/usr/bin/env python3
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.verify import verify
p=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'data/ledger.json'
e=verify(json.load(open(p)))
print('LEDGER VERIFIED' if not e else '\n'.join(e))
raise SystemExit(1 if e else 0)
