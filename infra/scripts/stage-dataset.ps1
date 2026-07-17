[CmdletBinding(SupportsShouldProcess)]
param(
  [Parameter(Mandatory)][ValidateSet('ims','exathlon')][string]$Dataset,
  [Parameter(Mandatory)][string]$SourcePath,
  [Parameter(Mandatory)][ValidatePattern('^[a-z0-9]{3,24}$')][string]$StorageAccount
)
$ErrorActionPreference = 'Stop'
$resolved = (Resolve-Path -LiteralPath $SourcePath).Path
if (-not (Test-Path -LiteralPath $resolved -PathType Container)) { throw 'Source must be a directory.' }
Write-Host "Review datasets/$($Dataset.ToUpper()).md and source terms before upload."
$manifestPath = Join-Path $resolved "dataset-manifest-$Dataset.json"
$files = Get-ChildItem -LiteralPath $resolved -File -Recurse | Where-Object FullName -ne $manifestPath
$root = $resolved.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
$entries = $files | ForEach-Object {
  [ordered]@{path=$_.FullName.Substring($root.Length).Replace('\','/'); bytes=$_.Length; sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant()}
}
[ordered]@{dataset=$Dataset; created_at_utc=(Get-Date).ToUniversalTime().ToString('o'); files=@($entries)} |
  ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding utf8
if ($PSCmdlet.ShouldProcess("https://$StorageAccount.blob.core.windows.net/datasets/$Dataset/", 'Upload dataset with Entra ID')) {
  az storage blob upload-batch --account-name $StorageAccount --auth-mode login --destination datasets --destination-path $Dataset --source $resolved --overwrite false
}

