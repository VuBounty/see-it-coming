# Methodology

SEE IT COMING is a forward-testing experiment, not a promise of profit. V1 combines three deliberately simple transparent models: momentum, breakout/volume, and mean reversion. Their signed probability votes form an ensemble. Every public call is created before its evaluation horizon and receives a SHA-256 proof hash.

## Evaluation
Primary metrics: accuracy, Brier score, target-hit rate, calibration by confidence bucket, and performance by asset/regime. Baselines should include 50/50 direction and a naive momentum rule. No result is evidence of edge until it is generated out-of-sample and forward in time.

## Anti-cherry-picking rules
- Start the public record at zero.
- Never delete a locked loss.
- Never modify a locked prediction.
- Resolve exactly once.
- Publish model version and evidence with each prediction.
- Separate experimental confidence from verified historical calibration.
