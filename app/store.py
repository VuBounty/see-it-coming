import json,threading
from pathlib import Path
from dataclasses import asdict
from .domain import Prediction,Resolution
class Ledger:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self.lock=threading.RLock()
        if not self.path.exists():self.path.write_text(json.dumps({"predictions":[],"resolutions":[]},indent=2))
    def _read(self):return json.loads(self.path.read_text())
    def _write(self,data):
        tmp=self.path.with_suffix(self.path.suffix+".tmp");tmp.write_text(json.dumps(data,indent=2,sort_keys=True));tmp.replace(self.path)
    def add_prediction(self,p):
        with self.lock:
            d=self._read()
            if any(x["id"]==p.id for x in d["predictions"]):raise ValueError("prediction id already exists")
            row=asdict(p);row["proof_hash"]=p.proof_hash;d["predictions"].append(row);self._write(d);return row
    def add_resolution(self,r):
        with self.lock:
            d=self._read()
            if not any(x["id"]==r.prediction_id for x in d["predictions"]):raise ValueError("unknown prediction")
            if any(x["prediction_id"]==r.prediction_id for x in d["resolutions"]):raise ValueError("prediction already resolved")
            row=asdict(r);d["resolutions"].append(row);self._write(d);return row
    def snapshot(self):
        with self.lock:return self._read()
