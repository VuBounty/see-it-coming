import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
html=(ROOT/'site/index.html').read_text()
snap=json.loads((ROOT/'site/snapshot.json').read_text())
ledger=json.loads((ROOT/'data/ledger.json').read_text())
for marker in [
    'SIC-V3.3-DEMO-MATCH-FREEZE','LIVE MARKET UNIVERSE','MARKET OBSERVATION TAPE',
    'universeCanvas','FROM CHAOS TO SIGNAL','prefers-reduced-motion'
]:
    if marker not in html: raise SystemExit('missing marker: '+marker)
if snap.get('version')!='V3.3-DEMO-MATCH': raise SystemExit('wrong snapshot version')
if snap.get('universe_count',0)<30: raise SystemExit('market universe too small: '+str(snap.get('universe_count')))
if snap.get('metrics',{}).get('locked')!=len(ledger.get('predictions',[])): raise SystemExit('ledger/UI mismatch')
if 'LIVE TRADES' in html: raise SystemExit('synthetic trade label forbidden')
print('V3.3 DEMO MATCH VERIFIED · universe',snap['universe_count'],'· source',snap['universe_source'])

