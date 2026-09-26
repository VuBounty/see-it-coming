import os,time,json
from datetime import datetime,timezone
from .market import klines_with_source,features
from .experiment import make_prediction,due,resolve_from_prices
from .store import Ledger
SYMBOLS=os.getenv("SIC_SYMBOLS","BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT,DOGEUSDT").split(",");LEDGER=Ledger(os.getenv("SIC_LEDGER","data/ledger.json"));MIN_CONFIDENCE=float(os.getenv("SIC_MIN_CONFIDENCE","0.53"))
def unresolved(d):
    done={r["prediction_id"] for r in d["resolutions"]};return[p for p in d["predictions"] if p["id"] not in done]
def cycle():
    d=LEDGER.snapshot();active={p["asset"] for p in unresolved(d) if not due(p)};created=[];resolved=[];abstained=[];sources={}
    for sym in SYMBOLS:
        try:
            bars,src=klines_with_source(sym,limit=120);sources[sym]=src;f=features(bars)
            if sym not in active:
                p=make_prediction(sym,f)
                if p.probability>=MIN_CONFIDENCE:created.append(LEDGER.add_prediction(p))
                else:abstained.append(sym)
        except Exception as e:print(json.dumps({"event":"scan_error","symbol":sym,"error":str(e)}),flush=True)
    for p in unresolved(LEDGER.snapshot()):
        if not due(p):continue
        try:
            bars,_=klines_with_source(p["asset"],limit=120);current=features(bars)["price"];entry=next((float(e.split("=",1)[1]) for e in p.get("evidence",[]) if e.startswith("entry=")),None)
            if entry is not None:resolved.append(LEDGER.add_resolution(resolve_from_prices(p,entry,current)))
        except Exception as e:print(json.dumps({"event":"resolve_error","id":p["id"],"error":str(e)}),flush=True)
    return {"created":len(created),"resolved":len(resolved),"abstained":len(abstained),"providers":sources}
def run_forever():
    interval=int(os.getenv("SIC_CYCLE_SECONDS","3600"))
    while True:print(json.dumps({"event":"cycle","at":datetime.now(timezone.utc).isoformat(),**cycle()}),flush=True);time.sleep(interval)
if __name__=="__main__":run_forever()
