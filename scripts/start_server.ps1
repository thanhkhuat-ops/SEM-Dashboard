# Start SaleSappV2 without a visible console. -Wait keeps Task Scheduler tracking the server.
param(
    [ValidateRange(1, 65535)][int]$Port = 8000,
    [System.Net.IPAddress]$BindAddress = '0.0.0.0',
    [switch]$Wait
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$logDirectory = Join-Path $projectRoot 'logs'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw "Missing Python: $pythonPath" }

$listeners = @(Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object LocalPort -eq $Port)
if ($listeners.Count) {
    foreach ($listener in $listeners) {
        $existing = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)" -ErrorAction Stop
        if (-not $existing -or $existing.CommandLine -notmatch '\s-m\s+uvicorn\s+app\.main:app(?:\s|$)' -or
            $listener.LocalAddress -ne $BindAddress.ToString()) {
            throw "Port $Port is occupied by a different process or bind address. Use restart_server.ps1 after checking it."
        }
    }
    Write-Host "SaleSappV2 is already listening on ${BindAddress}:$Port."
    if ($Wait) {
        # Track a server started manually as well. If it stops, let Task Scheduler retry.
        $existingServerIds = @($listeners | Select-Object -ExpandProperty OwningProcess -Unique)
        Wait-Process -Id $existingServerIds -ErrorAction SilentlyContinue
        exit 1
    }
    return
}

New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
$logSuffix = if ($Port -eq 8000) { '' } else { "_$Port" }
$serverProcess = Start-Process -FilePath $pythonPath -WorkingDirectory $projectRoot -WindowStyle Hidden `
    -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', $BindAddress.ToString(), '--port', $Port) `
    -RedirectStandardOutput (Join-Path $logDirectory "web${logSuffix}_stdout.log") `
    -RedirectStandardError (Join-Path $logDirectory "web${logSuffix}_stderr.log") -PassThru

# Detect early failures; API/database health is checked separately during deployment.
for ($attempt = 0; $attempt -lt 20; $attempt++) {
    Start-Sleep -Milliseconds 500
    if ($serverProcess.HasExited) { throw "Server exited with code $($serverProcess.ExitCode). See logs/web${logSuffix}_stderr.log." }
    $ready = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners() |
        Where-Object { $_.Port -eq $Port -and $_.Address.ToString() -eq $BindAddress.ToString() }
    if ($ready) { break }
}
if (-not $ready) { throw "No listener appeared on port $Port within 10 seconds. Inspect the server logs." }
Write-Host "SaleSappV2 started on ${BindAddress}:$Port (launcher PID $($serverProcess.Id))."
if ($Wait) {
    $serverProcess.WaitForExit()
    exit $serverProcess.ExitCode
}
