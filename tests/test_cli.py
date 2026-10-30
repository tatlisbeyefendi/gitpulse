"""End-to-end tests for the command line interface."""

from __future__ import annotations

import json

import pytest

from gitpulse import __version__
from gitpulse.cli import main

from .conftest import commit, git, write


def run(capsys, *argv):
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_basic_run(tmp_path, make_repo, capsys):
    make_repo("alpha")
    make_repo("beta")
    code, out, err = run(capsys, str(tmp_path), "--color", "never")
    assert code == 0
    assert "alpha" in out and "beta" in out
    assert "gitpulse" in out
    assert "clean" in out
    assert err == ""


def test_reports_dirty_repository(tmp_path, make_repo, capsys):
    repo = make_repo("dirty")
    write(repo, "README.md", "changed\n")
    code, out, _ = run(capsys, str(tmp_path), "--color", "never")
    assert code == 0
    assert "1 dirty repo" in out
    assert "1 modified" in out


def test_only_filter(tmp_path, make_repo, capsys):
    make_repo("clean")
    dirty = make_repo("dirty")
    write(dirty, "x.txt")
    _, out, _ = run(capsys, str(tmp_path), "--color", "never", "--only", "dirty")
    assert "dirty" in out
    assert "1 of 2 repos" in out


def test_only_with_no_matches(tmp_path, make_repo, capsys):
    make_repo("clean")
    code, out, _ = run(capsys, str(tmp_path), "--color", "never", "--only", "dirty")
    assert code == 0
    assert "nothing matches --only dirty" in out


def test_verbose_shows_the_last_commit(tmp_path, make_repo, capsys):
    repo = make_repo("project")
    write(repo, "next.txt")
    commit(repo, "feat: add the thing")
    _, out, _ = run(capsys, str(tmp_path), "--color", "never", "-v")
    assert "LAST COMMIT" in out
    assert "feat: add the thing" in out


def test_sort_by_name(tmp_path, make_repo, capsys):
    for name in ("zulu", "alpha"):
        make_repo(name)
    _, out, _ = run(capsys, str(tmp_path), "--color", "never", "--sort", "name")
    rows = [line for line in out.splitlines() if "alpha" in line or "zulu" in line]
    assert "alpha" in rows[0]
    assert "zulu" in rows[1]


def test_json_output(tmp_path, make_repo, capsys):
    make_repo("alpha")
    code, out, _ = run(capsys, str(tmp_path), "--json")
    assert code == 0
    payload = json.loads(out)
    assert payload["tool"] == "gitpulse"
    assert payload["version"] == __version__
    assert payload["totals"]["repos"] == 1
    assert payload["repos"][0]["name"] == "alpha"
    assert payload["roots"] == [str(tmp_path)]


def test_fail_on_dirty(tmp_path, make_repo, capsys):
    repo = make_repo("dirty")
    write(repo, "x.txt")
    code, _, _ = run(capsys, str(tmp_path), "--fail-on", "dirty", "--color", "never")
    assert code == 1


def test_fail_on_none_is_always_zero(tmp_path, make_repo, capsys):
    repo = make_repo("dirty")
    write(repo, "x.txt")
    code, _, _ = run(capsys, str(tmp_path), "--color", "never")
    assert code == 0


def test_fail_on_is_reported_in_the_output(tmp_path, make_repo, capsys):
    repo = make_repo("dirty")
    write(repo, "x.txt")
    _, out, _ = run(capsys, str(tmp_path), "--fail-on", "dirty", "--color", "never")
    assert "fail-on dirty" in out


def test_missing_path(tmp_path, capsys):
    code, _, err = run(capsys, str(tmp_path / "nope"), "--color", "never")
    assert code == 1
    assert "not a directory" in err


def test_directory_without_repositories(tmp_path, capsys):
    code, out, _ = run(capsys, str(tmp_path), "--color", "never")
    assert code == 0
    assert "no git repository" in out


def test_depth_zero_only_looks_here(tmp_path, make_repo, capsys):
    make_repo("nested")
    _, out, _ = run(capsys, str(tmp_path), "--color", "never", "--depth", "0")
    assert "no git repository" in out


def test_jobs_one_works(tmp_path, make_repo, capsys):
    make_repo("alpha")
    code, out, _ = run(capsys, str(tmp_path), "--color", "never", "--jobs", "1")
    assert code == 0
    assert "alpha" in out


def test_exclude(tmp_path, make_repo, capsys):
    make_repo("keep")
    make_repo("skipme")
    _, out, _ = run(capsys, str(tmp_path), "--color", "never", "--exclude", "skipme")
    assert "keep" in out
    assert "skipme" not in out


def test_stale_threshold(tmp_path, make_repo, capsys):
    repo = make_repo("project")
    git(repo, "checkout", "-q", "-b", "old")
    write(repo, "old.txt")
    commit(repo, "old work", days_ago=120)
    git(repo, "checkout", "-q", "main")
    _, out, _ = run(capsys, str(tmp_path), "--color", "never", "--stale", "30d")
    assert "1 stale branch" in out
    _, generous, _ = run(capsys, str(tmp_path), "--color", "never", "--stale", "365d")
    assert "stale branch" not in generous


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_invalid_filter_is_a_usage_error(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main([".", "--only", "whatever"])
    assert excinfo.value.code == 2


def test_git_missing(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("gitpulse.cli.git.version", lambda: None)
    code, _, err = run(capsys, str(tmp_path))
    assert code == 2
    assert "git was not found" in err


def test_quietest_hint(tmp_path, make_repo, capsys):
    make_repo("fresh")
    old = make_repo("sleepy")
    write(old, "old.txt")
    commit(old, "old commit", days_ago=40)
    _, out, _ = run(capsys, str(tmp_path), "--color", "never")
    assert "quietest" in out
    assert "sleepy" in out


def test_empty_repository_is_listed(tmp_path, make_repo, capsys):
    make_repo("empty", commits=0)
    _, out, _ = run(capsys, str(tmp_path), "--color", "never")
    assert "(empty)" in out
