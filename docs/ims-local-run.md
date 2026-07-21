# IMS local run

Obtain IMS Bearings from the official NASA catalog and manually extract Test Set 2.
Do not use an undocumented mirror. Keep the data outside Git. Review its bundled README
to confirm four columns, bearing order, 20 kHz sampling, and 20,480 samples per file.

On an approximately 8 GB RAM laptop, use the streaming runner from `benchmarks/`:

```powershell
python -m pip install -e ../../MCIFT
python -m pip install -e ".[dev]"
python -m mcift_benchmarks ims validate-dataset --config configs/ims-set2-v1.yaml --dataset-root D:/datasets/IMS/2nd_test
python -m mcift_benchmarks ims run --config configs/ims-set2-v1.yaml --dataset-root D:/datasets/IMS/2nd_test --mcift-repo ../../MCIFT --output-root artifacts
```

The loader hashes every timestamp-named recording, rejects duplicates, verifies strict
chronology and dimensions, and uses `mcift.adapters.ims.load_ims_file`. Raw evaluation
windows are not retained. Expect several GB of disk for the source archive and run
artifacts, hundreds of MB of working RAM, and machine-dependent multi-hour runtime;
use `benchmark-parser --limit-files 50` for a local estimate.

For a run that survives closing the terminal, start it detached and retain its run ID:

```powershell
./scripts/start-ims-run.ps1 -DatasetRoot D:/datasets/IMS/2nd_test
./scripts/check-ims-run.ps1 -RunId <printed-run-id>
```

The hidden worker writes a PID record, append-only log and atomic final status below
`artifacts/ims-set2/launcher/`. A benchmark interrupted during primary evaluation can
be resumed with the same `--run-id` plus `--resume`; critical hashes and the monitor
fingerprint must match.

Use `--limit-files 20` only for engineering smoke tests. Those outputs are marked
non-scientific. `--dry-run` validates inputs and resolves the split without fitting.
