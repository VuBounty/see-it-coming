import json, html
from pathlib import Path

ledger_path = Path("data/ledger.json")
data = json.loads(ledger_path.read_text()) if ledger_path.exists() else {"predictions": [], "resolutions": []}
preds = data.get("predictions", [])
ress = data.get("resolutions", [])
resmap = {r["prediction_id"]: r for r in ress}

def e(v): return html.escape(str(v))
def evmap(p):
    out={}
    for x in p.get("evidence",[]):
        if "=" in x:
            k,v=x.split("=",1); out[k]=v
    return out

scored=[]
for p in preds:
    r=resmap.get(p["id"])
    if r and r.get("outcome") in ("CORRECT","WRONG"):
        scored.append((float(p["probability"]),1 if r["outcome"]=="CORRECT" else 0))

n=len(scored)
correct=sum(a for _,a in scored)
accuracy=(correct/n) if n else None
brier=(sum((p-a)**2 for p,a in scored)/n) if n else None

def pct(x):
    return "—" if x is None else f"{x*100:.1f}%"
def dec(x):
    return "—" if x is None else f"{x:.3f}"

cards=[]
for p in reversed(preds[-12:]):
    r=resmap.get(p["id"])
    ev=evmap(p)
    state=(r.get("outcome") if r else "LOCKED")
    state_cls="ok" if state=="CORRECT" else ("bad" if state=="WRONG" else "lock")
    direction=p.get("direction","—")
    arrow="↑" if direction=="UP" else "↓"
    cards.append(f'''
    <article class="forecast-card">
      <div class="fc-top">
        <div><span class="label">FORECAST OBJECT</span><h3>{e(p.get("asset","—"))}</h3></div>
        <span class="state {state_cls}">{e(state)}</span>
      </div>
      <div class="fc-main">
        <div>
          <div class="dir {'up' if direction=='UP' else 'down'}">{arrow} {e(direction)}</div>
          <div class="prob">{float(p.get("probability",0))*100:.1f}<small>%</small></div>
          <span class="micro">MODEL PROBABILITY</span>
        </div>
        <div class="facts">
          <div><span>ENTRY</span><b>{e(ev.get("entry","—"))}</b></div>
          <div><span>TARGET</span><b>{e(p.get("target_pct","—"))}%</b></div>
          <div><span>HORIZON</span><b>{e(p.get("horizon_hours","—"))}H</b></div>
          <div><span>CREATED</span><b>{e(p.get("created_at","—"))[:19]}</b></div>
        </div>
      </div>
      <div class="why">
        <span class="label">WHY IT FIRED</span>
        <div class="whygrid">
          <div><span>r6</span><b>{e(ev.get("r6","—"))}</b></div>
          <div><span>r24</span><b>{e(ev.get("r24","—"))}</b></div>
          <div><span>z-score</span><b>{e(ev.get("z","—"))}</b></div>
          <div><span>volume ratio</span><b>{e(ev.get("vr","—"))}</b></div>
        </div>
      </div>
      <div class="proof">
        <span>SHA-256 PROOF</span>
        <code>{e(p.get("proof_hash","—"))}</code>
      </div>
    </article>
    ''')
cards_html="".join(cards) if cards else '<div class="empty">NO LOCKED FORECASTS YET.</div>'

bins=[(0.50,0.60),(0.60,0.70),(0.70,0.80),(0.80,0.90),(0.90,1.01)]
cal=[]
for lo,hi in bins:
    vals=[(p,a) for p,a in scored if lo<=p<hi]
    if vals:
        observed=sum(a for _,a in vals)/len(vals)
        cal.append((f"{int(lo*100)}–{int(min(1,hi)*100)}%",observed,len(vals)))
    else:
        cal.append((f"{int(lo*100)}–{int(min(1,hi)*100)}%",None,0))
cal_html=""
for band,obs,count in cal:
    width=0 if obs is None else obs*100
    cal_html+=f'''
    <div class="cal-row">
      <span>{band}</span>
      <div class="track"><i style="width:{width:.1f}%"></i></div>
      <b>{"—" if obs is None else f"{obs*100:.1f}%"}</b>
      <small>N={count}</small>
    </div>'''

page=f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#091126">
<title>SEE IT COMING. — Scientific Forward Intelligence</title>
<meta name="description" content="Forward-locked market forecasts. No edits. No deleted losses. Reality keeps the score.">
<!-- SIC-UI-2026-09-26-SCIENTIFIC-V2 -->
<style>
:root{{--bg:#08101f;--card:#101b39;--line:#2b3f75;--ice:#f8fbff;--muted:#9baed4;--cobalt:#4f7cff;--violet:#9a65ff;--coral:#ff6688;--mint:#48f0bd;--cyan:#57d9ff}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:linear-gradient(180deg,#07101f 0%,#0a1430 42%,#08101f 100%);color:var(--ice)}}
body:before{{content:"";position:fixed;inset:0;pointer-events:none;background:radial-gradient(circle at 18% 0%,rgba(79,124,255,.32),transparent 27%),radial-gradient(circle at 82% 5%,rgba(154,101,255,.28),transparent 24%),radial-gradient(circle at 70% 42%,rgba(255,102,136,.11),transparent 18%)}}
.wrap{{width:min(1240px,calc(100% - 34px));margin:auto;position:relative}}
nav{{height:80px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid rgba(151,176,230,.18)}}.brand{{font-size:20px;font-weight:950;letter-spacing:-.04em}}.brand i{{font-style:normal;color:var(--coral)}}.navstate{{font-size:10px;letter-spacing:.17em;color:#9eb2da}}.navstate b{{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--cyan);box-shadow:0 0 18px var(--cyan);margin-right:8px}}
.hero{{min-height:640px;padding:72px 0 60px;display:grid;grid-template-columns:1.06fr .94fr;gap:58px;align-items:center}}.eyebrow{{display:block;color:#8eb0ff;font-size:10px;letter-spacing:.2em;font-weight:900;margin-bottom:12px}}h1{{font-size:clamp(70px,9.5vw,138px);line-height:.78;letter-spacing:-.08em;margin:16px 0 30px}}h1 .grad{{background:linear-gradient(95deg,#6d91ff,#a66cff 55%,#ff6b8b);-webkit-background-clip:text;background-clip:text;color:transparent}}.hero p{{font-size:19px;line-height:1.65;color:var(--muted);max-width:720px}}.rules{{display:flex;gap:18px;flex-wrap:wrap;margin-top:26px;font-size:9px;letter-spacing:.13em;color:#7e92bb}}
.pulse{{position:relative;border:1px solid rgba(120,151,220,.34);border-radius:30px;padding:28px;background:linear-gradient(145deg,rgba(19,32,74,.94),rgba(8,16,35,.94));box-shadow:0 35px 100px rgba(0,0,0,.33),inset 0 0 80px rgba(79,124,255,.06)}}.pulsehead{{display:flex;justify-content:space-between;font-size:9px;letter-spacing:.14em;color:#92a6cf}}.orb{{height:230px;position:relative;display:grid;place-items:center}}.orb:before,.orb:after{{content:"";position:absolute;border-radius:50%}}.orb:before{{width:178px;height:178px;background:radial-gradient(circle,rgba(87,217,255,.12),rgba(79,124,255,.06) 42%,transparent 70%);border:1px solid rgba(87,217,255,.36);box-shadow:0 0 75px rgba(79,124,255,.28)}}.orb:after{{width:112px;height:112px;border:1px solid rgba(154,101,255,.7);box-shadow:0 0 55px rgba(154,101,255,.3)}}.orb strong{{z-index:2;font-size:18px;letter-spacing:.13em}}.pipeline{{display:grid;grid-template-columns:repeat(8,1fr);gap:5px}}.pipeline span{{border-top:1px solid rgba(130,155,220,.24);padding:10px 3px;text-align:center;font-size:7px;letter-spacing:.08em;color:#7f93bd}}
section{{padding:66px 0}}.head{{display:flex;align-items:end;justify-content:space-between;border-bottom:1px solid rgba(151,176,230,.18);padding-bottom:22px;margin-bottom:26px}}h2{{font-size:44px;letter-spacing:-.05em;margin:0}}.head p{{max-width:500px;text-align:right;color:var(--muted);line-height:1.55}}
.metrics{{display:grid;grid-template-columns:repeat(6,1fr);gap:10px}}.metric{{padding:18px;border-radius:16px;border:1px solid rgba(120,151,220,.3);background:linear-gradient(145deg,rgba(19,32,74,.76),rgba(10,19,43,.78))}}.metric span{{display:block;font-size:8px;letter-spacing:.13em;color:#8095c0;margin-bottom:10px}}.metric b{{font-size:25px}}
.forecasts{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}.forecast-card{{padding:22px;border-radius:22px;border:1px solid rgba(120,151,220,.3);background:linear-gradient(145deg,rgba(19,32,74,.9),rgba(9,18,41,.92));box-shadow:0 20px 60px rgba(0,0,0,.18)}}.fc-top{{display:flex;justify-content:space-between;align-items:start}}.fc-top h3{{font-size:20px;margin:4px 0 0}}.label{{font-size:7px;letter-spacing:.15em;color:#7f94bf}}.state{{font-size:8px;letter-spacing:.12em;border:1px solid #4a5d91;border-radius:999px;padding:7px 9px}}.state.ok{{color:var(--mint);border-color:rgba(72,240,189,.4)}}.state.bad{{color:var(--coral);border-color:rgba(255,102,136,.45)}}.state.lock{{color:#b9c6e6}}.fc-main{{display:grid;grid-template-columns:.8fr 1.2fr;gap:20px;margin-top:24px}}.dir{{font-size:13px;font-weight:900}}.dir.up{{color:var(--mint)}}.dir.down{{color:var(--coral)}}.prob{{font-size:60px;font-weight:950;letter-spacing:-.06em;line-height:1;margin-top:6px}}.prob small{{font-size:20px}}.micro{{font-size:7px;letter-spacing:.13em;color:#7188b4}}.facts{{display:grid;grid-template-columns:1fr 1fr;gap:7px}}.facts div,.whygrid div{{padding:10px;border:1px solid rgba(108,139,204,.2);border-radius:10px;background:rgba(5,12,29,.32)}}.facts span,.whygrid span{{display:block;font-size:7px;color:#7188b4;letter-spacing:.1em;margin-bottom:5px}}.facts b,.whygrid b{{font-size:10px;word-break:break-word}}.why{{margin-top:18px;padding-top:16px;border-top:1px solid rgba(151,176,230,.16)}}.whygrid{{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-top:10px}}.proof{{margin-top:14px;padding-top:12px;border-top:1px solid rgba(151,176,230,.16)}}.proof span{{display:block;font-size:7px;color:#7085ad;letter-spacing:.12em}}.proof code{{display:block;margin-top:6px;color:#9db0d7;font-size:8px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.science{{display:grid;grid-template-columns:.9fr 1.1fr;gap:14px}}.science-card{{padding:24px;border-radius:20px;border:1px solid rgba(120,151,220,.3);background:linear-gradient(145deg,rgba(19,32,74,.78),rgba(9,18,41,.8))}}.science-card h3{{font-size:26px;margin:0 0 8px}}.science-card p{{font-size:13px;color:var(--muted);line-height:1.55}}.cal-row{{display:grid;grid-template-columns:65px 1fr 58px 42px;gap:9px;align-items:center;margin:13px 0;font-size:10px}}.track{{height:8px;border-radius:99px;background:#17284f;overflow:hidden}}.track i{{display:block;height:100%;background:linear-gradient(90deg,var(--cobalt),var(--violet),var(--coral))}}.cal-row small{{color:#788db8}}.anatomy{{display:grid;grid-template-columns:repeat(9,1fr);gap:5px;margin-top:20px}}.anatomy div{{padding:13px 4px;text-align:center;border:1px solid rgba(120,151,220,.26);border-radius:9px;font-size:7px;letter-spacing:.08em;color:#8ba0ca}}.anatomy div:nth-child(5){{border-color:rgba(154,101,255,.75);color:#c8adff}}.anatomy div:nth-child(6){{border-color:rgba(255,102,136,.7);color:#ffa2b7}}
.manifesto{{margin:65px 0 85px;padding:46px;border-radius:27px;border:1px solid rgba(118,151,224,.4);background:linear-gradient(115deg,rgba(79,124,255,.18),rgba(154,101,255,.13),rgba(255,102,136,.1))}}.manifesto h3{{font-size:53px;letter-spacing:-.055em;margin:7px 0 13px}}.manifesto p{{max-width:840px;color:#a6b6d7;font-size:17px;line-height:1.65}}.empty{{padding:44px;border:1px dashed #455c91;border-radius:18px;color:#9eafd2}}
footer{{display:flex;justify-content:space-between;padding:28px 0 44px;border-top:1px solid rgba(151,176,230,.18);color:#7388b2;font-size:9px;letter-spacing:.11em}}
@media(max-width:950px){{.hero,.science{{grid-template-columns:1fr}}.metrics{{grid-template-columns:repeat(3,1fr)}}.forecasts{{grid-template-columns:1fr}}.head{{display:block}}.head p{{text-align:left}}}}
@media(max-width:620px){{h1{{font-size:62px}}.metrics{{grid-template-columns:1fr 1fr}}.pipeline{{grid-template-columns:repeat(4,1fr)}}.fc-main{{grid-template-columns:1fr}}.whygrid{{grid-template-columns:1fr 1fr}}.anatomy{{grid-template-columns:repeat(3,1fr)}}footer{{display:block;line-height:2}}}}
</style>
</head>
<body><div class="wrap">
<nav><div class="brand">SEE IT COMING<i>.</i></div><div class="navstate"><b></b>PUBLIC FORWARD EXPERIMENT · V1.0</div></nav>

<section class="hero">
<div>
<span class="eyebrow">THE MOVE HASN'T HAPPENED YET.</span>
<h1>SEE IT<br><span class="grad">BEFORE</span><br>IT MOVES.</h1>
<p>Predictions are locked before outcomes. No edits. No deleted losses. Reality keeps the score.</p>
<div class="rules"><span>FORWARD ONLY</span><span>PUBLIC PROOF</span><span>NO BACKFILLING</span><span>NO TRADE EXECUTION</span></div>
</div>
<div class="pulse">
<div class="pulsehead"><span>LIVE INTELLIGENCE PIPELINE</span><span>PUBLIC RECORD</span></div>
<div class="orb"><strong>OBSERVE</strong></div>
<div class="pipeline"><span>OBSERVE</span><span>DETECT</span><span>PREDICT</span><span>LOCK</span><span>WAIT</span><span>RESOLVE</span><span>SCORE</span><span>LEARN</span></div>
</div>
</section>

<section>
<div class="head"><div><span class="eyebrow">SCIENTIFIC SCOREBOARD</span><h2>Reality keeps the score.</h2></div><p>Sample size lives beside performance. Confidence is evaluated — never celebrated by itself.</p></div>
<div class="metrics">
<div class="metric"><span>LOCKED FORECASTS</span><b>{len(preds)}</b></div>
<div class="metric"><span>RESOLVED</span><b>{n}</b></div>
<div class="metric"><span>CORRECT</span><b>{correct}</b></div>
<div class="metric"><span>ACCURACY</span><b>{pct(accuracy)}</b></div>
<div class="metric"><span>BRIER SCORE</span><b>{dec(brier)}</b></div>
<div class="metric"><span>EDGE STATUS</span><b>{"INSUFFICIENT DATA" if n < 50 else "EVALUATING"}</b></div>
</div>
</section>

<section>
<div class="head"><div><span class="eyebrow">FORWARD-LOCKED FORECASTS</span><h2>Prediction → proof → outcome.</h2></div><p>Every forecast is a scientific object with direction, probability, evidence, horizon and immutable proof.</p></div>
<div class="forecasts">{cards_html}</div>
</section>

<section>
<div class="head"><div><span class="eyebrow">MODEL SCIENCE</span><h2>Confidence must earn trust.</h2></div><p>A 70% forecast is meaningful only when comparable forecasts resolve correctly around 70% of the time.</p></div>
<div class="science">
<div class="science-card"><span class="eyebrow">CALIBRATION</span><h3>Predicted vs observed.</h3><p>Observed success rate inside each confidence band. Empty bins remain visibly empty.</p>{cal_html}</div>
<div class="science-card"><span class="eyebrow">PREDICTION ANATOMY</span><h3>A complete chain of custody.</h3><p>Observation, inference, commitment and outcome are separated so a later result cannot silently rewrite the original call.</p>
<div class="anatomy"><div>OBSERVATION</div><div>FEATURES</div><div>MODEL VOTES</div><div>ENSEMBLE</div><div>PROBABILITY</div><div>LOCK</div><div>WAIT</div><div>RESOLUTION</div><div>SCORE</div></div>
</div>
</div>
</section>

<div class="manifesto">
<span class="eyebrow">THE STANDARD</span>
<h3>DON'T TRUST THE MODEL.<br>CHECK THE RECORD.</h3>
<p>Every call is timestamped before the outcome. Every loss remains public. A signal is not an edge, and a streak is not evidence. Credibility must be earned through forward observations, calibration and honest scoring.</p>
</div>

<footer><span>SEE IT COMING. · PROOF BEFORE PERSUASION.</span><span>EXPERIMENTAL · NOT FINANCIAL ADVICE</span></footer>
</div></body></html>'''

out=Path("site")
out.mkdir(exist_ok=True)
(out/"index.html").write_text(page)
(out/"ledger.json").write_text(json.dumps(data,indent=2))
print("Built SCIENTIFIC V2 UI:", out/"index.html")
