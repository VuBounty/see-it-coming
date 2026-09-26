import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pathlib import Path
import json, html
from app.metrics import accuracy,brier
ledger=Path("data/ledger.json")
d=json.loads(ledger.read_text()) if ledger.exists() else {"predictions":[],"resolutions":[]}
pred=d.get("predictions",[]); res=d.get("resolutions",[])
rm={r["prediction_id"]:r for r in res}; scored=[]
for p in pred:
    r=rm.get(p["id"])
    if r and r["outcome"] in ("CORRECT","WRONG"):
        scored.append({"probability":p["probability"],"actual":1 if r["outcome"]=="CORRECT" else 0})
acc=accuracy(scored); bs=brier(scored)
rows=""
for p in reversed(pred[-100:]):
    r=rm.get(p["id"]); outcome=r["outcome"] if r else "LOCKED"
    rows += "<tr><td>{}</td><td>{}</td><td>{:.0f}%</td><td>{}H</td><td>{}</td><td><code>{}</code></td></tr>".format(
        html.escape(p["asset"]),html.escape(p["direction"]),p["probability"]*100,p["horizon_hours"],html.escape(outcome),html.escape(p["id"]))
if not rows: rows='<tr><td colspan="6" class="empty">The public experiment starts at zero. No backfilled predictions.</td></tr>'
accs="—" if acc is None else "{:.1f}%".format(acc*100)
bss="—" if bs is None else "{:.3f}".format(bs)
page='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SEE IT COMING.</title>
<style>body{margin:0;background:#07090d;color:#f5f7fb;font:14px system-ui}.s{width:min(1120px,calc(100% - 30px));margin:auto}nav{height:72px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #1d2430}.brand{font-weight:900;font-size:19px}.a{color:#d9ff63}h1{font-size:clamp(58px,9vw,110px);line-height:.85;letter-spacing:-.07em;margin:75px 0 25px}.lead{font-size:19px;color:#9aa5b7;max-width:680px}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:50px 0}.box{border:1px solid #202837;border-radius:14px;padding:18px}.box span{display:block;color:#758094;font-size:10px;text-transform:uppercase}.box b{font-size:24px}table{width:100%;border-collapse:collapse;border:1px solid #202837}th,td{padding:13px;text-align:left;border-bottom:1px solid #1a2130}th{font-size:10px;color:#758094;text-transform:uppercase}code{font-size:10px;color:#8d98aa}.empty{color:#788396}.note{margin:55px 0;padding:28px;border:1px solid #202837;border-radius:16px;color:#8994a6}footer{margin-top:60px;border-top:1px solid #1d2430;padding:25px 0 45px;color:#657084}@media(max-width:700px){.stats{grid-template-columns:1fr 1fr}table{font-size:11px}th:nth-child(6),td:nth-child(6){display:none}}</style></head><body><div class="s">
<nav><div class="brand">SEE IT COMING<span class="a">.</span></div><div><span class="a">●</span> PUBLIC FORWARD TEST</div></nav>
<h1>PROOF<br>BEFORE<br>PERSUASION.</h1><p class="lead">Every prediction is created before its outcome. Wins stay. Losses stay. The experiment is scored in public.</p>
<div class="stats"><div class="box"><span>Predictions</span><b>__P__</b></div><div class="box"><span>Resolved</span><b>__R__</b></div><div class="box"><span>Accuracy</span><b>__A__</b></div><div class="box"><span>Brier</span><b>__B__</b></div></div>
<h2>PUBLIC LEDGER</h2><table><thead><tr><th>Asset</th><th>Direction</th><th>Confidence</th><th>Horizon</th><th>Outcome</th><th>ID</th></tr></thead><tbody>__ROWS__</tbody></table>
<div class="note"><b>Scientific boundary.</b><br>A model is not considered to have predictive edge merely because it produces signals. Evidence requires forward-locked predictions, resolved outcomes, sufficient sample size, calibration, and comparison against baselines.</div>
<footer>SEE IT COMING. · INTELLIGENCE, NOT HYPE.</footer></div></body></html>'''
page=page.replace("__P__",str(len(pred))).replace("__R__",str(len(res))).replace("__A__",accs).replace("__B__",bss).replace("__ROWS__",rows)
out=Path("site"); out.mkdir(exist_ok=True); (out/"index.html").write_text(page); (out/"ledger.json").write_text(json.dumps(d,indent=2))
print("Built site/index.html and site/ledger.json")
