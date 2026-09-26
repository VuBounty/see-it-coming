from datetime import datetime, timezone, timedelta
from .domain import Prediction, Resolution
from .models import ensemble

def iso_now(): return datetime.now(timezone.utc).isoformat()
def make_prediction(symbol, f, horizon=12, now=None):
    e=ensemble(f); now=now or iso_now()
    safe=now.replace(":","").replace("+00:00","Z").replace("-","")
    pid=f"SIC-{symbol}-{safe}"
    target=max(0.8,min(6.0,abs(f["r24"])*100*.75+0.8))
    invalidation=max(0.6,min(3.0,target*.55))
    evidence=(f'entry={f["price"]:.12g}',f'r6={f["r6"]:.6f}',f'r24={f["r24"]:.6f}',f'z={f["z"]:.4f}',f'vr={f["vr"]:.4f}',f'invalidation_pct={invalidation:.2f}')
    return Prediction(pid,symbol,e["direction"],e["probability"],horizon,round(target,2),"EXPERIMENTAL",evidence,"ensemble-v1",now)

def due(pred, now=None):
    now=now or datetime.now(timezone.utc); created=datetime.fromisoformat(pred["created_at"].replace("Z","+00:00"))
    return now >= created + timedelta(hours=int(pred["horizon_hours"]))

def resolve_from_prices(pred, entry, future, now=None):
    move=(future/entry-1)*100
    signed=move if pred["direction"]=="UP" else -move
    outcome="CORRECT" if signed>=float(pred["target_pct"]) else "WRONG"
    return Resolution(pred["id"],outcome,now or iso_now(),round(move,6),f"entry={entry}; future={future}; signed_move={signed:.6f}")
