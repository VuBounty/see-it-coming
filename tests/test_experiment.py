from datetime import datetime,timezone,timedelta
from app.models import ensemble
from app.experiment import make_prediction,due,resolve_from_prices
from app.verify import verify
from app.store import Ledger

def feat(): return {"price":100.0,"r1":.01,"r6":.04,"r24":.08,"z":1.4,"vr":1.8}
def test_ensemble_bounds():
    e=ensemble(feat());assert e["direction"] in ("UP","DOWN") and .5<=e["probability"]<=.92 and len(e["votes"])==3
def test_prediction_contains_entry_and_hash(tmp_path):
    p=make_prediction("BTCUSDT",feat(),now="2026-01-01T00:00:00+00:00");L=Ledger(str(tmp_path/'l.json'));row=L.add_prediction(p)
    assert any(x.startswith("entry=") for x in row["evidence"]);assert len(row["proof_hash"])==64;assert verify(L.snapshot())==[]
def test_due_and_resolution():
    p=make_prediction("BTCUSDT",feat(),horizon=12,now="2026-01-01T00:00:00+00:00");row={**p.__dict__}
    assert due(row,datetime(2026,1,1,13,tzinfo=timezone.utc));r=resolve_from_prices(row,100,110,now="2026-01-01T13:00:00+00:00");assert r.outcome=="CORRECT"
def test_hash_tamper_detected(tmp_path):
    p=make_prediction("ETHUSDT",feat(),now="2026-01-01T00:00:00+00:00");L=Ledger(str(tmp_path/'l.json'));L.add_prediction(p);d=L.snapshot();d["predictions"][0]["probability"]=.99;assert verify(d)
