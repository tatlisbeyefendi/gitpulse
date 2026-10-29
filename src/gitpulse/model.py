"""The data model: one immutable snapshot per repository."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class StaleBranch:
    """A local branch that is not merged and has not moved in a while."""

    name: str
    age_seconds: float


@dataclass(frozen=True)
class RepoState:
    path: Path
    name: str
    branch: str | None = None
    detached: bool = False
    empty: bool = False
    staged: int = 0
    modified: int = 0
    untracked: int = 0
    ahead: int = 0
    behind: int = 0
    has_upstream: bool = False
    commits: int = 0
    last_commit_at: float | None = None
    last_message: str | None = None
    stale_branches: tuple[StaleBranch, ...] = ()
    merged_branches: int = 0
    local_branches: int = 0
    error: str | None = None

    # ------------------------------------------------------------- derived

    @property
    def changes(self) -> int:
        return self.staged + self.modified + self.untracked

    @property
    def dirty(self) -> bool:
        return self.changes > 0

    @property
    def unpushed(self) -> bool:
        return self.ahead > 0

    @property
    def needs_attention(self) -> bool:
        return self.dirty or self.unpushed or self.behind > 0 or self.error is not None

    @property
    def stale_count(self) -> int:
        return len(self.stale_branches)

    def age_seconds(self, now: float) -> float | None:
        if self.last_commit_at is None:
            return None
        return max(0.0, now - self.last_commit_at)

    def flags(self) -> list[str]:
        """Short labels for the FLAGS column, most urgent first."""
        labels: list[str] = []
        if self.error:
            labels.append("error")
        if self.staged:
            labels.append(f"{self.staged} staged")
        if self.modified:
            labels.append(f"{self.modified} modified")
        if self.untracked:
            labels.append(f"{self.untracked} untracked")
        if self.detached:
            labels.append("detached")
        if self.stale_count:
            labels.append(f"{self.stale_count} stale branch")
        if self.merged_branches:
            labels.append(f"{self.merged_branches} merged")
        if not self.has_upstream and not self.empty and not self.error:
            labels.append("no upstream")
        return labels

    @property
    def attention_score(self) -> int:
        """Higher means "look at this first"."""
        score = 0
        if self.error:
            score += 100
        if self.dirty:
            score += 10
        if self.unpushed:
            score += 5
        if self.behind:
            score += 4
        if self.detached:
            score += 3
        score += min(self.stale_count, 3)
        return score


@dataclass
class ScanResult:
    roots: tuple[Path, ...] = ()
    repos: list[RepoState] = field(default_factory=list)
    scanned_dirs: int = 0
    missing: list[str] = field(default_factory=list)
    now: float = 0.0

    @property
    def attention(self) -> list[RepoState]:
        return [repo for repo in self.repos if repo.needs_attention]

    @property
    def dirty(self) -> list[RepoState]:
        return [repo for repo in self.repos if repo.dirty]

    @property
    def unpushed(self) -> list[RepoState]:
        return [repo for repo in self.repos if repo.unpushed]

    @property
    def behind(self) -> list[RepoState]:
        return [repo for repo in self.repos if repo.behind]

    @property
    def total_stale(self) -> int:
        return sum(repo.stale_count for repo in self.repos)

    @property
    def total_merged(self) -> int:
        return sum(repo.merged_branches for repo in self.repos)


__all__ = ["RepoState", "ScanResult", "StaleBranch"]
