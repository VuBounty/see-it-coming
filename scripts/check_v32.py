import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
site = ROOT / "site"
html = (site / "index.html").read_text()
snapshot = json.loads((site / "snapshot.json").read_text())
ledger = json.loads((ROOT / "data" / "ledger.json").read_text())

required_markers = [
    "SIC-OBSERVATORY-CHAOS-V3.2-MOTION",
    "MARKET OBSERVATION STREAM",
    "FROM CHAOS TO SIGNAL",
    "THE FUTURE STARTS HERE",
    "prefers-reduced-motion",
    "chaosCanvas",
]
for marker in required_markers:
    if marker not in html:
        raise SystemExit("missing UI marker: " + marker)

if snapshot.get("version") != "V3.2-MOTION":
    raise SystemExit("wrong snapshot version")
if snapshot.get("total_assets") != 6:
    raise SystemExit("unexpected asset count")
if len(snapshot.get("assets", [])) != 6:
    raise SystemExit("snapshot assets incomplete")
if snapshot.get("metrics", {}).get("locked") != len(ledger.get("predictions", [])):
    raise SystemExit("ledger/UI locked count mismatch")
if "LIVE TRADES (SAMPLE)" in html:
    raise SystemExit("synthetic trade feed must not appear")

for asset in snapshot["assets"]:
    if "error" not in asset and len(asset.get("bars", [])) < 25:
        raise SystemExit("real sparkline lacks sufficient bars for " + asset["symbol"])

print("V3.2 UI VERIFIED")
