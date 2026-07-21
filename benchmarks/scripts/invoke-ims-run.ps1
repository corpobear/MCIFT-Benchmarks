param(
    [Parameter(Mandatory = $true)][string]$DatasetRoot,
    [string]$Config = "configs/ims-set2-v1.yaml",
    [string]$MciftRepo = "../../MCIFT",
    [string]$OutputRoot = "artifacts",
    [string]$RunId,
    [switch]$Resume,
    [string]$Python = "python",
    [Parameter(Mandatory = $true)][string]$LogPath,
    [Parameter(Mandatory = $true)][string]$StatusPath
)

$started = [DateTime]::UtcNow.ToString("o")
$arguments = @(
    "-m", "mcift_benchmarks", "ims", "run",
    "--config", $Config,
    "--dataset-root", $DatasetRoot,
    "--mcift-repo", $MciftRepo,
    "--output-root", $OutputRoot
)
if ($RunId) { $arguments += @("--run-id", $RunId) }
if ($Resume) { $arguments += "--resume" }

try {
    & $Python @arguments *>> $LogPath
    $code = $LASTEXITCODE
} catch {
    $_ | Out-String | Add-Content -LiteralPath $LogPath
    $code = 1
}

$status = @{
    started_at_utc = $started
    completed_at_utc = [DateTime]::UtcNow.ToString("o")
    exit_code = $code
    succeeded = ($code -eq 0)
    log_path = (Resolve-Path -LiteralPath $LogPath).Path
}
$temporary = "$StatusPath.tmp"
$status | ConvertTo-Json | Set-Content -LiteralPath $temporary -Encoding UTF8
Move-Item -LiteralPath $temporary -Destination $StatusPath -Force
exit $code
