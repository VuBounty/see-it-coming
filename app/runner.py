import os,time,json
from datetime import datetime,timezone
from .market import klines,features
from .experiment import make_prediction,due,resolve_from_prices
from .store import Ledger

SYMBOLS=os.getenv("SIC_SYMBOLS","BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT,DOGEUSDT").split(",")
LEDGER=Ledger(os.getenv("SIC_LEDGER","data/ledger.json"))

def unresolved(data):
    done={r["prediction_id"] for r in data["resolutions"]}
    return [p for p in data["predictions"] if p["id"] not in done]

def cycle():
    data=LEDGER.snapshot(); active={p["asset"] for p in unresolved(data) if not due(p)}
    created=[]; resolved=[]
    for sym in SYMBOLS:
        try:
            bars=klines(sym,limit=120); f=features(bars)
            if sym not in active:
                p=make_prediction(sym,f); created.append(LEDGER.add_prediction(p))
        except Exception as e: print(json.dumps({"event":"scan_error","symbol":sym,"error":str(e)}),flush=True)
    data=LEDGER.snapshot()
    for p in unresolved(data):
        if not due(p): continue
        try:
            current=features(klines(p["asset"],limit=120))["price"]
            # Entry is reconstructed from evidence-time market price only for new records that store it in evidence later;
            # until then, use a dedicated entry evidence field if present.
            entry=None
            for e in p.get("evidence",[]):
                if e.startswith("entry="): entry=float(e.split("=",1)[1])
            if entry is None: continue
            resolved.append(LEDGER.add_resolution(resolve_from_prices(p,entry,current)))
        except Exception as e: print(json.dumps({"event":"resolve_error","id":p["id"],"error":str(e)}),flush=True)
    return {"created":len(created),"resolved":len(resolved)}

def run_forever():
    interval=int(os.getenv("SIC_CYCLE_SECONDS","3600"))
    while True:
        print(json.dumps({"event":"cycle","at":datetime.now(timezone.utc).isoformat(),**cycle()}),flush=True); time.sleep(interval)
if __name__=="__main__": run_forever()
