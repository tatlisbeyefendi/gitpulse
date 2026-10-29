"""Tests for the git wrapper."""

from __future__ import annotations

from pathlib import Path

from gitpulse import git

from .conftest import commit, write
from .conftest import git as run_git


def test_version_reports_git():
    version = git.version()
    assert version is not None
    assert version.startswith("git version")


def test_is_repository(tmp_path, make_repo):
    repo = make_repo()
    assert git.is_repository(repo) is True
    assert git.is_repository(tmp_path) is False


def test_toplevel_from_a_subdirectory(make_repo):
    repo = make_repo()
    nested = repo / "src" / "deep"
    nested.mkdir(parents=True)
    assert git.toplevel(nested) == repo.resolve()


def test_toplevel_outside_a_repository(tmp_path):
    assert git.toplevel(tmp_path) is None


def test_failure_does_not_raise(make_repo):
    result = git.run(make_repo(), "rev-parse", "--verify", "refs/heads/does-not-exist")
    assert result.ok is False
    assert result.stderr


def test_missing_binary_is_reported(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    result = git.run(tmp_path, "status")
    assert result.ok is False
    assert "No such file" in result.stderr or result.stderr


def test_porcelain_keeps_the_leading_space(make_repo):
    """Regression: `` M file`` means modified-unstaged; stripping hides that."""
    repo = make_repo()
    write(repo, "README.md", "changed\n")
    porcelain = git.run(repo, "status", "--porcelain").stdout
    assert porcelain.startswith(" M"), porcelain


def test_lines_helper_skips_blanks(make_repo):
    repo = make_repo()
    write(repo, "a.txt")
    write(repo, "b.txt")
    result = git.run(repo, "status", "--porcelain")
    assert len(result.lines) == 2
    assert all(line.strip() for line in result.lines)


def test_git_output_is_immutable():
    output = git.GitOutput(ok=True, stdout="a\nb")
    assert output.lines == ["a", "b"]
    try:
        output.ok = False  # type: ignore[misc]
    except Exception:
        pass
    else:  # pragma: no cover - dataclass is frozen
        raise AssertionError("GitOutput should be frozen")


def test_status_after_commit_is_clean(make_repo):
    repo = make_repo()
    assert git.run(repo, "status", "--porcelain").stdout == ""


def test_branch_name(tmp_path: Path):
    path = tmp_path / "named"
    path.mkdir()
    run_git(path, "init", "-q", "-b", "main")
    write(path, "f.txt")
    commit(path, "init")
    assert git.run(path, "rev-parse", "--abbrev-ref", "HEAD").stdout == "main"
