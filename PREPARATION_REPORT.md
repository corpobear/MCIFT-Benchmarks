# Public benchmark preparation report

Prepared 2026-07-17. This report contains no scientific benchmark result.
Configuration-like identifiers that belong in GitHub variables are intentionally
withheld from this public repository.

## 1. Repository changes

The target repository was a new, empty Git repository with remote
`corpobear/MCIFT-Benchmarks`. The separate source repository
`corpobear/Quantum-field-hypothesis` was inspected before implementation:

- it carries AGPL-3.0 plus a separate commercial-licensing notice;
- it describes MCIFT as speculative/toy scaffolding;
- `simulations/mcift_v1_00_shared_reducer.py` contains `weighted_mean`,
  `weighted_std`, `rho`, and `compute_shared_state` toy/proxy calculations;
- `simulations/mcift_v0_97_threefold_reducer.py` contains related `wmean`,
  `wstd`, and `rho` helpers;
- it has no packaged Python configuration and no reviewed feature mapping from
  MCIFT quantities to bearing vibration or Spark telemetry.

No theory or scientific claim was copied or rewritten. The new benchmark adapter
therefore raises `NotImplementedError` with a precise theory-to-observable TODO.
Conventional feature/evaluation scaffolding is present but has not been tuned or
evaluated. AGPL/commercial notices, a pinned Python 3.12 package, hash-locked
dependencies, a non-root CPU image, configurations, schemas, synthetic tests,
dataset staging, static report shell, Bicep, scripts, and manual workflows were added.

## 2. Azure resources actually deployed

In `rg-mcift-benchmarks-weu`:

- user-assigned identity `id-mcift-benchmarks`;
- GPv2 storage account `stmciftwkuz2bqjva`;
- private containers `datasets`, `runs`, and `approved-releases`;
- Log Analytics workspace `log-mcift-benchmarks` with 30-day retention;
- workspace-based Application Insights `appi-mcift-benchmarks`;
- Key Vault `kv-mcift-sbwccyanku`;
- Azure ML workspace `mlw-mcift-benchmarks`;
- Azure ML environment `mcift-benchmarks:1` using the unpublished image reference;
- resource-group monthly budget `budget-mcift-benchmarks`.

All resources use the requested tags. No VM, AKS cluster, GPU, online endpoint,
compute instance, AML compute cluster, Container Apps environment, or Container
Apps job was left deployed.

## 3. Prepared in code but not deployed

- `caj-mcift-ims` and `cae-mcift-benchmarks`: West Europe repeatedly returned
  `ManagedEnvironmentCapacityHeavyUsageError` / `AKSCapacityHeavyUsage`. The two
  failed, empty environments were explicitly removed. Code remains enabled by default.
- `cpu-mcift-exathlon`: `Standard_D8as_v5` was listed but restricted for this
  subscription with `NotAvailableForSubscription` (Zone). The exact usage API did
  not return a DASv5 quota row. Code retains Spot, min 0, max 1, and two-minute
  idle scale-down. `Standard_D8s_v5` is documented only as an optional similar-size
  fallback; it was not substituted.
- GHCR image: build workflow and Dockerfile exist, but no image was published.
- GitHub repository variables and the protected `azure-benchmarks` environment:
  not configured because authenticated GitHub CLI/API access was unavailable.

## 4. Active subscription and region

Active subscription name: `MCIFT`. The subscription ID was verified before
deployment but is redacted from this public report and must be stored only in the
`AZURE_SUBSCRIPTION_ID` GitHub variable. Region: `westeurope`.

Required providers were registered. `Microsoft.Insights` was still completing
registration during the first check and subsequently supported deployment.

## 5. Storage and workspace names

- Storage account: `stmciftwkuz2bqjva`
- Azure ML workspace: `mlw-mcift-benchmarks`
- Intended AML compute: `cpu-mcift-exathlon` (not deployed due restriction)

## 6. Container image

Prepared publication name: `ghcr.io/corpobear/mcift-benchmarks`.
Current infrastructure placeholder: `sha-unpublished`. No SHA tag or benchmark
image digest exists because the local Docker daemon was unavailable and the build
workflow was not run. The pinned Linux AMD64 Python base manifest was resolved,
but that base digest is not a benchmark-image digest.

## 7. OIDC status

An Entra application and service principal named `app-mcift-benchmarks-github`
were created with a federated credential restricted to:

```text
repo:corpobear/MCIFT-Benchmarks:environment:azure-benchmarks
```

The application has one federated credential and zero password credentials.
Roles were verified: resource-group Contributor, resource-group Role Based Access
Control Administrator (needed for Bicep-owned scoped RBAC), and Blob Data Reader
on `approved-releases` only. GitHub-side variables and required-reviewer protection
remain a manual step because GitHub authentication was unavailable. All identifier
values are withheld from Git.

## 8. Compute and execution status

Post-deployment ARM inventory proved:

```text
Container Apps environments: 0
Container Apps jobs: 0
AML computes: 0
AML online endpoints: 0
VMs: 0
AKS clusters: 0
```

Because the Container Apps job could not be created, it has no executions; this
task initiated zero executions. The AML cluster was deliberately omitted after
the quota/availability check, so active AML nodes are zero. No scientific command
was submitted.

## 9. Budget and lifecycle status

The resource-group budget amount is 20 in subscription billing currency. Actual
cost alerts at 50%, 80%, and 100% are enabled with one recipient derived from the
signed-in Azure account; the address is not printed or committed. A budget is an
alert mechanism, not a hard spending limit.

Blob and container soft delete are enabled for seven days. Lifecycle management
deletes only `runs/temp/` and `runs/failed-temp/` blobs after 30 days. It does not
delete successful run prefixes or `approved-releases`. Shared-key authorization
and anonymous blobs are disabled; HTTPS and TLS 1.2 are required. The managed
identity has Blob Data Contributor only on `datasets` and `runs` containers.

## 10. Validation commands and results

Passed:

```text
ruff format --check benchmarks
ruff check benchmarks
mypy --config-file benchmarks/pyproject.toml benchmarks/src
pytest benchmarks/tests/synthetic                    # 4 software tests
JSON Schema meta-schema checks                       # 2 schemas
YAML parsing                                         # 6 workflows
az bicep build --file infra/bicep/main.bicep
az deployment sub validate ...                       # intended and blocker-aware
az deployment sub what-if ...                        # 18 create, 2 provider-opaque
az deployment sub create ...                         # blocker-aware deployment succeeded
python -m mcift_benchmarks --help
python -m mcift_benchmarks validate-config ...       # both configs
secret-assignment pattern scan                       # none found
```

The local image build could not run because Docker Desktop's Linux engine pipe was
absent. CI will build the image without running either benchmark. Azure deployment
validation and what-if succeeded before apply. No validation processed real data.

## 11. Quota and permission blockers

- West Europe Container Apps managed-environment capacity blocked creation twice.
- `Standard_D8as_v5` was unavailable for this subscription; no larger or more
  expensive size was selected.
- GitHub authentication was unavailable, blocking repository variables,
  environment protection, push, image workflow execution, and draft PR creation
  until a later authenticated step.
- Azure permissions were sufficient for resources, Entra federation, and scoped RBAC.

## 12. Idle monthly cost categories

Possible idle charges include Blob capacity/transactions, retained Log Analytics
or Application Insights data, Key Vault operations, and any Azure ML workspace
control-plane-dependent storage. There is no always-running VM or compute node.
Future Container Apps and AML charges occur only during explicitly started jobs.
No exact future bill is claimed.

## 13. Next steps for IMS staging

1. Recheck the [NASA catalog](https://data.nasa.gov/dataset/ims-bearings), bundled
   README, attribution, and current terms; obtain the dataset manually.
2. Reconcile the authoritative 20 kHz rate and 20,480 samples/record before
   changing unresolved protocol fields.
3. Run `infra/scripts/stage-dataset.ps1 -Dataset ims -SourcePath <secure-set2-path>
   -StorageAccount stmciftwkuz2bqjva` while signed in with Entra ID.
4. Review the generated SHA-256 manifest, its manifest hash, and private upload
   under `datasets/ims/`; never add it or source files to Git.
5. Resolve and review every `unresolved` field and implement the MCIFT adapter
   from an approved theory-to-code mapping.
6. After West Europe capacity recovers, rerun what-if/apply with
   `deployContainerApps=true`; confirm the new job has zero executions.

## 14. Next steps for Exathlon staging

1. Obtain data from the [official Exathlon repository](https://github.com/exathlonbenchmark/exathlon).
   Preserve CC BY-NC-SA 4.0 dataset obligations; its code license is separately Apache-2.0.
2. Run `infra/scripts/stage-dataset.ps1 -Dataset exathlon -SourcePath <secure-path>
   -StorageAccount stmciftwkuz2bqjva` using Entra ID.
3. Review checksums and the private `datasets/exathlon/` layout.
4. Resolve the 19-feature, resampling, missing-data, split, interval, event, and
   MCIFT relationship/topology protocol fields before any run.
5. Obtain suitable West Europe low-priority DASv5 quota/availability, rerun
   what-if with `deployExathlonCompute=true`, and verify min nodes/current nodes zero.

## 15. Later start mechanisms

After all blockers and scientific TODOs are resolved, publish a SHA-tagged image
with `build-benchmark-image.yml`, record its digest, and configure GitHub variables.

- IMS: manually dispatch `run-ims-benchmark.yml` with exact confirmation
  `RUN_IMS_PUBLIC_BENCHMARK`, immutable image digest, IMS manifest path, and new run ID.
- Exathlon: manually dispatch `run-exathlon-benchmark.yml` with exact confirmation
  `RUN_EXATHLON_PUBLIC_BENCHMARK`, immutable image digest, Exathlon data URI, and new run ID.

Neither workflow has push, pull-request, schedule, or event triggers. Publication
is a separate manual workflow that reads only `approved-releases`, verifies schema,
provenance, and checksums, and opens a draft pull request.

## 16. Scientific execution confirmation

No IMS or Exathlon dataset was downloaded. No scientific benchmark, baseline
tuning, report generation, Container Apps execution, or Azure ML job was run.
No result or placeholder metric was invented or published. All tests used small
synthetic arrays and are software tests, not scientific evidence.

## Delivery status

Branch: `infra/public-benchmarks`. Draft PR: pending GitHub authentication and
initial push. Azure preparation is complete except for the explicitly documented
Container Apps capacity and AML SKU restriction. Both scientific workloads remain
unexecuted.

