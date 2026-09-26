from app.analytics import report
def test_empty_report(): assert report({'predictions':[],'resolutions':[]})['edge_status']=='INSUFFICIENT_DATA'
def test_scored_report():
    p=[];r=[]
    for i in range(60):
        p.append({'id':str(i),'probability':.7,'asset':'BTCUSDT','model_version':'x'})
        r.append({'prediction_id':str(i),'outcome':'CORRECT' if i<40 else 'WRONG'})
    x=report({'predictions':p,'resolutions':r});assert x['resolved_scored']==60 and x['accuracy']>.6 and x['brier']<.24
