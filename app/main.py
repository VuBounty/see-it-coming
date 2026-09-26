from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from pathlib import Path
import json
import os

from .store import Ledger
from .market import scan
from .analytics import report

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
LEDGER = Ledger(os.getenv("SIC_LEDGER", str(ROOT / "data" / "ledger.json")))
SYMBOLS = "BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT,DOGEUSDT".split(",")


class Handler(BaseHTTPRequestHandler):
    def _bytes(self, code, body, content_type):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, value):
        self._bytes(code, json.dumps(value).encode(), "application/json; charset=utf-8")

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            target = SITE / "index.html"
            if not target.exists():
                return self._bytes(503, b"Build the dashboard first: python scripts/build_pages.py", "text/plain; charset=utf-8")
            return self._bytes(200, target.read_bytes(), "text/html; charset=utf-8")
        if path in ("/snapshot.json", "/ledger.json"):
            target = SITE / path.lstrip("/")
            if not target.exists():
                return self._json(404, {"error": "not built"})
            return self._bytes(200, target.read_bytes(), "application/json; charset=utf-8")
        if path == "/health":
            target = SITE / "snapshot.json"
            payload = json.loads(target.read_text()) if target.exists() else {"system_status_at_build": "UNBUILT"}
            return self._json(200, {"product": "SEE-IT-COMING", "ui": "V3.2-MOTION", **payload})
        if path == "/api/radar":
            return self._json(200, scan(SYMBOLS))
        if path == "/api/predictions":
            return self._json(200, LEDGER.snapshot())
        if path == "/api/stats":
            return self._json(200, report(LEDGER.snapshot()))
        return self._json(404, {"error": "not found"})

    def log_message(self, *args):
        pass


def run(host="127.0.0.1", port=8080):
    print("SEE IT COMING. V3.2 Motion Observatory on http://%s:%s" % (host, port))
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    run(port=int(os.getenv("PORT", "8080")))
