import json
import os
import statistics
import time
import urllib.parse
import urllib.request

UA = {"User-Agent": "SEE-IT-COMING/1.0 (+https://github.com/VuBounty/see-it-coming)"}


def _json(url, timeout=None):
    timeout = float(os.getenv("SIC_MARKET_TIMEOUT", "5")) if timeout is None else timeout
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode())


def _binance(symbol, interval="1h", limit=120):
    base = os.getenv("SIC_BINANCE_BASE", "https://api.binance.com")
    query = urllib.parse.urlencode({"symbol": symbol, "interval": interval, "limit": limit})
    raw = _json(base + "/api/v3/klines?" + query)
    rows = [{"t": int(x[0]), "c": float(x[4]), "v": float(x[5])} for x in raw]
    return rows, "Binance"


def _coinbase(symbol, interval="1h", limit=120):
    product = symbol.replace("USDT", "-USD")
    granularity = 3600
    end = int(time.time())
    start = end - (limit + 5) * granularity
    query = urllib.parse.urlencode({
        "granularity": granularity,
        "start": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(start)),
        "end": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(end)),
    })
    raw = _json("https://api.exchange.coinbase.com/products/%s/candles?%s" % (product, query))
    rows = [{"t": int(x[0]) * 1000, "c": float(x[4]), "v": float(x[5])} for x in raw]
    rows.sort(key=lambda x: x["t"])
    if len(rows) < 25:
        raise ValueError("Coinbase returned insufficient bars")
    return rows[-limit:], "Coinbase Exchange"


def _kraken(symbol, interval="1h", limit=120):
    base = symbol.replace("USDT", "USD")
    aliases = {"BTCUSD": "XBTUSD", "DOGEUSD": "XDGUSD"}
    pair = aliases.get(base, base)
    query = urllib.parse.urlencode({"pair": pair, "interval": 60})
    raw = _json("https://api.kraken.com/0/public/OHLC?" + query)
    if raw.get("error"):
        raise RuntimeError("; ".join(raw["error"]))
    result = raw["result"]
    key = next(k for k in result if k != "last")
    rows = [{"t": int(x[0]) * 1000, "c": float(x[4]), "v": float(x[6])} for x in result[key]]
    if len(rows) < 25:
        raise ValueError("Kraken returned insufficient bars")
    return rows[-limit:], "Kraken"


def klines_with_source(symbol="BTCUSDT", interval="1h", limit=120):
    errors = []
    for provider in (_binance, _coinbase, _kraken):
        try:
            bars, source = provider(symbol, interval, limit)
            if len(bars) >= 25:
                return bars, source
        except Exception as exc:
            errors.append("%s: %s" % (provider.__name__.lstrip("_"), exc))
    raise RuntimeError("all market providers unavailable | " + " | ".join(errors))


def klines(symbol="BTCUSDT", interval="1h", limit=120):
    return klines_with_source(symbol, interval, limit)[0]


def features(bars):
    if len(bars) < 25:
        raise ValueError("at least 25 bars required")
    closes = [x["c"] for x in bars]
    volumes = [x["v"] for x in bars]
    ret = lambda n: closes[-1] / closes[-1-n] - 1
    mean = sum(closes[-20:]) / 20
    sd = statistics.pstdev(closes[-20:]) or 1e-9
    vmean = sum(volumes[-20:-1]) / 19 or 1e-9
    return {
        "price": closes[-1],
        "r1": ret(1),
        "r6": ret(6),
        "r24": ret(24),
        "z": (closes[-1] - mean) / sd,
        "vr": volumes[-1] / vmean,
    }


def score(feature_map):
    from .models import ensemble
    result = ensemble(feature_map)
    anomaly = min(abs(feature_map["z"]) / 3 + max(feature_map["vr"] - 1, 0) / 4, 1)
    return {
        "direction": result["direction"],
        "confidence": result["probability"],
        "anomaly": round(anomaly, 3),
        "raw": result["raw"],
    }


def scan(symbols):
    from .models import ensemble
    out = []
    for symbol in symbols:
        try:
            bars, source = klines_with_source(symbol)
            feature_map = features(bars)
            result = ensemble(feature_map)
            anomaly = min(abs(feature_map["z"]) / 3 + max(feature_map["vr"] - 1, 0) / 4, 1)
            out.append({
                "symbol": symbol,
                **feature_map,
                "direction": result["direction"],
                "confidence": result["probability"],
                "anomaly": round(anomaly, 3),
                "models": result["votes"],
                "source": source,
            })
        except Exception as exc:
            out.append({"symbol": symbol, "error": str(exc), "source": "unavailable"})
    return sorted(out, key=lambda row: row.get("anomaly", -1), reverse=True)


def _coingecko_universe(limit=100):
    query = urllib.parse.urlencode({
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": int(limit),
        "page": 1,
        "sparkline": "true",
        "price_change_percentage": "24h",
    })
    raw = _json("https://api.coingecko.com/api/v3/coins/markets?" + query, timeout=10)
    out = []
    for row in raw:
        price = row.get("current_price")
        if price is None:
            continue
        spark = (((row.get("sparkline_in_7d") or {}).get("price")) or [])[-48:]
        out.append({
            "id": str(row.get("id") or ""),
            "symbol": str(row.get("symbol") or "").upper(),
            "name": str(row.get("name") or ""),
            "price": float(price),
            "change_24h": float(row.get("price_change_percentage_24h") or 0.0),
            "market_cap_rank": row.get("market_cap_rank"),
            "market_cap": row.get("market_cap"),
            "volume_24h": row.get("total_volume"),
            "sparkline": [float(x) for x in spark if x is not None],
            "source": "CoinGecko",
        })
    if len(out) < min(20, int(limit)):
        raise ValueError("CoinGecko returned insufficient universe rows")
    return out[:int(limit)]


def _cryptocompare_universe(limit=100):
    query = urllib.parse.urlencode({"limit": int(limit)-1, "tsym": "USD"})
    raw = _json("https://min-api.cryptocompare.com/data/top/mktcapfull?" + query, timeout=10)
    rows = raw.get("Data") or []
    out = []
    for item in rows:
        coin = item.get("CoinInfo") or {}
        display = (item.get("DISPLAY") or {}).get("USD") or {}
        rawusd = (item.get("RAW") or {}).get("USD") or {}
        price = rawusd.get("PRICE")
        if price is None:
            continue
        out.append({
            "id": str(coin.get("Name") or ""),
            "symbol": str(coin.get("Name") or "").upper(),
            "name": str(coin.get("FullName") or coin.get("Name") or ""),
            "price": float(price),
            "change_24h": float(rawusd.get("CHANGEPCT24HOUR") or 0.0),
            "market_cap_rank": None,
            "market_cap": rawusd.get("MKTCAP"),
            "volume_24h": rawusd.get("TOTALVOLUME24HTO"),
            "sparkline": [],
            "source": "CryptoCompare",
        })
    if len(out) < min(20, int(limit)):
        raise ValueError("CryptoCompare returned insufficient universe rows")
    return out[:int(limit)]


def market_universe(limit=100):
    """Return a broad real-market universe for the visual chaos layer.

    This is intentionally independent from the prediction asset list. It never
    invents prices or percentage changes. If all providers fail, it raises so
    callers can render an explicit degraded/no-data state.
    """
    errors = []
    for provider in (_coingecko_universe, _cryptocompare_universe):
        try:
            rows = provider(limit)
            if rows:
                return rows, rows[0].get("source", provider.__name__)
        except Exception as exc:
            errors.append("%s: %s" % (provider.__name__.lstrip("_"), exc))
    raise RuntimeError("all universe providers unavailable | " + " | ".join(errors))

