import json,urllib.request,urllib.parse,statistics,math
BASE=os_base=None
def _base():
    import os
    return os.getenv("SIC_MARKET_BASE","https://api.binance.com")
def _get(path,params):
    url=_base()+path+"?"+urllib.parse.urlencode(params); req=urllib.request.Request(url,headers={"User-Agent":"SeeItComing/1.0"})
    with urllib.request.urlopen(req,timeout=8) as r:return json.loads(r.read().decode())
def klines(symbol="BTCUSDT",interval="1h",limit=120):
    raw=_get("/api/v3/klines",{"symbol":symbol,"interval":interval,"limit":limit})
    return [{"t":x[0],"c":float(x[4]),"v":float(x[5])} for x in raw]
def features(b):
    if len(b)<25: raise ValueError("at least 25 bars required")
    c=[x["c"] for x in b];v=[x["v"] for x in b];ret=lambda n:c[-1]/c[-1-n]-1
    mean=sum(c[-20:])/20;sd=statistics.pstdev(c[-20:]) or 1e-9;vmean=sum(v[-20:-1])/19 or 1e-9
    return {"price":c[-1],"r1":ret(1),"r6":ret(6),"r24":ret(24),"z":(c[-1]-mean)/sd,"vr":v[-1]/vmean}
def scan(symbols):
    from .models import ensemble
    out=[]
    for sym in symbols:
        try:
            f=features(klines(sym));e=ensemble(f);an=min(abs(f["z"])/3+max(f["vr"]-1,0)/4,1)
            out.append({"symbol":sym,**f,"direction":e["direction"],"confidence":e["probability"],"anomaly":round(an,3),"models":e["votes"],"source":"Binance Spot public market data"})
        except Exception as ex:out.append({"symbol":sym,"error":str(ex),"source":"unavailable"})
    return sorted(out,key=lambda x:x.get("anomaly",-1),reverse=True)

def score(f):
    e=__import__('app.models',fromlist=['ensemble']).ensemble(f)
    anomaly=min(abs(f['z'])/3+max(f['vr']-1,0)/4,1)
    return {'direction':e['direction'],'confidence':e['probability'],'anomaly':round(anomaly,3),'raw':e['raw']}
