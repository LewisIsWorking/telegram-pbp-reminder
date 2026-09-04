# `preflight/`: checks that run before the bot posts anything

One question: **can the bot still record what it sends?** If it cannot,
nothing should be sent.

## Why this exists

On 2026-08-18 `main` gained branch protection. The workflow's state-commit
step began failing with `GH006`, and every run afterwards checked out the
same frozen state, saw an empty `msg_ids`, and posted the same GM-queue
notice again. **25 consecutive runs failed and nothing said so.** State had
not moved since `2026-08-18T15:01`; the fault surfaced ~15 hours later as
four duplicate `📋 Unreplied: 1` posts.

The posting code was correct throughout. It was reading state that could
never change.

## The asymmetry that decides the behaviour

| | cost |
|---|---|
| **not posting** | the next hourly run posts it, so it is recoverable |
| **posting without recording** | the message id is lost, so nothing will ever delete it. Past 48h Telegram refuses to delete it at all: **a permanent orphan** |

There are already 41 such orphans. So when the bot cannot show that it
remembers what it sends, it stays quiet.

## The pieces

| file | job |
|---|---|
| `prior_runs.py` | pure decision logic over both signals, with no I/O, so every case is testable directly |
| `heartbeat.py` | reads and writes `data/ci_heartbeat.json`, which is both the freshness signal and the guarantee there is **always** something to push |
| `run_history.py` | the Actions API call and nothing else; the only file here that touches the network |
| `delivery_gap.py` | tells *"GitHub never ran us"* apart from *"our push failed"*, from the run timestamps (2026-09-04) |
| `gate.py` | the entry point: read heartbeat → read history → publish `halt` → alert → write heartbeat |
| `watchdog.py`, `self_repair.py`, `alert_cadence.py` | is anything running at all, force a run if not, and how often to say so |

⚠️ **The heartbeat is read before this run writes its own.** Written first, the
gate would measure itself and every run would look perfectly healthy, silently
and permanently. There is a test pinning the call order for exactly this reason.

## ⭐ Two signals, combined as a union

`halt_reasons()` asks both, and **either may add a reason to stay quiet while
neither can clear the other's.**

| signal | strength | weakness |
|---|---|---|
| committed heartbeat age | local repo content, cannot be served from a cache | says nothing until the first heartbeat exists |
| Actions run history | catches the very first broken run immediately | an API query, so it can be stale or 403 |

This shape was forced by a real miss, hours after the first version shipped. The
Actions API served a **cached page of runs from three days earlier**, the gate
read it as *0 failed runs*, and posting proceeded on a run whose real streak was
27. Re-querying minutes later returned correct data, so it was transient rather
than a bad query.

The lesson is not "use a better query". It is that a source which can only ever
make the gate **more** cautious does not need to be reliable. Under a union,
neither a stale API nor a missing heartbeat can unlock anything.

## ⭐ A stale heartbeat has two causes (2026-09-04)

Not posting is *cheap*, but it is not free, and for a while it was being paid
for nothing. On 2026-09-04 the bot paused and alerted Lewis three times, at
3.2h, 3.1h and 3.3h, while **every one of the last 40 runs had concluded
`success`**. No push had failed. GitHub had skipped two hours of a cron it was
delivering about 27% of, and each gap read as a state-persistence outage.

The heartbeat only advances inside a successful push, so its timestamp `H` is
the moment of the last one. That makes the causes separable:

| observation | meaning |
|---|---|
| a run finished after `H`, and `H` did not move | the push is broken, **halt** |
| no run finished after `H` at all | nothing has tried yet, the scheduler is quiet, **post** |

⛔⛔ **The suppression is refused unless the history proves itself fresh**, and it
proves it the only way a cache cannot forge: *the currently executing run must
appear in it*. Without that proof this would have re-opened the 2026-08-19
incident above, because a cached page of old runs looks exactly like a quiet
scheduler: old runs, none since `H`.

It removes the stale-heartbeat reason only. A **failed-run streak is never
suppressed**: that is direct evidence a push lost.

Replayed against the real run history, all 8 pauses in 2026-09-02..04 were
delivery gaps. `test_the_gate_tells_a_gap_from_a_broken_push.py` holds both
directions, and seven mutations of the logic were each confirmed to fail it.

## Two properties that are easy to break

**The gate must never fail its own job.** It exits `0` on every path
including its own errors. A gate that failed the run would keep the
failure streak alive, which keeps the gate closed. The bot could never
recover, not even after the cause was fixed. The commit-and-push step
still runs, so a repaired push turns the run green and reopens the gate an
hour later.

**The gate fails open when it cannot tell.** An unreachable API is not
evidence that anything is wrong, and halting on "don't know" is
unrecoverable for the same reason. `fetch_conclusions` returns `None` for
*no answer* and `[]` for *no prior runs*. Collapsing those two would let
an auth failure read as a clean history and silently disarm the gate.

## Why the heartbeat is not optional

The commit step short-circuits when there is nothing staged, so a quiet
hour goes green **without contacting the remote**. One such run would reset
the streak and reopen the gate while the push was still broken. The
heartbeat guarantees every run attempts a push, which is what makes
"green" mean "state landed".

It lives in `data/`, **not** `data/state/`: the schema registry there
requires an owning module and a runtime reader, and the heartbeat has
neither by design.

## Requirements

`actions: read` in the job's `permissions:` block. Without it the runs API
returns 403 and the gate fails open, armed in appearance only.

## Testing

```
cd scripts && python -m pytest test_preflight_prior_runs.py test_preflight_gate.py \
    test_the_gate_tells_a_gap_from_a_broken_push.py -q
```

The guards are proven by mutation, not by reading. Nine mutations, each
asserted to have **applied** before the run so green can never mean "the probe
never arrived":

inverting `should_halt_posting` either way, inverting the streak arithmetic,
collapsing `None` into `[]`, removing the heartbeat signal, making a stale
heartbeat never halt, making an unknown age halt, **collapsing the union back
into an intersection**, and **writing the heartbeat before reading it**.

Two load-bearing cases: the real 2026-08-18 run history must halt, and the
cached-API reading from 2026-08-19 (`streak 0`, heartbeat 15h old) must halt
anyway. Each is paired with a healthy case so a hardcoded `True` cannot pass.

Seven more cover `delivery_gap` (2026-09-04): removing the freshness proof,
emptying `finished_since`, counting in-progress runs as evidence, making the
suppression a no-op, letting it reach the streak reason, cutting it out of
`main`, and swapping started-after for finished-after. Every one was confirmed
to fail the suite before being reverted.
