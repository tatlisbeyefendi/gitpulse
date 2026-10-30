#!/usr/bin/env python3
"""Rebuild the README screenshot from the real CLI output.

    python scripts/render_demo.py

Builds a throw-away workspace of real repositories (scripts/make_demo_repos.py),
runs ``gitpulse`` against it and writes ``docs/demo.svg``. Nothing in the image
is hand-written, so it cannot drift away from the tool.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def main() -> int:
    home = Path(tempfile.gettempdir()) / "gitpulse-demo"
    env = dict(os.environ, PYTHONPATH=str(REPO / "src"), COLUMNS="112", HOME=str(home))
    subprocess.run(
        [PYTHON, str(REPO / "scripts" / "make_demo_repos.py"), str(home), "--force"],
        check=True,
        env=env,
        capture_output=True,
    )
    subprocess.run(
        [
            PYTHON,
            str(REPO / "scripts" / "render_demo_svg.py"),
            str(REPO / "docs" / "demo.svg"),
            "--title",
            "gitpulse — every repo at a glance",
            "--prompt",
            "gitpulse ~/code --verbose",
            "--",
            PYTHON,
            "-m",
            "gitpulse",
            str(home / "code"),
            "--verbose",
        ],
        check=True,
        env=env,
    )
    subprocess.run(
        [
            PYTHON,
            str(REPO / "scripts" / "render_demo_svg.py"),
            str(REPO / "docs" / "demo-only.svg"),
            "--title",
            "gitpulse --only attention",
            "--prompt",
            "gitpulse ~/code --only attention",
            "--",
            PYTHON,
            "-m",
            "gitpulse",
            str(home / "code"),
            "--only",
            "attention",
        ],
        check=True,
        env=env,
    )
    print("demo images regenerated in docs/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
