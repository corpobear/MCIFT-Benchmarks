# Benchmark package

One CPU-only CLI serves local validation and the public benchmark scaffolding. The
IMS local runner uses the separately maintained MCIFT package public API. The older
generic cloud `run` command remains fail-closed.

Commands:

```text
python -m mcift_benchmarks validate-config --config <path>
python -m mcift_benchmarks inspect-input --dataset <ims|exathlon> --input <uri>
python -m mcift_benchmarks run --config <path> --input <uri> --output <uri>
python -m mcift_benchmarks build-report --run <uri> --output <path>
python -m mcift_benchmarks ims validate-dataset --config configs/ims-set2-v1.yaml --dataset-root <path>
python -m mcift_benchmarks ims show-split --config configs/ims-set2-v1.yaml
python -m mcift_benchmarks ims benchmark-parser --config configs/ims-set2-v1.yaml --dataset-root <path>
python -m mcift_benchmarks ims run --config configs/ims-set2-v1.yaml --dataset-root <path> --mcift-repo ../../MCIFT --output-root artifacts
python -m mcift_benchmarks ims summarize --run-dir <run-directory>
```

`inspect-input` reads metadata/manifests, not the complete dataset. Blob access
uses `DefaultAzureCredential`; account keys and SAS tokens are rejected.

`--limit-files` creates only a non-scientific engineering smoke run. `--skip-controls`
is also explicit in the run manifest. Full protocol results require all recordings and
all controls.

