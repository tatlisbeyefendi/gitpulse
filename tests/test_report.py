"""Tests for formatting, ordering, filtering and the JSON view."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pytest

from gitpulse import report
from gitpulse.model import RepoState, ScanResult, StaleBranch
from gitpulse.ui import (
    Style,
    ellipsize,
    human_age,
    plural,
    render_table,
    shorten_home,
)

STYLE = Style(enabled=False)


def make(name: str, **kwargs) -> RepoState:
    return RepoState(path=Path("/tmp") / name, name=name, **kwargs)


# ---------------------------------------------------------------- ui helpers


@pytest.mark.parametrize(
    "seconds, expected",
    [
        (0, "0s"),
        (59, "59s"),
        (60, "1m"),
        (3600, "1h"),
        (86400, "1d"),
        (86400 * 45, "1mo"),
        (86400 * 400, "1y"),
        (None, "-"),
    ],
)
def test_human_age(seconds, expected):
    assert human_age(seconds) == expected


def test_plural():
    assert plural(1, "repo") == "1 repo"
    assert plural(2, "repo") == "2 repos"
    assert plural(2, "branch", "branches") == "2 branches"


def test_ellipsize_keeps_the_tail():
    assert ellipsize("short", 20) == "short"
    assert ellipsize("/a/very/long/path", 10) == "…long/path"


def test_shorten_home():
    assert shorten_home("/home/dev/code", home="/home/dev") == "~/code"
    assert shorten_home("/opt/x", home="/home/dev") == "/opt/x"


def test_render_table_aligns_after_padding():
    text = render_table(
        ["A", "B"],
        [["xx", "1"], ["y", "22"]],
        align=["left", "right"],
        styler=lambda column, _row, cell: f"<{cell}>" if column == 1 else cell,
    )
    lines = text.splitlines()
    assert "< 1>" in lines[2] or "<1>" in lines[2]
    assert lines[0].endswith("B")


def test_style_is_a_noop_when_disabled():
    assert STYLE.bold("x") == "x"
    assert Style(enabled=True).bold("x") == "\x1b[1mx\x1b[0m"


# ------------------------------------------------------------------ duration


@pytest.mark.parametrize(
    "text, expected",
    [
        ("30d", timedelta(days=30)),
        ("12h", timedelta(hours=12)),
        ("2w", timedelta(weeks=2)),
        ("90s", timedelta(seconds=90)),
        ("15m", timedelta(minutes=15)),
    ],
)
def test_parse_duration(text, expected):
    assert report.parse_duration(text) == expected


def test_parse_duration_rejects_junk():
    with pytest.raises(ValueError):
        report.parse_duration("soon")


# ------------------------------------------------------------------ ordering


@pytest.fixture
def sample() -> list[RepoState]:
    now = 1_000_000.0
    return [
        make("clean", branch="main", last_commit_at=now - 3600, has_upstream=True),
        make("dirty", branch="main", modified=2, last_commit_at=now - 86400 * 3),
        make("ahead", branch="main", ahead=2, has_upstream=True, last_commit_at=now - 7200),
        make("stale", branch="main", stale_branches=(StaleBranch("x", 86400 * 40),)),
    ]


def test_sort_by_attention_puts_problems_first(sample):
    names = [repo.name for repo in report.sort_repos(sample, "attention", 1_000_000.0)]
    assert names[0] == "dirty"
    assert names[-1] == "clean"


def test_sort_by_name(sample):
    assert [repo.name for repo in report.sort_repos(sample, "name", 0)] == [
        "ahead",
        "clean",
        "dirty",
        "stale",
    ]


def test_sort_by_activity(sample):
    # oldest first; "stale" has no last_commit_at at all, so it sorts first
    names = [repo.name for repo in report.sort_repos(sample, "activity", 0)]
    assert names == ["stale", "dirty", "ahead", "clean"]


def test_sort_by_changes(sample):
    assert report.sort_repos(sample, "changes", 0)[0].name == "dirty"


# ------------------------------------------------------------------ filters


def test_filters(sample):
    assert [repo.name for repo in report.filter_repos(sample, None)] == [
        "clean",
        "dirty",
        "ahead",
        "stale",
    ]
    assert [repo.name for repo in report.filter_repos(sample, "dirty")] == ["dirty"]
    assert [repo.name for repo in report.filter_repos(sample, "unpushed")] == ["ahead"]
    assert [repo.name for repo in report.filter_repos(sample, "stale")] == ["stale"]
    assert report.filter_repos(sample, "attention")


def test_filter_behind_and_detached():
    behind = make("b", behind=3, has_upstream=True)
    detached = make("d", detached=True, branch="HEAD")
    assert report.filter_repos([behind, detached], "behind") == [behind]
    assert report.filter_repos([behind, detached], "detached") == [detached]


# ------------------------------------------------------------------- labels


def test_labels_use_relative_paths(tmp_path):
    outer = make("acme-site")
    outer = RepoState(path=tmp_path / "clients" / "acme-site", name="acme-site")
    top = RepoState(path=tmp_path / "devdust", name="devdust")
    labels = report.labels_for([outer, top], [tmp_path])
    assert labels[top.path] == "devdust"
    assert labels[outer.path] == "clients/acme-site"


def test_labels_disambiguate_duplicate_names(tmp_path):
    first = RepoState(path=tmp_path / "a" / "site", name="site")
    second = RepoState(path=tmp_path / "b" / "site", name="site")
    labels = report.labels_for([first, second], [tmp_path])
    assert labels[first.path] != labels[second.path]


# ------------------------------------------------------------------ summary


def test_summary_when_everything_is_clean():
    result = ScanResult(
        roots=(Path("/tmp"),),
        repos=[make("clean", branch="main", has_upstream=True)],
        now=1.0,
    )
    assert "tidy" in report.summary(result, STYLE, timedelta(days=30))


def test_summary_mentions_problems():
    result = ScanResult(
        roots=(Path("/tmp"),),
        repos=[
            make("dirty", branch="main", modified=1),
            make("ahead", branch="main", ahead=1, has_upstream=True),
        ],
        now=1.0,
    )
    text = report.summary(result, STYLE, timedelta(days=30))
    assert "1 dirty repo" in text
    assert "1 unpushed repo" in text


def test_summary_of_empty_scan():
    assert "no git repositories" in report.summary(ScanResult(), STYLE, timedelta(days=30))


# --------------------------------------------------------------------- json


def test_json_is_valid_and_consistent(tmp_path):
    result = ScanResult(
        roots=(tmp_path,),
        repos=[
            make("dirty", branch="main", modified=1, untracked=2),
            make("stale", branch="main", stale_branches=(StaleBranch("x", 86400 * 40),)),
        ],
        scanned_dirs=9,
        now=1_000.0,
    )
    payload = json.loads(report.as_json(result, report.labels_for(result.repos, [tmp_path]), 0.25))
    assert payload["tool"] == "gitpulse"
    assert payload["totals"]["repos"] == 2
    assert payload["totals"]["dirty"] == 1
    assert payload["totals"]["stale_branches"] == 1
    dirt = payload["repos"][0]
    assert dirt["changes"] == 3
    assert dirt["flags"] == ["1 modified", "2 untracked", "no upstream"]
    assert payload["scanned_dirs"] == 9
