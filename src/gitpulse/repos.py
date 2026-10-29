"""Finding repositories and reading their state — in parallel."""

from __future__ import annotations

import time
from collections.abc import Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

from . import git
from .model import RepoState, ScanResult, StaleBranch

#: Directories that never contain a repository you care about (and are huge).
SKIP_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        ".venv",
        "venv",
        "env",
        "__pycache__",
        ".tox",
        ".nox",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        "dist",
        "build",
        "target",
        ".next",
        ".nuxt",
        ".cache",
        ".gradle",
        "vendor",
        "Pods",
        "site-packages",
    }
)

DEFAULT_DEPTH = 4
DEFAULT_STALE = timedelta(days=30)


def discover(
    roots: Iterable[Path | str],
    *,
    depth: int = DEFAULT_DEPTH,
    excludes: Sequence[str] = (),
) -> tuple[list[Path], int]:
    """Return every git work tree under ``roots`` plus the number of dirs visited.

    A directory containing ``.git`` is a repository: it is collected and *not*
    descended into, so nested test repositories inside a project cannot turn one
    entry into twenty.
    """
    excluded = {name for name in excludes if name}
    found: list[Path] = []
    visited = 0
    seen: set[Path] = set()

    for raw in roots:
        root = Path(raw).expanduser()
        try:
            root = root.resolve()
        except OSError:  # pragma: no cover - broken symlink
            continue
        if not root.is_dir():
            continue
        stack: list[tuple[Path, int]] = [(root, 0)]
        while stack:
            directory, level = stack.pop()
            if directory in seen:
                continue
            seen.add(directory)
            visited += 1
            if (directory / ".git").exists():
                found.append(directory)
                continue
            if level >= depth:
                continue
            try:
                children = sorted(
                    (child for child in directory.iterdir() if child.is_dir()),
                    key=lambda path: path.name,
                )
            except OSError:
                continue
            for child in children:
                if child.name in SKIP_DIRS or child.name in excluded:
                    continue
                stack.append((child, level + 1))
    return sorted(found), visited


def _count_status(porcelain: str) -> tuple[int, int, int]:
    """``(staged, modified, untracked)`` from ``git status --porcelain``."""
    staged = modified = untracked = 0
    for line in porcelain.splitlines():
        if len(line) < 2:
            continue
        index_state, worktree_state = line[0], line[1]
        if index_state == "?" and worktree_state == "?":
            untracked += 1
            continue
        if index_state not in (" ", "?"):
            staged += 1
        if worktree_state not in (" ", "?"):
            modified += 1
    return staged, modified, untracked


def inspect(path: Path, *, now: float, stale_after: timedelta = DEFAULT_STALE) -> RepoState:
    """Build a snapshot of one repository. Never raises for a broken repo."""
    path = Path(path)
    head = git.run(path, "rev-parse", "--abbrev-ref", "HEAD")
    empty = not head.ok or not head.stdout.strip()
    branch = None if empty else head.stdout.strip()
    detached = branch == "HEAD"

    staged, modified, untracked = _count_status(git.run(path, "status", "--porcelain").stdout)

    commits = 0
    counted = git.run(path, "rev-list", "--count", "HEAD")
    if counted.ok and counted.stdout.isdigit():
        commits = int(counted.stdout)

    upstream = git.run(path, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    has_upstream = upstream.ok and bool(upstream.stdout.strip())
    ahead = behind = 0
    if has_upstream:
        divergence = git.run(path, "rev-list", "--left-right", "--count", "@{upstream}...HEAD")
        if divergence.ok:
            parts = divergence.stdout.replace("\t", " ").split()
            if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                behind, ahead = int(parts[0]), int(parts[1])

    last_commit_at = None
    last_message = None
    log = git.run(path, "log", "-1", "--format=%ct%x00%s")
    if log.ok and log.stdout:
        timestamp, _, subject = log.stdout.partition("\x00")
        if timestamp.strip().isdigit():
            last_commit_at = float(timestamp.strip())
        last_message = subject.strip() or None

    merged_names: set[str] = set()
    stale: list[StaleBranch] = []
    local_branches = 0
    if not empty:
        merged_names = set(
            git.run(
                path, "for-each-ref", "--merged=HEAD", "--format=%(refname:short)", "refs/heads"
            ).lines
        )
        refs = git.run(
            path,
            "for-each-ref",
            "--sort=-committerdate",
            "--format=%(refname:short)%00%(committerdate:unix)",
            "refs/heads",
        )
        for line in refs.lines:
            name, _, stamp = line.partition("\x00")
            name = name.strip()
            if not name:
                continue
            local_branches += 1
            if name in merged_names:
                continue
            try:
                committed_at = float(stamp)
            except ValueError:
                continue
            age = now - committed_at
            if age >= stale_after.total_seconds():
                stale.append(StaleBranch(name=name, age_seconds=age))

    merged_branches = len(merged_names - ({branch} if branch else set()))

    return RepoState(
        path=path,
        name=path.name,
        branch=branch,
        detached=detached,
        empty=empty,
        staged=staged,
        modified=modified,
        untracked=untracked,
        ahead=ahead,
        behind=behind,
        has_upstream=has_upstream,
        commits=commits,
        last_commit_at=last_commit_at,
        last_message=last_message,
        stale_branches=tuple(sorted(stale, key=lambda item: -item.age_seconds)),
        merged_branches=merged_branches,
        local_branches=local_branches,
    )


def inspect_safely(path: Path, *, now: float, stale_after: timedelta) -> RepoState:
    try:
        return inspect(path, now=now, stale_after=stale_after)
    except Exception as exc:
        return RepoState(path=Path(path), name=Path(path).name, error=str(exc))


def scan(
    roots: Iterable[Path | str],
    *,
    depth: int = DEFAULT_DEPTH,
    stale_after: timedelta = DEFAULT_STALE,
    jobs: int = 8,
    excludes: Sequence[str] = (),
    now: float | None = None,
) -> ScanResult:
    """Discover and inspect every repository under ``roots``."""
    now = time.time() if now is None else now
    root_paths: list[Path] = []
    missing: list[str] = []
    for raw in roots:
        path = Path(raw).expanduser()
        if path.is_dir():
            root_paths.append(path.resolve())
        else:
            missing.append(str(raw))
    if not root_paths:
        return ScanResult(roots=(), missing=missing, now=now)

    found, visited = discover(root_paths, depth=depth, excludes=excludes)
    if not found:
        return ScanResult(roots=tuple(root_paths), scanned_dirs=visited, missing=missing, now=now)

    workers = max(1, min(jobs, len(found)))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="gitpulse") as pool:
        states = list(
            pool.map(
                lambda path: inspect_safely(path, now=now, stale_after=stale_after),
                found,
            )
        )
    return ScanResult(
        roots=tuple(root_paths),
        repos=states,
        scanned_dirs=visited,
        missing=missing,
        now=now,
    )


__all__ = [
    "DEFAULT_DEPTH",
    "DEFAULT_STALE",
    "SKIP_DIRS",
    "discover",
    "inspect",
    "inspect_safely",
    "scan",
]
