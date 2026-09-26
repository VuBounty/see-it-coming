import json
import html
import sys
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.market import klines_with_source, features, score
from app.presentation import market_state, scientific_metrics, forecast_ui_state

LEDGER_PATH = ROOT / "data" / "ledger.json"
OUT = ROOT / "site"
OUT.mkdir(exist_ok=True)
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT"]
STALE_AFTER_MINUTES = 90


def esc(value):
    return html.escape(str(value))


def evidence_map(prediction):
    out = {}
    for item in prediction.get("evidence", []):
        if "=" in item:
            key, value = item.split("=", 1)
            out[key] = value
    return out


def polyline(values, width=100.0, height=28.0, pad=2.0):
    if not values:
        return ""
    if len(values) == 1:
        return f"0,{height/2:.2f} {width},{height/2:.2f}"
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    pts = []
    for i, value in enumerate(values):
        x = i / (len(values) - 1) * width
        y = height - pad - ((value - lo) / span) * (height - 2 * pad)
        pts.append(f"{x:.2f},{y:.2f}")
    return " ".join(pts)


def pct(value, digits=1):
    return "—" if value is None else f"{value * 100:.{digits}f}%"


def decimal(value, digits=3):
    return "—" if value is None else f"{value:.{digits}f}"


ledger = json.loads(LEDGER_PATH.read_text()) if LEDGER_PATH.exists() else {"predictions": [], "resolutions": []}
predictions = ledger.get("predictions", [])
resolutions = ledger.get("resolutions", [])
resolution_map = {row["prediction_id"]: row for row in resolutions}
metrics = scientific_metrics(predictions, resolutions)
generated_at = datetime.now(timezone.utc).isoformat()

unresolved_ids = {p["id"] for p in predictions if p["id"] not in resolution_map}
locked_assets = {p["asset"] for p in predictions if p["id"] in unresolved_ids}

def load_asset(symbol):
    try:
        bars, source = klines_with_source(symbol, limit=72)
        feat = features(bars)
        model_score = score(feat)
        return {
            "symbol": symbol,
            "price": feat["price"],
            "r1": feat["r1"],
            "r6": feat["r6"],
            "r24": feat["r24"],
            "z": feat["z"],
            "vr": feat["vr"],
            "anomaly": model_score["anomaly"],
            "direction": model_score["direction"],
            "confidence": model_score["confidence"],
            "provider": source,
            "state": market_state(model_score["anomaly"], symbol in locked_assets),
            "bars": [{"t": int(row["t"]), "c": float(row["c"])} for row in bars[-36:]],
        }
    except Exception as exc:
        return {"symbol": symbol, "error": str(exc), "provider": "unavailable", "state": "NO DATA", "bars": []}

with ThreadPoolExecutor(max_workers=len(SYMBOLS)) as executor:
    by_symbol = {asset["symbol"]: asset for asset in executor.map(load_asset, SYMBOLS)}
assets = [by_symbol[symbol] for symbol in SYMBOLS]

available = sum(1 for asset in assets if "error" not in asset)
initial_status = "LIVE" if available == len(SYMBOLS) else ("DEGRADED" if available else "NO DATA")
latest = predictions[-1] if predictions else None
latest_resolution = resolution_map.get(latest["id"]) if latest else None
latest_evidence = evidence_map(latest) if latest else {}
latest_ui_state = None
if latest:
    latest_ui_state = forecast_ui_state(latest["created_at"], latest_resolution.get("outcome") if latest_resolution else None)

snapshot = {
    "version": "V3.2-MOTION",
    "generated_at": generated_at,
    "stale_after_minutes": STALE_AFTER_MINUTES,
    "system_status_at_build": initial_status,
    "available_assets": available,
    "total_assets": len(SYMBOLS),
    "assets": assets,
    "metrics": metrics,
    "latest_forecast": latest,
    "latest_resolution": latest_resolution,
    "latest_ui_state": latest_ui_state,
}

asset_positions = [(8, 13), (39, 4), (72, 13), (12, 61), (44, 69), (74, 60)]
asset_cards = []
for index, symbol in enumerate(SYMBOLS):
    asset = next(row for row in assets if row["symbol"] == symbol)
    left, top = asset_positions[index]
    short = symbol.replace("USDT", "")
    if "error" in asset:
        asset_cards.append(f'''
        <div class="asset-node no-data" data-symbol="{esc(symbol)}" style="--x:{left}%;--y:{top}%;--delay:{index * -1.2}s">
          <div class="node-top"><b>{esc(short)}</b><span>NO DATA</span></div>
          <div class="node-state">UNAVAILABLE</div>
        </div>''')
        continue
    move = float(asset["r24"]) * 100
    move_class = "gain" if move >= 0 else "loss"
    arrow = "↑" if move >= 0 else "↓"
    path = polyline([row["c"] for row in asset["bars"]], width=100, height=26)
    anomaly = float(asset["anomaly"])
    drift = 4 + anomaly * 12
    duration = 13 - anomaly * 6
    pulse = 4.2 - anomaly * 2.0
    asset_cards.append(f'''
    <div class="asset-node {move_class}" data-symbol="{esc(symbol)}" data-anomaly="{anomaly:.3f}"
         style="--x:{left}%;--y:{top}%;--drift:{drift:.1f}px;--duration:{duration:.2f}s;--pulse:{pulse:.2f}s;--delay:{index * -1.15}s">
      <div class="node-top"><b>{esc(short)}</b><span>{arrow} {move:+.2f}%</span></div>
      <svg class="mini-chart" viewBox="0 0 100 26" preserveAspectRatio="none" aria-label="{esc(short)} price sparkline"><polyline points="{path}"/></svg>
      <div class="node-foot"><span>{esc(asset['state'])}</span><em>A {anomaly:.2f}</em></div>
    </div>''')
asset_cards_html = "".join(asset_cards)

noise_rows = []
for asset in assets:
    short = asset["symbol"].replace("USDT", "")
    if "error" in asset:
        noise_rows.append(f"<tr><td>{esc(short)}</td><td>—</td><td>—</td><td>NO DATA</td></tr>")
    else:
        move = asset["r24"] * 100
        cls = "pos" if move >= 0 else "neg"
        noise_rows.append(
            f"<tr><td>{esc(short)}</td><td>{asset['price']:.8g}</td><td class='{cls}'>{move:+.2f}%</td><td>{esc(asset['state'])}</td></tr>"
        )
noise_rows_html = "".join(noise_rows)

stream_rows = []
for asset in assets:
    if "error" in asset:
        continue
    short = asset["symbol"].replace("USDT", "")
    cls = "pos" if asset["r24"] >= 0 else "neg"
    stream_rows.append(
        f"<div class='stream-row' data-stream-row><span>SNAPSHOT</span><b>{esc(short)}</b><strong>{asset['price']:.8g}</strong><em class='{cls}'>{asset['r24']*100:+.2f}%</em></div>"
    )
stream_rows_html = "".join(stream_rows) or "<div class='stream-row'><span>—</span><b>MARKET FEED</b><strong>UNAVAILABLE</strong><em>—</em></div>"

if latest:
    direction = latest.get("direction", "—")
    arrow = "↑" if direction == "UP" else "↓"
    direction_class = "up" if direction == "UP" else "down"
    latest_asset = latest["asset"].replace("USDT", "")
    outcome = latest_resolution.get("outcome") if latest_resolution else "UNKNOWN"
    latest_forecast_html = f'''
      <div class="forecast-identity">
        <div class="coin-emblem">{esc(latest_asset[:2])}</div>
        <div><h3>{esc(latest_asset)} / USD</h3><div class="forecast-dir {direction_class}">{arrow} {esc(direction)}</div>
        <div class="forecast-prob">{float(latest['probability'])*100:.1f}<small>%</small></div><span>MODEL PROBABILITY</span></div>
      </div>
      <div class="forecast-facts">
        <div><span>Entry observation</span><b>{esc(latest_evidence.get('entry','—'))}</b></div>
        <div><span>Target move</span><b>{esc(latest.get('target_pct','—'))}%</b></div>
        <div><span>Horizon</span><b>{esc(latest.get('horizon_hours','—'))}H</b></div>
        <div><span>Decision threshold</span><b>53.0%</b></div>
        <div><span>Locked at</span><b>{esc(latest.get('created_at','—'))[:19]} UTC</b></div>
        <div><span>Outcome</span><b>{esc(outcome)}</b></div>
      </div>'''
    def bar_width(key, scale, base=18):
        try:
            return min(100, abs(float(latest_evidence.get(key, 0))) * scale + base)
        except Exception:
            return base
    why_html = "".join([
        f"<div class='why-row'><span>Momentum 6H</span><i><u style='width:{bar_width('r6',1800):.0f}%'></u></i><b>{esc(latest_evidence.get('r6','—'))}</b></div>",
        f"<div class='why-row'><span>Momentum 24H</span><i><u style='width:{bar_width('r24',900):.0f}%'></u></i><b>{esc(latest_evidence.get('r24','—'))}</b></div>",
        f"<div class='why-row'><span>Price deviation</span><i><u style='width:{bar_width('z',28):.0f}%'></u></i><b>{esc(latest_evidence.get('z','—'))}</b></div>",
        f"<div class='why-row'><span>Volume ratio</span><i><u style='width:{bar_width('vr',42):.0f}%'></u></i><b>{esc(latest_evidence.get('vr','—'))}</b></div>",
    ])
    proof_hash = latest.get("proof_hash", "—")
    forecast_status = latest_resolution.get("outcome") if latest_resolution else "LOCKED"
else:
    latest_asset = "—"
    latest_forecast_html = "<div class='empty-state'>NO LOCKED FORECAST YET</div>"
    why_html = "<div class='empty-state'>WAITING FOR A QUALIFIED SIGNAL</div>"
    proof_hash = "—"
    forecast_status = "WAITING"

latest_asset_data = next((a for a in assets if latest and a["symbol"] == latest["asset"] and "error" not in a), None)
if latest_asset_data:
    main_chart_points = polyline([row["c"] for row in latest_asset_data["bars"]], width=100, height=100, pad=8)
    chart_provider = latest_asset_data["provider"]
else:
    main_chart_points = ""
    chart_provider = "unavailable"

cal_rows = []
for lo, hi in [(0.50,0.60),(0.60,0.70),(0.70,0.80),(0.80,0.90),(0.90,1.01)]:
    vals = []
    for p in predictions:
        r = resolution_map.get(p["id"])
        if r and r.get("outcome") in ("CORRECT", "WRONG"):
            probability = float(p["probability"])
            if lo <= probability < hi:
                vals.append(1 if r["outcome"] == "CORRECT" else 0)
    observed = sum(vals)/len(vals) if vals else None
    cal_rows.append((f"{int(lo*100)}–{int(min(1,hi)*100)}%", observed, len(vals)))
calibration_html = "".join(
    f"<div class='cal-line'><span>{band}</span><div><i style='width:{0 if observed is None else observed*100:.1f}%'></i></div><b>{'waiting' if observed is None else f'{observed*100:.1f}%'}</b><em>N={count}</em></div>"
    for band, observed, count in reversed(cal_rows)
)

recent_rows = []
for prediction in reversed(predictions[-6:]):
    resolution = resolution_map.get(prediction["id"])
    status = resolution.get("outcome") if resolution else "LOCKED"
    direction_class = "pos" if prediction["direction"] == "UP" else "neg"
    recent_rows.append(
        f"<tr><td>{esc(prediction['id'][-6:])}</td><td>{esc(prediction['asset'].replace('USDT',''))}</td>"
        f"<td class='{direction_class}'>{esc(prediction['direction'])}</td><td>{float(prediction['probability'])*100:.1f}%</td><td>{esc(status)}</td></tr>"
    )
recent_rows_html = "".join(recent_rows) if recent_rows else "<tr><td colspan='5'>No public predictions yet.</td></tr>"

feature_context = []
if latest:
    feature_context = [
        ("24H MOMENTUM", latest_evidence.get("r24", "—")),
        ("6H MOMENTUM", latest_evidence.get("r6", "—")),
        ("PRICE DEVIATION", latest_evidence.get("z", "—")),
        ("VOLUME RATIO", latest_evidence.get("vr", "—")),
    ]
context_html = "".join(f"<div><span>{label}</span><b>{esc(value)}</b></div>" for label, value in feature_context) if feature_context else "<div><span>HISTORICAL CONTEXT</span><b>COLLECTING</b></div>"

snapshot_json = json.dumps(snapshot, separators=(",", ":")).replace("</", "<\\/")

page = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#06101f">
<title>SEE IT COMING. — Motion Observatory</title>
<meta name="description" content="Forward-locked market intelligence. From chaos to signal.">
<!-- SIC-OBSERVATORY-CHAOS-V3.2-MOTION -->
<style>
:root{{--bg:#030914;--panel:#06152b;--panel2:#071b36;--line:#17508b;--blue:#3f7dff;--cyan:#29e6ff;--violet:#9661ff;--pink:#ff4fa3;--coral:#ff5e7c;--mint:#2ef3bd;--white:#f7fbff;--muted:#8ea8d0}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:radial-gradient(circle at 45% 2%,#13295d 0,#071329 27%,#030914 74%);color:var(--white);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;overflow-x:hidden}}
body:before{{content:"";position:fixed;inset:-50px;pointer-events:none;background-image:linear-gradient(rgba(70,124,255,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(70,124,255,.035) 1px,transparent 1px);background-size:44px 44px;animation:gridDrift 42s linear infinite}}
@keyframes gridDrift{{to{{transform:translate3d(44px,44px,0)}}}}
.shell{{width:min(1500px,calc(100% - 36px));margin:auto;position:relative}}nav{{height:68px;display:flex;align-items:center;gap:34px;border-bottom:1px solid rgba(63,125,255,.28)}}.brand{{font-size:20px;font-weight:950;letter-spacing:-.045em}}.brand i{{font-style:normal;color:var(--pink)}}.navlinks{{display:flex;gap:26px;font-size:10px;color:#9bb0d5}}.navlinks span:first-child{{color:#7eb2ff;text-shadow:0 0 20px #3d7aff}}.navstate{{margin-left:auto;font-size:8px;letter-spacing:.16em;color:#849bc2}}.health{{border:1px solid #397cff;border-radius:8px;padding:7px 10px;color:#70aaff;font-size:8px;font-weight:900;letter-spacing:.08em}}.health.live{{color:var(--mint);border-color:rgba(46,243,189,.45)}}.health.degraded,.health.stale{{color:#ffbc64;border-color:rgba(255,188,100,.5)}}.health.no-data{{color:var(--coral);border-color:rgba(255,94,124,.5)}}
.hero{{display:grid;grid-template-columns:320px minmax(600px,1fr) 300px;min-height:455px;border-bottom:1px solid rgba(63,125,255,.3)}}.hero-copy{{padding:50px 18px 32px 0;position:relative;z-index:8}}.eyebrow{{display:block;color:#72a9ff;font-size:9px;letter-spacing:.21em;font-weight:900;margin-bottom:18px}}h1{{font-size:68px;line-height:.88;letter-spacing:-.07em;margin:0 0 24px}}h1 span{{background:linear-gradient(95deg,#5b9cff,#9d64ff 54%,#ff5fa2);-webkit-background-clip:text;background-clip:text;color:transparent}}.hero-copy p{{color:#b0c0dd;font-size:16px;line-height:1.5}}.trust{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:23px;color:#7f97be;font-size:7px;letter-spacing:.12em}}
.chaos{{position:relative;overflow:hidden;min-height:455px}}#chaosCanvas{{position:absolute;inset:0;width:100%;height:100%;opacity:.9}}.ticker-cloud{{position:absolute;inset:0;pointer-events:none;overflow:hidden}}.ticker-cloud span{{position:absolute;color:rgba(104,148,220,.26);font:700 9px ui-monospace,monospace;letter-spacing:.04em;animation:floatNoise var(--noise-duration,18s) ease-in-out infinite alternate;animation-delay:var(--noise-delay,0s)}}@keyframes floatNoise{{to{{transform:translate3d(var(--noise-x,18px),var(--noise-y,-12px),0);opacity:.75}}}}
.asset-node{{position:absolute;left:var(--x);top:var(--y);width:174px;transform:translate(-50%,-50%);padding:10px 12px;border:1px solid #28578f;border-radius:10px;background:linear-gradient(145deg,rgba(5,18,41,.95),rgba(7,21,50,.90));box-shadow:0 10px 28px rgba(0,0,0,.3);z-index:6;animation:nodeDrift var(--duration,10s) ease-in-out infinite alternate,nodePulse var(--pulse,3.4s) ease-in-out infinite;animation-delay:var(--delay,0s)}}@keyframes nodeDrift{{to{{transform:translate(calc(-50% + var(--drift,8px)),calc(-50% - var(--drift,8px)))}}}}@keyframes nodePulse{{50%{{box-shadow:0 12px 34px rgba(0,0,0,.35),0 0 calc(12px + var(--drift,8px)) rgba(72,126,255,.18)}}}}.asset-node.gain{{border-color:rgba(46,243,189,.48)}}.asset-node.loss{{border-color:rgba(255,94,124,.55)}}.asset-node.no-data{{opacity:.45}}.node-top,.node-foot{{display:flex;justify-content:space-between;gap:8px;align-items:center}}.node-top b{{font-size:13px}}.node-top span{{font-size:13px;font-weight:900}}.gain .node-top span{{color:var(--mint)}}.loss .node-top span{{color:var(--coral)}}.mini-chart{{width:100%;height:27px;margin:6px 0;overflow:visible}}.mini-chart polyline{{fill:none;stroke:currentColor;stroke-width:2;vector-effect:non-scaling-stroke;stroke-dasharray:160;stroke-dashoffset:160;animation:drawLine 1s ease forwards}}.gain .mini-chart{{color:var(--mint)}}.loss .mini-chart{{color:var(--coral)}}@keyframes drawLine{{to{{stroke-dashoffset:0}}}}.node-foot{{font-size:6px;letter-spacing:.08em;color:#7892bb}}.node-foot em{{font-style:normal;color:#a9bae0}}
.scan-sweep{{position:absolute;width:55%;height:1px;left:23%;top:52%;background:linear-gradient(90deg,transparent,var(--cyan),var(--violet),transparent);box-shadow:0 0 18px rgba(41,230,255,.75);transform:rotate(-8deg);animation:scanSweep 11s ease-in-out infinite;z-index:4}}@keyframes scanSweep{{0%,100%{{opacity:.15;transform:translateY(-80px) rotate(-8deg)}}50%{{opacity:.9;transform:translateY(90px) rotate(-8deg)}}}}
.side{{padding:12px 0 12px 14px;display:grid;grid-template-rows:1fr 1fr;gap:10px}}.sidebox,.panel{{border:1px solid #174d83;border-radius:10px;background:linear-gradient(145deg,rgba(6,21,44,.96),rgba(3,12,28,.96));overflow:hidden}}.sidebox h3,.panel-title{{font-size:10px;letter-spacing:.08em;margin:0;padding:12px 14px;border-bottom:1px solid #174574;color:#bfd1ef}}table{{width:100%;border-collapse:collapse}}th,td{{padding:6px 9px;text-align:left;border-bottom:1px solid rgba(37,78,129,.28);font-size:8px}}th{{color:#6d86af;font-size:6px;letter-spacing:.1em}}.pos{{color:var(--mint)}}.neg{{color:var(--coral)}}.snapshot-age{{padding:8px 11px;color:#6e88b2;font-size:7px;border-top:1px solid rgba(37,78,129,.28)}}.stream-viewport{{height:156px;overflow:hidden;position:relative}}.stream-list{{transition:transform .5s cubic-bezier(.2,.8,.2,1)}}.stream-row{{display:grid;grid-template-columns:48px 1fr 1fr 56px;gap:7px;padding:7px 10px;border-bottom:1px solid rgba(37,78,129,.25);font-size:8px}}.stream-row span{{color:#687fa8}}.stream-row em{{font-style:normal;text-align:right}}
.pipeline{{margin:16px 0 12px;border:1px solid #1758a0;border-radius:10px;background:linear-gradient(90deg,rgba(5,30,64,.9),rgba(7,16,43,.94));display:grid;grid-template-columns:150px repeat(8,1fr);align-items:center;overflow:hidden;position:relative}}.pipeline:before{{content:"";position:absolute;top:0;bottom:0;width:90px;background:linear-gradient(90deg,transparent,rgba(73,146,255,.10),transparent);animation:pipelineGlow 10s linear infinite}}@keyframes pipelineGlow{{from{{left:-100px}}to{{left:100%}}}}.pipe-title{{padding:18px;color:#5fa8ff;font-size:10px;font-weight:900;letter-spacing:.11em}}.step{{padding:14px 4px;text-align:center;position:relative}}.step:after{{content:"→";position:absolute;right:-6px;top:21px;color:#426b9f}}.step:last-child:after{{display:none}}.step i{{display:grid;place-items:center;width:28px;height:28px;margin:auto;border-radius:50%;border:1px solid #557ce7;color:#7ca6ff;box-shadow:0 0 14px rgba(55,112,255,.3);font-style:normal}}.step:nth-child(4) i{{border-color:#a05cff;color:#b77dff}}.step:nth-child(5) i{{border-color:#ff50a1;color:#ff7ab7}}.step:nth-child(7) i{{border-color:#24dfff;color:#24dfff}}.step b{{display:block;font-size:7px;margin-top:7px}}.step span{{font-size:6px;color:#7188ae}}
.gridtop{{display:grid;grid-template-columns:1.08fr 1.08fr .84fr;gap:10px;margin-bottom:10px}}.forecast-panel{{display:grid;grid-template-columns:1.05fr 1fr;gap:14px;padding:16px;position:relative}}.forecast-panel.fresh{{animation:freshPanel .85s ease both}}@keyframes freshPanel{{0%{{box-shadow:inset 0 0 0 1px rgba(255,79,163,0),0 0 0 rgba(255,79,163,0)}}50%{{box-shadow:inset 0 0 0 1px rgba(255,79,163,.75),0 0 42px rgba(255,79,163,.22)}}100%{{box-shadow:none}}}}.future-line{{display:none;position:absolute;left:14px;right:14px;bottom:10px;text-align:center;color:#ff81bb;font-size:7px;letter-spacing:.14em}}.forecast-panel.fresh .future-line{{display:block;animation:futureReveal 1.2s .25s both}}@keyframes futureReveal{{from{{opacity:0;transform:scaleX(.6)}}to{{opacity:1;transform:none}}}}.forecast-identity{{display:flex;gap:13px;align-items:center}}.coin-emblem{{width:66px;height:66px;border-radius:50%;display:grid;place-items:center;background:radial-gradient(circle,#1d65ff,#101936);border:1px solid #4277d9;font-weight:900;box-shadow:0 0 28px rgba(46,100,255,.3)}}.forecast-identity h3{{font-size:18px;margin:0 0 4px}}.forecast-dir{{font-size:16px;font-weight:900}}.forecast-dir.up{{color:var(--mint)}}.forecast-dir.down{{color:var(--coral)}}.forecast-prob{{font-size:44px;font-weight:950;letter-spacing:-.05em;color:#2df0c0}}.forecast-prob small{{font-size:17px}}.forecast-identity span{{font-size:6px;letter-spacing:.13em;color:#7890b9}}.forecast-facts div{{display:flex;justify-content:space-between;gap:10px;padding:5px 0;border-bottom:1px solid rgba(40,80,130,.27);font-size:8px}}.forecast-facts span{{color:#8299bd}}.whybox{{padding:14px}}.why-row{{display:grid;grid-template-columns:92px 1fr 60px;gap:8px;align-items:center;margin:11px 0;font-size:7px}}.why-row span{{color:#8ba1c5}}.why-row i{{display:block;height:8px;background:#122a4d;border-radius:99px;overflow:hidden}}.why-row u{{display:block;height:100%;background:linear-gradient(90deg,#8e61ff,#24dfff);border-radius:99px;text-decoration:none}}.proofbox{{padding:14px;border-top:1px solid rgba(40,80,130,.25)}}.lockicon{{width:48px;height:48px;border-radius:50%;display:grid;place-items:center;border:1px solid #ff4f9f;color:#ff6bb0;box-shadow:0 0 23px rgba(255,79,159,.25);font-size:19px;margin:5px 0 12px}}.proofbox code{{display:block;font-size:7px;color:#a2b8dd;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.proofstatus{{margin-top:14px;display:flex;justify-content:space-between;font-size:7px}}.proofstatus b{{color:#ff7db4}}.context{{padding:0 14px 14px;display:grid;grid-template-columns:1fr 1fr;gap:6px}}.context div{{border:1px solid rgba(42,83,135,.28);padding:7px;border-radius:7px}}.context span{{display:block;color:#6f87af;font-size:6px}}.context b{{font-size:8px}}.chartbox{{padding:12px}}.chartbox svg{{width:100%;height:125px}}.chartbox polyline{{fill:none;stroke:url(#mainGradient);stroke-width:2.2;vector-effect:non-scaling-stroke;stroke-dasharray:230;stroke-dashoffset:230;animation:drawMain 1.1s ease forwards}}@keyframes drawMain{{to{{stroke-dashoffset:0}}}}
.time-spine{{display:grid;grid-template-columns:repeat(7,1fr);margin:0 0 12px;border:1px solid #174d83;border-radius:10px;background:rgba(5,18,39,.72);overflow:hidden}}.time-spine div{{padding:10px;text-align:center;border-right:1px solid rgba(42,83,135,.28);position:relative}}.time-spine div:last-child{{border-right:0}}.time-spine span{{display:block;font-size:6px;color:#6d86ae}}.time-spine b{{font-size:8px}}.time-spine .lock{{background:linear-gradient(180deg,rgba(255,79,159,.12),transparent)}}.time-spine .future{{background:linear-gradient(180deg,rgba(65,123,255,.08),transparent)}}
.gridbottom{{display:grid;grid-template-columns:1.2fr .75fr .78fr;gap:10px;margin-bottom:34px}}.score{{padding:13px}}.score-grid{{display:grid;grid-template-columns:repeat(6,1fr);gap:7px;margin-top:10px}}.score-card{{padding:13px 9px;border:1px solid #173f70;border-radius:8px;background:rgba(5,18,39,.55)}}.score-card b{{font-size:21px}}.score-card span{{display:block;color:#859cc1;font-size:6px;margin-top:5px}}.calibration{{padding:12px}}.cal-line{{display:grid;grid-template-columns:58px 1fr 55px 34px;gap:7px;align-items:center;margin:8px 0;font-size:7px}}.cal-line>div{{height:6px;background:#12284b;border-radius:99px;overflow:hidden}}.cal-line i{{display:block;height:100%;background:linear-gradient(90deg,#4a84ff,#a15fff)}}.cal-line b{{font-size:7px}}.cal-line em{{font-style:normal;color:#7188ae}}.recent table td{{font-size:7px}}footer{{border-top:1px solid rgba(63,125,255,.3);padding:22px 0 36px;display:flex;justify-content:space-between;color:#6d84aa;font-size:7px;letter-spacing:.12em}}
@media(max-width:1180px){{.hero{{grid-template-columns:300px 1fr}}.side{{grid-column:1/-1;grid-template-columns:1fr 1fr;grid-template-rows:auto}}.gridtop,.gridbottom{{grid-template-columns:1fr}}.pipeline{{grid-template-columns:140px repeat(4,1fr)}}}}
@media(max-width:760px){{.navlinks{{display:none}}.navstate{{display:none}}.hero{{grid-template-columns:1fr}}.hero-copy{{padding-right:0}}h1{{font-size:58px}}.chaos{{min-height:560px}}.asset-node{{width:150px}}.side{{grid-template-columns:1fr}}.pipeline{{grid-template-columns:1fr 1fr 1fr}}.score-grid{{grid-template-columns:1fr 1fr}}.forecast-panel{{grid-template-columns:1fr}}.time-spine{{grid-template-columns:1fr 1fr 1fr}}}}
@media(prefers-reduced-motion:reduce){{*,*:before,*:after{{animation:none!important;transition:none!important;scroll-behavior:auto!important}}}}
</style>
</head>
<body>
<div class="shell">
<nav>
  <div class="brand">SEE IT COMING<i>.</i></div>
  <div class="navlinks"><span>Home</span><span>Live</span><span>Forecasts</span><span>Record</span><span>Method</span><span>About</span></div>
  <div class="navstate">● PUBLIC FORWARD EXPERIMENT · V1.0</div>
  <div class="health {initial_status.lower().replace(' ','-')}" id="healthBadge">{initial_status} · {available}/{len(SYMBOLS)}</div>
</nav>
<section class="hero">
  <div class="hero-copy">
    <span class="eyebrow">THE MOVE HASN'T HAPPENED YET.</span>
    <h1>See it<br><span>before</span><br>it moves.</h1>
    <p>Predictions are locked before outcomes. No edits. No deleted losses. Reality keeps the score.</p>
    <div class="trust"><span>◉ FORWARD ONLY</span><span>◉ PUBLIC PROOF</span><span>◉ NO BACKFILLING</span><span>◉ NO TRADE EXECUTION</span></div>
  </div>
  <div class="chaos" id="chaosField">
    <canvas id="chaosCanvas" aria-hidden="true"></canvas>
    <div class="scan-sweep" aria-hidden="true"></div>
    <div class="ticker-cloud" aria-hidden="true">
      <span style="left:5%;top:24%;--noise-duration:17s;--noise-x:28px;--noise-y:-12px">MARKET NOISE</span>
      <span style="left:54%;top:8%;--noise-duration:23s;--noise-delay:-6s;--noise-x:-18px;--noise-y:15px">ANOMALY FIELD</span>
      <span style="left:69%;top:74%;--noise-duration:19s;--noise-delay:-3s;--noise-x:24px;--noise-y:-10px">SIGNAL EXTRACTION</span>
      <span style="left:22%;top:82%;--noise-duration:21s;--noise-delay:-8s;--noise-x:-16px;--noise-y:-18px">FORWARD ONLY</span>
    </div>
    {asset_cards_html}
  </div>
  <div class="side">
    <div class="sidebox"><h3>LIVE MARKET NOISE</h3><table><thead><tr><th>ASSET</th><th>PRICE</th><th>24H</th><th>STATE</th></tr></thead><tbody>{noise_rows_html}</tbody></table><div class="snapshot-age" id="snapshotAge">DATA SNAPSHOT · {generated_at[:16].replace('T',' ')} UTC</div></div>
    <div class="sidebox"><h3>MARKET OBSERVATION STREAM</h3><div class="stream-viewport"><div class="stream-list" id="streamList">{stream_rows_html}</div></div><div class="snapshot-age">No synthetic trades · snapshot observations only</div></div>
  </div>
</section>
<div class="pipeline"><div class="pipe-title">THE INTELLIGENCE<br>PIPELINE</div><div class="step"><i>◉</i><b>OBSERVE</b><span>Market data</span></div><div class="step"><i>⌁</i><b>DETECT</b><span>Anomalies</span></div><div class="step"><i>△</i><b>PREDICT</b><span>Model ensemble</span></div><div class="step"><i>▣</i><b>LOCK</b><span>Immutable proof</span></div><div class="step"><i>◷</i><b>WAIT</b><span>Market decides</span></div><div class="step"><i>✓</i><b>RESOLVE</b><span>Measure outcome</span></div><div class="step"><i>∑</i><b>SCORE</b><span>Update record</span></div><div class="step"><i>↗</i><b>LEARN</b><span>Next version</span></div></div>
<div class="gridtop">
  <div class="panel"><div class="panel-title">LATEST LOCKED FORECAST <span id="freshBadge"></span></div><div class="forecast-panel" id="forecastPanel">{latest_forecast_html}<div class="future-line">THE FUTURE STARTS HERE</div></div></div>
  <div class="panel"><div class="panel-title">WHY IT FIRED · CURRENT FEATURE SNAPSHOT</div><div class="whybox">{why_html}</div><div class="context">{context_html}</div><div class="proofbox"><div class="lockicon">▣</div><span class="micro">LOCKED PROOF · SHA-256</span><code id="proofHash" data-proof="{esc(proof_hash)}">{esc(proof_hash)}</code><div class="proofstatus"><span>Status</span><b>{esc(forecast_status)}</b></div></div></div>
  <div class="panel"><div class="panel-title">PRICE CHART · {esc(latest_asset)} · {esc(chart_provider)}</div><div class="chartbox"><svg viewBox="0 0 100 100" preserveAspectRatio="none"><defs><linearGradient id="mainGradient"><stop offset="0%" stop-color="#3d7dff"/><stop offset="100%" stop-color="#a35fff"/></linearGradient></defs><polyline points="{main_chart_points}"/></svg></div></div>
</div>
<div class="time-spine"><div><span>OBSERVE</span><b>DATA</b></div><div><span>DETECT</span><b>FEATURES</b></div><div><span>PREDICT</span><b>PROBABILITY</b></div><div class="lock"><span>LOCK</span><b>IMMUTABLE</b></div><div class="future"><span>WAIT</span><b>FUTURE</b></div><div class="future"><span>RESOLVE</span><b>OUTCOME</b></div><div class="future"><span>SCORE</span><b>RECORD</b></div></div>
<div class="gridbottom">
  <div class="panel score"><div class="panel-title">SCIENTIFIC SCOREBOARD · PUBLIC FORWARD RECORD</div><div class="score-grid"><div class="score-card"><b>{metrics['locked']}</b><span>LOCKED</span></div><div class="score-card"><b>{metrics['resolved']}</b><span>RESOLVED</span></div><div class="score-card"><b>{metrics['correct']}</b><span>CORRECT</span></div><div class="score-card"><b>{pct(metrics['accuracy']) if metrics['accuracy'] is not None else 'COLLECTING'}</b><span>ACCURACY</span></div><div class="score-card"><b>{decimal(metrics['brier']) if metrics['brier'] is not None else 'PENDING'}</b><span>BRIER SCORE</span></div><div class="score-card"><b>{metrics['edge_status']}</b><span>EDGE STATUS</span></div></div></div>
  <div class="panel calibration"><div class="panel-title">CALIBRATION LADDER</div>{calibration_html}</div>
  <div class="panel recent"><div class="panel-title">RECENT PREDICTIONS</div><table><thead><tr><th>#</th><th>ASSET</th><th>DIR</th><th>PROB.</th><th>STATUS</th></tr></thead><tbody>{recent_rows_html}</tbody></table></div>
</div>
<footer><span>SEE IT COMING. · FROM CHAOS TO SIGNAL.</span><span>DON'T TRUST THE MODEL. CHECK THE RECORD. · EXPERIMENTAL</span></footer>
</div>
<script id="snapshot-data" type="application/json">{snapshot_json}</script>
<script>
(() => {{
  const snapshot = JSON.parse(document.getElementById('snapshot-data').textContent);
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const healthBadge = document.getElementById('healthBadge');
  const snapshotAge = document.getElementById('snapshotAge');
  const generated = new Date(snapshot.generated_at);
  function updateHealth() {{
    const age = Math.max(0, (Date.now() - generated.getTime()) / 60000);
    let state = snapshot.system_status_at_build;
    if (snapshot.available_assets === 0) state = 'NO DATA';
    else if (age > snapshot.stale_after_minutes) state = 'STALE';
    else if (snapshot.available_assets < snapshot.total_assets) state = 'DEGRADED';
    else state = 'LIVE';
    healthBadge.className = 'health ' + state.toLowerCase().replaceAll(' ','-');
    healthBadge.textContent = state + ' · ' + snapshot.available_assets + '/' + snapshot.total_assets;
    snapshotAge.textContent = 'DATA SNAPSHOT · ' + generated.toISOString().slice(0,16).replace('T',' ') + ' UTC · ' + Math.round(age) + 'm old';
  }}
  updateHealth(); setInterval(updateHealth, 30000);

  const latest = snapshot.latest_forecast;
  const resolution = snapshot.latest_resolution;
  if (latest && !resolution) {{
    const age = Math.max(0, (Date.now() - new Date(latest.created_at).getTime()) / 60000);
    const panel = document.getElementById('forecastPanel');
    const badge = document.getElementById('freshBadge');
    const proof = document.getElementById('proofHash');
    if (age < 15) {{
      panel.classList.add('fresh'); badge.textContent = ' · FORECAST LOCKED';
      if (!reduce && proof && proof.dataset.proof) {{
        const full = proof.dataset.proof; let i = 2; proof.textContent = '';
        const timer = setInterval(() => {{ proof.textContent = full.slice(0, i); i += 2; if (i > full.length) {{ proof.textContent = full; clearInterval(timer); }} }}, 35);
      }}
    }} else if (age < 60) badge.textContent = ' · NEWLY LOCKED';
  }}

  const stream = document.getElementById('streamList');
  let streamIndex = 0, streamTimer = null;
  function runStream() {{
    if (reduce || document.hidden || !stream) return;
    const rows = [...stream.querySelectorAll('[data-stream-row]')];
    if (rows.length < 2) return;
    streamIndex = (streamIndex + 1) % rows.length;
    stream.style.transform = `translateY(${{-streamIndex * rows[0].offsetHeight}}px)`;
  }}
  if (!reduce) streamTimer = setInterval(runStream, 1900);

  const canvas = document.getElementById('chaosCanvas');
  const ctx = canvas.getContext('2d');
  let animationId = null, running = !reduce;
  const particles = Array.from({{length:44}}, (_, i) => ({{
    a:(i*0.61803398875)%1*Math.PI*2,
    r:0.18+((i*37)%61)/100,
    s:0.0006+((i*17)%9)/9000,
    z:0.35+((i*23)%65)/100
  }}));
  function resize() {{
    const rect = canvas.getBoundingClientRect();
    const dpr = Math.min(devicePixelRatio || 1, 2);
    canvas.width = Math.max(1, Math.round(rect.width*dpr)); canvas.height = Math.max(1, Math.round(rect.height*dpr));
    ctx.setTransform(dpr,0,0,dpr,0,0);
  }}
  function draw(t=0) {{
    if (!running) return;
    const w=canvas.clientWidth,h=canvas.clientHeight,cx=w*.5,cy=h*.52,rx=w*.34,ry=h*.31;
    ctx.clearRect(0,0,w,h);
    const glow=ctx.createRadialGradient(cx,cy,10,cx,cy,Math.max(rx,ry)); glow.addColorStop(0,'rgba(44,96,255,.24)'); glow.addColorStop(.55,'rgba(76,48,180,.09)'); glow.addColorStop(1,'rgba(0,0,0,0)'); ctx.fillStyle=glow;ctx.fillRect(0,0,w,h);
    ctx.lineWidth=1;
    for(let ring=0; ring<4; ring++) {{
      ctx.beginPath(); ctx.strokeStyle=`rgba(${{40+ring*20}},${{130+ring*10}},255,${{.12+ring*.035}})`;
      ctx.ellipse(cx,cy,rx*(.58+ring*.12),ry*(.58+ring*.12),(-.22+ring*.11)+(t/90000)*(ring%2?1:-1),0,Math.PI*2); ctx.stroke();
    }}
    const pts=[];
    particles.forEach((p,i)=>{{
      const a=p.a+t*p.s; const x=cx+Math.cos(a)*rx*p.r; const y=cy+Math.sin(a*1.17)*ry*p.r*.84;
      pts.push([x,y,p.z]); ctx.beginPath(); ctx.fillStyle=i%9===0?'rgba(255,82,157,.62)':i%5===0?'rgba(41,230,255,.68)':'rgba(83,128,255,.48)'; ctx.arc(x,y,1+p.z*1.2,0,Math.PI*2);ctx.fill();
    }});
    for(let i=0;i<pts.length;i++) for(let j=i+1;j<pts.length;j++) {{ const dx=pts[i][0]-pts[j][0],dy=pts[i][1]-pts[j][1],d=Math.hypot(dx,dy); if(d<82) {{ctx.strokeStyle=`rgba(70,135,255,${{(1-d/82)*.11}})`;ctx.beginPath();ctx.moveTo(pts[i][0],pts[i][1]);ctx.lineTo(pts[j][0],pts[j][1]);ctx.stroke();}} }}
    animationId=requestAnimationFrame(draw);
  }}
  resize(); addEventListener('resize', resize); if (running) animationId=requestAnimationFrame(draw);
  document.addEventListener('visibilitychange',()=>{{
    running = !reduce && !document.hidden;
    if (running && !animationId) animationId=requestAnimationFrame(draw);
    if (!running && animationId) {{cancelAnimationFrame(animationId);animationId=null;}}
  }});
}})();
</script>
</body>
</html>'''

(OUT / "index.html").write_text(page)
(OUT / "ledger.json").write_text(json.dumps(ledger, indent=2))
(OUT / "snapshot.json").write_text(json.dumps(snapshot, indent=2))
print("Built OBSERVATORY CHAOS V3.2 MOTION:", OUT / "index.html", "| market:", initial_status, f"{available}/{len(SYMBOLS)}")
