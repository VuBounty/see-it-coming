from app import market


def test_market_universe_falls_back(monkeypatch):
    def fail(limit=100):
        raise RuntimeError("primary down")
    def ok(limit=100):
        return [{
            "id":"btc","symbol":"BTC","name":"Bitcoin","price":100.0,
            "change_24h":1.5,"market_cap_rank":1,"market_cap":1,
            "volume_24h":1,"sparkline":[1,2,3],"source":"Fixture"
        }] * 20
    monkeypatch.setattr(market, "_coingecko_universe", fail)
    monkeypatch.setattr(market, "_cryptocompare_universe", ok)
    rows, src = market.market_universe(20)
    assert len(rows) == 20
    assert src == "Fixture"
    assert rows[0]["price"] == 100.0


def test_market_universe_raises_when_all_fail(monkeypatch):
    def fail(limit=100):
        raise RuntimeError("down")
    monkeypatch.setattr(market, "_coingecko_universe", fail)
    monkeypatch.setattr(market, "_cryptocompare_universe", fail)
    try:
        market.market_universe(20)
        assert False
    except RuntimeError as exc:
        assert "all universe providers unavailable" in str(exc)

