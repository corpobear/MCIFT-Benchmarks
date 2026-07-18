# Public benchmark preparation report

Prepared 2026-07-17. This report contains no scientific benchmark result.
Configuration-like identifiers that belong in GitHub variables are intentionally
withheld from this public repository.

Dataset staging update, 2026-07-18: the official NASA IMS archive was streamed
directly into private Blob Storage without retaining a complete local copy. The
blob is `datasets/ims/source/IMS.zip`, its size is 1,061,902,801 bytes, and its
SHA-256 is `6cb42c263b0281c725abf99f4b9fcf49915c949f31dbd2333877dc2e06ce9ec2`.
The private manifest is `datasets/ims/manifests/IMS.zip.manifest.json`.

Exathlon staging update, 2026-07-18: all 94 ZIP files under the official
repository's `data/raw/` tree were streamed directly into private Blob Storage.
Their aggregate size is 2,812,211,810 bytes. The aggregate manifest is
`datasets/exathlon/manifests/dataset-manifest.json`, with SHA-256
`9fb7069ba4cf53ce730cebfae7acb50cfd6c0f727f0f48afb784a47347b46796`.
Its blob metadata matches the locally calculated manifest hash. The dataset
container remains private and shared-key access remains disabled.

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
  MCIFT quantities to bearing vibration or Spark telemetry;
- commit `e1d93e1d8b21a4420b2f3a566d5a66ac2a7ba687` defines the pairwise
  information-exchange toy law used by the engineering proposal.

No theory or scientific claim was rewritten. `MCIFT_MAPPING_PROPOSAL.md` clearly
separates the source equation from inferred sensor/telemetry observables. The
proposal adapter implements the pairwise equation on synthetic arrays, while the
default contract still fails closed and both benchmark configurations remain
blocked pending scientific approval and frozen parameters.
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
- GHCR image publication remains pending because the available Git credential
  lacks package-write scope; repository automation is configured.

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
Current infrastructure placeholder: `sha-unpublished`. No published SHA tag or
benchmark image digest exists. Docker Desktop locally built the Linux AMD64 image
for source commit `bcae09711fe4d59b6ff548186ce78ae56bf28354`; its local image ID is
`sha256:bccb16d6ee8b2b52422c60cbe4f86a9968ba03ef229cda920e004f504e5eae45`,
and container CLI help passed. GHCR rejected publication because the available
token did not have the expected package scope. This local ID is not presented as
a published registry digest.

## 7. OIDC status

An Entra application and service principal named `app-mcift-benchmarks-github`
were created with a federated credential restricted to:

```text
repo:corpobear/MCIFT-Benchmarks:environment:azure-benchmarks
```

The application has one federated credential and zero password credentials.
Roles were verified: resource-group Contributor, resource-group Role Based Access
Control Administrator (needed for Bicep-owned scoped RBAC), and Blob Data Reader
on `approved-releases` only. The GitHub `azure-benchmarks` environment was created
with reviewer protection, and all seven required repository variables were set.
Their values are withheld from Git and from command output.

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
The signed-in operator was additionally granted Blob Data Contributor on the
`datasets` container to perform the explicitly requested staging operation.

## 10. Validation commands and results

Passed:

```text
ruff format --check benchmarks
ruff check benchmarks
mypy --config-file benchmarks/pyproject.toml benchmarks/src
pytest benchmarks/tests/synthetic                    # 7 software tests
JSON Schema meta-schema checks                       # 2 schemas
YAML parsing                                         # 6 workflows
az bicep build --file infra/bicep/main.bicep
az deployment sub validate ...                       # intended and blocker-aware
az deployment sub what-if ...                        # 18 create, 2 provider-opaque
az deployment sub create ...                         # blocker-aware deployment succeeded
python -m mcift_benchmarks --help
python -m mcift_benchmarks validate-config ...       # both configs
python -m mcift_benchmarks preflight-run ...          # fail-closed, unresolved fields listed
secret-assignment pattern scan                       # none found
```

The local Linux AMD64 image build and container CLI help passed. GHCR publication
failed only at package authorization. GitHub push and pull-request CI previously
passed, including a Linux container build without running either benchmark.
Azure deployment validation and what-if succeeded before apply. No validation
processed dataset contents.

## 11. Quota and permission blockers

- West Europe Container Apps managed-environment capacity blocked creation twice.
- `Standard_D8as_v5` was unavailable for this subscription; no larger or more
  expensive size was selected.
- GHCR push needs a token with `write:packages` or the protected manual build
  workflow must be dispatched after it exists on the default branch. Package
  visibility must then be changed to public before Azure uses it anonymously.
- Azure permissions were sufficient for resources, Entra federation, and scoped RBAC.

## 12. Idle monthly cost categories

Possible idle charges include Blob capacity/transactions, retained Log Analytics
or Application Insights data, Key Vault operations, and any Azure ML workspace
control-plane-dependent storage. There is no always-running VM or compute node.
Future Container Apps and AML charges occur only during explicitly started jobs.
No exact future bill is claimed.

## 13. Next steps for IMS staging

The source archive and checksum manifest are now staged privately. Remaining steps:

1. Review the staged archive's bundled README and attribution.
2. Reconcile the authoritative 20 kHz rate and 20,480 samples/record before
   changing unresolved protocol fields.
3. Review the generated SHA-256 manifest and its own manifest hash; never add it
   or source files to Git.
4. Resolve and review every `unresolved` field, approve or replace the proposed
   MCIFT observable mapping, and wire the approved adapter into the run pipeline.
5. After West Europe capacity recovers, rerun what-if/apply with
   `deployContainerApps=true`; confirm the new job has zero executions.

## 14. Next steps for Exathlon staging

All 94 official raw ZIPs and the aggregate checksum manifest are staged privately.
No local dataset download is now required. Remaining steps:

1. Review the manifest and preserve CC BY-NC-SA 4.0 dataset obligations; the
   repository's code license is separately Apache-2.0.
2. Resolve the exact 19-feature list, resampling, missing-data, split, interval,
   event, and
   MCIFT relationship/topology protocol fields before any run.
3. Obtain suitable West Europe low-priority DASv5 quota/availability, rerun
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

The official IMS archive and all official Exathlon raw ZIPs were staged directly
to private Azure storage; no complete local copy was retained. No
scientific benchmark, baseline tuning, report generation, Container Apps
execution, or Azure ML job was run. No result or placeholder metric was invented
or published. All tests used small synthetic arrays and are software tests, not
scientific evidence.

## Delivery status

Branch: `infra/public-benchmarks`. Draft PR:
https://github.com/corpobear/MCIFT-Benchmarks/pull/1. Azure preparation is complete
except for the explicitly documented GHCR package permission, Container Apps
capacity, AML SKU restriction, and unresolved scientific protocol. Both
scientific workloads remain unexecuted.
