# Scientific decisions required before execution

Engineering is fail-closed until these choices are reviewed and frozen. Provide
values plus a source/rationale; do not answer by asking engineering to guess.

## Shared MCIFT mapping

1. Approve or replace `MCIFT_MAPPING_PROPOSAL.md`, derived from source commit `e1d93e1`.
2. Healthy/training-only per-channel scale estimator, units, normalization,
   topology, boundary conditions, and parameter provenance.
3. Which parameters are derived, fitted, assumed, or fixed before evaluation.
4. A falsification rule and expected behavior when the mapping is undefined.

## IMS Set 2

1. Detrending/filtering method, window size, and overlap.
2. Healthy-reference start/end timestamps or file indices.
3. Threshold method and value-selection rule using healthy data only.
4. Stable-warning duration/consecutive-window rule.
5. False-alarm definition and treatment of warning resets.
6. Reconciliation of 20 kHz metadata with 20,480 samples per recording.

## Exathlon 19-feature mode

1. Exact 19 feature names and ordering.
2. Resampling interval and aggregation per feature.
3. Missing-value policy and maximum allowed gap.
4. Training/evaluation split policy without anomaly leakage.
5. Closed/open interval semantics for ground-truth events.
6. Event matching, aggregation, tolerance, and duplicate-detection rules.
7. Approve the proposed undirected complete feature graph or provide another topology.

## Approval record

Record reviewer, date, source commit, config hashes, and an explicit statement
that all choices were frozen before viewing benchmark outcomes.
