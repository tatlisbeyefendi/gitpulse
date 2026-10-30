#!/usr/bin/env python3
"""Build a believable multi-repository workspace for demos and screenshots.

Every repository here is a real git repository in a real state — dirty, ahead,
behind, stale, merged, empty — so the screenshot cannot show anything that the
tool does not actually detect.

    python scripts/make_demo_repos.py /tmp/gitpulse-demo --force
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

AUTHOR = {
    "GIT_AUTHOR_NAME": "Demo Dev",
    "GIT_AUTHOR_EMAIL": "dev@example.com",
    "GIT_COMMITTER_NAME": "Demo Dev",
    "GIT_COMMITTER_EMAIL": "dev@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
}


def git(repo: Path, *args: str, when: float | None = None) -> None:
    env = {**os.environ, **AUTHOR}
    if when is not None:
        stamp = f"@{int(when)} +0000"
        env["GIT_AUTHOR_DATE"] = stamp
        env["GIT_COMMITTER_DATE"] = stamp
    completed = subprocess.run(
        ["git", "-c", "init.defaultBranch=main", *args],
        cwd=str(repo),
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {repo}: {completed.stderr.strip()}")


def write(repo: Path, relative: str, text: str = "") -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text or f"# {relative}\n", encoding="utf-8")


def commit(repo: Path, message: str, *, days_ago: float = 0.0) -> None:
    git(repo, "add", "-A")
    stamp = time.time() - days_ago * 86400
    git(repo, "commit", "-q", "-m", message, when=stamp)


def init(repo: Path) -> Path:
    repo.mkdir(parents=True, exist_ok=True)
    git(repo, "init", "-q", "-b", "main")
    return repo


def with_remote(repo: Path, bare_root: Path) -> None:
    bare = bare_root / f"{repo.name}.git"
    bare.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True, capture_output=True
    )
    git(repo, "remote", "add", "origin", str(bare))
    git(repo, "push", "-q", "-u", "origin", "main")


def build(root: Path) -> Path:
    code = root / "code"
    remotes = root / "remotes"
    shutil.rmtree(code, ignore_errors=True)

    # ---------------------------------------------------------------- web-app
    web = init(code / "web-app")
    write(web, "README.md", "# web-app\n\nA dashboard.\n")
    write(web, "src/app.ts", "export const app = () => 1;\n")
    commit(web, "feat: scaffold the dashboard", days_ago=6)
    with_remote(web, remotes)
    write(web, "src/usage.ts", "export const usage = () => [];\n")
    commit(web, "feat: add the usage chart", days_ago=2)
    write(web, "src/empty.ts", "export const empty = () => true;\n")
    commit(web, "fix: handle empty datasets", days_ago=1)
    write(web, "src/app.ts", "export const app = () => 2;\n")
    write(web, "src/chart.ts", "export const chart = () => 1;\n")

    # ------------------------------------------------------------- api-server
    api = init(code / "api-server")
    write(api, "README.md", "# api-server\n\nJSON API.\n")
    write(api, "app/main.py", "def health():\n    return {'ok': True}\n")
    commit(api, "feat: health endpoint", days_ago=9)
    with_remote(api, remotes)
    with tempfile.TemporaryDirectory() as tmp:
        clone = Path(tmp) / "clone"
        subprocess.run(
            ["git", "clone", "-q", str(remotes / "api-server.git"), str(clone)], check=True
        )
        write(clone, "app/metrics.py", "def metrics():\n    return {}\n")
        commit(clone, "feat: metrics endpoint", days_ago=3)
        git(clone, "push", "-q", "origin", "main")
    git(api, "fetch", "-q", "origin")

    # ---------------------------------------------------------- design-tokens
    tokens = init(code / "design-tokens")
    write(tokens, "README.md", "# design-tokens\n\nCSS variables.\n")
    write(tokens, "tokens.json", "{}\n")
    commit(tokens, "feat: initial token set", days_ago=14)
    with_remote(tokens, remotes)

    # --------------------------------------------------------- clients/acme
    acme = init(code / "clients" / "acme-site")
    write(acme, "README.md", "# acme-site\n\nMarketing site.\n")
    write(acme, "index.html", "<h1>Acme</h1>\n")
    commit(acme, "feat: landing page", days_ago=4)
    with_remote(acme, remotes)

    # ------------------------------------------------------------ legacy-crm
    legacy = init(code / "legacy-crm")
    write(legacy, "README.md", "# legacy-crm\n\nAn old friend.\n")
    write(legacy, "src/crm.py", "print('crm')\n")
    commit(legacy, "chore: initial import", days_ago=212)
    with_remote(legacy, remotes)
    # a merged branch
    git(legacy, "checkout", "-q", "-b", "feature/reports")
    write(legacy, "src/reports.py", "print('reports')\n")
    commit(legacy, "feat: reports", days_ago=190)
    git(legacy, "checkout", "-q", "main")
    git(
        legacy,
        "merge",
        "-q",
        "--no-ff",
        "-m",
        "merge: reports",
        "feature/reports",
        when=time.time() - 189 * 86400,
    )
    # ... and one nobody ever merged
    git(legacy, "checkout", "-q", "-b", "experiment/rewrite")
    write(legacy, "src/rewrite.py", "print('rewrite')\n")
    commit(legacy, "wip: rewrite in progress", days_ago=151)
    git(legacy, "checkout", "-q", "main")

    # --------------------------------------------------------------- scratch
    init(code / "scratch")  # empty repository, no commits at all

    return code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="?", default="/tmp/gitpulse-demo")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    target = Path(args.target).expanduser()
    if target.exists() and args.force:
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    code = build(target.resolve())
    print(f"demo workspace ready at {code}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
