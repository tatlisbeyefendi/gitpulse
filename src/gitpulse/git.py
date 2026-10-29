"""Thin, predictable wrapper around the ``git`` command line.

Everything here is read-only. If ``git`` is missing or a repository is broken,
the helpers report it instead of raising — a dashboard that dies because one
repository is corrupt is a useless dashboard.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

#: Environment that keeps git from prompting, paging or writing to the index.
_SAFE_ENV = {
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_PAGER": "cat",
    "GIT_OPTIONAL_LOCKS": "0",
    "LC_ALL": "C",
}


@dataclass(frozen=True)
class GitOutput:
    ok: bool
    stdout: str
    stderr: str = ""

    @property
    def lines(self) -> list[str]:
        return [line for line in self.stdout.splitlines() if line.strip()]


def run(repo: Path | str, *args: str, timeout: float = 20.0) -> GitOutput:
    """Run ``git <args>`` inside ``repo`` and never raise on failure."""
    environment = {**os.environ, **_SAFE_ENV}
    try:
        completed = subprocess.run(
            ["git", "-c", "core.pager=cat", "-c", "color.ui=false", *args],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=environment,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError) as excuse:
        return GitOutput(ok=False, stdout="", stderr=str(excuse))
    return GitOutput(
        ok=completed.returncode == 0,
        # only the right side: `git status --porcelain` lines start with a
        # meaningful space (" M file" means "modified, not staged").
        stdout=completed.stdout.rstrip(),
        stderr=completed.stderr.strip(),
    )


def version() -> str | None:
    """The installed git version, or ``None`` when git is not available."""
    try:
        completed = subprocess.run(
            ["git", "--version"], capture_output=True, text=True, check=False
        )
    except (OSError, subprocess.SubprocessError):  # pragma: no cover - no git
        return None
    return completed.stdout.strip() or None


def is_repository(path: Path | str) -> bool:
    """True when ``path`` is the top level of a work tree."""
    result = run(path, "rev-parse", "--is-inside-work-tree")
    return result.ok and result.stdout.strip() == "true"


def toplevel(path: Path | str) -> Path | None:
    """The work tree root that contains ``path``."""
    result = run(path, "rev-parse", "--show-toplevel")
    if not result.ok or not result.stdout.strip():
        return None
    return Path(result.stdout.strip().splitlines()[0])


__all__ = ["GitOutput", "is_repository", "run", "toplevel", "version"]
