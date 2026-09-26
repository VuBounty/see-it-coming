def report(snapshot):
    rs={r['prediction_id']:r for r in snapshot.get('resolutions',[])}
    rows=[]
    for p in snapshot.get('predictions',[]):
        r=rs.get(p['id'])
        if not r or r['outcome'] not in ('CORRECT','WRONG'): continue
        actual=1 if r['outcome']=='CORRECT' else 0
        rows.append((float(p['probability']),actual,p['asset'],p['model_version']))
    n=len(rows)
    if not n:return {'resolved_scored':0,'accuracy':None,'brier':None,'edge_status':'INSUFFICIENT_DATA'}
    acc=sum(a for _,a,_,_ in rows)/n
    br=sum((p-a)**2 for p,a,_,_ in rows)/n
    status='INSUFFICIENT_DATA' if n<50 else ('PROMISING' if acc>=.58 and br<.24 else 'NO_VERIFIED_EDGE')
    buckets={}
    for p,a,_,_ in rows:
        key='HIGH' if p>=.70 else ('MEDIUM' if p>=.60 else 'LOW')
        buckets.setdefault(key,[]).append(a)
    return {'resolved_scored':n,'accuracy':round(acc,4),'brier':round(br,4),'random_baseline':.5,'accuracy_excess_vs_random':round(acc-.5,4),'confidence_buckets':{k:{'n':len(v),'accuracy':round(sum(v)/len(v),4)} for k,v in buckets.items()},'edge_status':status}
