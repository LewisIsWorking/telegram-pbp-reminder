# Removes the Startup-folder launcher and stops any running bridge.
#   powershell -ExecutionPolicy Bypass -File discord_bridge\uninstall_startup.ps1
$ErrorActionPreference = "SilentlyContinue"
$vbs = Join-Path ([Environment]::GetFolderPath("Startup")) "PathWarsVoiceBridge.vbs"
Remove-Item $vbs -Force
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*voice_bridge*' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Write-Host "Removed startup launcher and stopped the bridge (if running)."
