param(
    [Parameter(Mandatory = $true)][string]$RunId,
    [string]$OutputRoot = "artifacts"
)

$stateRoot = Join-Path $OutputRoot "ims-set2/launcher"
$pidPath = Join-Path $stateRoot "$RunId.pid.json"
$statusPath = Join-Path $stateRoot "$RunId.status.json"
$logPath = Join-Path $stateRoot "$RunId.log"
$progressPath = Join-Path $OutputRoot "ims-set2/$RunId/live_progress.json"
if (-not (Test-Path -LiteralPath $pidPath)) {
    throw "No launcher record found for run $RunId"
}
$launch = Get-Content -Raw -LiteralPath $pidPath | ConvertFrom-Json
$process = Get-Process -Id $launch.process_id -ErrorAction SilentlyContinue
if ($process) {
    Write-Output "RUNNING process=$($launch.process_id) run=$RunId"
} elseif (Test-Path -LiteralPath $statusPath) {
    Get-Content -Raw -LiteralPath $statusPath
} else {
    Write-Output "STOPPED_WITHOUT_STATUS process=$($launch.process_id) run=$RunId"
}
if (Test-Path -LiteralPath $logPath) {
    Write-Output "Recent log:"
    Get-Content -Tail 30 -LiteralPath $logPath
}
if (Test-Path -LiteralPath $progressPath) {
    Write-Output "Structured progress:"
    Get-Content -Raw -LiteralPath $progressPath
}
