"""Keep the documentation honest: links resolve, screenshots are valid."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
DOCS = ["README.md", "README.tr.md", "CONTRIBUTING.md", "CHANGELOG.md"]


@pytest.mark.parametrize("document", DOCS)
def test_document_exists(document):
    assert (REPO / document).is_file()


@pytest.mark.parametrize("document", DOCS)
def test_relative_links_resolve(document):
    text = (REPO / document).read_text(encoding="utf-8")
    broken = []
    for target in LINK_RE.findall(text):
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        if not (REPO / target.split("#")[0].strip()).exists():
            broken.append(target)
    assert broken == [], f"broken links in {document}: {broken}"


@pytest.mark.parametrize("image", ["docs/demo.svg", "docs/demo-only.svg"])
def test_demo_svg_is_valid_xml(image):
    root = ET.parse(REPO / image).getroot()
    assert root.tag.endswith("svg")
    assert root.get("width") and root.get("height")
    assert len([element for element in root.iter() if element.tag.endswith("circle")]) == 3


def test_pyproject_and_package_versions_agree():
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"', pyproject, re.M)
    assert match is not None
    from gitpulse import __version__

    assert match.group(1) == __version__


def test_readme_documents_every_flag():
    from gitpulse.cli import build_parser

    readme = (REPO / "README.md").read_text(encoding="utf-8")
    missing = []
    for action in build_parser()._actions:
        for flag in action.option_strings:
            if flag.startswith("--") and flag not in ("--help",) and flag not in readme:
                missing.append(flag)
    assert missing == [], f"flags missing from the README: {missing}"
