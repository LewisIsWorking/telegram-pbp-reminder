"""Bin packing + file emission for ``test_splitter``.

Holds the two halves of the split algorithm that are big enough to
deserve their own home: turning section ranges into bins (``pack_bins``)
and writing each bin out as a sub-file (``emit_bins``).

Split out from ``test_splitter.py`` to keep that entry-point file
under the 200-line cap.
"""

import ast
import os

from _splitter_helpers import safe_name


HEADER_TEMPLATE = '''"""Tests extracted from {orig}.py — bin {idx}.

Sections in this file:
{label_block}
"""
{module_header}

{all_helpers_block}

'''


def pack_bins(section_ranges, target, tests_in_range, section_preamble):
    """Greedy bin-packer.

    Walks ``section_ranges`` (list of ``(start, end, title, span)``)
    and groups them into bins of at most ``target`` body lines. A
    section bigger than the cap is split internally by AST: each test
    in the section becomes its own row, packed into chunks of
    ``target`` lines, and each chunk records the section's preamble
    so the chunked sub-file still has its imports/helpers.

    Bin entries are tagged tuples:
        ("SECTION", s, e, title, span)                  — full section
        ("CHUNK", label, total, preamble, [(s, e), …])  — partial section
    """
    bins = []
    current = []
    cur_lines = 0
    for s, e, t, span in section_ranges:
        if span > target:
            if current:
                bins.append(current)
                current = []
                cur_lines = 0
            preamble = section_preamble(s, e)
            sec_tests = tests_in_range(s, e)
            chunks = []
            cur = []
            cur_l = 0
            for nd, tls, tle in sec_tests:
                tspan = tle - tls + 1
                if cur_l + tspan > target and cur:
                    chunks.append(cur)
                    cur = []
                    cur_l = 0
                cur.append((nd, tls, tle))
                cur_l += tspan
            if cur:
                chunks.append(cur)
            for ci, ct in enumerate(chunks):
                label = f"{t} (part {chr(ord('a') + ci)})"
                test_ranges = [(tls, tle) for nd, tls, tle in ct]
                total = sum(le - ls + 1 for ls, le in test_ranges)
                bins.append([("CHUNK", label, total, preamble, test_ranges)])
            continue
        if cur_lines + span > target and current:
            bins.append(current)
            current = []
            cur_lines = 0
        current.append(("SECTION", s, e, t, span))
        cur_lines += span
    if current:
        bins.append(current)
    return bins


def emit_bins(bins, prefix, out_dir, module_header,
              all_helpers_block, extract):
    """Write every bin as a sub-file under ``out_dir``.

    Returns a list of ``(path, line_count, bin_size)`` tuples for the
    caller to log/check. Also writes a tiny stub at
    ``{out_dir}/{prefix}.py`` so the original module name still
    resolves for any tooling that grepped for it.
    """
    os.makedirs(out_dir, exist_ok=True)
    generated = []
    for i, b in enumerate(bins):
        first = b[0]
        if first[0] == "CHUNK":
            base = safe_name(first[1])
            label_block = f"  - {first[1]}"
        else:
            base = safe_name(first[3])
            label_block = "\n".join(f"  - {x[3]}" for x in b)

        fname = f"{out_dir}/{prefix}_{i + 1:02d}_{base}.py"

        body = HEADER_TEMPLATE.format(
            orig=prefix,
            idx=i + 1,
            label_block=label_block,
            module_header=module_header,
            all_helpers_block=all_helpers_block,
        )

        body_parts = []
        for entry in b:
            if entry[0] == "SECTION":
                _, s, e, t, span = entry
                body_parts.append(extract(s, e))
            else:
                _, label, total, preamble, test_ranges = entry
                section_body = preamble
                if section_body and not section_body.endswith("\n"):
                    section_body += "\n"
                test_bodies = "\n\n".join(
                    extract(ls, le) for ls, le in test_ranges
                )
                section_body += "\n" + test_bodies
                body_parts.append(section_body)

        body += "\n\n".join(body_parts)
        if not body.endswith("\n"):
            body += "\n"

        with open(fname, "w", encoding="utf-8") as f:
            f.write(body)
        generated.append((fname, len(body.split("\n")), len(b)))

    stub = (
        f'"""Original {prefix}.py was split into themed sibling files.\n\n'
        f"See ``{prefix}_NN_<topic>.py``.\n"
        f'"""\n'
    )
    with open(f"{out_dir}/{prefix}.py", "w", encoding="utf-8") as f:
        f.write(stub)
    return generated
