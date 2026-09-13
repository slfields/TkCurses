"""Laying text out in cells: wrapping, alignment and measurement.

A label decides how big it needs to be from the text it holds, and where each
line sits from ``justify`` and ``anchor``. None of that needs a terminal, so it
is here rather than in the widget - it can be exercised directly, and the
awkward cases (a word longer than the line, a wrap width of zero, trailing
blank lines) are worth exercising.

Wrapping is by word, falling back to breaking mid-word only when a single word
cannot fit. That is what Tk does, and the alternative - refusing to break and
letting the word overflow - puts characters outside the widget, which in a
character grid means on top of a neighbour.
"""

from __future__ import annotations

__all__ = ["align_offset", "measure", "wrap", "wrap_spans"]

#: Where each justification puts a short line within the available width.
_JUSTIFY_FRACTIONS: dict[str, float] = {
    "left": 0.0,
    "center": 0.5,
    "right": 1.0,
}


def wrap(text: str, width: int = 0) -> list[str]:
    """Break ``text`` into display lines.

    Explicit newlines always break a line. ``width`` of zero or less means no
    wrapping at all, which is what a label without a ``wraplength`` does.

    An empty string is one empty line rather than no lines: a label holding
    nothing still occupies a row, as it does in Tk.
    """
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if width <= 0:
            lines.append(paragraph)
            continue
        lines.extend(_wrap_paragraph(paragraph, width))
    return lines or [""]


def _wrap_paragraph(paragraph: str, width: int) -> list[str]:
    """Wrap one newline-free run of text to ``width`` cells."""
    words = paragraph.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        for piece in _fit(word, width):
            if not current:
                current = piece
            elif len(current) + 1 + len(piece) <= width:
                current = f"{current} {piece}"
            else:
                lines.append(current)
                current = piece
    lines.append(current)
    return lines


def _fit(word: str, width: int) -> list[str]:
    """Split a word that cannot fit on a line of its own.

    Returned whole when it fits, so the common case allocates nothing.
    """
    if len(word) <= width:
        return [word]
    return [word[start : start + width] for start in range(0, len(word), width)]


def measure(lines: list[str]) -> tuple[int, int]:
    """The cells a block of text occupies, as ``(width, height)``."""
    return max((len(line) for line in lines), default=0), len(lines)


def align_offset(line_width: int, available: int, justify: str = "left") -> int:
    """Where a line starts within ``available`` cells.

    Never negative: a line wider than the space it is given starts at the left
    edge and is clipped by whoever draws it, rather than starting off-screen.

    Raises:
        ValueError: If ``justify`` is not one tkinter defines.
    """
    try:
        fraction = _JUSTIFY_FRACTIONS[justify.strip().lower()]
    except KeyError:
        raise ValueError(f"unknown justify: {justify!r}") from None
    return max(0, int((available - line_width) * fraction))


def wrap_spans(line: str, width: int, mode: str = "char") -> list[tuple[int, int]]:
    """Where one line breaks on screen, as ``(start, end)`` character offsets.

    Offsets rather than strings, because a Text has to turn a screen position
    back into a position in its buffer, and a list of wrapped strings cannot
    answer that - the breaks have thrown the offsets away. :func:`wrap` is
    still the right thing for a Label, which only ever needs to draw.

    ``mode`` is Tk's ``wrap`` option: ``none`` leaves the line whole and lets
    the widget scroll sideways, ``char`` breaks wherever the width runs out,
    and ``word`` breaks at the last space that fits, keeping that space at the
    end of the line it broke - which is what stops a wrapped paragraph
    starting every line with a space.

    Always at least one span, so an empty line still occupies a row.
    """
    if width <= 0 or mode == "none" or not line:
        return [(0, len(line))]
    spans: list[tuple[int, int]] = []
    start = 0
    while start < len(line):
        end = min(start + width, len(line))
        if mode == "word" and end < len(line):
            cut = line.rfind(" ", start, end + 1)
            if cut > start:
                end = cut + 1
        spans.append((start, end))
        start = end
    return spans
