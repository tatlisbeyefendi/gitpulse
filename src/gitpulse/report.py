"""Rendering the overview: the table, the summary and the JSON view."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from datetime import timedelta
from pathlib import Path

from . import __version__
from .model import RepoState, ScanResult
from .ui import Style, ellipsize, human_age, plural, shorten_home, terminal_width
from .ui import render_table as _table

SORTS = ("attention", "activity", "name", "changes")
ONLY = ("attention", "dirty", "unpushed", "behind", "stale", "detached")
FAIL_ON = ("none", "attention", "dirty", "unpushed", "stale")

_DURATION_RE = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*([smhdw])\s*$", re.IGNORECASE)
_DURATION_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}


def parse_duration(text: str) -> timedelta:
    """Parse ``30d`` / ``12h`` / ``2w`` into a timedelta."""
    match = _DURATION_RE.match(text)
    if not match:
        raise ValueError(f"cannot parse duration: {text!r} (try 12h, 7d, 2w)")
    number, unit = match.group(1).replace(",", "."), match.group(2).lower()
    return timedelta(seconds=float(number) * _DURATION_UNITS[unit])


# ------------------------------------------------------------------ ordering


def sort_repos(repos: Sequence[RepoState], order: str, now: float) -> list[RepoState]:
    if order == "activity":
        return sorted(repos, key=lambda repo: (repo.last_commit_at or 0.0, repo.name))
    if order == "name":
        return sorted(repos, key=lambda repo: repo.name.lower())
    if order == "changes":
        return sorted(repos, key=lambda repo: (-repo.changes, repo.name.lower()))
    return sorted(
        repos,
        key=lambda repo: (-repo.attention_score, -(repo.last_commit_at or 0.0), repo.name.lower()),
    )


def filter_repos(repos: Sequence[RepoState], only: str | None) -> list[RepoState]:
    if not only:
        return list(repos)
    if only == "attention":
        return [repo for repo in repos if repo.needs_attention]
    if only == "dirty":
        return [repo for repo in repos if repo.dirty]
    if only == "unpushed":
        return [repo for repo in repos if repo.unpushed]
    if only == "behind":
        return [repo for repo in repos if repo.behind]
    if only == "stale":
        return [repo for repo in repos if repo.stale_count]
    if only == "detached":
        return [repo for repo in repos if repo.detached]
    return list(repos)


# ------------------------------------------------------------------- labels


def labels_for(repos: Sequence[RepoState], roots: Sequence[Path]) -> dict[Path, str]:
    """Short, unambiguous labels: ``devdust`` or ``clients/api``."""
    labels: dict[Path, str] = {}
    for repo in repos:
        relative = None
        for root in roots:
            try:
                relative = repo.path.relative_to(root)
                break
            except ValueError:
                continue
        if relative is None or relative == Path("."):
            labels[repo.path] = repo.name
        else:
            labels[repo.path] = relative.as_posix()
    counts: dict[str, int] = {}
    for label in labels.values():
        counts[label] = counts.get(label, 0) + 1
    if any(count > 1 for count in counts.values()):
        for repo in repos:
            if counts[labels[repo.path]] > 1:
                labels[repo.path] = f"{labels[repo.path]} ({shorten_home(str(repo.path))})"
    return labels


def _sync_cell(repo: RepoState) -> str:
    if repo.empty:
        return "-"
    parts = []
    if repo.ahead:
        parts.append(f"↑{repo.ahead}")
    if repo.behind:
        parts.append(f"↓{repo.behind}")
    if parts:
        return " ".join(parts)
    return "=" if repo.has_upstream else "no up"


def _change_cell(repo: RepoState) -> str:
    if repo.empty:
        return "-"
    if not repo.dirty:
        return "clean"
    return str(repo.changes)


def _branch_cell(repo: RepoState) -> str:
    if repo.empty:
        return "(empty)"
    if repo.detached:
        return "(detached)"
    return repo.branch or "?"


# ------------------------------------------------------------------- blocks


def header(
    result: ScanResult, elapsed: float, style: Style, stale: timedelta, shown: int | None = None
) -> str:
    title = f"{style.bold('gitpulse')} {style.dim(__version__)}"
    total = plural(len(result.repos), "repo")
    where = total if shown is None or shown == len(result.repos) else f"{shown} of {total}"
    roots = ", ".join(shorten_home(str(root)) for root in result.roots) or "-"
    bits = [
        where,
        style.dim(f"under {ellipsize(roots, 48)}"),
        style.dim(f"{result.scanned_dirs} dirs"),
        style.dim(f"{elapsed:.2f}s"),
    ]
    return f"{title} · " + " · ".join(bits)


def render_table(
    repos: Sequence[RepoState],
    labels: dict[Path, str],
    style: Style,
    *,
    now: float,
    verbose: bool,
    stale: timedelta,
) -> str:
    budget = max(18, min(34, terminal_width() - 74))
    headers = ["REPO", "BRANCH"]
    if verbose:
        headers.append("LAST COMMIT")
    headers += ["CHANGES", "SYNC", "LAST", "FLAGS"]
    rows: list[list[str]] = []
    for repo in repos:
        row = [ellipsize(labels[repo.path], budget), ellipsize(_branch_cell(repo), 22)]
        if verbose:
            row.append(ellipsize(repo.last_message or "-", 40))
        options = f"{_change_cell(repo)}\0{repo.dirty}"
        row += [
            options,
            _sync_cell(repo),
            human_age(repo.age_seconds(now)),
            " · ".join(repo.flags()) or "✓",
        ]
        rows.append(row)

    def strip(cell: str) -> str:
        return cell.split("\0")[0]

    plain_rows = [[strip(cell) for cell in row] for row in rows]

    def styler(column: int, row_index: int, cell: str) -> str:
        repo = repos[row_index]
        name = headers[column]
        if name == "REPO":
            return style.paint(cell, "bold") if repo.needs_attention else cell
        if name == "BRANCH":
            return style.paint(cell, "cyan")
        if name == "CHANGES":
            return style.dim(cell) if not repo.dirty else style.paint(cell, "yellow")
        if name == "SYNC":
            return style.paint(cell, "yellow") if repo.ahead or repo.behind else style.dim(cell)
        if name == "LAST":
            return style.dim(cell)
        if name == "FLAGS":
            if repo.error:
                return style.red(cell)
            return style.paint(cell, "green") if not repo.flags() else style.dim(cell)
        return cell

    return _table(
        headers,
        plain_rows,
        align=["left", "left"]
        + (["left"] if verbose else [])
        + ["right", "right", "right", "left"],
        styler=styler,
        header_styler=lambda _column, cell: style.dim(cell),
    )


def summary(result: ScanResult, style: Style, stale: timedelta) -> str:
    if not result.repos:
        return style.dim("no git repositories found here")

    bits = []
    if result.dirty:
        bits.append(style.yellow(plural(len(result.dirty), "dirty repo")))
    if result.unpushed:
        bits.append(style.yellow(plural(len(result.unpushed), "unpushed repo")))
    behind = result.behind
    if behind:
        bits.append(style.yellow(plural(len(behind), "repo behind")))
    if result.total_stale:
        days = int(stale.total_seconds() // 86400)
        bits.append(
            style.dim(f"{plural(result.total_stale, 'stale branch', 'stale branches')} (>{days}d)")
        )
    if result.total_merged:
        bits.append(style.dim(f"{plural(result.total_merged, 'merged branch', 'merged branches')}"))

    local_only = [repo for repo in result.repos if not repo.has_upstream and not repo.empty]
    tail = ""
    if local_only:
        tail = " · " + style.dim(plural(len(local_only), "local-only repo"))

    if not bits:
        return style.green("everything is committed, pushed and tidy ✓") + tail
    return " · ".join(bits) + tail


def hints(result: ScanResult, style: Style, failed_filter: str | None) -> list[str]:
    lines: list[str] = []
    for repo in result.repos:
        if repo.error:
            lines.append(style.red(f"! {repo.name}: {repo.error}"))
    if failed_filter:
        lines.append(style.red(f"✗ fail-on {failed_filter}: at least one repository matches"))
    return lines


# --------------------------------------------------------------------- json


def as_json(result: ScanResult, labels: dict[Path, str], elapsed: float) -> str:
    payload = {
        "tool": "gitpulse",
        "version": __version__,
        "roots": [str(root) for root in result.roots],
        "missing": result.missing,
        "scanned_dirs": result.scanned_dirs,
        "elapsed_seconds": round(elapsed, 3),
        "totals": {
            "repos": len(result.repos),
            "dirty": len(result.dirty),
            "unpushed": len(result.unpushed),
            "behind": len(result.behind),
            "stale_branches": result.total_stale,
            "merged_branches": result.total_merged,
            "needs_attention": len(result.attention),
        },
        "repos": [
            {
                "name": repo.name,
                "label": labels[repo.path],
                "path": str(repo.path),
                "branch": repo.branch,
                "detached": repo.detached,
                "empty": repo.empty,
                "staged": repo.staged,
                "modified": repo.modified,
                "untracked": repo.untracked,
                "changes": repo.changes,
                "dirty": repo.dirty,
                "ahead": repo.ahead,
                "behind": repo.behind,
                "has_upstream": repo.has_upstream,
                "commits": repo.commits,
                "last_commit_at": repo.last_commit_at,
                "last_message": repo.last_message,
                "age_seconds": repo.age_seconds(result.now),
                "stale_branches": [
                    {"name": branch.name, "age_seconds": round(branch.age_seconds, 1)}
                    for branch in repo.stale_branches
                ],
                "merged_branches": repo.merged_branches,
                "local_branches": repo.local_branches,
                "flags": repo.flags(),
                "needs_attention": repo.needs_attention,
                "error": repo.error,
            }
            for repo in result.repos
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


__all__ = [
    "FAIL_ON",
    "ONLY",
    "SORTS",
    "as_json",
    "filter_repos",
    "header",
    "hints",
    "labels_for",
    "parse_duration",
    "render_table",
    "sort_repos",
    "summary",
]
