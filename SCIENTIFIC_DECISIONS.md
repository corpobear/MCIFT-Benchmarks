# Scientific decisions frozen for execution

The repository operator approved the mapping on 2026-07-18. The choices below
were frozen in the versioned configurations before any benchmark outcome was viewed.

## Shared MCIFT mapping

1. Approve or replace `MCIFT_MAPPING_PROPOSAL.md`, derived from source commit
   `e1d93e1d8b21a4420b2f3a566d5a66ac2a7ba687`.
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

- Reviewer: repository operator via the Codex thread.
- Approval date: 2026-07-18.
- Theory source: `e1d93e1d8b21a4420b2f3a566d5a66ac2a7ba687`.
- IMS configuration SHA-256:
  `efff5b906c793bcb5872f33632596f0a6ac21bd1be6419706109e8b0d9d780b8`.
- Exathlon configuration SHA-256:
  `d870e7e5346fbf521b919789865b97adc128459e762d3139fcab0a9b75abcadb`.
- All choices were frozen before benchmark outcomes were viewed.
- Exact implemented values are authoritative in the two versioned YAML files.
