#!/usr/bin/env bash
set -euo pipefail
mode="${1:-what-if}"
location="${AZURE_LOCATION:-westeurope}"
budget="${MONTHLY_BUDGET_AMOUNT:-20}"
image="${BENCHMARK_IMAGE:-ghcr.io/corpobear/mcift-benchmarks:sha-unpublished}"
rg='rg-mcift-benchmarks-weu'
[[ "$mode" == what-if || "$mode" == apply ]]
az account show --query '{subscription:name,id:id}' --output table
printf 'Target resource group: %s\nTarget region: %s\n' "$rg" "$location"
for namespace in Microsoft.App Microsoft.OperationalInsights Microsoft.Storage Microsoft.ManagedIdentity Microsoft.MachineLearningServices Microsoft.KeyVault Microsoft.Insights Microsoft.Consumption; do
  state="$(az provider show --namespace "$namespace" --query registrationState -o tsv)"
  [[ "$state" == Registered ]] || az provider register --namespace "$namespace" --wait
done
az vm list-usage --location "$location" --query "[?contains(localName, 'Das v5')].{name:localName,current:currentValue,limit:limit}" -o table
az bicep build --file infra/bicep/main.bicep
args=(--location "$location" --template-file infra/bicep/main.bicep --parameters "location=$location" "monthlyBudgetAmount=$budget" "benchmarkImage=$image")
az deployment sub validate --name mcift-benchmark-validate "${args[@]}"
az deployment sub what-if --name mcift-benchmark-what-if "${args[@]}"
echo 'Cost review: logs, blob usage, executions, AML jobs, and Key Vault operations. No always-on compute is configured.'
if [[ "$mode" == apply ]]; then az deployment sub create --name mcift-benchmark-prepare "${args[@]}"; else echo 'What-if complete. No resources applied.'; fi
