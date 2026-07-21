# Benchmark methodology

The monitor is fitted on the reference split, calibrated on the next chronological
healthy split, tested for false positives on a separate healthy holdout with fresh
history, and evaluated on the remaining chronological sequence. The saved schema-4
monitor is reloaded before any evaluation.

All six package gates are retained separately. Screening, persistent MCIFT warning,
and high-confidence IMS warning are reported without collapsing them. Benchmark-level
3-, 5-, and 10-recording sustained runs do not alter MCIFT decisions.

Conventional baselines are centered RMS, excess kurtosis, crest factor, maximum
absolute amplitude, their per-channel OR, same-channel two-feature agreement, and
maximum standardized exceedance. Thresholds use the same 0.995 linear healthy
calibration quantile; evaluation never calibrates them.

Controls use fresh history: deterministic shuffled chronology, fixed non-identity
channel permutation, independent per-channel recording-order permutation, and the
healthy-only sequence. Shuffled results are explicitly invalid as progression evidence.
