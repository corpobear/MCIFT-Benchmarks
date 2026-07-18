[CmdletBinding()]
param(
  [Parameter(Mandatory)][ValidateSet('ims', 'exathlon')][string]$Dataset,
  [Parameter(Mandatory)][ValidatePattern('^https://')][string]$SourceUrl,
  [Parameter(Mandatory)][ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$')][string]$BlobName,
  [string]$ResourceGroup = 'rg-mcift-benchmarks-weu',
  [string]$Confirmation = '',
  [switch]$Overwrite
)

$ErrorActionPreference = 'Stop'
$source = [Uri]$SourceUrl
if (-not [string]::IsNullOrEmpty($source.Query)) {
  throw 'SourceUrl must not contain a query string, SAS token, or other credential.'
}

az account show --output none
if ($LASTEXITCODE -ne 0) { throw 'Run az login first.' }

$storageAccount = az storage account list `
  --resource-group $ResourceGroup `
  --query '[0].name' `
  --output tsv `
  --only-show-errors
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($storageAccount)) {
  throw 'Benchmark storage account was not found in the expected resource group.'
}

Write-Host "Dataset: $Dataset"
Write-Host "Private destination: datasets/$Dataset/source/$BlobName"
if ($Dataset -eq 'ims') {
  Write-Host 'Review NASA catalog attribution and the dataset README before continuing.'
} else {
  Write-Host 'Exathlon data is CC BY-NC-SA 4.0; preserve attribution and non-commercial terms.'
}

$confirmation = if ([string]::IsNullOrEmpty($Confirmation)) {
  Read-Host "Type STAGE_$($Dataset.ToUpperInvariant()) to stream the public source into private Azure storage"
} else {
  $Confirmation
}
if ($confirmation -cne "STAGE_$($Dataset.ToUpperInvariant())") {
  throw 'Confirmation did not match. Nothing uploaded.'
}

$taskRoot = Join-Path ([IO.Path]::GetTempPath()) "mcift-direct-stage-$([Guid]::NewGuid().ToString('N'))"
$venvPath = Join-Path $taskRoot 'venv'
$pythonScript = Join-Path $taskRoot 'stream_to_blob.py'
New-Item -ItemType Directory -Path $taskRoot | Out-Null

try {
  python -m venv $venvPath
  if ($LASTEXITCODE -ne 0) { throw 'Python virtual environment creation failed.' }
  $python = Join-Path $venvPath 'Scripts/python.exe'
  & $python -m pip install --quiet --disable-pip-version-check `
    azure-identity==1.19.0 azure-storage-blob==12.24.0
  if ($LASTEXITCODE -ne 0) { throw 'Azure Python package installation failed.' }

  @'
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
import urllib.request
from datetime import UTC, datetime

from azure.identity import AzureCliCredential
from azure.storage.blob import BlobBlock, BlobServiceClient, ContentSettings

BLOCK_SIZE = 8 * 1024 * 1024
MAX_BLOCKS = 50_000


def block_id(index: int) -> str:
    return base64.b64encode(f"{index:08d}".encode("ascii")).decode("ascii")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--account", required=True)
    parser.add_argument("--dataset", choices=("ims", "exathlon"), required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--blob-name", required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    credential = AzureCliCredential()
    service = BlobServiceClient(
        account_url=f"https://{args.account}.blob.core.windows.net",
        credential=credential,
    )
    destination = f"{args.dataset}/source/{args.blob_name}"
    blob = service.get_blob_client(container="datasets", blob=destination)
    if blob.exists() and not args.overwrite:
        raise RuntimeError("destination exists; rerun with -Overwrite only after review")

    digest = hashlib.sha256()
    blocks: list[BlobBlock] = []
    byte_count = 0
    index = 0
    request = urllib.request.Request(
        args.source,
        headers={"User-Agent": "mcift-benchmark-dataset-stager/1.0"},
    )

    with urllib.request.urlopen(request, timeout=120) as response:
        while True:
            chunk = response.read(BLOCK_SIZE)
            if not chunk:
                break
            if index >= MAX_BLOCKS:
                raise RuntimeError("source exceeds the supported block count")
            identifier = block_id(index)
            digest.update(chunk)
            byte_count += len(chunk)
            blob.stage_block(block_id=identifier, data=chunk, length=len(chunk))
            blocks.append(BlobBlock(block_id=identifier))
            index += 1
            print(f"streamed {byte_count} bytes", file=sys.stderr)

    if not blocks:
        raise RuntimeError("source returned no data")
    sha256 = digest.hexdigest()
    blob.commit_block_list(
        blocks,
        metadata={
            "dataset": args.dataset,
            "sha256": sha256,
            "staged_by": "mcift-direct-stager",
        },
    )

    manifest = {
        "dataset": args.dataset,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "source_url": args.source,
        "files": [
            {
                "path": f"source/{args.blob_name}",
                "bytes": byte_count,
                "sha256": sha256,
            }
        ],
    }
    manifest_name = f"{args.dataset}/manifests/{args.blob_name}.manifest.json"
    manifest_blob = service.get_blob_client(container="datasets", blob=manifest_name)
    manifest_blob.upload_blob(
        json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8") + b"\n",
        overwrite=True,
        content_settings=ContentSettings(content_type="application/json"),
    )
    print(json.dumps({
        "bytes": byte_count,
        "sha256": sha256,
        "blob": destination,
        "manifest": manifest_name,
    }, indent=2))
    credential.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'@ | Set-Content -LiteralPath $pythonScript -Encoding utf8

  $arguments = @(
    $pythonScript,
    '--account', $storageAccount,
    '--dataset', $Dataset,
    '--source', $SourceUrl,
    '--blob-name', $BlobName
  )
  if ($Overwrite) { $arguments += '--overwrite' }
  & $python @arguments
  if ($LASTEXITCODE -ne 0) { throw 'Direct staging failed.' }
} finally {
  if (Test-Path -LiteralPath $taskRoot) {
    Remove-Item -LiteralPath $taskRoot -Recurse -Force
  }
  Remove-Variable storageAccount -ErrorAction SilentlyContinue
}
