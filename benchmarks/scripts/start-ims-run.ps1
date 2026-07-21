param(
    [Parameter(Mandatory = $true)][string]$DatasetRoot,
    [string]$Config = "configs/ims-set2-v1.yaml",
    [string]$MciftRepo = "../../MCIFT",
    [string]$OutputRoot = "artifacts",
    [string]$RunId,
    [string]$Python = "python"
)

if (-not $RunId) {
    $shortCommit = (git rev-parse --short=8 HEAD).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $shortCommit) { $shortCommit = "unknown" }
    $timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
    $RunId = "$timestamp-$shortCommit"
}

$stateRoot = Join-Path $OutputRoot "ims-set2/launcher"
New-Item -ItemType Directory -Force -Path $stateRoot | Out-Null
$logPath = Join-Path $stateRoot "$RunId.log"
$statusPath = Join-Path $stateRoot "$RunId.status.json"
$pidPath = Join-Path $stateRoot "$RunId.pid.json"
$invoker = Join-Path $PSScriptRoot "invoke-ims-run.ps1"

$processArguments = @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $invoker,
    "-DatasetRoot", $DatasetRoot,
    "-Config", $Config,
    "-MciftRepo", $MciftRepo,
    "-OutputRoot", $OutputRoot,
    "-RunId", $RunId,
    "-Python", $Python,
    "-LogPath", $logPath,
    "-StatusPath", $statusPath
)
$process = Start-Process -FilePath "powershell" -ArgumentList $processArguments -PassThru -WindowStyle Hidden
@{
    run_id = $RunId
    process_id = $process.Id
    started_at_utc = [DateTime]::UtcNow.ToString("o")
    log_path = (Resolve-Path -LiteralPath $logPath -ErrorAction SilentlyContinue).Path
    status_path = $statusPath
} | ConvertTo-Json | Set-Content -LiteralPath $pidPath -Encoding UTF8

Write-Output "Started IMS run $RunId as process $($process.Id)"
Write-Output "Check with: ./scripts/check-ims-run.ps1 -RunId '$RunId' -OutputRoot '$OutputRoot'"
