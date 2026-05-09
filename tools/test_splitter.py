"""Multi-strategy splitter for test files that violate the 200-line cap.

Descent of the splitter used during the 200-line refactor (phases 3-7
revisited in the post-incident fix-up). Kept here so that if any test
file ever drifts back over 200 lines, the splitter can be re-run
without re-deriving twelve sessions of debugging.

See:
  * docs/dev/ROADMAP.md  — entry P0/1 explains why this lives in tools/
  * docs/dev/REFACTOR_PROGRESS.md  — the L1—L14 learnings encoded here

Three splitting strategies, picked per file:

  A) Section-marker splits (``# ── ... ──``, ``# ━━━``, ``# ═══``)
     Walks header lines and uses them as bin boundaries.

  B) Internal AST splits for sections bigger than the line target.
     Falls back to test-by-test packing within a section.

  C) Module-level helper / constant preservation. Functions and
     ``Assign``/``AnnAssign`` nodes that live inside *any* section get
     copied into *every* sub-file produced from that source, so
     cross-section ``_ctx`` / ``_bt_msg`` / ``_CHECKER_FUNCS`` patterns
     keep working after the split.

Usage::

    cd tools
    python -X utf8 test_splitter.py <stem> [<stem> ...]

Reads ``_<stem>_full.py`` from the working directory (typically a
file fetched via ``git show <pre-split-commit>:scripts/<stem>.py``)
and writes themed sub-files to ``out/<stem>_NN_<topic>.py``.

The ``target`` parameter (default 140) is the soft body-line cap per
bin. The splitter retries with ``target=110`` automatically if any
produced file exceeds 200 lines.

Bugs the original phase-3-7 splitter had (all fixed here):

  1. Module-level helper functions defined BEFORE the first section
     comment were dropped from every sub-file.
  2. When a section was bigger than the line target and got split
     internally by AST, the section's preamble (lines between section
     comment and first test, often containing imports the tests need)
     was kept ONLY with the first chunk. Subsequent chunks lost the
     imports.
  3. Helpers and constants defined INSIDE one section that were used
     by tests in OTHER sections (cross-section ``_ctx``, ``_bt_msg``,
     ``_CHECKER_FUNCS`` patterns) got dropped from every bin except
     the one containing the original definition.

Fix shape:
  - The module header (everything before the first section/test) is
    captured verbatim and prepended to every sub-file.
  - For each section, the preamble is captured and prepended to every
    chunk produced by an internal AST split.
  - Every non-test top-level definition (FunctionDef, Assign,
    AnnAssign) inside any section is copied into every sub-file's
    helper block.
"""

import ast
import os
import sys

from _splitter_helpers import find_sections, full_range
from _splitter_pack import emit_bins, pack_bins


def _capture_helpers_block(tree, top_funcs, first_section_line, extract):
    """Build the cross-section helpers/constants block.

    Walks every top-level ``FunctionDef`` (non-test) and every
    ``Assign``/``AnnAssign`` node that lives inside a section, and
    returns their concatenated source verbatim. Deduped by line range.
    """
    block = ""
    seen = set()
    for nd, ls, le in top_funcs:
        if not nd.name.startswith("test_") and ls >= first_section_line:
            key = (ls, le)
            if key not in seen:
                seen.add(key)
                block += extract(ls, le) + "\n\n"
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        ls, le = node.lineno, node.end_lineno
        if ls < first_section_line:
            continue
        key = (ls, le)
        if key not in seen:
            seen.add(key)
            block += extract(ls, le) + "\n\n"
    return block.rstrip()


def split_file(src_path, prefix, target=140, out_dir="out"):
    """Split a single section-marked test file into themed sub-files.

    Returns a list of ``(path, line_count, bin_size)`` tuples for any
    sub-files that were generated. An empty list means the source had
    no section markers and the splitter declined to fall through.
    """
    with open(src_path, encoding="utf-8") as f:
        SRC = f.read()
    LINES = SRC.split("\n")
    tree = ast.parse(SRC)

    sections = find_sections(LINES)
    if not sections:
        print(f"  {src_path}: NO sections found, falling through")
        return []

    section_ranges = []
    for idx, (lineno, title) in enumerate(sections):
        end = (sections[idx + 1][0] - 1) if idx + 1 < len(sections) else len(LINES)
        section_ranges.append((lineno, end, title, end - lineno + 1))

    top_funcs = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            f, l = full_range(node)
            top_funcs.append((node, f, l))

    def tests_in_range(start, end):
        return [(n, ls, le) for n, ls, le in top_funcs
                if n.name.startswith("test_") and ls >= start and le <= end]

    def extract(start, end):
        return "\n".join(LINES[start - 1: end])

    # FIX #1: capture the module header (everything before first section).
    first_section_line = sections[0][0]
    module_header_lines = LINES[: first_section_line - 1]
    while module_header_lines and module_header_lines[-1].strip() == "":
        module_header_lines.pop()
    module_header = "\n".join(module_header_lines)

    # FIX #1b/c: capture cross-section helpers and module-level constants.
    all_helpers_block = _capture_helpers_block(
        tree, top_funcs, first_section_line, extract,
    )

    # FIX #2: per-section preambles for internal AST splits.
    def section_preamble(s, e):
        sec_tests = tests_in_range(s, e)
        if not sec_tests:
            return ""
        first_test_start = sec_tests[0][1]
        return "\n".join(LINES[s - 1: first_test_start - 1])

    bins = pack_bins(section_ranges, target, tests_in_range, section_preamble)
    return emit_bins(bins, prefix, out_dir, module_header,
                     all_helpers_block, extract)


def _run_cli(stems):
    """Run the splitter on each stem with retry-on-overflow at target=110."""
    overlong = []
    for stem in stems:
        print(f"\n=== {stem} ===")
        results = split_file(f"_{stem}_full.py", stem,
                             target=140, out_dir="out")
        for path, lines, n in results:
            flag = "  ⚠OVER" if lines > 200 else ""
            print(f"  {path:65s} {lines:4d} lines, {n} bins{flag}")
            if lines > 200:
                overlong.append(path)

    if overlong:
        print(f"\n⚠ {len(overlong)} files over 200 — retrying with target=110")
        for p in overlong:
            os.remove(p)
        for stem in stems:
            stem_overlong = [p for p in overlong if f"/{stem}_" in p]
            if not stem_overlong:
                continue
            for f in os.listdir("out"):
                if f.startswith(f"{stem}_"):
                    os.remove(f"out/{f}")
            print(f"  retrying {stem} with target=110")
            split_file(f"_{stem}_full.py", stem, target=110, out_dir="out")
    print("\nDone.")


if __name__ == "__main__":
    if not sys.argv[1:]:
        print("Usage: python test_splitter.py <stem> [<stem> ...]")
        sys.exit(1)
    _run_cli(sys.argv[1:])
