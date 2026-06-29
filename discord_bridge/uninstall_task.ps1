# Stops and removes the voice-bridge scheduled task.
#   powershell -ExecutionPolicy Bypass -File discord_bridge\uninstall_task.ps1
$ErrorActionPreference = "SilentlyContinue"
$taskName = "PathWarsVoiceBridge"
Stop-ScheduledTask -TaskName $taskName
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
Write-Host "Removed scheduled task '$taskName' (if it existed)."
