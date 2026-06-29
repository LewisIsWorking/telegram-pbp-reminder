# Launcher used by the scheduled task. Runs the voice bridge with its working
# directory set here (so .env loads) and appends all output to bridge.log.
$ErrorActionPreference = "Stop"
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $dir

$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { $python = "C:\Python313\python.exe" }

# *>> appends stdout AND stderr. The bridge forces UTF-8 itself, so emoji
# event lines log cleanly.
& $python "voice_bridge.py" *>> "bridge.log"
