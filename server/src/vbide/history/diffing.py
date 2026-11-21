"""Unified diff hunks for the review: only the changed lines, with `context` lines around them.

Each hunk is {old_start, old_count, new_start, new_count, lines: [{t, o, n, s}]}, where t is " ", "-"
or "+", o/n are old/new line numbers (null on the side the line isn't on) and s is the text.
"""

from __future__ import annotations

import difflib

MAX_DIFF_LINES = 60_000


def split_lines(text: str) -> list[str]:
    return text.splitlines()


def hunks(old: str, new: str, context: int = 3) -> tuple[list[dict], int, int]:
    """Returns (hunks, lines added, lines removed)."""
    a, b = split_lines(old), split_lines(new)
    if len(a) > MAX_DIFF_LINES or len(b) > MAX_DIFF_LINES:
        raise ValueError("too large to diff")
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    out: list[dict] = []
    added = removed = 0
    for group in sm.get_grouped_opcodes(max(0, context)):
        lines: list[dict] = []
        o0, n0 = group[0][1], group[0][3]
        for tag, i1, i2, j1, j2 in group:
            if tag == "equal":
                for k in range(i2 - i1):
                    lines.append({"t": " ", "o": i1 + k + 1, "n": j1 + k + 1, "s": a[i1 + k]})
                continue
            for k in range(i1, i2):
                lines.append({"t": "-", "o": k + 1, "n": None, "s": a[k]})
                removed += 1
            for k in range(j1, j2):
                lines.append({"t": "+", "o": None, "n": k + 1, "s": b[k]})
                added += 1
        o_end, n_end = group[-1][2], group[-1][4]
        out.append({"old_start": o0 + 1, "old_count": o_end - o0, "new_start": n0 + 1, "new_count": n_end - n0,
                    "lines": lines})
    return out, added, removed
