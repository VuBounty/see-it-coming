from dataclasses import dataclass
import math

@dataclass(frozen=True)
class ModelVote:
    name: str
    direction: str
    probability: float
    raw: float

def _vote(name, raw):
    p=0.5+min(abs(raw),0.45)
    return ModelVote(name, "UP" if raw>=0 else "DOWN", round(p,4), round(raw,5))

def momentum(f):
    raw=.58*math.tanh(f["r6"]*18)+.42*math.tanh(f["r24"]*8)
    return _vote("momentum-v1",raw)

def breakout(f):
    raw=.72*math.tanh(f["z"]/2)+.28*math.tanh((f["vr"]-1)/2)
    return _vote("breakout-v1",raw)

def mean_reversion(f):
    raw=-.8*math.tanh(f["z"]/2)+.2*math.tanh(f["r6"]*10)
    return _vote("mean-reversion-v1",raw)

def ensemble(f):
    votes=[momentum(f),breakout(f),mean_reversion(f)]
    signed=[(1 if v.direction=="UP" else -1)*(v.probability-.5) for v in votes]
    raw=sum(signed)/len(signed)
    direction="UP" if raw>=0 else "DOWN"
    probability=round(.5+min(abs(raw)*1.7,.42),4)
    return {"direction":direction,"probability":probability,"raw":round(raw,5),"votes":[v.__dict__ for v in votes]}
