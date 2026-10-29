"""Fixtures that build real (tiny) git repositories in ``tmp_path``."""

from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

import pytest

IDENTITY = {
    "GIT_AUTHOR_NAME": "Test Dev",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test Dev",
    "GIT_COMMITTER_EMAIL": "test@example.com",
    # never read the developer's real config or hooks
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
    "GIT_TERMINAL_PROMPT": "0",
}


def git(repo: Path, *args: str, when: float | None = None, check: bool = True) -> str:
    """Run git in ``repo`` with a throw-away identity."""
    env = {**os.environ, **IDENTITY}
    if when is not None:
        stamp = f"@{int(when)} +0000"
        env["GIT_AUTHOR_DATE"] = stamp
        env["GIT_COMMITTER_DATE"] = stamp
    completed = subprocess.run(
        ["git", "-c", "init.defaultBranch=main", *args],
        cwd=str(repo),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and completed.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {completed.stderr}")
    return completed.stdout


def write(repo: Path, relative: str, text: str = "x\n") -> Path:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def commit(repo: Path, message: str = "change", *, days_ago: float = 0.0) -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message, when=time.time() - days_ago * 86400)


@pytest.fixture
def make_repo(tmp_path: Path) -> Callable[..., Path]:
    """Create a repository with one commit (``commits=0`` for an empty one)."""

    def factory(name: str = "repo", *, commits: int = 1) -> Path:
        path = tmp_path / name
        path.mkdir(parents=True, exist_ok=True)
        git(path, "init", "-q", "-b", "main")
        if commits:
            write(path, "README.md", f"# {name}\n")
            commit(path, "init")
        return path

    return factory


@pytest.fixture
def make_remote(tmp_path: Path) -> Callable[[Path], Path]:
    """Create a bare repository and push ``main`` to it."""

    def factory(repo: Path) -> Path:
        bare = tmp_path / "remotes" / f"{repo.name}.git"
        bare.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "init", "-q", "--bare", "-b", "main", str(bare)],
            check=True,
            capture_output=True,
        )
        git(repo, "remote", "add", "origin", str(bare))
        git(repo, "push", "-q", "-u", "origin", "HEAD")
        return bare

    return factory


@pytest.fixture
def clone_of(tmp_path: Path) -> Callable[[Path, str], Path]:
    """A second working copy of a bare remote, for ahead/behind scenarios."""

    def factory(bare: Path, name: str = "clone") -> Path:
        target = tmp_path / name
        subprocess.run(
            ["git", "clone", "-q", str(bare), str(target)], check=True, capture_output=True
        )
        return target

    return factory


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Keep git and gitpulse away from the real home directory."""
    home = tmp_path / "_home"
    home.mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
