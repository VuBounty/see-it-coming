def brier(rows):
    scored = [r for r in rows if r.get("actual") in (0,1)]
    if not scored:
        return None
    return sum((r["probability"] - r["actual"])**2 for r in scored) / len(scored)

def accuracy(rows):
    scored = [r for r in rows if r.get("actual") in (0,1)]
    if not scored:
        return None
    return sum((r["probability"] >= .5) == bool(r["actual"]) for r in scored) / len(scored)
