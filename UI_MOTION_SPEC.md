# SEE IT COMING — OBSERVATORY CHAOS V3.2 MOTION

V3.2 is a presentation-layer evolution of the frozen V1.0 prediction engine.

## Visual contract

- The market field is intentionally animated and chaotic.
- Motion intensity is derived from the asset anomaly score.
- Sparklines and percentages are generated only from real provider data.
- The observation stream is a snapshot stream, not a synthetic trade feed.
- `LIVE`, `DEGRADED`, `STALE`, and `NO DATA` are distinct states.
- A fresh forecast receives the full lock animation only for its first 15 minutes.
- A 15–60 minute forecast may show `NEWLY LOCKED`; older forecasts remain simply `LOCKED`.
- Reduced-motion preferences disable decorative motion without hiding data.
- Background canvas animation pauses when the browser tab is hidden.

## Scientific contract

Observation → Detect → Predict → Lock → Wait → Resolve → Score.

Anything that looks like market data must be real. Decorative chaos may use abstract particles, glow, scan lines, or network geometry, but never invented prices, percentages, trades, forecasts, or system-health states.
