from app.market import market_universe


def test_universe_contract_with_fixture(monkeypatch):
    from app import market
    rows=[{'id':str(i),'symbol':'T'+str(i),'name':'Token '+str(i),'price':1+i,'change_24h':i/10,
           'market_cap_rank':i+1,'market_cap':100-i,'volume_24h':10,'sparkline':[1,2,3],'source':'Fixture'} for i in range(40)]
    monkeypatch.setattr(market,'_coingecko_universe',lambda limit=100: rows[:limit])
    out,src=market_universe(40)
    assert len(out)==40 and src=='Fixture'
    assert all('price' in r and 'change_24h' in r for r in out)

