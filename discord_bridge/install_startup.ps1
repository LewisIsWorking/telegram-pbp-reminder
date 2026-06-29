# No-admin auto-start: drops a launcher in the user's Startup folder so the
# voice bridge starts (hidden) at every logon. Use this when you can't / don't
# want to register a Scheduled Task (install_task.ps1 needs elevation).
#
#   powershell -ExecutionPolicy Bypass -File discord_bridge\install_startup.ps1
#
# Also starts the bridge immediately so you don't have to log out/in first.
$ErrorActionPreference = "Stop"
$dir      = Split-Path -Parent $MyInvocation.MyCommand.Path
$launcher = Join-Path $dir "run_bridge.ps1"
$startup  = [Environment]::GetFolderPath("Startup")
$vbs      = Join-Path $startup "PathWarsVoiceBridge.vbs"

# A .vbs wrapper runs PowerShell with a truly hidden window (no console flash).
# Inner double-quotes are doubled per VBScript string escaping.
$inner   = 'powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File ""' + $launcher + '""'
$content = 'CreateObject("WScript.Shell").Run "' + $inner + '", 0, False'
Set-Content -Path $vbs -Value $content -Encoding ASCII

Write-Host "Installed startup launcher: $vbs"

# Start it now (detached) so it's live immediately.
Start-Process wscript.exe -ArgumentList "`"$vbs`""
Write-Host "Started the bridge. Logs: $(Join-Path $dir 'bridge.log')"
