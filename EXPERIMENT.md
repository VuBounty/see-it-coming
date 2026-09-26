# Public Experiment Protocol

1. Run the experiment worker continuously.
2. It creates at most one unresolved call per configured asset/horizon.
3. Calls are immutable after lock.
4. When the horizon expires, the worker resolves against fresh public market data.
5. The ledger can be independently hash-verified with `python scripts/verify_ledger.py`.
6. Do not interpret early win streaks as proof. Evaluate after meaningful sample sizes and across different market regimes.
