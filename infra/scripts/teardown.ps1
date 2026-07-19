[CmdletBinding()]
param([string]$Confirmation = '')
$resourceGroup = 'rg-mcift-benchmarks-weu'
Write-Host "Exact resource group: $resourceGroup"
Write-Warning 'Deletion removes private datasets, unpublished runs, logs, and all benchmark infrastructure. Recovery is not guaranteed.'
if ($Confirmation -cne "DELETE $resourceGroup") {
  Write-Host "No change. Re-run with -Confirmation 'DELETE $resourceGroup' to delete."
  exit 0
}
az group show --name $resourceGroup --query '{name:name,location:location,id:id}' -o table
az group delete --name $resourceGroup --yes --no-wait

