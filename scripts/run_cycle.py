import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.runner import cycle
from datetime import datetime, timezone
import json
result=cycle()
print(json.dumps({"event":"scheduled_cycle","at":datetime.now(timezone.utc).isoformat(),**result}))
