from __future__ import annotations

import sys
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
from invoke.exceptions import Exit
from invoke.runners import Result

from invoke_tasklib import imports
from tests.helpers import commands, make_context, run_kwargs

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    _Maker = Callable[[str, dict[str, str]], None]


@pytest.fixture(autouse=True)
def _fixed_python(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "executable", "/venv/bin/python")


_WORKER_CMD = "/venv/bin/python -m invoke_tasklib._discover --import-each mypkg"


####################################
#     Tests for check_isolated     #
####################################


def test_check_isolated_runs_the_worker_once() -> None:
    c = make_context(
        tasklib_config={"package": {"name": "mypkg"}},
        run={_WORKER_CMD: Result(stdout="4\n")},
    )
    imports.check_isolated(c)
    assert commands(c) == [_WORKER_CMD]


def test_check_isolated_uses_the_import_name() -> None:
    cmd = "/venv/bin/python -m invoke_tasklib._discover --import-each my_pkg"
    c = make_context(
        tasklib_config={"package": {"name": "my-pkg"}},
        run={cmd: Result(stdout="1\n")},
    )
    imports.check_isolated(c)
    assert commands(c) == [cmd]


def test_check_isolated_uses_the_configured_import_name() -> None:
    cmd = "/venv/bin/python -m invoke_tasklib._discover --import-each other"
    c = make_context(
        tasklib_config={"package": {"name": "my-pkg", "import_name": "other"}},
        run={cmd: Result(stdout="1\n")},
    )
    imports.check_isolated(c)
    assert commands(c) == [cmd]


def test_check_isolated_reports_progress(capsys: pytest.CaptureFixture[str]) -> None:
    c = make_context(
        tasklib_config={"package": {"name": "mypkg"}},
        run={_WORKER_CMD: Result(stdout="3\n")},
    )
    imports.check_isolated(c)
    assert capsys.readouterr().out == (
        "🔍 Importing each module of mypkg in its own interpreter...\n"
        "✅ All 3 module(s) imported on their own\n"
    )


##################################
#     Tests for check_cycles     #
##################################


@pytest.fixture
def make_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _Maker:
    def make(name: str, files: dict[str, str]) -> None:
        for rel, content in files.items():
            path = tmp_path / name / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        monkeypatch.syspath_prepend(str(tmp_path))

    return make


def test_check_cycles_passes_without_cycle(
    make_package: _Maker, capsys: pytest.CaptureFixture[str]
) -> None:
    make_package("cyc_ok", {"__init__.py": "", "a.py": "from cyc_ok import b\n", "b.py": ""})
    imports.check_cycles(make_context({"package": {"name": "cyc_ok"}}))
    assert capsys.readouterr().out == (
        "🔍 Building the import graph of cyc_ok...\n✅ No import cycle in 3 module(s)\n"
    )


def test_check_cycles_runs_no_command(make_package: _Maker) -> None:
    make_package("cyc_cmd", {"__init__.py": ""})
    c = make_context({"package": {"name": "cyc_cmd"}})
    imports.check_cycles(c)
    assert commands(c) == []


def test_check_cycles_reports_the_cycle_path(make_package: _Maker) -> None:
    make_package(
        "cyc_bad",
        {"__init__.py": "", "a.py": "from cyc_bad import b\n", "b.py": "from cyc_bad import a\n"},
    )
    with pytest.raises(
        Exit, match=r"Found 1 import cycle\(s\) in cyc_bad:\n  cyc_bad.a -> cyc_bad.b -> cyc_bad.a"
    ):
        imports.check_cycles(make_context({"package": {"name": "cyc_bad"}}))


def test_check_cycles_exits_with_code_1(make_package: _Maker) -> None:
    make_package(
        "cyc_code",
        {"a.py": "import cyc_code.b\n", "b.py": "import cyc_code.a\n", "__init__.py": ""},
    )
    with pytest.raises(Exit, match=r"Found 1 import cycle") as info:
        imports.check_cycles(make_context({"package": {"name": "cyc_code"}}))
    assert info.value.code == 1


def test_check_cycles_detects_a_cycle_through_the_package(make_package: _Maker) -> None:
    make_package(
        "cyc_init", {"__init__.py": "from cyc_init import a\n", "a.py": "from cyc_init import X\n"}
    )
    with pytest.raises(Exit, match=r"cyc_init -> cyc_init.a -> cyc_init"):
        imports.check_cycles(make_context({"package": {"name": "cyc_init"}}))


def test_check_cycles_ignores_type_checking_imports(
    make_package: _Maker, capsys: pytest.CaptureFixture[str]
) -> None:
    make_package(
        "cyc_tc",
        {
            "__init__.py": "",
            "a.py": (
                "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from cyc_tc import b\n"
            ),
            "b.py": "from cyc_tc import a\n",
        },
    )
    imports.check_cycles(make_context({"package": {"name": "cyc_tc"}}))
    assert "✅ No import cycle in 3 module(s)" in capsys.readouterr().out


def test_check_cycles_can_follow_type_checking_imports(make_package: _Maker) -> None:
    make_package(
        "cyc_tc2",
        {
            "__init__.py": "",
            "a.py": "if TYPE_CHECKING:\n    from cyc_tc2 import b\n",
            "b.py": "from cyc_tc2 import a\n",
        },
    )
    with pytest.raises(Exit, match=r"cyc_tc2.a -> cyc_tc2.b -> cyc_tc2.a"):
        imports.check_cycles(make_context({"package": {"name": "cyc_tc2"}}), type_checking=True)


def test_check_cycles_ignores_lazy_imports(
    make_package: _Maker, capsys: pytest.CaptureFixture[str]
) -> None:
    make_package(
        "cyc_lazy",
        {
            "__init__.py": "",
            "a.py": "def f():\n    from cyc_lazy import b\n",
            "b.py": "from cyc_lazy import a\n",
        },
    )
    imports.check_cycles(make_context({"package": {"name": "cyc_lazy"}}))
    assert "✅ No import cycle in 3 module(s)" in capsys.readouterr().out


def test_check_cycles_can_follow_lazy_imports(make_package: _Maker) -> None:
    make_package(
        "cyc_lazy2",
        {
            "__init__.py": "",
            "a.py": "def f():\n    from cyc_lazy2 import b\n",
            "b.py": "from cyc_lazy2 import a\n",
        },
    )
    with pytest.raises(Exit, match=r"Found 1 import cycle"):
        imports.check_cycles(make_context({"package": {"name": "cyc_lazy2"}}), lazy=True)


def test_check_cycles_does_not_report_a_syntax_error_as_a_cycle(make_package: _Maker) -> None:
    make_package("cyc_syntax", {"__init__.py": "", "a.py": "def (:\n"})
    with pytest.raises(Exit, match=r"Cannot parse module cyc_syntax\.a: invalid syntax \(line 1\)"):
        imports.check_cycles(make_context({"package": {"name": "cyc_syntax"}}))


def test_check_cycles_reports_a_relative_import_above_the_top_level_package(
    make_package: _Maker,
) -> None:
    make_package("cyc_rel", {"__init__.py": "", "a.py": "from .. import x\n"})
    msg = r"Cannot parse module cyc_rel\.a: attempted relative import beyond top-level package"
    with pytest.raises(Exit, match=msg):
        imports.check_cycles(make_context({"package": {"name": "cyc_rel"}}))


def test_check_cycles_does_not_report_a_missing_dependency_as_a_cycle(
    make_package: _Maker, capsys: pytest.CaptureFixture[str]
) -> None:
    make_package("cyc_dep", {"__init__.py": "", "a.py": "import not_installed_anywhere\n"})
    imports.check_cycles(make_context({"package": {"name": "cyc_dep"}}))
    assert "✅ No import cycle in 2 module(s)" in capsys.readouterr().out


def test_check_cycles_reports_a_missing_package() -> None:
    with pytest.raises(Exit, match=r"No module named 'cyc_missing'"):
        imports.check_cycles(make_context({"package": {"name": "cyc_missing"}}))


def test_check_cycles_reads_the_directory_of_paths_src(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "src" / "cyc_src").mkdir(parents=True)
    (tmp_path / "src" / "cyc_src" / "__init__.py").write_text("")
    monkeypatch.chdir(tmp_path)
    imports.check_cycles(make_context({"package": {"name": "cyc_src"}}))
    assert "✅ No import cycle in 1 module(s)" in capsys.readouterr().out


def test_check_cycles_missing_package_names_paths_src() -> None:
    with pytest.raises(
        Exit,
        match=(
            r"No module named 'cyc_missing': not found in 'src/cyc_missing' "
            r"\(tasklib\.paths\.src\) and not installed"
        ),
    ):
        imports.check_cycles(make_context({"package": {"name": "cyc_missing"}}))


def test_check_cycles_uses_the_configured_import_name(
    make_package: _Maker, capsys: pytest.CaptureFixture[str]
) -> None:
    make_package("cyc_named", {"__init__.py": ""})
    imports.check_cycles(make_context({"package": {"name": "my-dist", "import_name": "cyc_named"}}))
    assert "✅ No import cycle in 1 module(s)" in capsys.readouterr().out


def test_check_isolated_reports_a_failure(capsys: pytest.CaptureFixture[str]) -> None:
    c = make_context(tasklib_config={"package": {"name": "mypkg"}})
    c.run = Mock(side_effect=Exit("boom", code=1))
    with pytest.raises(Exit, match=r"boom"):
        imports.check_isolated(c)
    assert "❌ Failed: Checking that each module imports on its own" in capsys.readouterr().err


def test_check_isolated_reads_the_modules_without_a_pty_nor_an_echo() -> None:
    c = make_context(tasklib_config={"package": {"name": "mypkg"}})
    imports.check_isolated(c)
    kwargs = run_kwargs(c)[0]
    assert (kwargs["hide"], kwargs["echo"], kwargs["pty"]) == (True, False, False)


def _failing() -> dict[str, Result]:
    r"""Fresh results: ``MockContext`` changes the dict it is given."""
    return {
        _WORKER_CMD: Result(
            stdout="3\nmypkg.a\tImportError: cannot import name 'X'\nmypkg.b\tSyntaxError: bad\n"
        )
    }


def test_check_isolated_exits_when_a_module_fails() -> None:
    c = make_context(tasklib_config={"package": {"name": "mypkg"}}, run=_failing())
    with pytest.raises(Exit, match=r"^2 of 3 module\(s\) failed to import on their own$"):
        imports.check_isolated(c)


def test_check_isolated_failure_exit_code_is_1() -> None:
    c = make_context(tasklib_config={"package": {"name": "mypkg"}}, run=_failing())
    with pytest.raises(Exit, match=r"failed to import") as info:
        imports.check_isolated(c)
    assert info.value.code == 1


def test_check_isolated_lists_the_failed_modules_with_their_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    c = make_context(tasklib_config={"package": {"name": "mypkg"}}, run=_failing())
    with pytest.raises(Exit, match=r"failed to import"):
        imports.check_isolated(c)
    assert capsys.readouterr().err == (
        "❌ mypkg.a: ImportError: cannot import name 'X'\n"
        "❌ mypkg.b: SyntaxError: bad\n"
        "❌ Failed: Checking that each module imports on its own\n"
    )


def test_check_isolated_does_not_echo_the_worker() -> None:
    c = make_context(tasklib_config={"package": {"name": "mypkg"}}, run=_failing())
    with pytest.raises(Exit, match=r"failed to import"):
        imports.check_isolated(c)
    assert [(k["hide"], k["echo"], k["pty"]) for k in run_kwargs(c)] == [(True, False, False)]


def test_check_isolated_does_not_report_success_after_a_failure(
    capsys: pytest.CaptureFixture[str],
) -> None:
    c = make_context(tasklib_config={"package": {"name": "mypkg"}}, run=_failing())
    with pytest.raises(Exit, match=r"failed to import"):
        imports.check_isolated(c)
    assert "✅" not in capsys.readouterr().out


########################################
#     Tests for _parse_import_each     #
########################################


def test_parse_import_each_without_failure() -> None:
    assert imports._parse_import_each("5\n") == (5, [])


def test_parse_import_each_with_failures() -> None:
    assert imports._parse_import_each("3\na\tImportError: x\nb\tSyntaxError: y\n") == (
        3,
        [("a", "ImportError: x"), ("b", "SyntaxError: y")],
    )


def test_parse_import_each_keeps_a_tab_of_the_reason() -> None:
    assert imports._parse_import_each("1\na\tError:\tx\n") == (1, [("a", "Error:\tx")])


def test_parse_import_each_of_an_empty_output_is_no_module() -> None:
    assert imports._parse_import_each("") == (0, [])


def test_parse_import_each_ignores_blank_lines() -> None:
    assert imports._parse_import_each("1\n\na\tE\n\n") == (1, [("a", "E")])
