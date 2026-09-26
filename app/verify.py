from .domain import Prediction
def verify(snapshot):
    errors=[];ids=set()
    for row in snapshot.get("predictions",[]):
        if row["id"] in ids:errors.append(f'duplicate prediction {row["id"]}')
        ids.add(row["id"]); fields={k:v for k,v in row.items() if k!="proof_hash"}
        if isinstance(fields.get("evidence"),list): fields["evidence"]=tuple(fields["evidence"])
        p=Prediction(**fields)
        if p.proof_hash!=row.get("proof_hash"):errors.append(f'hash mismatch {row["id"]}')
    seen=set()
    for r in snapshot.get("resolutions",[]):
        if r["prediction_id"] not in ids:errors.append(f'orphan resolution {r["prediction_id"]}')
        if r["prediction_id"] in seen:errors.append(f'duplicate resolution {r["prediction_id"]}')
        seen.add(r["prediction_id"])
    return errors
