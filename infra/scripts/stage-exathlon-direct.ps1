[CmdletBinding()]
param(
  [string]$ResourceGroup = 'rg-mcift-benchmarks-weu',
  [string]$Ref = 'master',
  [string]$Confirmation = '',
  [ValidateRange(1, 12)][int]$Parallelism = 6,
  [switch]$Overwrite
)

$ErrorActionPreference = 'Stop'
$repository = 'exathlonbenchmark/exathlon'
$treeUri = "https://api.github.com/repos/$repository/git/trees/$Ref`?recursive=1"
$headers = @{ 'User-Agent' = 'mcift-benchmark-dataset-stager/1.0' }
$tree = Invoke-RestMethod -Uri $treeUri -Headers $headers
$files = @(
  $tree.tree |
    Where-Object { $_.type -eq 'blob' -and $_.path -match '^data/raw/.+\.zip$' } |
    Sort-Object path
)
if ($files.Count -eq 0) { throw 'No Exathlon raw ZIP files were found at the official source.' }

Write-Host "Official Exathlon ZIP files discovered: $($files.Count)"
Write-Host 'Dataset license: CC BY-NC-SA 4.0. Staging destination remains private.'
$confirmation = if ([string]::IsNullOrEmpty($Confirmation)) {
  Read-Host 'Type STAGE_EXATHLON_ALL to continue'
} else {
  $Confirmation
}
if ($confirmation -cne 'STAGE_EXATHLON_ALL') { throw 'Confirmation did not match.' }

$storageAccount = az storage account list `
  --resource-group $ResourceGroup --query '[0].name' --output tsv --only-show-errors
if ([string]::IsNullOrWhiteSpace($storageAccount)) { throw 'Storage account not found.' }

$runtimeRoot = Join-Path ([IO.Path]::GetTempPath()) "mcift-exathlon-runtime-$([Guid]::NewGuid().ToString('N'))"
$runtimeVenv = Join-Path $runtimeRoot 'venv'
New-Item -ItemType Directory -Path $runtimeRoot | Out-Null
python -m venv $runtimeVenv
if ($LASTEXITCODE -ne 0) { throw 'Python virtual environment creation failed.' }
$runtimePython = Join-Path $runtimeVenv 'Scripts/python.exe'
& $runtimePython -m pip install --quiet --disable-pip-version-check `
  azure-identity==1.19.0 azure-storage-blob==12.24.0
if ($LASTEXITCODE -ne 0) { throw 'Azure Python package installation failed.' }

$scriptPath = Join-Path $PSScriptRoot 'stage-dataset-direct.ps1'
$uploadJobs = @()
try {
  $existingBlobs = @{}
  $listedJson = az storage blob list --auth-mode login --account-name $storageAccount `
    --container-name datasets --prefix 'exathlon/source/' `
    --include m --output json --only-show-errors
  $listedBlobs = ($listedJson -join "`n") | ConvertFrom-Json
  foreach ($blob in $listedBlobs) { $existingBlobs[$blob.name] = $blob }

  $pending = [Collections.Generic.Queue[object]]::new()
  foreach ($file in $files) {
    $sourceUrl = "https://raw.githubusercontent.com/$repository/$Ref/$($file.path)"
    $blobName = $file.path.Substring('data/raw/'.Length).Replace('/', '__')
    $destination = "exathlon/source/$blobName"
    if (-not $Overwrite -and $existingBlobs.ContainsKey($destination)) {
      if ([string]::IsNullOrWhiteSpace($existingBlobs[$destination].metadata.sha256)) {
        throw "Existing blob lacks SHA-256 metadata: $destination"
      }
      Write-Host "Already staged: $destination"
      continue
    }
    $pending.Enqueue([pscustomobject]@{
      SourceUrl = $sourceUrl
      BlobName = $blobName
    })
  }

  while ($pending.Count -gt 0 -or $uploadJobs.Count -gt 0) {
    while ($pending.Count -gt 0 -and $uploadJobs.Count -lt $Parallelism) {
      $item = $pending.Dequeue()
      $uploadJobs += Start-Job -ArgumentList @(
        $scriptPath, $item.SourceUrl, $item.BlobName, $ResourceGroup, $runtimePython, [bool]$Overwrite
      ) -ScriptBlock {
        param($ScriptPath, $SourceUrl, $BlobName, $ResourceGroup, $RuntimePython, $AllowOverwrite)
        $arguments = @{
          Dataset = 'exathlon'
          SourceUrl = $SourceUrl
          BlobName = $BlobName
          ResourceGroup = $ResourceGroup
          Confirmation = 'STAGE_EXATHLON'
          PythonExecutable = $RuntimePython
        }
        if ($AllowOverwrite) { $arguments.Overwrite = $true }
        & $ScriptPath @arguments
      }
    }
    if ($uploadJobs.Count -gt 0) {
      $finished = Wait-Job -Job $uploadJobs -Any
      Receive-Job -Job $finished -ErrorAction Continue
      if ($finished.State -ne 'Completed') {
        throw "Exathlon staging worker failed: $($finished.ChildJobs[0].JobStateInfo.Reason.Message)"
      }
      Remove-Job -Job $finished
      $uploadJobs = @($uploadJobs | Where-Object Id -ne $finished.Id)
    }
  }
} finally {
  if ($uploadJobs.Count -gt 0) {
    $uploadJobs | Stop-Job -ErrorAction SilentlyContinue
    $uploadJobs | Remove-Job -Force -ErrorAction SilentlyContinue
  }
  Remove-Item -LiteralPath $runtimeRoot -Recurse -Force
}

$allBlobsJson = az storage blob list --auth-mode login --account-name $storageAccount `
  --container-name datasets --prefix 'exathlon/source/' `
  --include m --output json --only-show-errors
$allBlobs = ($allBlobsJson -join "`n") | ConvertFrom-Json
$blobIndex = @{}
foreach ($blob in $allBlobs) { $blobIndex[$blob.name] = $blob }
$entries = @()
foreach ($file in $files) {
  $sourceUrl = "https://raw.githubusercontent.com/$repository/$Ref/$($file.path)"
  $blobName = $file.path.Substring('data/raw/'.Length).Replace('/', '__')
  $destination = "exathlon/source/$blobName"
  if (-not $blobIndex.ContainsKey($destination)) { throw "Expected blob is missing: $destination" }
  $properties = $blobIndex[$destination]
  $entries += [ordered]@{
    path = "source/$blobName"
    original_path = $file.path
    source_url = $sourceUrl
    bytes = $properties.properties.contentLength
    sha256 = $properties.metadata.sha256
  }
}

$aggregate = [ordered]@{
  dataset = 'exathlon'
  source_repository = "https://github.com/$repository"
  source_ref = $Ref
  license = 'CC-BY-NC-SA-4.0'
  created_at_utc = (Get-Date).ToUniversalTime().ToString('o')
  files = $entries
}
$taskRoot = Join-Path ([IO.Path]::GetTempPath()) "mcift-exathlon-manifest-$([Guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Path $taskRoot | Out-Null
$manifestPath = Join-Path $taskRoot 'dataset-manifest.json'
try {
  $aggregate | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding utf8
  $manifestHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $manifestPath).Hash.ToLowerInvariant()
  az storage blob upload --auth-mode login --account-name $storageAccount `
    --container-name datasets --name 'exathlon/manifests/dataset-manifest.json' `
    --file $manifestPath --overwrite true --content-type application/json `
    --metadata "sha256=$manifestHash" --only-show-errors --output none
  Write-Host "Aggregate files: $($entries.Count)"
  Write-Host "Aggregate manifest SHA-256: $manifestHash"
  Write-Host 'Private manifest: datasets/exathlon/manifests/dataset-manifest.json'
} finally {
  Remove-Item -LiteralPath $taskRoot -Recurse -Force
  Remove-Variable storageAccount -ErrorAction SilentlyContinue
}
