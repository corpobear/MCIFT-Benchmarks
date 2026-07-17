# Azure preparation

The subscription-scope Bicep deployment creates the fixed West Europe resource
group and deploys modular resources inside it. Storage names use a deterministic
subscription/resource-group suffix. Outputs contain names and IDs only, never
keys or tokens.

## Apply sequence

```powershell
az login
./infra/scripts/bootstrap-azure.ps1 -Mode what-if
./infra/scripts/bootstrap-azure.ps1 -Mode apply -BudgetContactEmails operator@example.org
```

The script displays the active subscription, target group/region, provider state,
and relevant VM-family quota before compile, validate, and what-if. Only `-Mode
apply` deploys. If the preferred `Standard_D8as_v5` low-priority size is blocked,
leave code unchanged and request quota. `Standard_D8s_v5` is a similarly sized
documented option, not an automatic fallback.

When quota is blocked, deploy all other preparation with
`deployExathlonCompute=false`. Keep the checked-in research parameter `true` so
the intended size remains source-controlled, then rerun what-if after quota is granted.
If West Europe reports `ManagedEnvironmentCapacityHeavyUsageError`, use
`deployContainerApps=false` to finish unrelated resources and retry the intended
region later. Do not silently move the benchmark to another region.

## Security

- Storage permits HTTPS/TLS 1.2+, disables public blobs and shared-key access.
- Application access uses a user-assigned identity and container-scoped Blob Data roles.
- GitHub uses environment-bound OIDC; no client secret exists.
- Dataset contents and credentials must never enter logs. Run logs carry only the
  execution ID, commit, image digest, config/dataset hashes, state, and error summary.
- The OIDC script intentionally needs object IDs as parameters and does not echo them.
  GitHub provisioning uses resource-group Contributor plus Role Based Access
  Control Administrator because Bicep owns scoped assignments. Publication has
  read-only data access to `approved-releases`; it cannot read source datasets.

Repository variables: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`,
`AZURE_SUBSCRIPTION_ID`, `AZURE_RESOURCE_GROUP`, `AZURE_LOCATION`,
`AZURE_ML_WORKSPACE`, and `AZURE_STORAGE_ACCOUNT`. Configure the GitHub environment
`azure-benchmarks` with required reviewers manually if repository permissions do
not allow API configuration.

## Cost controls

The AML cluster has min 0/max 1 and a two-minute idle scale-down; Spot nodes may
be interrupted. The Container Apps job has a manual trigger and no idle replica.
Logs retain 30 days. Temporary prefixes expire after 30 days; approved releases
never expire automatically. A budget defaults to 20 in billing currency and sends
50/80/100 percent alerts only when recipient emails are explicitly supplied.
Budget alerts are notifications, not hard spending limits.

Idle charges may include small storage, Key Vault operations, log retention or
ingestion, and control-plane-dependent workspace resources. Compute charges occur
only when jobs allocate nodes or replicas.

## Troubleshooting

- Quota: inspect regional `Das v5` usage and request low-priority quota; do not resize upward silently.
- OIDC: verify subject exactly matches the repository and `azure-benchmarks` environment.
- GHCR: make the package public or grant the job a supported registry credential before deployment.
- Identity: allow RBAC propagation and verify container-scoped assignments.

## Teardown

`teardown.ps1` shows the exact group and makes no change without the typed phrase.
It never targets unrelated resources. Do not run it when private data must remain.
