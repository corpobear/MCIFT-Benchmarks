# Frozen IMS Test Set 2 protocol v1

This protocol was frozen before evaluation results were inspected. Half-open recording
index ranges are reference `[0, 96)`, chronological calibration `[96, 352)`, healthy
holdout `[352, 448)`, and evaluation `[448, end)`. They are disjoint and ordered.

Test Set 2 has four recording columns. The bundled IMS metadata describes one sensor
for each of bearings 1 through 4; the frozen mapping is column 0 through 3 to
`bearing_1` through `bearing_4`. The staged source PDF was checked against this mapping.
Because that metadata does not state an acceleration unit, every channel
uses `unknown_raw_acceleration_unit`. Operators must compare the extracted dataset's
bundled README with this mapping before a scientific run.

The early 448-recording allocation is predeclared as a presumed healthy segment. This
does not prove every window is fault-free. Reference uses 96 windows, calibration uses
256 (well above the MCIFT minimum of 20), and holdout uses 96. Calibration is never
shuffled and passes `sequence_order="chronological"`.

The frozen profiles are `mcift.exchange.vibration.v1` and
`mcift.gates.ims-six-gate.v1`; caller-owned history has maximum length 32. The random
seed is 20260101. Limited-file runs substitute proportional splits, use MCIFT's
explicit small-sample override, and are always labelled non-scientific.

The configured damaged bearing is bearing 1, matching the source metadata, which says
an outer-race failure occurred at the end of Set 2. The terminal timestamp is frozen as
`2004-02-19T06:22:39Z`. Warning times are reported against configured documented
anchors and the terminal recording. A terminal-relative interval is not a physical
fault-onset lead time.

> The benchmark evaluates the predictive and anomaly-detection behaviour of a frozen
> software method. It does not validate MCIFT as a physical theory.
