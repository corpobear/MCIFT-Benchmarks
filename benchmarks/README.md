# Benchmark package

One CPU-only CLI serves local validation, the IMS Container Apps job, and the
Exathlon Azure ML command job. `run` refuses to proceed while the MCIFT mapping
is unresolved. This is deliberate: source theory scripts expose toy/proxy
reducers but no reviewed mapping to vibration or Spark telemetry features.

Commands:

```text
python -m mcift_benchmarks validate-config --config <path>
python -m mcift_benchmarks inspect-input --dataset <ims|exathlon> --input <uri>
python -m mcift_benchmarks run --config <path> --input <uri> --output <uri>
python -m mcift_benchmarks build-report --run <uri> --output <path>
```

`inspect-input` reads metadata/manifests, not the complete dataset. Blob access
uses `DefaultAzureCredential`; account keys and SAS tokens are rejected.

