import json, tempfile
from app.domain import Prediction, Resolution
from app.store import Ledger
from app.metrics import brier, accuracy

def pred(i="1"):
    return Prediction(i,"ETH","UP",.8,6,3.0,"MEDIUM",("momentum","volume"),"V1","2026-09-26T00:00:00+00:00")

def test_hash_is_deterministic():
    assert pred().proof_hash == pred().proof_hash
    assert len(pred().proof_hash)==64

def test_prediction_is_append_only():
    with tempfile.TemporaryDirectory() as d:
        l=Ledger(d+"/l.json"); l.add_prediction(pred())
        try: l.add_prediction(pred()); assert False
        except ValueError: pass

def test_resolution_requires_prediction():
    with tempfile.TemporaryDirectory() as d:
        l=Ledger(d+"/l.json")
        try: l.add_resolution(Resolution("x","CORRECT","now",2)); assert False
        except ValueError: pass

def test_resolution_only_once():
    with tempfile.TemporaryDirectory() as d:
        l=Ledger(d+"/l.json"); l.add_prediction(pred())
        l.add_resolution(Resolution("1","CORRECT","now",3))
        try: l.add_resolution(Resolution("1","WRONG","later",-2)); assert False
        except ValueError: pass

def test_metrics():
    rows=[{"probability":.8,"actual":1},{"probability":.7,"actual":0}]
    assert round(brier(rows),3)==.265
    assert accuracy(rows)==.5
