import json, urllib.request, urllib.parse, statistics, os, time
UA={"User-Agent":"SEE-IT-COMING/1.1 (+https://github.com/VuBounty/see-it-coming)"}
def _json(url,timeout=10):
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=timeout) as r:return json.loads(r.read().decode())
def _binance(symbol,interval="1h",limit=120):
    q=urllib.parse.urlencode({"symbol":symbol,"interval":interval,"limit":limit})
    raw=_json(os.getenv("SIC_BINANCE_BASE","https://api.binance.com")+"/api/v3/klines?"+q)
    return [{"t":int(x[0]),"c":float(x[4]),"v":float(x[5])} for x in raw],"Binance"
def _coinbase(symbol,interval="1h",limit=120):
    product=symbol.replace("USDT","-USD"); granularity=3600; end=int(time.time()); start=end-(limit+5)*granularity
    q=urllib.parse.urlencode({"granularity":granularity,"start":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime(start)),"end":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime(end))})
    raw=_json("https://api.exchange.coinbase.com/products/%s/candles?%s"%(product,q))
    rows=[{"t":int(x[0])*1000,"c":float(x[4]),"v":float(x[5])} for x in raw]; rows.sort(key=lambda x:x["t"])
    if len(rows)<25: raise ValueError("Coinbase insufficient bars")
    return rows[-limit:],"Coinbase Exchange"
def _kraken(symbol,interval="1h",limit=120):
    pair={"BTCUSD":"XBTUSD","DOGEUSD":"XDGUSD"}.get(symbol.replace("USDT","USD"),symbol.replace("USDT","USD"))
    raw=_json("https://api.kraken.com/0/public/OHLC?"+urllib.parse.urlencode({"pair":pair,"interval":60}))
    if raw.get("error"): raise RuntimeError(";".join(raw["error"]))
    key=next(k for k in raw["result"] if k!="last")
    rows=[{"t":int(x[0])*1000,"c":float(x[4]),"v":float(x[6])} for x in raw["result"][key]]
    if len(rows)<25: raise ValueError("Kraken insufficient bars")
    return rows[-limit:],"Kraken"
def klines_with_source(symbol="BTCUSDT",interval="1h",limit=120):
    errors=[]
    for fn in (_binance,_coinbase,_kraken):
        try:
            b,s=fn(symbol,interval,limit)
            if len(b)>=25:return b,s
        except Exception as e:errors.append(f"{fn.__name__}:{e}")
    raise RuntimeError("all market providers unavailable | "+" | ".join(errors))
def klines(symbol="BTCUSDT",interval="1h",limit=120):return klines_with_source(symbol,interval,limit)[0]
def features(b):
    if len(b)<25:raise ValueError("at least 25 bars required")
    c=[x["c"] for x in b];v=[x["v"] for x in b];ret=lambda n:c[-1]/c[-1-n]-1;mean=sum(c[-20:])/20;sd=statistics.pstdev(c[-20:]) or 1e-9;vmean=sum(v[-20:-1])/19 or 1e-9
    return {"price":c[-1],"r1":ret(1),"r6":ret(6),"r24":ret(24),"z":(c[-1]-mean)/sd,"vr":v[-1]/vmean}
def score(f):
    from .models import ensemble
    e=ensemble(f);a=min(abs(f["z"])/3+max(f["vr"]-1,0)/4,1);return {"direction":e["direction"],"confidence":e["probability"],"anomaly":round(a,3),"raw":e["raw"]}
def scan(symbols):
    from .models import ensemble
    out=[]
    for sym in symbols:
        try:
            b,src=klines_with_source(sym);f=features(b);e=ensemble(f);a=min(abs(f["z"])/3+max(f["vr"]-1,0)/4,1)
            out.append({"symbol":sym,**f,"direction":e["direction"],"confidence":e["probability"],"anomaly":round(a,3),"models":e["votes"],"source":src})
        except Exception as ex:out.append({"symbol":sym,"error":str(ex),"source":"unavailable"})
    return sorted(out,key=lambda x:x.get("anomaly",-1),reverse=True)
