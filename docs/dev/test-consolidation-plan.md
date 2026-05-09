## Test consolidation pass — plan for ROADMAP P2/6

Status: **draft for review**. Risky enough that it deserves a written
plan before any test gets deleted.

---

### Why this exists

The 200-line refactor split a number of "coverage-seed" files
(`test_branch_gaps`, `test_remaining_*`, `test_final_*`,
`test_close_gaps`, `test_zero_coverage`, etc.) into themed sub-files.
Many of those sub-files duplicate behaviour-focused tests in proper
feature files.

Rough inventory of suspected overlap:

```
scripts/test_branch_gaps_*           (16 sub-files, ~13 KB each)
scripts/test_remaining_100_*         (5  sub-files)
scripts/test_remaining_gaps_*        (6  sub-files)
scripts/test_final_100_*             (4  sub-files)
scripts/test_final_coverage_*        (8  sub-files)
scripts/test_final_gaps_*            (3  sub-files)
scripts/test_final_push_*            (6  sub-files)
scripts/test_close_gaps_*            (3  sub-files)
scripts/test_zero_coverage_*         (5  sub-files)
scripts/test_dispatch_coverage_*     (9  sub-files)
scripts/test_scheduled_coverage_*    (4  sub-files)
scripts/test_commands_coverage_*     (5  sub-files)
scripts/test_utility_coverage_*      (5  sub-files)
scripts/test_aaa_isolated_*          (6  sub-files)
scripts/test_push_to_100_*           (4  sub-files)
```

That's ~89 sub-files, all generated to hit specific coverage gaps.
Each sub-file's docstring identifies the production module(s) it
tests. For most production modules there's *also* a feature-test
file (`test_<module>.py`) covering the same code from a behaviour-
first angle.

The hypothesis: many coverage-seed tests duplicate the feature
tests, and the duplicates can be deleted while keeping coverage at
100%.

---

### Why this is risky

Deleting a test that *looks* like a duplicate but actually covers
an edge case the feature test misses is silent: `pytest --cov`
reports 100% line coverage, but a regression slips through later.
Coverage is a necessary but not sufficient signal.

Three failure modes:

* **Branch coverage divergence.** Line coverage stays 100% but
  branch coverage drops. Two tests can both touch the same line
  with different branch outcomes; deleting one loses a branch.
* **Mutation-equivalent gaps.** A coverage-seed test asserts on
  the exact return value (e.g. `assert result == "expected"`)
  while the feature test only checks shape (`assert isinstance(result,
  str)`). The "duplicate" coverage-seed test is the only one that
  would catch a mutation that returns the wrong string.
* **Implicit fixture coverage.** A coverage-seed test happens to
  call a helper function as a side effect of its setup. Without
  that test, the helper drops to 0% coverage, but no other test
  exercises it.

So the safety net is: **branch coverage** (not line coverage) and
**diff review of every deletion**.

---

### Proposed process

The work is best done in batches, one production module at a time,
not one sub-file at a time. The mapping is sub-file → production
module, but the *unit of decision* is "for this production module,
what's the minimum set of tests that gives us 100% line + branch
coverage?"

**Step 1. Map sub-file → production module.** Walk every
coverage-seed sub-file's docstring and extract the "Coverage tests
for: X" line(s). Some sub-files cover multiple modules; that's fine,
they appear in multiple module-buckets.

Output: `tools/test_consolidation_map.json` with shape

```json
{
  "boons/display.py": [
    "test_scheduled_coverage_01_boons_display.py",
    "test_scheduled_coverage_04_boons_display.py"
  ],
  "checker.py": [
    "test_dispatch_coverage_01_checker.py",
    "test_dispatch_coverage_07_checker_voting.py",
    "test_checker_*.py (ALL feature files)"
  ],
  ...
}
```

This step is mechanical — script it.

**Step 2. Establish the baseline.** Run

```
pytest --cov=. --cov-branch --cov-report=html
```

Save the HTML report at `tools/coverage_baseline_<sha>.html` (or
copy it somewhere outside `data/`). Both line coverage AND branch
coverage are recorded. This is the bar every subsequent run must
match or beat.

**Step 3. Process one module per session.** For each production
module:

1. Open all sub-files in the bucket.
2. For each test in each coverage-seed sub-file, find the closest
   semantic equivalent in the feature test file.
3. Delete the coverage-seed test if its *behaviour* is covered by
   the feature test.
4. Run `pytest --cov=. --cov-branch` for that module's coverage
   line specifically. If it dropped, revert the last deletion.
5. If a coverage-seed test caught something the feature test
   doesn't, *move* the test into the feature file with a comment
   explaining why it's there.
6. Commit per-module. Never bundle multiple modules in one commit.

**Step 4. Cleanup empty sub-files.** After processing, some sub-
files end up with one or two surviving tests. If there are fewer
than 3 tests left, fold them into the feature file and delete the
sub-file. If a sub-file ends up empty, delete it.

**Step 5. Update the splitter.** `tools/test_splitter.py` will
have to deal with smaller source files going forward. No changes
to the splitter itself — it only runs when a file is over 200 lines,
so as long as the new feature files stay small, the splitter stays
dormant.

---

### What this DOESN'T do

* **Doesn't change behaviour.** No production code is touched.
* **Doesn't change test contracts.** The remaining tests assert
  the same things they always did.
* **Doesn't change coverage.** Both line and branch coverage stay
  at the baseline level. We only delete genuine duplicates.
* **Doesn't add new tests.** This is consolidation, not coverage
  expansion. If a sub-file caught a real edge case, that test moves
  but doesn't get rewritten.

---

### Estimated scope

There are ~17 coverage-seed file families × ~3 modules per family
= ~50 module-buckets to process. At ~30 minutes per bucket
(careful read of the tests, semantic comparison, delete + verify),
that's ~25 hours of work. Spread over multiple sessions.

Realistic target: **-25% test code** (the original ROADMAP figure).
Could be more if some entire sub-files turn out to be pure
duplicates; could be less if most coverage-seed tests turn out to
catch real edge cases the feature tests miss.

---

### Order of operations

Process modules in *risk order*, lowest-risk first:

1. **Pure helper modules** (`helpers_pkg/*`, `parsing/*`) — small
   modules with simple contracts. Easy to verify "feature test
   covers all branches".
2. **Display/formatting modules** (`boons/display.py`,
   `commands/queue_io.py`) — output-shape tests dominate; easy to
   spot duplicates.
3. **Command modules** (`commands/*`, `dispatch/*`) — medium
   complexity. Behaviour usually well-covered by feature tests.
4. **Scheduled jobs** (`scheduled/*`) — complex flows. Coverage-
   seed tests here often catch real edge cases.
5. **`checker.py`** — the orchestrator. Last, because it's the
   most-shared module and any miss here has the widest blast
   radius.

Bail out and pause if at any point the bucket-by-bucket coverage
report shows persistent branch drops we can't explain.

---

### Tooling needed before starting

Two scripts in `tools/`:

* **`tools/build_consolidation_map.py`.** Walks every
  `scripts/test_*_NN_*.py`, parses the docstring, emits the
  module → sub-files JSON. Run once, output committed.
* **`tools/coverage_diff.py`.** Reads two `coverage.json` files
  and emits a per-module table of (line coverage delta, branch
  coverage delta). Used after every deletion to spot drops.

These scripts are pure tooling, not production code. They live
alongside `tools/test_splitter.py`.

---

### Decision needed

1. **Confirm scope.** The -25% target is a guess; do you have a
   stronger preference (e.g. "delete all `test_branch_gaps_*` and
   accept whatever coverage that costs")?
2. **Branch coverage threshold.** Is "branch coverage must not
   drop" the right bar? Or is "line coverage stays 100%, branch
   coverage stays >= baseline minus 0.5pp" acceptable?
3. **Order.** Risk-ordered processing as above, or attack the
   biggest sub-file family first (`test_branch_gaps_*` at 16 files)
   to clear the most ground per session?

---

### Why this is P2 not P1

The duplicate tests aren't *wrong* — they pass, they cover code,
they stay green. The cost is maintenance overhead (changes to a
production function require updating multiple tests) and CI time
(~12 seconds today, but it grows with every coverage-seed file).
Neither is urgent. P3/9 (StateStore) and P3/10 (concurrency) are
higher leverage even though they're rated P3, because they unlock
future work that today is structurally hard.

This is genuine "tidying", not "fix a bug". Which is exactly why
it deserves a written plan instead of a "just delete the
duplicates" session.
