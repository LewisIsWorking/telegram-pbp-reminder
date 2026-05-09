"""AST-walk helpers and small pure utilities for ``test_splitter``.

Lives separate from ``_splitter_pack.py`` so the section-detection
logic, the path-slug logic, and the AST-range helper can be reused
or exercised in isolation. Imported by both ``test_splitter.py``
(the entry point) and ``_splitter_pack.py`` (the bin-packer).
"""

import re


def find_sections(LINES):
    """Locate ``# ── ... ──`` / ``# ━━━`` / ``# ═══`` headers.

    Returns a list of ``(line_number, title)`` tuples in source order.
    Markers whose body is empty have their title pulled from the next
    comment line (the ``═══``-style headers usually span 2-3 lines).
    Consecutive duplicate-title markers within ~3 lines are deduped.
    """
    section_re = re.compile(r"^# [─━═]")
    sections = []
    for i, line in enumerate(LINES, 1):
        if not section_re.match(line):
            continue
        stripped = line.lstrip("#").strip()
        stripped = re.sub(r"^[─━═]+|[─━═]+$", "", stripped).strip()
        if not stripped:
            # Pure marker line — title is on next non-empty comment line
            j = i
            while j < len(LINES):
                nxt = LINES[j].strip()
                if nxt.startswith("#"):
                    title = nxt.lstrip("#").strip()
                    title = re.sub(r"^[─━═]+|[─━═]+$", "", title).strip()
                    if title:
                        sections.append((i, title))
                        break
                j += 1
        else:
            sections.append((i, stripped))
    # Dedupe consecutive same-title markers within ~3 lines
    deduped = []
    for ls, title in sections:
        skip = False
        for ds, dt in deduped[-2:]:
            if dt == title and ls - ds < 4:
                skip = True
                break
        if not skip:
            deduped.append((ls, title))
    return deduped


def safe_name(title):
    """Slugify a section title into a filename-safe stem.

    Drops everything after the first colon, em-dash, or open paren
    (those introduce sub-titles or qualifications), then replaces
    path/extension/space chars with underscore and strips anything
    outside ``[a-z0-9_]``. Returns ``"misc"`` if the result is empty.
    """
    s = title.split(":")[0].split("—")[0].split("(")[0].strip()
    s = s.replace("/", "_").replace(".py", "").replace(" ", "_")
    return re.sub(r"[^a-z0-9_]", "_", s.lower()) or "misc"


def full_range(node):
    """Return ``(first_line, last_line)`` for an AST function/class node.

    Includes any decorator lines as part of the range so the splitter
    extracts decorators alongside their target.
    """
    if hasattr(node, "decorator_list") and node.decorator_list:
        first = node.decorator_list[0].lineno
    else:
        first = node.lineno
    return first, node.end_lineno
