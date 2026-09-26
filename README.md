# SEE IT COMING.

> **Can a machine detect the move before the market makes it?**
> We don't know yet. So we're testing it in public.

Every prediction is locked before the outcome. Every win stays. Every loss stays. Nothing gets rewritten.

## What this is
An open forward-testing laboratory for market signals. It scans public spot data, runs multiple transparent models, combines them into an ensemble, locks predictions into an append-only ledger, resolves them after their horizon, and exposes a public dashboard.

## What this is not
Not financial advice. Not an exchange. No wallet, deposit, leverage, token, NFT, or trade execution. Experimental confidence is not proven predictive edge.

## Quick start
```bash
python3 -m app.main
```
Open `http://127.0.0.1:8080`.

Run the autonomous forward experiment in a second terminal:
```bash
python3 -m app.runner
```

Or run both with Docker:
```bash
docker compose up --build
```

Verify the public ledger:
```bash
python3 scripts/verify_ledger.py
```

## Architecture
Market data → features → momentum/breakout/mean-reversion → ensemble → immutable prediction → wait → resolve → score → public proof.

See `METHODOLOGY.md` and `EXPERIMENT.md` before interpreting results.

## 24/7 public mode — no personal computer required

GitHub Actions runs one forward-test cycle every hour, verifies the ledger, and commits new experiment records. A second workflow builds and deploys the public proof dashboard to GitHub Pages whenever the ledger changes.

After publishing the repository, enable **Settings → Pages → Source: GitHub Actions**.

Important: GitHub scheduled workflows can be delayed. This V1 mode is for public forward-testing, not latency-sensitive trade execution.
