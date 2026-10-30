"""The ``gitpulse`` command line interface."""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Sequence

from . import __version__, git, report
from . import repos as repos_mod
from .ui import Style, ellipsize, plural, supports_color

PROG = "gitpulse"

EPILOG = """\
examples:
  gitpulse                         every repo under the current directory
  gitpulse ~/code ~/work           several roots at once
  gitpulse --only attention        just the ones that want something from you
  gitpulse --stale 90d --only stale  branches nobody touched in a quarter
  gitpulse --verbose               include the last commit subject
  gitpulse --sort activity         which projects have gone quiet?
  gitpulse --json | jq '.totals'   for dashboards and cron jobs
  gitpulse --fail-on dirty         exit 1 if anything is uncommitted (great for CI)

exit codes:
  0  nothing to report (or nothing matched --fail-on)
  1  --fail-on matched, or no root could be scanned
  2  invalid usage
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description=(
            "One table for every git repository you own: what is dirty, what is "
            "unpushed, what has gone stale."
        ),
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "paths",
        nargs="*",
        metavar="PATH",
        help="directories to search for repositories (default: .)",
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=repos_mod.DEFAULT_DEPTH,
        metavar="N",
        help=f"how deep to look for repositories (default: {repos_mod.DEFAULT_DEPTH})",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=8,
        metavar="N",
        help="repositories inspected in parallel (default: 8)",
    )
    parser.add_argument(
        "--stale",
        type=report.parse_duration,
        default=repos_mod.DEFAULT_STALE,
        metavar="AGE",
        help="a branch is stale after AGE without commits (default: 30d)",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="NAME",
        help="skip directories with this name (repeatable)",
    )
    parser.add_argument(
        "--only",
        choices=report.ONLY,
        default=None,
        metavar="FILTER",
        help="show only: " + ", ".join(report.ONLY),
    )
    parser.add_argument(
        "--sort",
        choices=report.SORTS,
        default="attention",
        help="ordering of the table (default: attention)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="add the last commit subject")
    parser.add_argument(
        "--json", action="store_true", dest="as_json", help="machine readable output"
    )
    parser.add_argument(
        "--fail-on",
        choices=report.FAIL_ON,
        default="none",
        help="exit 1 when a repository matches this condition (default: none)",
    )
    parser.add_argument(
        "--color", choices=("auto", "always", "never"), default="auto", help="colourise output"
    )
    parser.add_argument("--version", action="version", version=f"{PROG} {__version__}")
    return parser


def _use_color(choice: str) -> bool:
    if choice == "always":
        return True
    if choice == "never":
        return False
    return supports_color(sys.stdout)


def _fails(result, fail_on: str) -> bool:
    if fail_on == "none":
        return False
    if fail_on == "attention":
        return bool(result.attention)
    if fail_on == "dirty":
        return bool(result.dirty)
    if fail_on == "unpushed":
        return bool(result.unpushed)
    if fail_on == "stale":
        return result.total_stale > 0
    return False


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(argv)

    style = Style(enabled=_use_color(args.color))
    roots = args.paths or ["."]

    if git.version() is None:
        print(f"{PROG}: git was not found on PATH", file=sys.stderr)
        return 2

    started = time.perf_counter()
    result = repos_mod.scan(
        roots,
        depth=max(0, args.depth),
        stale_after=args.stale,
        jobs=max(1, args.jobs),
        excludes=args.exclude,
    )
    elapsed = time.perf_counter() - started

    for missing in result.missing:
        print(f"{PROG}: not a directory: {missing}", file=sys.stderr)
    if not result.roots:
        return 1

    shown = report.sort_repos(report.filter_repos(result.repos, args.only), args.sort, result.now)
    labels = report.labels_for(shown, result.roots)

    if args.as_json:
        print(report.as_json(result, labels, elapsed))
        return 1 if _fails(result, args.fail_on) else 0

    lines = [report.header(result, elapsed, style, args.stale, shown=len(shown))]
    if not shown:
        lines.append("")
        if result.repos and args.only:
            lines.append(
                "  "
                + style.green(f"nothing matches --only {args.only}")
                + style.dim(f" ({plural(len(result.repos), 'repo')} scanned)")
            )
        else:
            lines.append("  " + style.dim(f"no git repository within {args.depth} levels of here"))
        print("\n".join(lines))
        return 1 if _fails(result, args.fail_on) else 0

    lines.append("")
    lines.append(
        report.render_table(
            shown,
            labels,
            style,
            now=result.now,
            verbose=args.verbose,
            stale=args.stale,
        )
    )
    lines.append("")
    lines.append("  " + report.summary(result, style, args.stale))
    for hint in report.hints(result, style, args.fail_on if _fails(result, args.fail_on) else None):
        lines.append("  " + hint)

    if args.only and not shown:
        lines.append("  " + style.dim(f"nothing matches --only {args.only}"))

    oldest = max(
        (repo for repo in shown if repo.age_seconds(result.now) is not None),
        key=lambda repo: repo.age_seconds(result.now) or 0.0,
        default=None,
    )
    if oldest and len(shown) > 1:
        age = oldest.age_seconds(result.now) or 0.0
        lines.append(
            "  "
            + style.dim(
                f"quietest: {ellipsize(oldest.name, 30)} "
                f"({plural(int(age // 86400), 'day')} without a commit)"
            )
        )

    print("\n".join(lines))
    return 1 if _fails(result, args.fail_on) else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
