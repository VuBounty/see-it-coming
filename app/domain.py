from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
from typing import Optional

class Status(str, Enum):
    LOCKED = "LOCKED"
    RESOLVED = "RESOLVED"

class Outcome(str, Enum):
    CORRECT = "CORRECT"
    WRONG = "WRONG"
    PARTIAL = "PARTIAL"
    INVALID = "INVALID"

@dataclass(frozen=True)
class Prediction:
    id: str
    asset: str
    direction: str
    probability: float
    horizon_hours: int
    target_pct: float
    risk: str
    evidence: tuple[str, ...]
    model_version: str
    created_at: str
    status: str = Status.LOCKED.value

    def canonical(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))

    @property
    def proof_hash(self) -> str:
        return sha256(self.canonical().encode()).hexdigest()

@dataclass(frozen=True)
class Resolution:
    prediction_id: str
    outcome: str
    resolved_at: str
    observed_move_pct: float
    notes: str = ""

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
