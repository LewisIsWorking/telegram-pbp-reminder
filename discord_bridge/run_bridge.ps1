# Launcher used by the Startup-folder VBS (and the scheduled task). Runs the
# voice bridge with its working directory set here (so .env loads) and appends
# all output to bridge.log.

# NOTE: discord.py writes its INFO logs (e.g. "logging in using static token")
# to STDERR, not stdout. Under `$ErrorActionPreference = 'Stop'` PowerShell
# promotes any native-process stderr output to a *terminating* NativeCommandError
# — so the launcher used to abort (killing the bridge) the instant the bridge
# logged its first healthy startup line. Keep Stop for the setup below, but run
# the bridge itself under 'Continue' and disable native-command error promotion
# so stderr logging is captured, not fatal.
$ErrorActionPreference = "Stop"
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $dir

$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { $python = "C:\Python313\python.exe" }

# From here on, the bridge's stderr logging must NOT be treated as an error.
$ErrorActionPreference = "Continue"
# PowerShell 7.3+: stop native exit codes / stderr from triggering error action.
# Assigning is harmless on older hosts that don't recognise the variable.
$PSNativeCommandUseErrorActionPreference = $false

# *>> appends every stream (incl. stderr) to the log. The bridge forces UTF-8
# itself, so emoji event lines log cleanly.
& $python "voice_bridge.py" *>> "bridge.log"
