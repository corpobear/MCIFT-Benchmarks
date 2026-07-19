[CmdletBinding()]
param(
  [ValidateSet('what-if','apply')][string]$Mode = 'what-if',
  [string]$Location = 'westeurope',
  [int]$MonthlyBudgetAmount = 20,
  [string[]]$BudgetContactEmails = @(),
  [string]$BenchmarkImage = 'ghcr.io/corpobear/mcift-benchmarks:sha-unpublished'
)
$ErrorActionPreference = 'Stop'
$resourceGroup = 'rg-mcift-benchmarks-weu'
az account show --query '{subscription:name,id:id}' --output table
Write-Host "Target resource group: $resourceGroup"
Write-Host "Target region: $Location"
foreach ($namespace in @('Microsoft.App','Microsoft.OperationalInsights','Microsoft.Storage','Microsoft.ManagedIdentity','Microsoft.MachineLearningServices','Microsoft.KeyVault','Microsoft.Insights','Microsoft.Consumption')) {
  $state = az provider show --namespace $namespace --query registrationState -o tsv
  if ($state -ne 'Registered') { az provider register --namespace $namespace --wait }
}
az vm list-usage --location $Location --query "[?contains(localName, 'Das v5')].{name:localName,current:currentValue,limit:limit}" -o table
az bicep build --file infra/bicep/main.bicep
$params = @(
  '--location', $Location,
  '--parameters', "location=$Location", "monthlyBudgetAmount=$MonthlyBudgetAmount", "benchmarkImage=$BenchmarkImage"
)
if ($BudgetContactEmails.Count -gt 0) {
  $emailJson = $BudgetContactEmails | ConvertTo-Json -Compress
  $params += @('--parameters', "budgetContactEmails=$emailJson")
}
az deployment sub validate @params --template-file infra/bicep/main.bicep --name mcift-benchmark-validate
az deployment sub what-if @params --template-file infra/bicep/main.bicep --name mcift-benchmark-what-if
Write-Host 'Cost review: Log Analytics/App Insights ingestion, Blob capacity/transactions, Container Apps executions, AML jobs, and Key Vault operations. No always-on compute is configured.'
if ($Mode -eq 'apply') {
  az deployment sub create @params --template-file infra/bicep/main.bicep --name mcift-benchmark-prepare
} else {
  Write-Host 'What-if complete. No resources applied.'
}

