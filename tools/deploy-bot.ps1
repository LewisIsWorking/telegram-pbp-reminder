#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Force an immediate run of the PathWars bot's GitHub Actions workflow.

.DESCRIPTION
    The PathWars nudge bot (LewisIsWorking/telegram-pbp-reminder) is
    serverless: it runs entirely from a GitHub Actions hourly cron. After
    a code change merges to main, the workflow already picks it up on the
    next cron tick (within an hour). This script is for when you want the
    new code live RIGHT NOW instead of waiting -- e.g. just shipped a
    hotfix and want to confirm it works before EOD.

    What this does:
        gh workflow run pbp-reminder.yml --repo LewisIsWorking/telegram-pbp-reminder

    Optionally tails the resulting run with `gh run watch`.

    NOTE: this is NOT a "deploy" in the traditional sense. The merge IS
    the deploy. This script just kicks the cron earlier.

    WHY IT LIVES HERE (moved 2026-09-07, Lewis's question)
    Until today this sat in ComeOnOverUno/scripts/, a private repo it has
    no other connection to: no imports, no repo-relative paths, nothing
    but this workflow and this repo name.

    That split was not merely untidy. Adding the VPS heartbeat to THIS
    repo on 2026-09-06 broke the run-selection logic in THAT one, because
    workflow_dispatch stopped being rare. A change and its consequence in
    different repositories is exactly the coupling that hides a defect,
    and the fix then had to travel back through a release-note gate and a
    version bump belonging to an unrelated product.

    It also could not go live: the ComeOnOverUno working copy was six
    commits behind and stuck, so the fixed script was merged but not the
    one being run. Here, the copy on disk is the copy that ships.

.PARAMETER Watch
    After triggering, tail the run with `gh run watch` so you see live
    progress + final result without leaving the terminal.

.PARAMETER DryRun
    Print what would happen without actually triggering the workflow.
#>
param(
    [switch]$Watch,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

# PATH/PATHEXT normalisation, same rationale as the other ops scripts.
if ($env:PATHEXT -notlike '*.EXE*') {
    $env:PATHEXT = '.COM;.EXE;.BAT;.CMD;.VBS;.VBE;.JS;.JSE;.WSF;.WSH;.MSC'
}
foreach ($candidate in @('C:\Program Files\GitHub CLI', 'C:\Program Files\Git\cmd')) {
    if ((Test-Path $candidate) -and ($env:PATH -notlike "*$candidate*")) {
        $env:PATH = "$candidate;$env:PATH"
    }
}

# Host-logging helpers, INLINED on 2026-09-07 with the move out of
# ComeOnOverUno. They were dot-sourced from scripts/lib/console-helpers.ps1
# there, which was the script's one remaining tie to that repo and would
# have made this copy fail on the first run from its new home.
#
# ⚠️ It nearly shipped broken. A grep for "$PSScriptRoot" came back empty
# and I read that as "no coupling" without checking the grep could match
# at all; the -DryRun caught it. Five one-line functions are not worth a
# shared library across a repository boundary anyway.
$script:Tag = 'deploy-bot'
function Write-Step([string]$msg) { Write-Host "`n[$script:Tag] $msg"       -ForegroundColor Cyan }
function Write-Ok  ([string]$msg) { Write-Host "[$script:Tag] OK: $msg"     -ForegroundColor Green }
function Write-Warn([string]$msg) { Write-Host "[$script:Tag] WARN: $msg"   -ForegroundColor Yellow }
function Write-Err ([string]$msg) { Write-Host "[$script:Tag] ERR: $msg"    -ForegroundColor Red }

$BotRepo = 'LewisIsWorking/telegram-pbp-reminder'
$Workflow = 'pbp-reminder.yml'

# Sanity-check gh CLI is available and authenticated against the right account.
# The keyring-stored cred should be LewisIsWorking; if a different user is
# active (e.g. someone left a CI token in env), bail early rather than push
# the wrong button.
Write-Step "Verifying gh CLI auth..."
if ($DryRun) {
    Write-Host "[deploy-bot] DryRun: would verify gh auth status against $BotRepo" -ForegroundColor Magenta
} else {
    $authCheck = & gh auth status 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Err "gh CLI not authenticated. Run 'gh auth login' first."
        exit 1
    }
    # Check we can actually see the bot repo (catches private-repo perms drift).
    $repoCheck = & gh repo view $BotRepo --json name 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Err "Can't view $BotRepo with current gh credentials: $repoCheck"
        exit 1
    }
    Write-Ok "gh CLI authenticated, $BotRepo visible."
}

# Show what's currently shipping so the user knows whether a manual
# trigger is even needed. If main is ahead of the last completed run,
# triggering catches things up. If they match, the cron already covered it.
Write-Step "Checking workflow status..."
if (-not $DryRun) {
    Write-Host '[deploy-bot] Last 3 runs:' -ForegroundColor DarkGray
    & gh run list --repo $BotRepo --workflow $Workflow --limit 3 --json status,conclusion,displayTitle,headSha,createdAt `
        --jq '.[] | "  \(.createdAt | fromdateiso8601 | strftime("%Y-%m-%d %H:%M")) | \(.status) \(.conclusion // "-") | \(.headSha[0:7]) | \(.displayTitle)"'
}

# Captured BEFORE the trigger so the poll below can require a new id.
# Empty string when there is no prior dispatch run at all, which makes the
# first-ever dispatch differ from it and match immediately.
$priorDispatch = & gh run list --repo $BotRepo --workflow $Workflow --event workflow_dispatch --limit 1 --json databaseId | ConvertFrom-Json
$priorDispatchId = if ($priorDispatch) { $priorDispatch[0].databaseId } else { '' }

Write-Step "Triggering immediate workflow run on main..."
if ($DryRun) {
    Write-Host "[deploy-bot] DryRun: would invoke 'gh workflow run $Workflow --repo $BotRepo --ref main'" -ForegroundColor Magenta
    Write-Host '[deploy-bot] Done.' -ForegroundColor Cyan
    return
}

& gh workflow run $Workflow --repo $BotRepo --ref main
if ($LASTEXITCODE -ne 0) {
    Write-Err "gh workflow run failed (exit $LASTEXITCODE)."
    exit $LASTEXITCODE
}

Write-Ok "Triggered. GitHub Actions schedules workflow_dispatch runs near-instantly."

# GitHub's API doesn't immediately return the new run id from `workflow run`,
# so we poll for the most recent dispatch-triggered run.
#
# ⛔ A 3s sleep and "take the newest dispatch run" USED to be safe, because
# workflow_dispatch was rare: the watchdog's self-repair and the odd manual
# nudge. Since 2026-09-06 the VPS external heartbeat dispatches whenever
# GitHub goes quiet for 45 minutes, which is running at roughly 12 a day.
#
# So "newest dispatch run" can now be the heartbeat's, not ours. The bad
# case is not a mislabelled URL: if the heartbeat's run has already
# FINISHED, `gh run watch` returns instantly with ITS conclusion and this
# script reports success for a run the user never triggered.
#
# ⭐ Fixed by remembering the newest dispatch id BEFORE triggering and
# waiting for a genuinely different one. Version-independent, and it makes
# "could not identify our run" a visible outcome rather than a wrong
# answer delivered confidently.
$runId = $null
foreach ($attempt in 1..10) {
    Start-Sleep -Seconds 2
    $latest = & gh run list --repo $BotRepo --workflow $Workflow --event workflow_dispatch --limit 1 --json databaseId,status,displayTitle,createdAt | ConvertFrom-Json
    if ($latest -and $latest[0].databaseId -ne $priorDispatchId) {
        $runId = $latest[0].databaseId
        break
    }
}
if (-not $runId) {
    Write-Warn "Triggered, but couldn't tell our run apart from an existing one after 20s."
    Write-Warn "Not watching, rather than reporting on a run that may not be ours."
    Write-Host "  https://github.com/$BotRepo/actions/workflows/$Workflow" -ForegroundColor DarkGray
    return
}
Write-Host "[deploy-bot] New run: #$runId -- $($latest[0].displayTitle)" -ForegroundColor DarkGray
Write-Host "[deploy-bot]   https://github.com/$BotRepo/actions/runs/$runId" -ForegroundColor DarkGray

if ($Watch) {
    Write-Step "Watching run (Ctrl-C to stop following; the run will keep going)..."
    # `gh run watch` blocks until the run finishes and exits 0/non-zero with
    # the final conclusion. Convenient for "trigger and wait" flows.
    & gh run watch $runId --repo $BotRepo --exit-status
    $watchExit = $LASTEXITCODE
    if ($watchExit -eq 0) {
        Write-Ok "Run #$runId completed successfully."
    } else {
        Write-Err "Run #$runId failed (exit $watchExit). Check the logs at the URL above."
        exit $watchExit
    }
} else {
    Write-Host '[deploy-bot] Pass -Watch to tail the run live. Otherwise check the URL above when convenient.' -ForegroundColor DarkGray
}

Write-Host ''
Write-Host '[deploy-bot] Done.' -ForegroundColor Cyan
