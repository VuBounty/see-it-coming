from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse
import json,os,html
from .store import Ledger
from .metrics import brier,accuracy
from .market import scan
from .analytics import report
LEDGER=Ledger(os.getenv("SIC_LEDGER","data/ledger.json"))
SYMBOLS="BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT,DOGEUSDT".split(",")
CSS="""body{margin:0;background:#07090d;color:#f5f7fb;font:14px system-ui}.s{width:min(1180px,calc(100% - 32px));margin:auto}nav{height:74px;border-bottom:1px solid #1b2230;display:flex;align-items:center;justify-content:space-between}.brand{font-weight:900;font-size:18px}.a,.up{color:#d9ff63}.down{color:#ff707a}.hero{padding:65px 0 38px;display:grid;grid-template-columns:1fr .95fr;gap:48px;align-items:center}.ey{font-size:11px;color:#d9ff63;letter-spacing:.16em;font-weight:800}h1{font-size:clamp(60px,8vw,105px);line-height:.86;letter-spacing:-.07em;margin:15px 0 25px}.lead{font-size:19px;color:#a6afbf}.tiny{font-size:11px;color:#6e788a}.panel{background:linear-gradient(#111722,#0b1017);border:1px solid #252e3e;border-radius:20px;padding:24px}.top{display:flex;justify-content:space-between}.tag{border:1px solid #30394a;border-radius:99px;padding:5px 8px;font-size:10px}.ticker{font-size:31px;font-weight:900;margin-top:28px}.prob{font-size:72px;font-weight:950;line-height:1;margin-top:15px}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:20px}.metric,.box{padding:13px;border:1px solid #1d2531;border-radius:11px}.metric span,.box span{display:block;color:#6f7a8c;font-size:9px;text-transform:uppercase}.section{padding:42px 0}.head{display:flex;justify-content:space-between;align-items:end}.head h2{font-size:34px}.head p{color:#788396}.table{border:1px solid #1c2430;border-radius:16px;overflow:hidden}.row{display:grid;grid-template-columns:1.4fr 1fr 1fr 1fr 1fr;padding:14px 18px;border-bottom:1px solid #171e29}.h{font-size:10px;color:#667184;text-transform:uppercase}.proof{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.box b{font-size:21px}.empty{color:#6f7989;padding:24px;border:1px dashed #242c38;border-radius:14px}.note{margin:55px 0 80px;padding:34px;border:1px solid #202735;border-radius:18px}.note h2{font-size:38px;margin:8px 0}.note p{color:#8792a4}footer{border-top:1px solid #171d27;padding:25px 0 40px;color:#626c7c;font-size:11px;display:flex;justify-content:space-between}@media(max-width:800px){.hero{grid-template-columns:1fr}.proof{grid-template-columns:1fr 1fr}.row{grid-template-columns:1.3fr 1fr 1fr}.row>*:nth-child(4),.row>*:nth-child(5){display:none}}"""
def page():
    live=scan(SYMBOLS); valid=[x for x in live if "error" not in x]; d=LEDGER.snapshot()
    if valid:
        x=valid[0]; cls="up" if x["direction"]=="UP" else "down"; arrow="↑" if x["direction"]=="UP" else "↓"
        card='<div class="panel"><div class="top"><span class="ey">TOP ANOMALY NOW</span><span class="tag">LIVE MARKET DATA</span></div><div class="ticker">%s</div><div class="%s">%s %s BIAS</div><div class="prob">%.0f%%</div><div class="tiny">EXPERIMENTAL MODEL CONFIDENCE · NOT A VERIFIED EDGE</div><div class="grid"><div class="metric"><span>Price</span><b>%.5g</b></div><div class="metric"><span>24H Momentum</span><b>%+.2f%%</b></div><div class="metric"><span>Anomaly</span><b>%.0f/100</b></div></div></div>'%(x["symbol"],cls,arrow,x["direction"],x["confidence"]*100,x["price"],x["r24"]*100,x["anomaly"]*100)
    else: card='<div class="panel"><div class="ey">MARKET FEED UNAVAILABLE</div><p class="lead">The system will not fabricate live signals. Refresh when public market data is reachable.</p></div>'
    rows=""
    for x in valid:
        cls="up" if x["direction"]=="UP" else "down"
        rows+='<div class="row"><b>%s</b><span>%.5g</span><span class="%s">%s</span><span>%.0f%%</span><span>%.0f/100</span></div>'%(x["symbol"],x["price"],cls,x["direction"],x["confidence"]*100,x["anomaly"]*100)
    if not rows: rows='<div class="empty">Live market data is temporarily unavailable. No synthetic signal is being shown.</div>'
    rs={r["prediction_id"]:r for r in d["resolutions"]}; scored=[]
    for p in d["predictions"]:
        r=rs.get(p["id"])
        if r and r["outcome"] in ("CORRECT","WRONG"): scored.append({"probability":p["probability"],"actual":1 if r["outcome"]=="CORRECT" else 0})
    ac=accuracy(scored); br=brier(scored)
    return """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SEE IT COMING.</title><style>%s</style></head><body><div class="s"><nav><div class="brand">SEE IT COMING<span class="a">.</span></div><div class="tiny"><span class="a">●</span> LIVE INTELLIGENCE · V1</div></nav><section class="hero"><div><div class="ey">PUBLIC INTELLIGENCE EXPERIMENT</div><h1>SEE IT<br>COMING.</h1><p class="lead">Markets move before headlines do. We scan unusual conditions, publish probability, lock the prediction, and keep the outcome.</p><p class="tiny">NO DEPOSIT · NO TRADE BUTTON · NO DELETED LOSSES</p></div>%s</section><section class="section"><div class="head"><h2>Market radar.</h2><p>Public spot data · 1H observations</p></div><div class="table"><div class="row h"><span>Asset</span><span>Price</span><span>Bias</span><span>Confidence</span><span>Anomaly</span></div>%s</div></section><section class="section"><div class="head"><h2>Public proof.</h2><p>Performance begins at zero. No backfilled marketing history.</p></div><div class="proof"><div class="box"><span>Locked</span><b>%d</b></div><div class="box"><span>Resolved</span><b>%d</b></div><div class="box"><span>Accuracy</span><b>%s</b></div><div class="box"><span>Brier Score</span><b>%s</b></div></div></section><section class="note"><div class="ey">THE STANDARD</div><h2>Proof before persuasion.</h2><p>A live market score is not a verified prediction record. Predictive edge is earned only after forward-locked calls resolve.</p></section><footer><span>SEE IT COMING. · INTELLIGENCE, NOT HYPE.</span><span>BEFORE IT MOVES.</span></footer></div></body></html>"""%(CSS,card,rows,len(d["predictions"]),len(d["resolutions"]),"—" if ac is None else "%.1f%%"%(ac*100),"—" if br is None else "%.3f"%br)
class Handler(BaseHTTPRequestHandler):
    def sendj(self,c,o):
        b=json.dumps(o).encode();self.send_response(c);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
    def do_GET(self):
        p=urlparse(self.path).path
        if p=="/":
            b=page().encode();self.send_response(200);self.send_header("Content-Type","text/html; charset=utf-8");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b);return
        if p=="/health":return self.sendj(200,{"status":"ok","product":"SEE-IT-COMING","version":"1.0-complete"})
        if p=="/api/radar":return self.sendj(200,scan(SYMBOLS))
        if p=="/api/predictions":return self.sendj(200,LEDGER.snapshot())
        if p=="/api/stats":return self.sendj(200,report(LEDGER.snapshot()))
        return self.sendj(404,{"error":"not found"})
    def log_message(self,*args):pass
def run(host="127.0.0.1",port=8080):
    print("SEE IT COMING. COMPLETE V1 on http://%s:%s"%(host,port));ThreadingHTTPServer((host,port),Handler).serve_forever()
if __name__=="__main__":run(port=int(os.getenv("PORT","8080")))
