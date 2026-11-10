# Restart only a verified SaleSappV2 Uvicorn process on the requested port.
# Add -Background for hidden execution with logs, or -BindAddress 127.0.0.1 for local use.
param(
    [ValidateRange(1, 65535)][int]$Port = 8000,
    [System.Net.IPAddress]$BindAddress = '0.0.0.0',
    [switch]$Background
)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$listeners = @(Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object LocalPort -eq $Port)
$serverIds = @($listeners | Select-Object -ExpandProperty OwningProcess -Unique)
foreach ($serverId in $serverIds) {
    $serverInfo = Get-CimInstance Win32_Process -Filter "ProcessId=$serverId" -ErrorAction Stop
    if (-not $serverInfo -or $serverInfo.CommandLine -notmatch '\s-m\s+uvicorn\s+app\.main:app(?:\s|$)') {
        throw "Port $Port belongs to an unverified process (PID $serverId). Nothing was stopped."
    }
}
# Validate every listener before stopping any of them.
foreach ($serverId in $serverIds) {
    Write-Host "Stopping SaleSappV2 PID $serverId on port $Port"
    Stop-Process -Id $serverId -Force -ErrorAction Stop
}
for ($attempt = 0; $attempt -lt 20; $attempt++) {
    if (-not (Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object LocalPort -eq $Port)) { break }
    Start-Sleep -Milliseconds 500
}
if (Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object LocalPort -eq $Port) {
    throw "Port $Port is still occupied."
}
if ($Background) {
    & "$PSScriptRoot\scripts\start_server.ps1" -Port $Port -BindAddress $BindAddress
} else {
    Write-Host "Starting SaleSappV2 on ${BindAddress}:$Port (Ctrl+C to stop)"
    & .\.venv\Scripts\python.exe -m uvicorn app.main:app --host $BindAddress.ToString() --port $Port
    exit $LASTEXITCODE
}
