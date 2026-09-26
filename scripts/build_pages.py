import sys, json, html
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.market import scan, klines_with_source

LEDGER = ROOT / "data" / "ledger.json"
OUT = ROOT / "site"
OUT.mkdir(exist_ok=True)

data = json.loads(LEDGER.read_text()) if LEDGER.exists() else {"predictions": [], "resolutions": []}
preds = data.get("predictions", [])
ress = data.get("resolutions", [])
resmap = {r["prediction_id"]: r for r in ress}
SYMBOLS = ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","DOGEUSDT"]

def esc(v):
    return html.escape(str(v))

def evmap(p):
    out = {}
    for item in p.get("evidence", []):
        if "=" in item:
            k, v = item.split("=", 1)
            out[k] = v
    return out

try:
    radar = scan(SYMBOLS)
except Exception as ex:
    radar = [{"symbol": s, "error": str(ex), "source": "unavailable"} for s in SYMBOLS]

valid = [x for x in radar if "error" not in x]
valid_map = {x["symbol"]: x for x in valid}
data_health = f"{len(valid)}/{len(SYMBOLS)}"
system_state = "LIVE" if len(valid) == len(SYMBOLS) else ("DEGRADED" if valid else "NO DATA")

scored = []
for p in preds:
    r = resmap.get(p["id"])
    if r and r.get("outcome") in ("CORRECT", "WRONG"):
        scored.append((float(p["probability"]), 1 if r["outcome"] == "CORRECT" else 0))

n_res = len(scored)
correct = sum(a for _, a in scored)
accuracy = correct / n_res if n_res else None
brier = sum((q-a)**2 for q, a in scored) / n_res if n_res else None

def pct(x):
    return "—" if x is None else f"{x*100:.1f}%"

def dec(x):
    return "—" if x is None else f"{x:.3f}"

latest = preds[-1] if preds else None
latest_ev = evmap(latest) if latest else {}
latest_res = resmap.get(latest["id"]) if latest else None

positions = [(8,12),(37,5),(68,13),(12,59),(42,69),(70,59)]
chips = []
for i, s in enumerate(SYMBOLS):
    x = valid_map.get(s)
    left, top = positions[i]
    if x:
        mv = x.get("r24", 0) * 100
        cls = "gain" if mv >= 0 else "loss"
        arrow = "↑" if mv >= 0 else "↓"
        chips.append(f'''
        <div class="coin-chip {cls}" style="left:{left}%;top:{top}%">
          <div class="coin-row"><b>{esc(s.replace("USDT",""))}</b><span>{arrow} {mv:+.2f}%</span></div>
          <svg viewBox="0 0 100 24" preserveAspectRatio="none">
            <polyline points="0,16 10,13 20,18 30,10 40,12 50,7 60,11 70,5 80,9 90,4 100,6"/>
          </svg>
        </div>''')
    else:
        chips.append(f'''
        <div class="coin-chip stale" style="left:{left}%;top:{top}%">
          <div class="coin-row"><b>{esc(s.replace("USDT",""))}</b><span>NO DATA</span></div>
        </div>''')
chips_html = "".join(chips)

noise_rows = []
for s in SYMBOLS:
    x = valid_map.get(s)
    if x:
        mv = x.get("r24", 0) * 100
        cls = "pos" if mv >= 0 else "neg"
        noise_rows.append(
            f"<tr><td>{esc(s.replace('USDT',''))}</td><td>{x['price']:.8g}</td>"
            f"<td class='{cls}'>{mv:+.2f}%</td><td>{esc(x.get('source',''))}</td></tr>"
        )
    else:
        noise_rows.append(f"<tr><td>{esc(s.replace('USDT',''))}</td><td>—</td><td>—</td><td>unavailable</td></tr>")
noise_html = "".join(noise_rows)

tape = []
for x in valid[:6]:
    cls = "pos" if x.get("r24", 0) >= 0 else "neg"
    tape.append(
        f"<div class='tape-row'><span class='t-time'>NOW</span><b>{esc(x['symbol'].replace('USDT',''))}</b>"
        f"<span>{x['price']:.8g}</span><em class='{cls}'>{x.get('r24',0)*100:+.2f}%</em></div>"
    )
tape_html = "".join(tape) if tape else "<div class='tape-row'><span>—</span><b>MARKET FEED</b><span>UNAVAILABLE</span><em>—</em></div>"

chart_asset = latest["asset"] if latest else "BTCUSDT"
chart_source = "unavailable"
try:
    bars, chart_source = klines_with_source(chart_asset, limit=48)
    prices = [float(b["c"]) for b in bars[-36:]]
    lo, hi = min(prices), max(prices)
    span = (hi - lo) or 1
    pts = []
    for i, price in enumerate(prices):
        xx = i / (len(prices)-1) * 100
        yy = 88 - ((price-lo)/span)*70
        pts.append(f"{xx:.2f},{yy:.2f}")
    chart_points = " ".join(pts)
except Exception:
    chart_points = "0,60 15,48 30,52 45,42 60,44 75,35 100,31"

if latest:
    direction = latest.get("direction", "—")
    arrow = "↑" if direction == "UP" else "↓"
    dir_cls = "up" if direction == "UP" else "down"
    state = latest_res.get("outcome") if latest_res else "LOCKED"
    latest_block = f'''
    <div class="asset-lock">
      <div class="asset-icon">{esc(latest["asset"].replace("USDT","")[:2])}</div>
      <div>
        <h3>{esc(latest["asset"].replace("USDT",""))} / USD</h3>
        <div class="lock-dir {dir_cls}">{arrow} {esc(direction)}</div>
        <div class="lock-prob">{float(latest.get("probability",0))*100:.1f}<small>%</small></div>
        <span class="micro">MODEL PROBABILITY</span>
      </div>
    </div>
    <div class="forecast-facts">
      <div><span>Entry observation</span><b>{esc(latest_ev.get("entry","—"))}</b></div>
      <div><span>Target move</span><b>{esc(latest.get("target_pct","—"))}%</b></div>
      <div><span>Horizon</span><b>{esc(latest.get("horizon_hours","—"))}H</b></div>
      <div><span>Decision threshold</span><b>53.0%</b></div>
      <div><span>Locked at</span><b>{esc(latest.get("created_at","—"))[:19]} UTC</b></div>
      <div><span>Status</span><b>{esc(state)}</b></div>
    </div>'''
    def w(v, scale, base=22):
        try:
            return min(100, abs(float(v))*scale + base)
        except Exception:
            return base
    why_block = f'''
    <div class="why-row"><span>Momentum 6H</span><i style="width:{w(latest_ev.get("r6","0"),1800):.0f}%"></i><b>{esc(latest_ev.get("r6","—"))}</b></div>
    <div class="why-row"><span>Momentum 24H</span><i style="width:{w(latest_ev.get("r24","0"),900):.0f}%"></i><b>{esc(latest_ev.get("r24","—"))}</b></div>
    <div class="why-row"><span>Price deviation</span><i style="width:{w(latest_ev.get("z","0"),28):.0f}%"></i><b>{esc(latest_ev.get("z","—"))}</b></div>
    <div class="why-row"><span>Volume ratio</span><i style="width:{w(latest_ev.get("vr","0"),42,18):.0f}%"></i><b>{esc(latest_ev.get("vr","—"))}</b></div>'''
    proof_hash = latest.get("proof_hash", "—")
else:
    latest_block = '<div class="empty-state">NO LOCKED FORECAST YET</div>'
    why_block = '<div class="empty-state">WAITING FOR QUALIFIED SIGNAL</div>'
    proof_hash = "—"

bins = [(0.50,0.60),(0.60,0.70),(0.70,0.80),(0.80,0.90),(0.90,1.01)]
cal_rows = []
for lo, hi in bins:
    vals = [(p,a) for p,a in scored if lo <= p < hi]
    obs = (sum(a for _,a in vals)/len(vals)) if vals else None
    obs_text = "—" if obs is None else f"{obs*100:.1f}%"
    cal_rows.append(f"<tr><td>{int(lo*100)}–{int(min(1,hi)*100)}%</td><td>{obs_text}</td><td>{len(vals)}</td></tr>")
cal_html = "".join(cal_rows)

recent = []
for p in reversed(preds[-6:]):
    r = resmap.get(p["id"])
    st = r.get("outcome") if r else "LOCKED"
    recent.append(
        f"<tr><td>{esc(p['id'][-6:])}</td><td>{esc(p['asset'].replace('USDT',''))}</td>"
        f"<td>{esc(p['direction'])}</td><td>{float(p['probability'])*100:.1f}%</td><td>{esc(st)}</td></tr>"
    )
recent_html = "".join(recent) if recent else "<tr><td colspan='5'>No public predictions yet.</td></tr>"

page = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#06101f">
<title>SEE IT COMING. — Observatory</title>
<meta name="description" content="Forward-locked market intelligence. From chaos to signal.">
<!-- SIC-OBSERVATORY-CHAOS-V3 -->
<style>
:root{{--bg:#050b16;--panel:#07152a;--line:#183e72;--blue:#3d79ff;--cyan:#24e5ff;--violet:#8d5cff;--pink:#ff4f9a;--coral:#ff5e78;--mint:#2ff3bd;--white:#f7fbff;--muted:#8da6ca}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:radial-gradient(circle at 45% 8%,#112455 0,#071127 30%,#040914 75%);color:var(--white);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}body:before{{content:"";position:fixed;inset:0;pointer-events:none;background-image:linear-gradient(rgba(61,121,255,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(61,121,255,.035) 1px,transparent 1px);background-size:44px 44px}}
.shell{{width:min(1480px,calc(100% - 40px));margin:auto;position:relative}}nav{{height:68px;display:flex;align-items:center;gap:38px;border-bottom:1px solid rgba(53,109,190,.35)}}.brand{{font-size:20px;font-weight:950;letter-spacing:-.04em;margin-right:20px}}.brand i{{font-style:normal;color:var(--pink)}}.navlinks{{display:flex;gap:26px;color:#a9bce0;font-size:11px}}.navlinks span:first-child{{color:#6fb6ff;text-shadow:0 0 18px #2d72ff}}.navstate{{margin-left:auto;font-size:9px;letter-spacing:.16em;color:#8fa4c9}}.navstate b{{display:inline-block;width:8px;height:8px;background:var(--mint);border-radius:50%;box-shadow:0 0 14px var(--mint);margin-right:8px}}.reald{{border:1px solid #3b79ff;padding:7px 10px;border-radius:8px;color:#70a7ff;font-weight:800;font-size:9px}}
.hero{{display:grid;grid-template-columns:340px 1fr 310px;min-height:440px;border-bottom:1px solid rgba(53,109,190,.32)}}.hero-copy{{padding:48px 22px 35px 0;z-index:3}}.eyebrow{{display:block;color:#6fa7ff;font-size:10px;letter-spacing:.2em;font-weight:900;margin-bottom:18px}}h1{{font-size:72px;line-height:.88;letter-spacing:-.065em;margin:0 0 24px}}h1 span{{background:linear-gradient(95deg,#5fa6ff,#9d68ff 53%,#ff62a2);-webkit-background-clip:text;background-clip:text;color:transparent}}.hero-copy p{{color:#afc0df;font-size:17px;line-height:1.45}}.trust{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:24px;font-size:8px;letter-spacing:.12em;color:#91a8cf}}
.chaos{{position:relative;overflow:hidden;min-height:440px;background:radial-gradient(circle at 55% 50%,rgba(29,100,255,.30),transparent 34%),radial-gradient(circle at 58% 54%,rgba(148,70,255,.22),transparent 26%)}}.chaos:before{{content:"";position:absolute;left:22%;top:19%;width:430px;height:290px;border-radius:50%;border:1px solid rgba(53,186,255,.35);box-shadow:0 0 80px rgba(38,115,255,.34),inset 0 0 80px rgba(41,59,255,.18);background:radial-gradient(circle at 50% 48%,rgba(20,78,190,.18),rgba(6,13,38,.1) 55%,transparent 70%)}}.chaos:after{{content:"";position:absolute;left:30%;top:25%;width:290px;height:210px;border-radius:50%;border:1px solid rgba(165,74,255,.42);transform:rotate(-12deg)}}.scanline{{position:absolute;left:26%;top:48%;width:390px;height:1px;background:linear-gradient(90deg,transparent,#24e5ff,#9d68ff,transparent);box-shadow:0 0 16px #24e5ff;transform:rotate(-8deg)}}.noise-number{{position:absolute;font:700 10px ui-monospace,monospace;color:rgba(255,92,120,.7)}}.n1{{left:9%;top:28%}}.n2{{left:61%;top:16%;color:rgba(47,243,189,.7)}}.n3{{left:67%;top:68%}}.n4{{left:15%;top:72%;color:rgba(47,243,189,.75)}}.n5{{left:48%;top:8%}}.coin-chip{{position:absolute;width:165px;padding:10px 12px;border-radius:10px;background:rgba(6,18,40,.88);border:1px solid #284f88;box-shadow:0 8px 28px rgba(0,0,0,.25)}}.coin-chip.gain{{border-color:rgba(47,243,189,.45)}}.coin-chip.loss{{border-color:rgba(255,94,120,.5)}}.coin-chip.stale{{opacity:.48}}.coin-row{{display:flex;justify-content:space-between;align-items:center}}.coin-row b{{font-size:13px}}.gain .coin-row span{{color:var(--mint)}}.loss .coin-row span{{color:var(--coral)}}.coin-chip svg{{width:100%;height:22px;margin-top:7px}}.coin-chip polyline{{fill:none;stroke:currentColor;stroke-width:2}}.gain{{color:var(--mint)}}.loss{{color:var(--coral)}}.stale{{color:#7087af}}
.side{{padding:12px 0 12px 14px;display:grid;grid-template-rows:1fr 1fr;gap:10px}}.sidebox,.panel{{border:1px solid #16467d;border-radius:10px;background:linear-gradient(145deg,rgba(7,21,42,.95),rgba(4,13,29,.95));overflow:hidden}}.sidebox h3,.panel-title{{font-size:11px;letter-spacing:.08em;margin:0;padding:12px 14px;border-bottom:1px solid #153e6d;color:#b9cdf0}}table{{width:100%;border-collapse:collapse}}th,td{{padding:6px 9px;text-align:left;border-bottom:1px solid rgba(32,76,125,.26);font-size:9px}}th{{color:#6f88b2;font-size:7px;letter-spacing:.1em}}.pos{{color:var(--mint)}}.neg{{color:var(--coral)}}.tape-row{{display:grid;grid-template-columns:42px 1fr 1fr 60px;gap:8px;padding:7px 10px;border-bottom:1px solid rgba(32,76,125,.25);font-size:9px}}.t-time{{color:#617ba7}}.tape-row em{{font-style:normal;text-align:right}}
.pipeline{{margin:16px 0 12px;border:1px solid #17539a;border-radius:10px;background:linear-gradient(90deg,rgba(6,28,59,.9),rgba(7,18,45,.9));display:grid;grid-template-columns:150px repeat(8,1fr);align-items:center;overflow:hidden}}.pipe-title{{padding:18px;color:#5da4ff;font-size:11px;font-weight:900;letter-spacing:.11em}}.step{{padding:15px 6px;text-align:center;position:relative}}.step:after{{content:"→";position:absolute;right:-6px;top:22px;color:#476fa8}}.step:last-child:after{{display:none}}.step i{{display:grid;place-items:center;width:28px;height:28px;margin:auto;border-radius:50%;border:1px solid #547df0;color:#78a6ff;box-shadow:0 0 16px rgba(55,112,255,.35)}}.step:nth-child(4) i{{border-color:#b45cff;color:#b985ff}}.step:nth-child(5) i{{border-color:#ff4f9a;color:#ff7bb4}}.step:nth-child(7) i{{border-color:#24e5ff;color:#24e5ff}}.step b{{display:block;font-size:8px;margin-top:8px}}.step span{{font-size:7px;color:#7188ae}}
.gridtop{{display:grid;grid-template-columns:1.15fr 1.1fr .8fr;gap:10px;margin-bottom:10px}}.forecast-panel{{display:grid;grid-template-columns:1.1fr 1fr;gap:16px;padding:18px}}.asset-lock{{display:flex;gap:14px;align-items:center}}.asset-icon{{width:70px;height:70px;border-radius:50%;display:grid;place-items:center;background:radial-gradient(circle,#1d64ff,#101936);border:1px solid #3e75da;font-weight:900}}.asset-lock h3{{font-size:19px;margin:0 0 5px}}.lock-dir{{font-size:17px;font-weight:900}}.lock-prob{{font-size:46px;font-weight:950;letter-spacing:-.05em;color:#29efc2}}.lock-prob small{{font-size:18px}}.micro{{font-size:7px;letter-spacing:.12em;color:#7890b9}}.forecast-facts div{{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid rgba(39,78,128,.25);font-size:9px}}.forecast-facts span{{color:#8399bf}}.whybox{{padding:15px}}.why-row{{display:grid;grid-template-columns:95px 1fr 58px;gap:9px;align-items:center;margin:12px 0;font-size:8px}}.why-row span{{color:#8ea4c7}}.why-row i{{height:8px;background:linear-gradient(90deg,#7b61ff,#29dfff);border-radius:99px;display:block}}.proofbox{{padding:16px}}.lockicon{{width:52px;height:52px;border-radius:50%;display:grid;place-items:center;border:1px solid #ff4f9a;color:#ff5a9f;box-shadow:0 0 24px rgba(255,79,154,.25);font-size:22px;margin:8px 0 14px}}.proofbox code{{display:block;font-size:8px;color:#a2b8dd;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.proofstatus{{margin-top:18px;display:flex;justify-content:space-between;font-size:8px}}.proofstatus b{{color:#ff79ad}}
.chartbox{{padding:12px}}.chartbox svg{{width:100%;height:120px;margin-top:8px}}.chartbox polyline{{fill:none;stroke:url(#grad);stroke-width:2.2}}.gridbottom{{display:grid;grid-template-columns:1.45fr .55fr .62fr;gap:10px;margin-bottom:36px}}.score{{padding:14px}}.score-grid{{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-top:12px}}.score-card{{padding:15px 10px;border:1px solid #173f70;border-radius:8px;background:rgba(5,18,39,.55)}}.score-card b{{font-size:24px}}.score-card span{{display:block;color:#8ca2c6;font-size:7px;margin-top:6px}}.calbox table td,.recent table td{{font-size:8px}}footer{{border-top:1px solid rgba(53,109,190,.32);padding:24px 0 38px;display:flex;justify-content:space-between;color:#6e85aa;font-size:8px;letter-spacing:.12em}}
.empty-state{{padding:30px;color:#7f95ba}}
@media(max-width:1100px){{.hero{{grid-template-columns:300px 1fr}}.side{{grid-column:1/-1;grid-template-columns:1fr 1fr;grid-template-rows:auto}}.gridtop,.gridbottom{{grid-template-columns:1fr}}.pipeline{{grid-template-columns:1fr repeat(4,1fr)}}}}
@media(max-width:720px){{.navlinks{{display:none}}.hero{{grid-template-columns:1fr}}.hero-copy{{padding-right:0}}h1{{font-size:58px}}.chaos{{min-height:520px}}.side{{grid-template-columns:1fr}}.pipeline{{grid-template-columns:1fr 1fr 1fr}}.score-grid{{grid-template-columns:1fr 1fr}}}}
</style>
</head>
<body>
<div class="shell">
<nav>
  <div class="brand">SEE IT COMING<i>.</i></div>
  <div class="navlinks"><span>Home</span><span>Live</span><span>Forecasts</span><span>Record</span><span>Method</span><span>About</span></div>
  <div class="navstate"><b></b>PUBLIC FORWARD EXPERIMENT · V1.0</div>
  <div class="reald">{system_state} · {data_health}</div>
</nav>

<section class="hero">
  <div class="hero-copy">
    <span class="eyebrow">THE MOVE HASN'T HAPPENED YET.</span>
    <h1>See it<br><span>before</span><br>it moves.</h1>
    <p>Predictions are locked before outcomes. No edits. No deleted losses. Reality keeps the score.</p>
    <div class="trust"><span>◉ FORWARD ONLY</span><span>◉ PUBLIC PROOF</span><span>◉ NO BACKFILLING</span><span>◉ NO TRADE EXECUTION</span></div>
  </div>
  <div class="chaos">
    <div class="scanline"></div>
    <span class="noise-number n1">−2.3%</span><span class="noise-number n2">+4.1%</span><span class="noise-number n3">−1.8%</span><span class="noise-number n4">+3.9%</span><span class="noise-number n5">+0.8%</span>
    {chips_html}
  </div>
  <div class="side">
    <div class="sidebox">
      <h3>LIVE MARKET NOISE</h3>
      <table><thead><tr><th>ASSET</th><th>PRICE</th><th>24H</th><th>SOURCE</th></tr></thead><tbody>{noise_html}</tbody></table>
    </div>
    <div class="sidebox">
      <h3>MARKET OBSERVATION TAPE</h3>
      {tape_html}
    </div>
  </div>
</section>

<div class="pipeline">
  <div class="pipe-title">THE INTELLIGENCE<br>PIPELINE</div>
  <div class="step"><i>◉</i><b>OBSERVE</b><span>Market data</span></div>
  <div class="step"><i>⌁</i><b>DETECT</b><span>Anomalies</span></div>
  <div class="step"><i>△</i><b>PREDICT</b><span>Model ensemble</span></div>
  <div class="step"><i>▣</i><b>LOCK</b><span>Immutable proof</span></div>
  <div class="step"><i>◷</i><b>WAIT</b><span>Market decides</span></div>
  <div class="step"><i>✓</i><b>RESOLVE</b><span>Measure outcome</span></div>
  <div class="step"><i>∑</i><b>SCORE</b><span>Update record</span></div>
  <div class="step"><i>↗</i><b>LEARN</b><span>Improve next version</span></div>
</div>

<div class="gridtop">
  <div class="panel">
    <div class="panel-title">LATEST LOCKED FORECAST</div>
    <div class="forecast-panel">{latest_block}</div>
  </div>
  <div class="panel">
    <div class="panel-title">WHY IT FIRED</div>
    <div class="whybox">{why_block}</div>
    <div class="proofbox">
      <div class="lockicon">▣</div>
      <span class="micro">LOCKED PROOF · SHA-256</span>
      <code>{esc(proof_hash)}</code>
      <div class="proofstatus"><span>Status</span><b>{"RESOLVED" if latest_res else "LOCKED"}</b></div>
    </div>
  </div>
  <div class="panel">
    <div class="panel-title">PRICE CHART · {esc(chart_asset.replace("USDT",""))} · {esc(chart_source)}</div>
    <div class="chartbox">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none">
        <defs><linearGradient id="grad"><stop offset="0%" stop-color="#3d79ff"/><stop offset="100%" stop-color="#b05cff"/></linearGradient></defs>
        <polyline points="{chart_points}"/>
      </svg>
    </div>
  </div>
</div>

<div class="gridbottom">
  <div class="panel score">
    <div class="panel-title">SCIENTIFIC SCOREBOARD · PUBLIC FORWARD RECORD</div>
    <div class="score-grid">
      <div class="score-card"><b>{len(preds)}</b><span>LOCKED</span></div>
      <div class="score-card"><b>{n_res}</b><span>RESOLVED</span></div>
      <div class="score-card"><b>{correct}</b><span>CORRECT</span></div>
      <div class="score-card"><b>{pct(accuracy)}</b><span>ACCURACY</span></div>
      <div class="score-card"><b>{dec(brier)}</b><span>BRIER SCORE</span></div>
      <div class="score-card"><b>{"INSUFFICIENT DATA" if n_res < 50 else "EVALUATING"}</b><span>EDGE STATUS</span></div>
    </div>
  </div>
  <div class="panel calbox">
    <div class="panel-title">CALIBRATION</div>
    <table><thead><tr><th>CONFIDENCE</th><th>OBSERVED</th><th>N</th></tr></thead><tbody>{cal_html}</tbody></table>
  </div>
  <div class="panel recent">
    <div class="panel-title">RECENT PREDICTIONS</div>
    <table><thead><tr><th>#</th><th>ASSET</th><th>DIR</th><th>PROB.</th><th>STATUS</th></tr></thead><tbody>{recent_html}</tbody></table>
  </div>
</div>

<footer><span>SEE IT COMING. · FROM CHAOS TO SIGNAL.</span><span>PROOF BEFORE PERSUASION · EXPERIMENTAL · NOT FINANCIAL ADVICE</span></footer>
</div>
</body></html>'''

(OUT/"index.html").write_text(page)
(OUT/"ledger.json").write_text(json.dumps(data, indent=2))
(OUT/"market.json").write_text(json.dumps(radar, indent=2))
print("Built OBSERVATORY CHAOS V3:", OUT/"index.html", "| market:", system_state, data_health)
