# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

_Nothing yet._

## [0.1.0] — 2026-10-30

The first release: one table for every repository you own.

### Added

- **Discovery.** Walks one or more roots (default: the current directory) and
  finds every git work tree, up to `--depth` levels. The walk stops at a
  repository, skips `node_modules`, `.venv`, `dist`, `target` and friends, and
  honours `--exclude`.
- **Per-repository snapshot**: branch (or `(detached)` / `(empty)`), staged,
  modified and untracked counts, ahead/behind against the upstream, last commit
  time and subject, local/merged/stale branches.
- **Attention ordering.** Problems first — errors, dirty trees, unpushed work,
  repositories behind their remote, stale branches — then everything else by
  recency.
- **Filters and sorting**: `--only attention|dirty|unpushed|behind|stale|detached`,
  `--sort attention|activity|name|changes`, and `--stale AGE` for the
  definition of "stale".
- **Parallel scanning** with `--jobs` (thread pool over subprocesses).
- **JSON output** (`--json`) with totals and a full per-repository record, for
  dashboards and cron jobs.
- **CI gate**: `--fail-on attention|dirty|unpushed|stale` exits `1` when
  something matches.
- **Colour** with `NO_COLOR` / `FORCE_COLOR` support and a `--color` switch.
- Documentation in English and Turkish, with demo images rendered from real
  repositories (`make demo`).
- Test suite covering the git wrapper, discovery, inspection, ordering,
  filters, JSON and the CLI — all against real repositories created in
  `tmp_path`, plus GitHub Actions CI on Python 3.11–3.14.

### Notes

- `gitpulse` is strictly read-only and makes no network requests; ahead/behind
  reflect your last `git fetch`.

[Unreleased]: https://github.com/tatlisbeyefendi/gitpulse/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/tatlisbeyefendi/gitpulse/releases/tag/v0.1.0
