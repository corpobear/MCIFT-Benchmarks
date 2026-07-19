IMS BENCHMARK PUBLICATION DATA EXPORT

This folder contains derived IMS benchmark data and exact implementation-traced
methodology for run ims-20260718-approved-v1. It contains no raw vibration
recordings, credentials, tokens, signed URLs, private storage locations, or
Azure resource identifiers.

Files:
- scores.csv: byte-identical verified per-recording scores.
- summary.json: byte-identical verified run summary.
- comparison.json: derived MCIFT-versus-conventional warning comparison.
- methodology.json: equations, algorithms, normalization, channel evidence,
  persistence semantics, missing-data policy, observed quality counts, status
  explanation, evidence links, and explicit unverifiable fields.
- methodology-table.csv: complete flat methodology evidence table.
- provenance.redacted.json: allowlisted reproducibility and timestamp facts.
- data-dictionary.json: field and file definitions.

The executed implementation uses all four IMS Set-2 columns. It does not select
a single bearing. Accelerometer direction and a bearing-specific end-of-test
fault are not verifiable from the preserved run and are not guessed here.

Three consecutive observations at ten-minute timestamp spacing span 20 minutes
between the first and third timestamps. The warning timestamp is the first
positive in that qualifying run. Lead time is measured to the final experiment
recording, not to a verified physical degradation onset.

The word "approved" in the run ID is an internal artifact label. Execution
completed, but scientific_review_status is unapproved and is authoritative for
publication. This export does not establish MCIFT superiority and does not
approve publication automatically.
