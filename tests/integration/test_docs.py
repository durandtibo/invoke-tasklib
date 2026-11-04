from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from invoke_tasklib.config import SCHEMA, json_schema

ROOT = Path(__file__).parents[2]
DOCS = ROOT / "docs" / "docs"
SRC = ROOT / "src" / "invoke_tasklib"
REFERENCE_DIRECTIVE = re.compile(r"^::: (\S+)", flags=re.MULTILINE)
ADMONITION = re.compile(r"!!! \w+")


def _broken_admonitions(text: str) -> list[int]:
    r"""Return the line numbers of the admonitions with an empty body.

    The body of an admonition must be indented by four spaces, otherwise
    MkDocs renders an empty box followed by a normal paragraph.
    """
    lines = text.splitlines()
    return [
        number
        for number, line in enumerate(lines, start=1)
        if ADMONITION.match(line) and not (number < len(lines) and lines[number].startswith("    "))
    ]


#################################################
#     Tests for the admonitions of the docs     #
#################################################


@pytest.mark.parametrize("path", sorted(DOCS.rglob("*.md")), ids=lambda p: p.name)
def test_admonitions_of_the_docs_have_an_indented_body(path: Path) -> None:
    assert _broken_admonitions(path.read_text()) == []


def test_docs_have_markdown_files() -> None:
    assert len(list(DOCS.rglob("*.md"))) > 0


#########################################
#     Tests for _broken_admonitions     #
#########################################


def test_broken_admonitions_accepts_an_indented_body() -> None:
    assert _broken_admonitions("!!! note\n    text\n") == []


def test_broken_admonitions_reports_a_body_at_column_zero() -> None:
    assert _broken_admonitions("intro\n\n!!! warning\ntext\n") == [3]


def test_broken_admonitions_reports_an_admonition_without_a_body() -> None:
    assert _broken_admonitions("!!! note") == [1]


def test_broken_admonitions_reports_a_blank_line_after_the_title() -> None:
    assert _broken_admonitions("!!! note\n\n    text\n") == [1]


def test_broken_admonitions_reports_every_broken_admonition() -> None:
    assert _broken_admonitions("!!! note\na\n\n!!! tip\n    b\n\n!!! warning\nc\n") == [1, 7]


def test_broken_admonitions_ignores_text_without_admonition() -> None:
    assert _broken_admonitions("just text\n") == []


##########################################
#     Tests for the reference pages      #
##########################################


def _documented_modules() -> set[str]:
    return {
        name
        for page in (DOCS / "refs").glob("*.md")
        for name in REFERENCE_DIRECTIVE.findall(page.read_text())
    }


def _public_modules() -> set[str]:
    modules = {
        f"invoke_tasklib.{path.stem}" for path in SRC.glob("*.py") if not path.stem.startswith("_")
    }
    packages = {f"invoke_tasklib.{path.parent.name}" for path in SRC.glob("*/__init__.py")}
    return {"invoke_tasklib"} | modules | packages


@pytest.mark.parametrize("module", sorted(_public_modules()))
def test_public_module_has_a_reference_page(module: str) -> None:
    assert module in _documented_modules()


@pytest.mark.parametrize("page", sorted((DOCS / "refs").glob("*.md")), ids=lambda p: p.name)
def test_reference_page_is_in_the_navigation(page: Path) -> None:
    assert f"refs/{page.name}" in (ROOT / "docs" / "mkdocs.yml").read_text()


def test_reference_directive_is_found_in_a_page() -> None:
    assert REFERENCE_DIRECTIVE.findall("::: invoke_tasklib.runner\n") == ["invoke_tasklib.runner"]


#######################################################
#     Tests for the config page and the JSON schema   #
#######################################################

CONFIG_KEY = re.compile(r"^\| `((?:package|paths|groups|test|types|check|fix)\.\w+)`", flags=re.MULTILINE)


def test_config_page_documents_every_key_of_the_schema() -> None:
    documented = set(CONFIG_KEY.findall((DOCS / "uguide" / "config.md").read_text()))
    assert documented == {f"{s}.{k}" for s, options in SCHEMA.items() for k in options}


def test_config_module_prints_the_json_schema() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "invoke_tasklib.config"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert json.loads(proc.stdout) == json_schema()


def test_config_module_fails_with_an_argument() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "invoke_tasklib.config", "--bad"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 2


def test_config_key_pattern_matches_a_table_row() -> None:
    assert CONFIG_KEY.findall("| `test.xdoctest`  | `true` |\n") == ["test.xdoctest"]


def test_published_json_schema_is_up_to_date() -> None:
    assert json.loads((DOCS / "schema.json").read_text()) == json_schema()
