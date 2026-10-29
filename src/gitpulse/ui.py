"""Small, dependency-free helpers for the terminal output."""

from __future__ import annotations

import os
import shutil
import sys
from typing import ClassVar


class Style:
    """ANSI styling that disappears when colour is disabled."""

    _CODES: ClassVar[dict[str, str]] = {
        "bold": "1",
        "dim": "2",
        "red": "31",
        "green": "32",
        "yellow": "33",
        "blue": "34",
        "magenta": "35",
        "cyan": "36",
        "grey": "90",
    }

    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled

    def paint(self, text: str, *styles: str) -> str:
        if not self.enabled or not text:
            return text
        codes = ";".join(self._CODES[s] for s in styles if s in self._CODES)
        if not codes:
            return text
        return f"\x1b[{codes}m{text}\x1b[0m"

    def bold(self, text: str) -> str:
        return self.paint(text, "bold")

    def dim(self, text: str) -> str:
        return self.paint(text, "dim")

    def green(self, text: str) -> str:
        return self.paint(text, "green")

    def yellow(self, text: str) -> str:
        return self.paint(text, "yellow")

    def red(self, text: str) -> str:
        return self.paint(text, "red")

    def cyan(self, text: str) -> str:
        return self.paint(text, "cyan")


def supports_color(stream=None) -> bool:
    stream = stream if stream is not None else sys.stdout
    if os.environ.get("FORCE_COLOR"):
        return True
    if "NO_COLOR" in os.environ:
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    return bool(getattr(stream, "isatty", lambda: False)())


def terminal_width(default: int = 110) -> int:
    try:
        return shutil.get_terminal_size((default, 24)).columns
    except OSError:  # pragma: no cover - unusual environments
        return default


def ellipsize(text: str, limit: int) -> str:
    """Shorten ``text``, keeping the informative tail for paths."""
    if limit <= 0 or len(text) <= limit:
        return text
    if limit <= 3:
        return text[:limit]
    return "…" + text[-(limit - 1) :]


def human_age(seconds: float | None) -> str:
    """Compact age: ``12m``, ``5h``, ``3d``, ``2mo``, ``1y``."""
    if seconds is None:
        return "-"
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h"
    days = hours // 24
    if days < 30:
        return f"{days}d"
    months = days // 30
    if months < 12:
        return f"{months}mo"
    return f"{days // 365}y"


def plural(count: int, singular: str, plural_form: str | None = None) -> str:
    if count == 1:
        return f"{count} {singular}"
    return f"{count} {plural_form or singular + 's'}"


def shorten_home(text: str, home: str | None = None) -> str:
    home = home if home is not None else os.path.expanduser("~")
    if not home or home == os.sep:
        return text
    home = home.rstrip(os.sep)
    if text == home:
        return "~"
    if text.startswith(home + os.sep):
        return "~" + text[len(home) :]
    return text


def render_table(
    headers: list[str],
    rows: list[list[str]],
    *,
    align: list[str] | None = None,
    indent: str = "  ",
    gap: str = "  ",
    styler=None,
    header_styler=None,
) -> str:
    """Align columns *before* styling, so ANSI escapes never break the layout."""
    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))
    align = align or ["left"] * len(headers)

    def pad(cell: str, index: int) -> str:
        if align[index] == "right":
            return cell.rjust(widths[index])
        if align[index] == "center":
            return cell.center(widths[index])
        return cell.ljust(widths[index])

    def line(cells: list[str], header: bool = False, row_index: int = 0) -> str:
        parts = []
        for index, cell in enumerate(cells):
            padded = pad(cell, index)
            if header and header_styler is not None:
                padded = header_styler(index, padded)
            elif not header and styler is not None:
                padded = styler(index, row_index, padded)
            parts.append(padded)
        return indent + gap.join(parts).rstrip()

    lines = [line(headers, header=True)]
    if rows:
        lines.append(indent + gap.join("-" * width for width in widths))
        for index, row in enumerate(rows):
            lines.append(line(row, row_index=index))
    return "\n".join(lines)


__all__ = [
    "Style",
    "ellipsize",
    "human_age",
    "plural",
    "render_table",
    "shorten_home",
    "supports_color",
    "terminal_width",
]
