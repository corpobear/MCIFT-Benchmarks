# Reproducibility

The run ID combines a UTC timestamp and benchmark commit. The protocol snapshot,
dataset manifest with per-file SHA-256, environment facts, split manifest, MCIFT
version/commit, monitor fingerprint and fixed random seed are saved together.

Never resume or compare runs whose configuration hash, dataset-manifest hash, MCIFT
version, or monitor fingerprint differs. JSON uses sorted keys; controls and plots use
fixed ordering and seeds. The source dataset remains external and is never committed.
