[CmdletBinding()]
param(
  [Parameter(Mandatory)][string]$ApplicationObjectId,
  [Parameter(Mandatory)][string]$ServicePrincipalObjectId
)
$ErrorActionPreference = 'Stop'
$issuer = 'https://token.actions.githubusercontent.com'
$subject = 'repo:corpobear/MCIFT-Benchmarks:environment:azure-benchmarks'
$credential = @{name='github-azure-benchmarks';issuer=$issuer;subject=$subject;description='MCIFT benchmark GitHub environment';audiences=@('api://AzureADTokenExchange')} | ConvertTo-Json -Compress
$temporaryFile = New-TemporaryFile
try {
  Set-Content -LiteralPath $temporaryFile -Value $credential -Encoding utf8
  az ad app federated-credential create --id $ApplicationObjectId --parameters $temporaryFile
  $rgId = az group show --name rg-mcift-benchmarks-weu --query id -o tsv
  $storageId = az storage account list --resource-group rg-mcift-benchmarks-weu --query '[0].id' -o tsv
  $approvedId = "$storageId/blobServices/default/containers/approved-releases"
  az role assignment create --assignee-object-id $ServicePrincipalObjectId --assignee-principal-type ServicePrincipal --role Contributor --scope $rgId
  az role assignment create --assignee-object-id $ServicePrincipalObjectId --assignee-principal-type ServicePrincipal --role 'Role Based Access Control Administrator' --scope $rgId
  az role assignment create --assignee-object-id $ServicePrincipalObjectId --assignee-principal-type ServicePrincipal --role 'Storage Blob Data Reader' --scope $approvedId
} finally { Remove-Item -LiteralPath $temporaryFile -Force }
Write-Host 'Federated credential configured. No client secret created.'
