# Registers (and starts) a Windows Scheduled Task that runs the voice bridge at
# logon, restarts it on failure, and keeps it running with no time limit.
#
# Usage (from anywhere):
#   powershell -ExecutionPolicy Bypass -File discord_bridge\install_task.ps1
#
# Re-running is safe — it overwrites the existing task (-Force).
$ErrorActionPreference = "Stop"
$dir      = Split-Path -Parent $MyInvocation.MyCommand.Path
$launcher = Join-Path $dir "run_bridge.ps1"
$taskName = "PathWarsVoiceBridge"

# Run the launcher via a hidden PowerShell so no console window appears.
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$launcher`""

# Start at logon, and immediately if the trigger was missed (StartWhenAvailable).
$trigger = New-ScheduledTaskTrigger -AtLogOn

# Resilience: restart on failure, never time out, run on battery too.
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Force `
    -Description "Discord -> Telegram voice bridge (Path Wars)" | Out-Null

Start-ScheduledTask -TaskName $taskName
Write-Host "Registered and started scheduled task '$taskName'."
Write-Host "Logs: $(Join-Path $dir 'bridge.log')"
Write-Host "Manage: Get-ScheduledTask $taskName | Get-ScheduledTaskInfo"
