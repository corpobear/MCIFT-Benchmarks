# MCIFT observable-mapping proposal

Status: **approved by the repository operator on 2026-07-18 for the two frozen v1 runs**.

Source inspected at `corpobear/Quantum-field-hypothesis` commit
`e1d93e1d8b21a4420b2f3a566d5a66ac2a7ba687`.
The source calls these equations speculative toy-model mechanics.

## Source-derived equations

The mechanics reference and `notes/information_exchange.md` define:

```text
Gamma_ij = g
  exp[-(I_i-I_j)^2 / (2 sigma_I^2)]
  exp[-(omega_i-omega_j)^2 / (2 sigma_omega^2)]
  cos^2(phi_i-phi_j)

X = exp(eta Gamma)
```

The first equation is implemented without alteration. The source's knot-level
normalization uses `C_n=2^n`, but it does not define what `n` means for sensors or
telemetry features. The proposal therefore reports the pairwise matrix and its
plain upper-triangle mean; it does **not** claim that mean is the source's
`Gamma_n`.

## Inferred observable map

For one samples-by-channels window:

- information point: one vibration channel or one Exathlon feature;
- normalize each mean-centered channel by a positive scale frozen from healthy
  or training-only data (the scale estimator is still unresolved);
- `I_i`: log RMS of that dimensionless normalized channel;
- `omega_i`: power-weighted spectral centroid in radians/second;
- shared comparison frequency: strongest aggregate non-DC FFT bin;
- `phi_i`: channel phase at that shared bin;
- output: full symmetric `Gamma_ij`, mean pairwise exchange, and
  `X=exp(eta * mean_pairwise_exchange)`.

This mapping is reproducible and dimensionless after frozen scaling, but it is
not stated in the theory repository. In particular, channel scaling, log RMS,
spectral centroid, shared-bin phase, and mean-edge aggregation are engineering
inferences.

## Required approval/freeze

Before results may be run, approve or replace:

1. this observable map;
2. per-channel scale estimation from frozen healthy/training windows;
3. `sigma_I` estimation from frozen healthy/training windows;
4. `sigma_omega` estimation from frozen healthy/training windows;
5. coupling `g` and densification `eta` (default proposal: both 1, declared assumed);
6. whether anomaly evidence is decreasing exchange, increasing densification,
   deviation from a healthy exchange matrix, or another predeclared statistic;
7. aggregation and threshold rules in each benchmark.

No parameter may be selected after looking at evaluation outcomes.
