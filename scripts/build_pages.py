import json, html, math, sys
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.market import klines_with_source, features, score, market_universe
from app.presentation import market_state, scientific_metrics, forecast_ui_state

LEDGER_PATH = ROOT / 'data' / 'ledger.json'
OUT = ROOT / 'site'
OUT.mkdir(exist_ok=True)
CORE = ['BTCUSDT','ETHUSDT','SOLUSDT','BNBUSDT','XRPUSDT','DOGEUSDT']
UNIVERSE_LIMIT = 100
STALE_AFTER_MINUTES = 90


def esc(v):
    return html.escape(str(v))


def evmap(p):
    out = {}
    for item in p.get('evidence', []):
        if '=' in item:
            k, v = item.split('=', 1)
            out[k] = v
    return out


def polyline(values, w=100.0, h=28.0, pad=2.0):
    if not values:
        return ''
    if len(values) == 1:
        return f'0,{h/2:.2f} {w},{h/2:.2f}'
    lo, hi = min(values), max(values)
    span = (hi-lo) or 1.0
    pts=[]
    for i,val in enumerate(values):
        x=i/(len(values)-1)*w
        y=h-pad-((val-lo)/span)*(h-2*pad)
        pts.append(f'{x:.2f},{y:.2f}')
    return ' '.join(pts)


def pct(x, d=1):
    return '—' if x is None else f'{x*100:.{d}f}%'


def dec(x, d=3):
    return '—' if x is None else f'{x:.{d}f}'


def price_text(v):
    v=float(v)
    if v >= 1000: return f'{v:,.0f}'
    if v >= 1: return f'{v:,.4f}'.rstrip('0').rstrip('.')
    if v >= .01: return f'{v:.5f}'.rstrip('0').rstrip('.')
    return f'{v:.8f}'.rstrip('0').rstrip('.')


def stable_seed(text):
    return sum((i+1)*ord(c) for i,c in enumerate(text)) % 10000


ledger = json.loads(LEDGER_PATH.read_text()) if LEDGER_PATH.exists() else {'predictions':[], 'resolutions':[]}
predictions = ledger.get('predictions', [])
resolutions = ledger.get('resolutions', [])
resolution_map = {r['prediction_id']: r for r in resolutions}
metrics = scientific_metrics(predictions, resolutions)
generated_at = datetime.now(timezone.utc).isoformat()
locked_assets = {p['asset'] for p in predictions if p['id'] not in resolution_map}


def load_core(symbol):
    try:
        bars, provider = klines_with_source(symbol, limit=72)
        feat = features(bars)
        s = score(feat)
        return {
            'symbol': symbol, 'price': feat['price'], 'r1': feat['r1'], 'r6': feat['r6'], 'r24': feat['r24'],
            'z': feat['z'], 'vr': feat['vr'], 'anomaly': s['anomaly'], 'direction': s['direction'],
            'confidence': s['confidence'], 'provider': provider,
            'state': market_state(s['anomaly'], symbol in locked_assets),
            'bars': [{'t': int(x['t']), 'c': float(x['c'])} for x in bars[-36:]],
        }
    except Exception as ex:
        return {'symbol':symbol, 'error':str(ex), 'provider':'unavailable', 'state':'NO DATA', 'bars':[]}

with ThreadPoolExecutor(max_workers=len(CORE)) as ex:
    core_assets = list(ex.map(load_core, CORE))
core_map = {x['symbol']:x for x in core_assets}
core_ok = [x for x in core_assets if 'error' not in x]

# Broad market universe. It is independent from the prediction list.
universe_source='unavailable'
universe=[]
universe_error=None
universe_generated_at=generated_at
universe_cached=False
try:
    universe, universe_source = market_universe(UNIVERSE_LIMIT)
    (OUT/'universe.json').write_text(json.dumps({'generated_at':generated_at,'source':universe_source,'assets':universe}, indent=2))
except Exception as ex:
    universe_error=str(ex)
    cache=OUT/'universe.json'
    if cache.exists():
        try:
            cached=json.loads(cache.read_text())
            universe=cached.get('assets',[])
            universe_source=(cached.get('source') or 'cached')+' · CACHE'
            universe_generated_at=cached.get('generated_at') or generated_at
            universe_cached=True
        except Exception:
            universe=[]

# Never invent a market universe. If no broad provider/cache exists, show the real core data only and mark degraded.
if not universe:
    for x in core_ok:
        universe.append({
            'id':x['symbol'], 'symbol':x['symbol'].replace('USDT',''), 'name':x['symbol'].replace('USDT',''),
            'price':x['price'], 'change_24h':x['r24']*100, 'market_cap_rank':None, 'market_cap':None,
            'volume_24h':None, 'sparkline':[b['c'] for b in x['bars']], 'source':x['provider']
        })
    universe_source='CORE FALLBACK'
    universe_generated_at=generated_at
    universe_cached=False

# de-duplicate and sanitize
seen=set(); clean=[]
for row in universe:
    sym=str(row.get('symbol') or '').upper().strip()
    if not sym or sym in seen or row.get('price') is None:
        continue
    seen.add(sym)
    rr=dict(row); rr['symbol']=sym
    rr['change_24h']=float(rr.get('change_24h') or 0.0)
    rr['price']=float(rr['price'])
    rr['sparkline']=[float(v) for v in (rr.get('sparkline') or []) if v is not None][-48:]
    clean.append(rr)
universe=clean[:UNIVERSE_LIMIT]

available_core=len(core_ok)
market_status='LIVE' if available_core==len(CORE) and len(universe)>=30 and not universe_cached else ('DEGRADED' if (available_core or universe) else 'NO DATA')

latest=predictions[-1] if predictions else None
latest_resolution=resolution_map.get(latest['id']) if latest else None
latest_evidence=evmap(latest) if latest else {}
latest_ui_state=forecast_ui_state(latest['created_at'], latest_resolution.get('outcome') if latest_resolution else None) if latest else None

snapshot={
    'version':'V3.3-DEMO-MATCH', 'generated_at':generated_at, 'stale_after_minutes':STALE_AFTER_MINUTES,
    'system_status_at_build':market_status, 'available_core_assets':available_core, 'total_core_assets':len(CORE),
    'universe_count':len(universe), 'universe_source':universe_source, 'universe_error':universe_error,
    'universe_generated_at':universe_generated_at, 'universe_cached':universe_cached, 'freshness_anchor':universe_generated_at if universe_cached else generated_at,
    'core_assets':core_assets, 'universe':universe, 'metrics':metrics,
    'latest_forecast':latest, 'latest_resolution':latest_resolution, 'latest_ui_state':latest_ui_state,
}
(OUT/'snapshot.json').write_text(json.dumps(snapshot, indent=2))
(OUT/'ledger.json').write_text(json.dumps(ledger, indent=2))

# ---------- HERO CHAOS: cards from entire market, not prediction list ----------
# rank by a blend of prominence and absolute 24h movement; keep BTC/ETH visible when available.
majors={'BTC':0,'ETH':1,'SOL':2,'BNB':3,'XRP':4,'DOGE':5}
def visual_rank(r):
    major_bonus=1000-majors.get(r['symbol'],999)*70 if r['symbol'] in majors else 0
    cap_bonus=max(0,180-(r.get('market_cap_rank') or 999))
    return major_bonus + cap_bonus + min(250,abs(r['change_24h'])*13)
visual_pool=sorted(universe, key=visual_rank, reverse=True)
hero_assets=[]
for r in visual_pool:
    if r['symbol'] not in {x['symbol'] for x in hero_assets}:
        hero_assets.append(r)
    if len(hero_assets)>=18: break

# Fixed composition inspired by the approved golden reference. Secondary cards add controlled density.
slots=[
 (8,13,190,1.08),(37,5,210,1.15),(69,13,180,1.03),(9,61,180,1.00),(42,70,185,1.06),(72,60,190,1.02),
 (23,29,145,.86),(57,30,150,.88),(30,76,132,.78),(62,75,140,.82),(50,13,136,.82),(79,37,132,.80),
 (16,42,126,.76),(67,46,126,.76),(34,48,118,.72),(54,56,118,.72),(25,8,112,.68),(82,70,112,.68)
]
hero_cards=[]
for idx,row in enumerate(hero_assets):
    left,top,width,scale=slots[idx]
    ch=row['change_24h']; gain=ch>=0; cls='gain' if gain else 'loss'; arrow='↑' if gain else '↓'
    spark=polyline(row.get('sparkline',[]),100,24) if row.get('sparkline') else ''
    seed=stable_seed(row['symbol'])
    drift=4+(seed%10); dur=8+(seed%8); delay=-(seed%7)
    hero_cards.append(f'''<div class="market-card {cls} {'secondary' if idx>=6 else ''}" data-chaos-card data-symbol="{esc(row['symbol'])}" style="left:{left}%;top:{top}%;width:{width}px;--drift:{drift}px;--dur:{dur}s;--delay:{delay}s;--scale:{scale}">
      <div class="mc-head"><b>{esc(row['symbol'])}</b><strong>{arrow} {ch:+.2f}%</strong></div>
      <div class="mc-price">${esc(price_text(row['price']))}</div>
      <svg viewBox="0 0 100 24" preserveAspectRatio="none">{f'<polyline points="{spark}"/>' if spark else ''}</svg>
    </div>''')
hero_cards_html=''.join(hero_cards)

# Micro market labels from broader universe to make the chaos field dense without pretending they are forecasted.
micro=[]
for idx,row in enumerate(universe[18:60]):
    seed=stable_seed(row['symbol'])
    left=4+(seed*7)%88; top=5+(seed*11)%86
    ch=row['change_24h']; cls='pos' if ch>=0 else 'neg'
    micro.append(f'<span class="micro-token {cls}" style="left:{left}%;top:{top}%;--d:{12+(seed%15)}s;--dl:{-(seed%10)}s">{esc(row["symbol"])} {ch:+.1f}%</span>')
micro_html=''.join(micro)

# Right market board: most active by abs 24h change from broad universe.
movers=sorted(universe,key=lambda r:abs(r['change_24h']),reverse=True)[:12]
market_rows=''.join(
    f'<tr><td>{esc(r["symbol"])}</td><td>{esc(price_text(r["price"]))}</td><td class="{"pos" if r["change_24h"]>=0 else "neg"}">{r["change_24h"]:+.2f}%</td><td><span class="trend-dot {"pos" if r["change_24h"]>=0 else "neg"}"></span></td></tr>'
    for r in movers
)
# Tape interleaves gainers/losers from entire universe.
tape_pool=sorted(universe,key=lambda r:abs(r['change_24h']),reverse=True)[:18]
tape_rows=''.join(
    f'<div class="tape-row"><span>SNAPSHOT</span><b>{esc(r["symbol"])}</b><strong>{esc(price_text(r["price"]))}</strong><em class="{"pos" if r["change_24h"]>=0 else "neg"}">{r["change_24h"]:+.2f}%</em></div>'
    for r in tape_pool
)

# ---------- latest forecast ----------
if latest:
    la=latest['asset'].replace('USDT',''); direction=latest.get('direction','—'); arrow='↑' if direction=='UP' else '↓'; dcls='up' if direction=='UP' else 'down'
    outcome=latest_resolution.get('outcome') if latest_resolution else 'UNKNOWN'
    latest_html=f'''<div class="forecast-identity"><div class="coin-emblem">{esc(la[:2])}</div><div><h3>{esc(la)} / USD</h3><div class="forecast-dir {dcls}">{arrow} {esc(direction)}</div><div class="forecast-prob">{float(latest['probability'])*100:.1f}<small>%</small></div><span>MODEL PROBABILITY</span></div></div>
    <div class="forecast-facts"><div><span>Entry observation</span><b>{esc(latest_evidence.get('entry','—'))}</b></div><div><span>Target move</span><b>{esc(latest.get('target_pct','—'))}%</b></div><div><span>Horizon</span><b>{esc(latest.get('horizon_hours','—'))}H</b></div><div><span>Decision threshold</span><b>53.0%</b></div><div><span>Locked at</span><b>{esc(latest.get('created_at','—'))[:19]} UTC</b></div><div><span>Outcome</span><b>{esc(outcome)}</b></div></div>'''
    def bw(key,scale,base=18):
        try:return min(100,abs(float(latest_evidence.get(key,0)))*scale+base)
        except:return base
    why_html=''.join([
      f'<div class="why-row"><span>Momentum 6H</span><i><u style="width:{bw("r6",1800):.0f}%"></u></i><b>{esc(latest_evidence.get("r6","—"))}</b></div>',
      f'<div class="why-row"><span>Momentum 24H</span><i><u style="width:{bw("r24",900):.0f}%"></u></i><b>{esc(latest_evidence.get("r24","—"))}</b></div>',
      f'<div class="why-row"><span>Price deviation</span><i><u style="width:{bw("z",28):.0f}%"></u></i><b>{esc(latest_evidence.get("z","—"))}</b></div>',
      f'<div class="why-row"><span>Volume ratio</span><i><u style="width:{bw("vr",42):.0f}%"></u></i><b>{esc(latest_evidence.get("vr","—"))}</b></div>',
    ])
    proof_hash=latest.get('proof_hash','—'); forecast_status=latest_resolution.get('outcome') if latest_resolution else 'LOCKED'; latest_asset=latest['asset']
else:
    latest_html='<div class="empty-state">NO LOCKED FORECAST YET</div>'; why_html='<div class="empty-state">WAITING FOR A QUALIFIED SIGNAL</div>'; proof_hash='—'; forecast_status='WAITING'; latest_asset='BTCUSDT'

chart_asset=core_map.get(latest_asset)
chart_points=polyline([b['c'] for b in chart_asset.get('bars',[])],100,100,7) if chart_asset and 'error' not in chart_asset else ''
chart_provider=chart_asset.get('provider','unavailable') if chart_asset else 'unavailable'

# ---------- metrics / calibration / recent ----------
cal=[]
for lo,hi in [(0.50,.60),(.60,.70),(.70,.80),(.80,.90),(.90,1.01)]:
    vals=[]
    for p in predictions:
        r=resolution_map.get(p['id'])
        q=float(p['probability'])
        if r and r.get('outcome') in ('CORRECT','WRONG') and lo<=q<hi:
            vals.append(1 if r['outcome']=='CORRECT' else 0)
    obs=sum(vals)/len(vals) if vals else None
    cal.append((f'{int(lo*100)}–{int(min(1,hi)*100)}%',obs,len(vals)))
cal_html=''.join(f'<div class="cal-line"><span>{band}</span><div><i style="width:{0 if obs is None else obs*100:.1f}%"></i></div><b>{"waiting" if obs is None else f"{obs*100:.1f}%"}</b><em>N={n}</em></div>' for band,obs,n in reversed(cal))
recent=''.join(f'<tr><td>{esc(p["id"][-6:])}</td><td>{esc(p["asset"].replace("USDT",""))}</td><td class="{"pos" if p["direction"]=="UP" else "neg"}">{esc(p["direction"])}</td><td>{float(p["probability"])*100:.1f}%</td><td>{esc((resolution_map.get(p["id"]) or {}).get("outcome") or "LOCKED")}</td></tr>' for p in reversed(predictions[-6:]))

snapshot_json=json.dumps(snapshot,separators=(',',':')).replace('</','<\\/')

page=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#030817"><title>SEE IT COMING. — Market Observatory</title><meta name="description" content="A public forward-locked market intelligence experiment."><!-- SIC-V3.3-DEMO-MATCH-FREEZE -->
<style>
:root{{--bg:#030817;--panel:#06132a;--panel2:#081a38;--line:#123c73;--blue:#2d78ff;--cyan:#22e5ff;--violet:#8a57ff;--pink:#ff4a9f;--red:#ff4f73;--mint:#23f2ba;--white:#f7fbff;--muted:#86a0c8}}*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:radial-gradient(circle at 52% 16%,#102451 0,#071329 33%,#030817 74%);color:var(--white);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;overflow-x:hidden}}body:before{{content:"";position:fixed;inset:0;pointer-events:none;background:linear-gradient(rgba(41,93,165,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(41,93,165,.035) 1px,transparent 1px);background-size:46px 46px}}.shell{{width:min(1540px,calc(100% - 38px));margin:auto;position:relative}}nav{{height:62px;display:flex;align-items:center;gap:34px;border-bottom:1px solid rgba(48,109,197,.32)}}.brand{{font-size:19px;font-weight:950;letter-spacing:-.04em;margin-right:16px}}.brand i{{font-style:normal;color:var(--pink)}}.navlinks{{display:flex;gap:27px;font-size:10px;color:#a9bee1}}.navlinks span:first-child{{color:#6aa8ff;text-shadow:0 0 16px #2b70ff}}.navstate{{margin-left:auto;font-size:8px;letter-spacing:.16em;color:#7f96bd}}.livebadge{{border:1px solid #3c78ff;border-radius:7px;padding:7px 10px;font-size:8px;color:#72a8ff;font-weight:800}}.livebadge.live{{border-color:#20dcb0;color:#48f1c6}}.hero{{display:grid;grid-template-columns:320px 1fr 300px;min-height:430px;border-bottom:1px solid rgba(48,109,197,.26)}}.hero-copy{{padding:46px 18px 28px 0;z-index:5}}.eyebrow{{display:block;color:#74a9ff;font-size:9px;letter-spacing:.21em;font-weight:900;margin-bottom:17px}}h1{{font-size:68px;line-height:.86;letter-spacing:-.065em;margin:0 0 23px}}h1 span{{background:linear-gradient(100deg,#5ba5ff,#9562ff 55%,#ff5aa7);-webkit-background-clip:text;background-clip:text;color:transparent}}.hero-copy p{{color:#b0c0dd;font-size:16px;line-height:1.45;max-width:300px}}.trust{{display:flex;gap:15px;flex-wrap:wrap;margin-top:23px;font-size:7px;letter-spacing:.11em;color:#8aa3ca}}.market-universe{{position:relative;min-height:430px;overflow:hidden;isolation:isolate}}#universeCanvas{{position:absolute;inset:0;width:100%;height:100%;z-index:0}}.market-universe:after{{content:"";position:absolute;inset:0;z-index:1;background:radial-gradient(circle at 50% 50%,rgba(34,229,255,.09),transparent 25%),radial-gradient(circle at 50% 52%,rgba(93,72,255,.16),transparent 42%);pointer-events:none}}.market-card{{position:absolute;z-index:4;padding:10px 12px;border-radius:9px;background:rgba(5,19,43,.88);border:1px solid #21588d;box-shadow:0 8px 28px rgba(0,0,0,.3),0 0 22px rgba(40,111,255,.10);transform:translate(-50%,-50%) scale(var(--scale));animation:cardDrift var(--dur) ease-in-out var(--delay) infinite alternate}}@keyframes cardDrift{{to{{transform:translate(calc(-50% + var(--drift)),calc(-50% - var(--drift)*.55)) scale(var(--scale))}}}}.market-card.gain{{border-color:rgba(35,242,186,.52)}}.market-card.loss{{border-color:rgba(255,79,115,.58)}}.market-card.secondary{{opacity:.77;filter:saturate(.92)}}.mc-head{{display:flex;justify-content:space-between;align-items:center;gap:9px}}.mc-head b{{font-size:12px}}.mc-head strong{{font-size:12px}}.gain .mc-head strong{{color:var(--mint)}}.loss .mc-head strong{{color:var(--red)}}.mc-price{{font-size:7px;color:#738eb9;margin-top:2px}}.market-card svg{{width:100%;height:22px;margin-top:5px}}.market-card polyline{{fill:none;stroke:currentColor;stroke-width:2;vector-effect:non-scaling-stroke}}.market-card.gain{{color:var(--mint)}}.market-card.loss{{color:var(--red)}}.micro-token{{position:absolute;z-index:2;font:800 7px ui-monospace,monospace;opacity:.46;animation:microDrift var(--d) ease-in-out var(--dl) infinite alternate}}.micro-token.pos{{color:#42e8b7}}.micro-token.neg{{color:#ff5d7b}}@keyframes microDrift{{to{{transform:translate(22px,-13px);opacity:.72}}}}.side{{padding:11px 0 11px 12px;display:grid;grid-template-rows:1.06fr .94fr;gap:9px}}.sidebox,.panel{{border:1px solid #12477e;border-radius:8px;background:linear-gradient(145deg,rgba(6,20,43,.96),rgba(3,12,27,.96));overflow:hidden}}.sidebox h3,.panel-title{{font-size:10px;letter-spacing:.08em;margin:0;padding:11px 13px;border-bottom:1px solid #123b69;color:#bfd1ef}}table{{width:100%;border-collapse:collapse}}th,td{{padding:5px 8px;text-align:left;border-bottom:1px solid rgba(30,75,128,.27);font-size:8px}}th{{font-size:6px;color:#6f88b3;letter-spacing:.11em}}.pos{{color:var(--mint)}}.neg{{color:var(--red)}}.trend-dot{{display:block;width:38px;height:2px;background:currentColor;box-shadow:0 0 9px currentColor}}.tape-window{{height:160px;overflow:hidden;position:relative}}.tape-list{{animation:tapeScroll 22s linear infinite}}@keyframes tapeScroll{{to{{transform:translateY(-50%)}}}}.tape-row{{display:grid;grid-template-columns:54px 1fr 1fr 54px;gap:7px;padding:6px 9px;border-bottom:1px solid rgba(30,75,128,.22);font-size:8px}}.tape-row span{{color:#607ca9}}.tape-row em{{font-style:normal;text-align:right}}.side-note{{padding:7px 9px;color:#5f789f;font-size:6px}}.pipeline{{margin:14px 0 10px;border:1px solid #17559b;border-radius:9px;background:linear-gradient(90deg,rgba(4,28,62,.92),rgba(6,17,42,.94));display:grid;grid-template-columns:150px repeat(8,1fr);align-items:center;overflow:hidden}}.pipe-title{{padding:16px;color:#5ba2ff;font-size:10px;font-weight:900;letter-spacing:.12em}}.step{{padding:13px 5px;text-align:center;position:relative}}.step:after{{content:"→";position:absolute;right:-5px;top:20px;color:#426da8}}.step:last-child:after{{display:none}}.step i{{display:grid;place-items:center;width:27px;height:27px;margin:auto;border-radius:50%;border:1px solid #527cf0;color:#79a6ff;box-shadow:0 0 15px rgba(55,112,255,.35)}}.step:nth-child(4) i{{border-color:#a357ff;color:#b983ff}}.step:nth-child(5) i{{border-color:#ff4a9f;color:#ff75b2}}.step:nth-child(7) i{{border-color:#22e5ff;color:#22e5ff}}.step b{{display:block;font-size:7px;margin-top:7px}}.step span{{font-size:6px;color:#7087ad}}.gridtop{{display:grid;grid-template-columns:1.15fr 1.18fr .84fr;gap:9px;margin-bottom:9px}}.forecast-panel{{display:grid;grid-template-columns:1.08fr 1fr;gap:15px;padding:16px}}.forecast-identity{{display:flex;gap:13px;align-items:center}}.coin-emblem{{width:67px;height:67px;border-radius:50%;display:grid;place-items:center;background:radial-gradient(circle,#1d63ff,#101a36);border:1px solid #3977dd;font-weight:900}}.forecast-identity h3{{font-size:17px;margin:0 0 4px}}.forecast-dir{{font-size:15px;font-weight:900}}.forecast-dir.up{{color:var(--mint)}}.forecast-dir.down{{color:var(--red)}}.forecast-prob{{font-size:43px;font-weight:950;letter-spacing:-.05em;color:#31efc2}}.forecast-prob small{{font-size:16px}}.forecast-identity span{{font-size:6px;letter-spacing:.12em;color:#7890b8}}.forecast-facts div{{display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid rgba(39,78,128,.25);font-size:8px}}.forecast-facts span{{color:#8299bf}}.whybox{{padding:13px}}.why-row{{display:grid;grid-template-columns:92px 1fr 57px;gap:8px;align-items:center;margin:10px 0;font-size:7px}}.why-row span{{color:#8da2c5}}.why-row i{{height:8px;background:#10284e;border-radius:99px;overflow:hidden}}.why-row u{{display:block;height:100%;background:linear-gradient(90deg,#8e57ff,#25dcff);border-radius:99px;text-decoration:none}}.why-row b{{font-size:7px}}.proofbox{{display:grid;grid-template-columns:48px 1fr;gap:10px;padding:12px;border-top:1px solid rgba(30,75,128,.25)}}.lockicon{{width:45px;height:45px;border-radius:50%;display:grid;place-items:center;border:1px solid #ff4a9f;color:#ff68ad;box-shadow:0 0 22px rgba(255,74,159,.25)}}.proofbox code{{display:block;font-size:7px;color:#a3b8dc;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.proofstatus{{font-size:7px;margin-top:6px}}.chartbox{{padding:11px}}.chartbox svg{{width:100%;height:122px}}.chartbox polyline{{fill:none;stroke:url(#grad);stroke-width:2.2;vector-effect:non-scaling-stroke;stroke-dasharray:240;stroke-dashoffset:240;animation:draw 1.1s ease forwards}}@keyframes draw{{to{{stroke-dashoffset:0}}}}.gridbottom{{display:grid;grid-template-columns:1.32fr .58fr .67fr;gap:9px;margin-bottom:30px}}.score{{padding:12px}}.score-grid{{display:grid;grid-template-columns:repeat(6,1fr);gap:7px;margin-top:9px}}.score-card{{padding:12px 8px;border:1px solid #173f70;border-radius:7px;background:rgba(5,18,39,.55)}}.score-card b{{font-size:20px}}.score-card span{{display:block;color:#849bc0;font-size:6px;margin-top:5px}}.calibration{{padding:10px}}.cal-line{{display:grid;grid-template-columns:55px 1fr 52px 32px;gap:6px;align-items:center;margin:7px 0;font-size:6px}}.cal-line>div{{height:6px;background:#11274b;border-radius:99px;overflow:hidden}}.cal-line i{{display:block;height:100%;background:linear-gradient(90deg,#4b85ff,#a35cff)}}.cal-line em{{font-style:normal;color:#7187ad}}.recent td{{font-size:7px}}footer{{border-top:1px solid rgba(53,109,190,.28);padding:21px 0 34px;display:flex;justify-content:space-between;color:#6c83a9;font-size:7px;letter-spacing:.12em}}.empty-state{{padding:28px;color:#7d93b8}}
@media(max-width:1180px){{.hero{{grid-template-columns:295px 1fr}}.side{{grid-column:1/-1;grid-template-columns:1fr 1fr;grid-template-rows:auto}}.gridtop,.gridbottom{{grid-template-columns:1fr}}.pipeline{{grid-template-columns:140px repeat(4,1fr)}}}}@media(max-width:760px){{.navlinks,.navstate{{display:none}}.hero{{grid-template-columns:1fr}}.hero-copy{{padding-right:0}}h1{{font-size:58px}}.market-universe{{min-height:620px}}.side{{grid-template-columns:1fr}}.pipeline{{grid-template-columns:1fr 1fr 1fr}}.score-grid{{grid-template-columns:1fr 1fr}}.forecast-panel{{grid-template-columns:1fr}}}}@media(prefers-reduced-motion:reduce){{*,*:before,*:after{{animation:none!important;transition:none!important;scroll-behavior:auto!important}}}}
</style></head><body><div class="shell">
<nav><div class="brand">SEE IT COMING<i>.</i></div><div class="navlinks"><span>Home</span><span>Live</span><span>Forecasts</span><span>Record</span><span>Method</span><span>About</span></div><div class="navstate">● PUBLIC FORWARD EXPERIMENT · V1.0</div><div class="livebadge {market_status.lower().replace(' ','-')}" id="healthBadge">{market_status} · {len(universe)} MARKET</div></nav>
<section class="hero"><div class="hero-copy"><span class="eyebrow">THE MOVE HASN'T HAPPENED YET.</span><h1>See it<br><span>before</span><br>it moves.</h1><p>Predictions are locked before outcomes. No edits. No deleted losses. Reality keeps the score.</p><div class="trust"><span>◉ FORWARD ONLY</span><span>◉ PUBLIC PROOF</span><span>◉ NO BACKFILLING</span><span>◉ NO TRADE EXECUTION</span></div></div>
<div class="market-universe" id="marketUniverse"><canvas id="universeCanvas"></canvas>{micro_html}{hero_cards_html}</div>
<div class="side"><div class="sidebox"><h3>LIVE MARKET UNIVERSE</h3><table><thead><tr><th>ASSET</th><th>PRICE</th><th>24H</th><th>TREND</th></tr></thead><tbody>{market_rows}</tbody></table><div class="side-note">{esc(universe_source)} · {len(universe)} REAL MARKET ASSETS</div></div><div class="sidebox"><h3>MARKET OBSERVATION TAPE</h3><div class="tape-window"><div class="tape-list">{tape_rows}{tape_rows}</div></div><div class="side-note">SNAPSHOT DATA · NO SYNTHETIC TRADES</div></div></div></section>
<div class="pipeline"><div class="pipe-title">THE INTELLIGENCE<br>PIPELINE</div><div class="step"><i>◉</i><b>OBSERVE</b><span>Market universe</span></div><div class="step"><i>⌁</i><b>DETECT</b><span>Anomalies</span></div><div class="step"><i>△</i><b>PREDICT</b><span>Model ensemble</span></div><div class="step"><i>▣</i><b>LOCK</b><span>Immutable proof</span></div><div class="step"><i>◷</i><b>WAIT</b><span>Market decides</span></div><div class="step"><i>✓</i><b>RESOLVE</b><span>Measure outcome</span></div><div class="step"><i>∑</i><b>SCORE</b><span>Update record</span></div><div class="step"><i>↗</i><b>LEARN</b><span>Next version</span></div></div>
<div class="gridtop"><div class="panel"><div class="panel-title">LATEST LOCKED FORECAST</div><div class="forecast-panel">{latest_html}</div></div><div class="panel"><div class="panel-title">WHY IT FIRED</div><div class="whybox">{why_html}</div><div class="proofbox"><div class="lockicon">▣</div><div><span class="eyebrow" style="margin:0 0 5px">LOCKED PROOF · SHA-256</span><code>{esc(proof_hash)}</code><div class="proofstatus">STATUS · <b>{esc(forecast_status)}</b></div></div></div></div><div class="panel"><div class="panel-title">PRICE CHART · {esc(latest_asset.replace('USDT',''))} · {esc(chart_provider)}</div><div class="chartbox"><svg viewBox="0 0 100 100" preserveAspectRatio="none"><defs><linearGradient id="grad"><stop offset="0%" stop-color="#2d78ff"/><stop offset="100%" stop-color="#ae5cff"/></linearGradient></defs><polyline points="{chart_points}"/></svg></div></div></div>
<div class="gridbottom"><div class="panel score"><div class="panel-title">SCIENTIFIC SCOREBOARD · PUBLIC FORWARD RECORD</div><div class="score-grid"><div class="score-card"><b>{metrics['locked']}</b><span>LOCKED</span></div><div class="score-card"><b>{metrics['resolved']}</b><span>RESOLVED</span></div><div class="score-card"><b>{metrics['correct']}</b><span>CORRECT</span></div><div class="score-card"><b>{pct(metrics['accuracy']) if metrics['accuracy'] is not None else 'COLLECTING'}</b><span>ACCURACY</span></div><div class="score-card"><b>{dec(metrics['brier']) if metrics['brier'] is not None else 'PENDING'}</b><span>BRIER SCORE</span></div><div class="score-card"><b>{metrics['edge_status']}</b><span>EDGE STATUS</span></div></div></div><div class="panel calibration"><div class="panel-title">CALIBRATION</div>{cal_html}</div><div class="panel recent"><div class="panel-title">RECENT PREDICTIONS</div><table><thead><tr><th>#</th><th>ASSET</th><th>DIR</th><th>PROB.</th><th>STATUS</th></tr></thead><tbody>{recent}</tbody></table></div></div>
<footer><span>SEE IT COMING. · FROM CHAOS TO SIGNAL.</span><span>DON'T TRUST THE MODEL. CHECK THE RECORD. · EXPERIMENTAL</span></footer></div>
<script id="snapshot-data" type="application/json">{snapshot_json}</script>
<script>
(()=>{{const snap=JSON.parse(document.getElementById('snapshot-data').textContent);const reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;const canvas=document.getElementById('universeCanvas');const box=document.getElementById('marketUniverse');const ctx=canvas.getContext('2d');let raf=0,particles=[];function resize(){{const d=Math.min(devicePixelRatio||1,2);canvas.width=box.clientWidth*d;canvas.height=box.clientHeight*d;ctx.setTransform(d,0,0,d,0,0);particles=Array.from({{length:70}},(_,i)=>({{a:Math.random()*Math.PI*2,r:.15+Math.random()*.36,s:.0008+Math.random()*.002,x:Math.random(),y:Math.random()}}));}}function draw(t){{const w=box.clientWidth,h=box.clientHeight;ctx.clearRect(0,0,w,h);const cx=w*.5,cy=h*.53,rx=Math.min(w*.30,280),ry=rx*.58;ctx.save();ctx.globalCompositeOperation='lighter';for(let k=0;k<7;k++){{ctx.beginPath();ctx.strokeStyle=`rgba(${{k%2?'130,83,255':'32,218,255'}},${{.11+k*.018}})`;ctx.lineWidth=.8;ctx.ellipse(cx,cy,rx*(.65+k*.055),ry*(.65+k*.045),k*.28+t*.00003*(k%2?1:-1),0,Math.PI*2);ctx.stroke();}}for(let i=0;i<particles.length;i++){{const p=particles[i],a=p.a+t*p.s;const x=cx+Math.cos(a)*rx*p.r*2.2,y=cy+Math.sin(a*1.3)*ry*p.r*2.0;ctx.fillStyle=i%7===0?'rgba(255,70,151,.75)':'rgba(47,154,255,.55)';ctx.beginPath();ctx.arc(x,y,i%7===0?1.5:1,0,Math.PI*2);ctx.fill();if(i>0&&i%3===0){{const q=particles[i-1],aq=q.a+t*q.s,qx=cx+Math.cos(aq)*rx*q.r*2.2,qy=cy+Math.sin(aq*1.3)*ry*q.r*2;ctx.strokeStyle='rgba(63,120,255,.11)';ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(qx,qy);ctx.stroke();}}}}// decorative candle texture: intentionally unlabeled and non-numeric
for(let i=0;i<48;i++){{const x=(i/48)*w,y=h*.23+Math.sin(i*.9+t*.0004)*35+((i*17)%53);const up=(i%3)!==0;ctx.strokeStyle=up?'rgba(35,242,186,.15)':'rgba(255,79,115,.15)';ctx.beginPath();ctx.moveTo(x,y-9);ctx.lineTo(x,y+10);ctx.stroke();ctx.fillStyle=ctx.strokeStyle;ctx.fillRect(x-2,y-4,4,8);}}ctx.restore();if(!reduce&&!document.hidden)raf=requestAnimationFrame(draw);}}document.addEventListener('visibilitychange',()=>{{cancelAnimationFrame(raf);if(!document.hidden&&!reduce)raf=requestAnimationFrame(draw);}});addEventListener('resize',resize);resize();if(!reduce)raf=requestAnimationFrame(draw);const gen=new Date(snap.freshness_anchor||snap.generated_at);const badge=document.getElementById('healthBadge');function health(){{const age=(Date.now()-gen.getTime())/60000;let s=snap.system_status_at_build;if(age>snap.stale_after_minutes&&s!=='NO DATA')s='STALE';badge.textContent=s+' · '+snap.universe_count+' MARKET';badge.className='livebadge '+s.toLowerCase().replaceAll(' ','-');}}health();setInterval(health,30000);}})();
</script></body></html>'''

(OUT/'index.html').write_text(page)
print('Built V3.3 DEMO MATCH:', OUT/'index.html', '| universe:', len(universe), universe_source, '| core:', available_core, '/', len(CORE))

