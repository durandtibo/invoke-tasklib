from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, call

import pytest
from invoke.exceptions import Exit

from invoke_tasklib import imports
from tests.helpers import commands, make_context

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    _Maker = Callable[[str, dict[str, str]], None]


def _fake_import_each(
    result: tuple[int, list[tuple[str, str]]] = (3, []),
) -> Mock:
    r"""A stand-in for ``import_each`` that returns ``result``."""
    return Mock(return_value=result)


####################################
#     Tests for check_isolated     #
####################################


def test_check_isolated_imports_each_module_of_the_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _fake_import_each()
    monkeypatch.setattr(imports, "import_each", fake)
    imports.check_isolated(make_context(tasklib_config={"package": {"name": "mypkg"}}))
    assert fake.call_args_list == [call("mypkg")]


def test_check_isolated_uses_the_import_name(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _fake_import_each()
    monkeypatch.setattr(imports, "import_each", fake)
    imports.check_isolated(make_context(tasklib_config={"package": {"name": "my-pkg"}}))
    assert fake.call_args_list == [call("my_pkg")]


def test_check_isolated_uses_the_configured_import_name(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _fake_import_each()
    monkeypatch.setattr(imports, "import_each", fake)
    c = make_context(tasklib_config={"package": {"name": "my-pkg", "import_name": "other"}})
    imports.check_isolated(c)
    assert fake.call_args_list == [call("other")]


def test_check_isolated_runs_no_command(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(imports, "import_each", _fake_import_each())
    c = make_context(tasklib_config={"package": {"name": "mypkg"}})
    imports.check_isolated(c)
    assert commands(c) == []


def test_check_isolated_reports_progress(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(imports, "import_each", _fake_import_each())
    imports.check_isolated(make_context(tasklib_config={"package": {"name": "mypkg"}}))
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


_FAILURES = (
    3,
    [("mypkg.a", "ImportError: cannot import name 'X'"), ("mypkg.b", "SyntaxError: bad")],
)


def test_check_isolated_exits_when_a_module_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(imports, "import_each", _fake_import_each(_FAILURES))
    c = make_context(tasklib_config={"package": {"name": "mypkg"}})
    with pytest.raises(Exit, match=r"^2 of 3 module\(s\) failed to import on their own$"):
        imports.check_isolated(c)


def test_check_isolated_failure_exit_code_is_1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(imports, "import_each", _fake_import_each(_FAILURES))
    c = make_context(tasklib_config={"package": {"name": "mypkg"}})
    with pytest.raises(Exit, match=r"failed to import") as info:
        imports.check_isolated(c)
    assert info.value.code == 1


def test_check_isolated_lists_the_failed_modules_with_their_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(imports, "import_each", _fake_import_each(_FAILURES))
    c = make_context(tasklib_config={"package": {"name": "mypkg"}})
    with pytest.raises(Exit, match=r"failed to import"):
        imports.check_isolated(c)
    assert capsys.readouterr().err == (
        "❌ mypkg.a: ImportError: cannot import name 'X'\n"
        "❌ mypkg.b: SyntaxError: bad\n"
        "❌ Failed: Checking that each module imports on its own\n"
    )


def test_check_isolated_does_not_report_success_after_a_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(imports, "import_each", _fake_import_each(_FAILURES))
    c = make_context(tasklib_config={"package": {"name": "mypkg"}})
    with pytest.raises(Exit, match=r"failed to import"):
        imports.check_isolated(c)
    assert "✅" not in capsys.readouterr().out


def test_check_isolated_exits_when_the_package_is_not_found() -> None:
    c = make_context(tasklib_config={"package": {"name": "no_such_pkg_xyz"}})
    with pytest.raises(
        Exit,
        match=(
            r"^No module named 'no_such_pkg_xyz': "
            r"not found in the current directory and not installed$"
        ),
    ) as info:
        imports.check_isolated(c)
    assert info.value.code == 1


def test_check_isolated_reports_a_package_that_is_not_found(
    capsys: pytest.CaptureFixture[str],
) -> None:
    c = make_context(tasklib_config={"package": {"name": "no_such_pkg_xyz"}})
    with pytest.raises(Exit, match=r"not found"):
        imports.check_isolated(c)
    assert "❌ Failed: Checking that each module imports on its own" in capsys.readouterr().err
