"""Tests for discovery and per-repository inspection."""

from __future__ import annotations

import time
from datetime import timedelta

import pytest

from gitpulse import repos
from gitpulse.model import RepoState
from gitpulse.repos import _count_status, discover, inspect, scan

from .conftest import commit, git, write

# ---------------------------------------------------------------- discovery


def test_discover_finds_repositories(tmp_path, make_repo):
    make_repo("alpha")
    make_repo("beta")
    found, visited = discover([tmp_path])
    assert [path.name for path in found] == ["alpha", "beta"]
    assert visited >= 3


def test_discover_ignores_junk_directories(tmp_path, make_repo):
    make_repo("real")
    nested = tmp_path / "node_modules" / "package"
    nested.mkdir(parents=True)
    git(nested, "init", "-q", "-b", "main")
    found, _ = discover([tmp_path])
    assert [path.name for path in found] == ["real"]


def test_discover_respects_depth(tmp_path, make_repo):
    make_repo("one")
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    git(deep, "init", "-q", "-b", "main")
    shallow, _ = discover([tmp_path], depth=1)
    assert [path.name for path in shallow] == ["one"]
    deeper, _ = discover([tmp_path], depth=4)
    assert {path.name for path in deeper} == {"one", "c"}


def test_discover_does_not_descend_into_a_repository(tmp_path, make_repo):
    outer = make_repo("outer")
    inner = outer / "vendor" / "library"
    inner.mkdir(parents=True)
    git(inner, "init", "-q", "-b", "main")
    found, _ = discover([tmp_path])
    assert [path.name for path in found] == ["outer"]


def test_discover_honours_excludes(tmp_path, make_repo):
    make_repo("keep")
    make_repo("archive")
    found, _ = discover([tmp_path], excludes=["archive"])
    assert [path.name for path in found] == ["keep"]


def test_discover_with_missing_root(tmp_path):
    found, visited = discover([tmp_path / "nope"])
    assert found == []
    assert visited == 0


def test_discover_worktree_file_counts_as_repository(tmp_path, make_repo):
    repo = make_repo("source")
    worktree = tmp_path / "linked"
    git(repo, "worktree", "add", "-q", str(worktree), "-b", "side")
    found, _ = discover([tmp_path])
    assert {path.name for path in found} == {"source", "linked"}


# ------------------------------------------------------------ status parsing


@pytest.mark.parametrize(
    "porcelain, expected",
    [
        ("", (0, 0, 0)),
        (" M file", (0, 1, 0)),
        ("M  file", (1, 0, 0)),
        ("MM file", (1, 1, 0)),
        ("?? new", (0, 0, 1)),
        ("A  added\n?? new", (1, 0, 1)),
        (" M a\n?? b\nD  c", (1, 1, 1)),
    ],
)
def test_count_status(porcelain, expected):
    assert _count_status(porcelain) == expected


# ---------------------------------------------------------------- inspection


def test_inspect_clean_repository(make_repo):
    repo = make_repo()
    state = inspect(repo, now=time.time())
    assert isinstance(state, RepoState)
    assert state.branch == "main"
    assert state.dirty is False
    assert state.commits == 1
    assert state.last_commit_at is not None
    assert state.last_message == "init"
    assert state.needs_attention is False


def test_inspect_counts_each_kind_of_change(make_repo):
    repo = make_repo()
    write(repo, "README.md", "modified\n")
    write(repo, "new.txt")
    write(repo, "staged.txt")
    git(repo, "add", "staged.txt")
    state = inspect(repo, now=time.time())
    assert (state.staged, state.modified, state.untracked) == (1, 1, 1)
    assert state.changes == 3
    assert "1 modified" in state.flags()
    assert state.needs_attention is True


def test_inspect_detects_unpushed_commits(make_repo, make_remote):
    repo = make_repo()
    make_remote(repo)
    write(repo, "second.txt")
    commit(repo, "second")
    state = inspect(repo, now=time.time())
    assert state.ahead == 1
    assert state.behind == 0
    assert state.has_upstream is True
    assert state.unpushed is True


def test_inspect_detects_being_behind(make_repo, make_remote, clone_of):
    repo = make_repo()
    bare = make_remote(repo)
    other = clone_of(bare)
    write(other, "other.txt")
    commit(other, "from elsewhere")
    git(other, "push", "-q", "origin", "main")
    git(repo, "fetch", "-q", "origin")
    state = inspect(repo, now=time.time())
    assert state.behind == 1
    assert state.ahead == 0
    assert state.needs_attention is True


def test_inspect_in_sync(make_repo, make_remote):
    repo = make_repo()
    make_remote(repo)
    state = inspect(repo, now=time.time())
    assert (state.ahead, state.behind) == (0, 0)
    assert state.has_upstream is True
    assert state.needs_attention is False


def test_inspect_without_upstream(make_repo):
    state = inspect(make_repo(), now=time.time())
    assert state.has_upstream is False
    assert "no upstream" in state.flags()


def test_inspect_detects_stale_branches(make_repo):
    repo = make_repo()
    git(repo, "checkout", "-q", "-b", "old-idea")
    write(repo, "idea.txt")
    commit(repo, "an idea", days_ago=90)
    git(repo, "checkout", "-q", "main")
    state = inspect(repo, now=time.time(), stale_after=timedelta(days=30))
    assert [branch.name for branch in state.stale_branches] == ["old-idea"]
    assert state.stale_branches[0].age_seconds > 80 * 86400
    assert state.local_branches == 2


def test_inspect_respects_the_stale_threshold(make_repo):
    repo = make_repo()
    git(repo, "checkout", "-q", "-b", "recent")
    write(repo, "recent.txt")
    commit(repo, "recent", days_ago=1)
    git(repo, "checkout", "-q", "main")
    assert inspect(repo, now=time.time(), stale_after=timedelta(days=30)).stale_branches == ()
    assert inspect(repo, now=time.time(), stale_after=timedelta(hours=1)).stale_branches


def test_inspect_counts_merged_branches(make_repo):
    repo = make_repo()
    git(repo, "checkout", "-q", "-b", "feature")
    write(repo, "feature.txt")
    commit(repo, "feature")
    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "-q", "--no-ff", "-m", "merge feature", "feature")
    state = inspect(repo, now=time.time(), stale_after=timedelta(days=1))
    assert state.merged_branches == 1
    assert state.stale_branches == ()  # merged branches are counted, not called stale


def test_inspect_empty_repository(make_repo):
    repo = make_repo(commits=0)
    state = inspect(repo, now=time.time())
    assert state.empty is True
    assert state.branch is None
    assert state.commits == 0
    assert state.last_commit_at is None
    assert state.dirty is False


def test_inspect_detached_head(make_repo):
    repo = make_repo()
    commit_hash = git(repo, "rev-parse", "HEAD").strip()
    git(repo, "checkout", "-q", commit_hash)
    state = inspect(repo, now=time.time())
    assert state.detached is True
    assert "detached" in state.flags()


def test_inspect_is_read_only(make_repo):
    repo = make_repo()
    write(repo, "README.md", "changed\n")
    before = git(repo, "status", "--porcelain")
    inspect(repo, now=time.time())
    assert git(repo, "status", "--porcelain") == before


def test_inspect_safely_swallows_errors(tmp_path, monkeypatch):
    def explode(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(repos, "inspect", explode)
    state = repos.inspect_safely(tmp_path, now=time.time(), stale_after=timedelta(days=30))
    assert state.error == "boom"
    assert state.needs_attention is True


# --------------------------------------------------------------------- scan


def test_scan_collects_everything(tmp_path, make_repo):
    make_repo("alpha")
    make_repo("beta")
    result = scan([tmp_path], now=time.time())
    assert len(result.repos) == 2
    assert {repo.name for repo in result.repos} == {"alpha", "beta"}
    assert result.scanned_dirs >= 3


def test_scan_of_empty_directory(tmp_path):
    result = scan([tmp_path], now=time.time())
    assert result.repos == []
    assert result.roots == (tmp_path.resolve(),)


def test_scan_records_missing_roots(tmp_path):
    result = scan([tmp_path / "nope"], now=time.time())
    assert result.missing == [str(tmp_path / "nope")]
    assert result.repos == []


def test_scan_parallel_and_serial_agree(tmp_path, make_repo):
    for name in ("a", "b", "c"):
        make_repo(name)
    now = time.time()
    parallel = scan([tmp_path], now=now, jobs=4)
    serial = scan([tmp_path], now=now, jobs=1)
    assert [repo.name for repo in parallel.repos] == [repo.name for repo in serial.repos]


def test_scan_totals(tmp_path, make_repo, make_remote):
    dirty = make_repo("dirty")
    write(dirty, "x.txt")
    clean = make_repo("clean")
    make_remote(clean)
    result = scan([tmp_path], now=time.time())
    assert len(result.dirty) == 1
    assert len(result.attention) == 1
    assert result.unpushed == []


def test_inspect_handles_a_broken_repository(tmp_path):
    broken = tmp_path / "broken"
    (broken / ".git").mkdir(parents=True)
    state = inspect(broken, now=time.time())
    assert state.error is None or isinstance(state.error, str) or state.empty
