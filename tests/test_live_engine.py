from app.market import features,score
def test_engine():
    b=[{"c":100+i*.1,"v":100+i} for i in range(130)]
    f=features(b);s=score(f)
    assert f["price"]>0 and 0.5<=s["confidence"]<=0.92 and s["direction"] in ("UP","DOWN")
