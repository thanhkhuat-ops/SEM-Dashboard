# Run in Administrator PowerShell. Applies the LAN firewall rule and logon task only.
param(
    [System.Net.IPAddress]$LanAddress = '192.168.1.42',
    [string]$LanSubnet = '192.168.1.0/24',
    [string]$TaskUser = [Security.Principal.WindowsIdentity]::GetCurrent().Name
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$logDirectory = Join-Path $projectRoot 'logs'
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
Start-Transcript -Path (Join-Path $logDirectory 'lan-setup.log') -Append | Out-Null
try {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    if (-not ([Security.Principal.WindowsPrincipal]::new($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Administrator privileges are required for the firewall rule. Run this script from Administrator PowerShell.'
    }
    $adapterAddress = Get-NetIPAddress -AddressFamily IPv4 -IPAddress $LanAddress.ToString() -ErrorAction Stop
    $profile = Get-NetConnectionProfile -InterfaceIndex $adapterAddress.InterfaceIndex -ErrorAction Stop
    if ($profile.NetworkCategory -ne 'Private') { throw 'The selected LAN interface must already use the Private profile.' }

    $ruleName = 'SaleSappV2-LAN-8000'
    $existingRule = Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue
    $ruleOptions = @{
        DisplayName = 'SaleSappV2 LAN TCP 8000'
        Description = 'SaleSappV2 web access from the trusted office subnet only.'
        Enabled = 'True'
        Direction = 'Inbound'
        Action = 'Allow'
        Protocol = 'TCP'
        LocalPort = 8000
        LocalAddress = $LanAddress.ToString()
        RemoteAddress = $LanSubnet
        Profile = 'Private'
        EdgeTraversalPolicy = 'Block'
    }
    if ($existingRule) {
        $ruleOptions.Remove('DisplayName')
        Set-NetFirewallRule -Name $ruleName -NewDisplayName 'SaleSappV2 LAN TCP 8000' @ruleOptions | Out-Null
    } else {
        New-NetFirewallRule -Name $ruleName @ruleOptions | Out-Null
    }
    Write-Host "Firewall configured: $LanSubnet -> ${LanAddress}:8000, Private profile."

    $powershellPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $startScript = Join-Path $PSScriptRoot 'start_server.ps1'
    $taskArguments = '-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}" -Wait' -f $startScript
    $action = New-ScheduledTaskAction -Execute $powershellPath -Argument $taskArguments -WorkingDirectory $projectRoot
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $TaskUser
    $principal = New-ScheduledTaskPrincipal -UserId $TaskUser -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable `
        -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    Register-ScheduledTask -TaskName 'SaleSappV2-Web' -Action $action -Trigger $trigger `
        -Principal $principal -Settings $settings -Description 'Start the SaleSappV2 LAN web server when its owner logs on.' -Force | Out-Null
    Write-Host "Task SaleSappV2-Web registered for $TaskUser at logon, limited privileges."
    $verifiedRule = Get-NetFirewallRule -Name $ruleName -PolicyStore ActiveStore -ErrorAction Stop
    $verifiedRule | Select-Object Name, Enabled, Profile, Direction, Action | Format-List
    $verifiedRule | Get-NetFirewallPortFilter | Select-Object Protocol, LocalPort | Format-List
    $verifiedRule | Get-NetFirewallAddressFilter | Select-Object LocalAddress, RemoteAddress | Format-List
    Get-ScheduledTask -TaskName 'SaleSappV2-Web' -ErrorAction Stop |
        Select-Object TaskName, State, @{Name='UserId';Expression={$_.Principal.UserId}},
            @{Name='RunLevel';Expression={$_.Principal.RunLevel}} | Format-List
    Write-Host 'LAN_SETUP_OK'
} finally {
    Stop-Transcript | Out-Null
}
