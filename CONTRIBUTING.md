# Contributing to gitpulse

Thanks for helping out. This project has three rules it will not bend:

1. **Read-only.** No command in `gitpulse` may change a repository. If a feature
   needs `git fetch`, `checkout` or a write, it needs an explicit opt-in flag and
   a paragraph in the README explaining exactly what it touches.
2. **No dependencies.** Standard library only. This runs on developer machines
   and in cron jobs; a supply chain is a liability.
3. **No network.** The tool must work offline and on a plane.

## Getting set up

```console
$ git clone https://github.com/OWNER/gitpulse.git
$ cd gitpulse
$ python3 -m venv .venv && source .venv/bin/activate
$ make install
$ make test
$ make lint
```

Optional: `pre-commit install` to run the same checks on commit.

## The tests build real repositories

Every test creates actual git repositories in `tmp_path` through the helpers in
`tests/conftest.py` (`make_repo`, `make_remote`, `clone_of`). No mocking, no
fixtures on disk. If you add a check, add a test that creates the situation it
detects:

```python
def test_detects_a_diverged_branch(make_repo, make_remote, clone_of):
    repo = make_repo()
    bare = make_remote(repo)
    other = clone_of(bare)
    ...
```

Git identity in tests is throw-away (`tests/conftest.py` sets `GIT_CONFIG_GLOBAL`
to `/dev/null`), so nothing leaks into your own configuration.

## Adding a flag

1. `cli.py`: add the argument and wire it into `repos.scan(...)` or
   `report.filter_repos/sort_repos`.
2. `report.py`: the rendering, if it changes the table.
3. Tests: one for the flag working, one for the failure mode.
4. README (both languages) and a `CHANGELOG.md` entry.

## Adding a column

The table is built in `report.render_table`. Keep alignment intact by building a
plain rows matrix and styling it through the `styler` callback — styling is
applied *after* padding, so ANSI escapes never break the layout.

## Reporting bugs

Please include:

- `gitpulse --version`, your git version (`git --version`) and OS,
- the command you ran,
- the output of `gitpulse --json` for the affected repository (redact paths if
  you need to).

## Pull requests

- One topic per PR, `make lint` and `make test` green, changelog entry added.
- Commit messages in the imperative mood (`Add --fetch flag`), under 72 chars in
  the first line.
- Regenerate the screenshots with `make demo` if you changed the output; the
  images are produced from real repositories and a stale image is a lie.

## Code style

- `ruff format` (100 columns) and `ruff check`.
- Type hints everywhere, `from __future__ import annotations` at the top.
- `print` only in `cli.py` and `report.py`; the lower layers return data.
- Everything is immutable where practical: `RepoState` is a frozen dataclass so
  rendering cannot accidentally change what was measured.

## Code of conduct

Be decent. Harassment or dismissive behaviour is not welcome here.
