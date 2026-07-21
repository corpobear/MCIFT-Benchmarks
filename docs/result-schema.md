# Result schema

`primary_results.jsonl` is canonical and contains one JSON object per recording.
The companion CSV JSON-encodes nested cells. Each row includes timestamp, file hash,
dataset-global sequence index, scores, candidates, decisions, availability/outcome/
value/threshold/evidence for every gate, G6 feature/channel evidence, warnings, and
diagnostics. `schemas/ims-recording-result.schema.json` defines its required core.

`summary.json` contains warning timing, sustained runs, holdout false positives,
baseline timing, controls, and localization. `runtime.json` contains phase timings,
throughput, memory and directory size. `run_manifest.json` binds every output to
dataset/config hashes, package and repository commits, seeds, split and profiles.
