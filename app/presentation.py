from datetime import datetime, timezone
from typing import Optional


def _parse_iso(value: str) -> datetime:
    if not value:
        raise ValueError("timestamp required")
    value = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def age_minutes(value: str, now: Optional[datetime] = None) -> float:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    delta = now.astimezone(timezone.utc) - _parse_iso(value)
    return max(0.0, delta.total_seconds() / 60.0)


def health_status(generated_at: str, available: int, total: int, now: Optional[datetime] = None,
                  stale_after_minutes: int = 90) -> str:
    if total <= 0 or available <= 0:
        return "NO DATA"
    if age_minutes(generated_at, now) > stale_after_minutes:
        return "STALE"
    if available < total:
        return "DEGRADED"
    return "LIVE"


def market_state(anomaly: float, has_locked_forecast: bool = False) -> str:
    if has_locked_forecast:
        return "LOCKED FORECAST"
    anomaly = max(0.0, min(float(anomaly), 1.0))
    if anomaly < 0.20:
        return "QUIET"
    if anomaly < 0.45:
        return "WATCHING"
    if anomaly < 0.70:
        return "ELEVATED"
    return "HIGH ANOMALY"


def forecast_ui_state(created_at: str, resolution_outcome: Optional[str] = None,
                      now: Optional[datetime] = None) -> str:
    if resolution_outcome:
        return "RESOLVED"
    age = age_minutes(created_at, now)
    if age < 15:
        return "FRESH_LOCK"
    if age < 60:
        return "NEWLY_LOCKED"
    return "LOCKED"


def scientific_metrics(predictions, resolutions):
    resolution_map = {r["prediction_id"]: r for r in resolutions}
    scored = []
    for p in predictions:
        r = resolution_map.get(p["id"])
        if r and r.get("outcome") in ("CORRECT", "WRONG"):
            scored.append((float(p["probability"]), 1 if r["outcome"] == "CORRECT" else 0))

    n = len(scored)
    correct = sum(actual for _, actual in scored)
    accuracy = (correct / n) if n else None
    brier = (sum((prob - actual) ** 2 for prob, actual in scored) / n) if n else None

    return {
        "locked": len(predictions),
        "resolved": n,
        "correct": correct,
        "accuracy": accuracy,
        "brier": brier,
        "edge_status": "INSUFFICIENT DATA" if n < 50 else "EVALUATING",
    }
