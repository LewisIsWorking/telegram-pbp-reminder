# Testing Guide

## Coverage requirement

All code in `scripts/` must maintain **100% test coverage** at all times.
Every commit must pass `pytest` with `--cov` showing no missed lines.
The CI workflow enforces this on every run.

## What 100% coverage does NOT guarantee

Coverage tells you which lines were *executed* by tests — not whether
those lines behaved correctly for all relevant inputs.

A line can be covered and still be buggy if:
- The test only exercises the happy path
- A falsy value (`None`, `""`, `0`, `[]`) is never passed
- A fallback branch exists but is never triggered in tests

### Real example

`format_queue_line` had this logic:

```python
mid = entry.get("message_id", "")
pfx = f"{entry_num:02d} [{mid}]" if mid else f"{entry_num:02d}"
```

Tests passed `message_id: "1970"` — the line was covered. But in
production, `message_id` is `None` when the transcript lacks a `msg#`
tag, so `mid` was falsy and no ID was shown. Coverage was 100%. The
bug shipped anyway.

## Required: test falsy/absent inputs for every fallback

For any function that has a fallback path, tests **must** include a case
where the primary value is absent or falsy. Specifically:

- If a function does `entry.get("x", "")` or `entry.get("x") or ""`,
  write a test where `"x"` is missing **and** where `"x"` is `None`
- If a function does `if value: ... else: fallback`, write a test that
  hits the `else` branch with a realistic production input (not just
  `None` in isolation)
- If a function has a link/URL extraction fallback, test with a real
  link format as it appears in production

## Checklist before shipping a new function

1. **Happy path** — normal input, expected output
2. **Missing key** — `entry.get("x")` when `"x"` is not in the dict
3. **Falsy value** — `entry.get("x")` when `"x"` is `None`, `""`, `0`, or `[]`
4. **Fallback path** — whatever the `else` / `or` branch does
5. **Edge cases** — empty lists, zero counts, very long strings

## Mocking external calls

All Telegram API calls (`tg.send_message`, `tg.edit_message`, etc.) must
be mocked in tests. External-call files are tested via mocking only —
never make real API calls from tests.

## File size

All source files must stay **under 200 lines**. When a file approaches
the limit, extract logic into a helper module rather than trimming tests
or removing comments. This applies to test files too.
