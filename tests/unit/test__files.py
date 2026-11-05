from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from invoke.exceptions import Exit
from invoke.runners import Result

from invoke_tasklib import doc, formatting, testing
from invoke_tasklib._files import (
    CACHE_DIRS,
    ENVIRONMENT_DIRS,
    EXCLUDED_DIRS,
    OUTPUT_DIRS,
    _in_git_work_tree,
    find_files,
    project_files,
    require_path,
)
from tests.helpers import commands, make_context

if TYPE_CHECKING:
    from collections.abc import Callable

    from invoke.context import MockContext

################################
#     Tests for find_files     #
################################


def _touch(root: Path, *names: str) -> None:
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("")


def test_find_files_returns_sorted_paths(tmp_path: Path) -> None:
    _touch(tmp_path, "b.sh", "a.sh", "src/c.sh")
    assert find_files(tmp_path, ".sh") == [
        tmp_path / "a.sh",
        tmp_path / "b.sh",
        tmp_path / "src" / "c.sh",
    ]


def test_find_files_empty_directory(tmp_path: Path) -> None:
    assert find_files(tmp_path, ".sh") == []


def test_find_files_ignores_other_suffixes(tmp_path: Path) -> None:
    _touch(tmp_path, "a.sh", "b.py", "c.shx")
    assert find_files(tmp_path, ".sh") == [tmp_path / "a.sh"]


def test_find_files_does_not_walk_into_default_excluded_dirs(tmp_path: Path) -> None:
    _touch(tmp_path, ".venv/a.sh", "b.sh")
    assert find_files(tmp_path, ".sh") == [tmp_path / "b.sh"]


def test_find_files_skips_excluded_dirs_at_any_depth(tmp_path: Path) -> None:
    _touch(tmp_path, "pkg/.git/a.sh", "pkg/b.sh")
    assert find_files(tmp_path, ".sh") == [tmp_path / "pkg" / "b.sh"]


@pytest.mark.parametrize("excluded", sorted(EXCLUDED_DIRS))
def test_find_files_does_not_walk_into_an_excluded_dir(tmp_path: Path, excluded: str) -> None:
    _touch(tmp_path, f"pkg/{excluded}/a.sh", "pkg/b.sh")
    assert find_files(tmp_path, ".sh") == [tmp_path / "pkg" / "b.sh"]


def test_find_files_current_directory_has_no_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _touch(tmp_path, "a.sh")
    monkeypatch.chdir(tmp_path)
    assert find_files(Path(), ".sh") == [Path("a.sh")]


#######################################
#     Tests for _in_git_work_tree     #
#######################################


def test_in_git_work_tree_without_git_entry(tmp_path: Path) -> None:
    assert _in_git_work_tree(tmp_path) is False


def test_in_git_work_tree_with_a_git_directory(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    assert _in_git_work_tree(tmp_path) is True


def test_in_git_work_tree_with_a_git_file(tmp_path: Path) -> None:
    (tmp_path / ".git").write_text("gitdir: elsewhere\n")
    assert _in_git_work_tree(tmp_path) is True


def test_in_git_work_tree_looks_at_the_parents(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "pkg" / "sub").mkdir(parents=True)
    assert _in_git_work_tree(tmp_path / "pkg" / "sub") is True


def test_in_git_work_tree_ignores_a_git_entry_of_a_child(tmp_path: Path) -> None:
    (tmp_path / "pkg" / ".git").mkdir(parents=True)
    assert _in_git_work_tree(tmp_path) is False


def test_in_git_work_tree_of_the_current_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    assert _in_git_work_tree(Path()) is True


###################################
#     Tests for project_files     #
###################################

_LS = "git ls-files -z --cached --others --exclude-standard -- '*.sh'"


def _git_context(stdout: str, exited: int = 0) -> MockContext:
    return make_context(run={_LS: Result(stdout=stdout, exited=exited, command=_LS)})


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    r"""A project in a git work tree (it has a ``.git`` directory)."""
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_project_files_walks_outside_a_work_tree(tmp_path: Path) -> None:
    _touch(tmp_path, "a.sh", ".venv/b.sh")
    c = make_context()
    assert project_files(c, tmp_path, ".sh") == [tmp_path / "a.sh"]


def test_project_files_runs_no_command_outside_a_work_tree(tmp_path: Path) -> None:
    c = make_context()
    project_files(c, tmp_path, ".sh")
    assert commands(c) == []


@pytest.mark.usefixtures("repo")
def test_project_files_asks_git_in_a_work_tree() -> None:
    c = _git_context("")
    project_files(c, Path(), ".sh")
    assert commands(c) == [_LS]


@pytest.mark.usefixtures("repo")
def test_project_files_returns_the_files_that_git_lists(repo: Path) -> None:
    _touch(repo, "a.sh", "src/b.sh")
    assert project_files(_git_context("src/b.sh\0a.sh\0"), Path(), ".sh") == [
        Path("a.sh"),
        Path("src/b.sh"),
    ]


@pytest.mark.usefixtures("repo")
def test_project_files_does_not_walk_in_a_work_tree(repo: Path) -> None:
    _touch(repo, "a.sh", "ignored.sh")
    assert project_files(_git_context("a.sh\0"), Path(), ".sh") == [Path("a.sh")]


@pytest.mark.usefixtures("repo")
def test_project_files_leaves_out_a_deleted_tracked_file(repo: Path) -> None:
    _touch(repo, "a.sh")
    assert project_files(_git_context("a.sh\0deleted.sh\0"), Path(), ".sh") == [Path("a.sh")]


@pytest.mark.usefixtures("repo")
def test_project_files_leaves_out_the_excluded_directories(repo: Path) -> None:
    _touch(repo, "a.sh", ".venv/lib/b.sh", "pkg/node_modules/c.sh")
    stdout = "a.sh\0.venv/lib/b.sh\0pkg/node_modules/c.sh\0"
    assert project_files(_git_context(stdout), Path(), ".sh") == [Path("a.sh")]


@pytest.mark.usefixtures("repo")
def test_project_files_keeps_a_tracked_build_directory(repo: Path) -> None:
    _touch(repo, "build/a.sh")
    assert project_files(_git_context("build/a.sh\0"), Path(), ".sh") == [Path("build/a.sh")]


@pytest.mark.usefixtures("repo")
def test_project_files_without_a_file_is_empty() -> None:
    assert project_files(_git_context(""), Path(), ".sh") == []


@pytest.mark.usefixtures("repo")
def test_project_files_falls_back_to_the_walk_when_git_fails(repo: Path) -> None:
    _touch(repo, "a.sh", ".venv/b.sh")
    assert project_files(_git_context("", exited=128), Path(), ".sh") == [Path("a.sh")]


@pytest.mark.usefixtures("repo")
def test_project_files_keeps_a_file_with_a_space(repo: Path) -> None:
    _touch(repo, "my dir/a b.sh")
    assert project_files(_git_context("my dir/a b.sh\0"), Path(), ".sh") == [Path("my dir/a b.sh")]


def test_project_files_limits_the_pattern_to_a_root_directory(
    repo: Path,
) -> None:
    _touch(repo, "scripts/a.sh")
    command = "git ls-files -z --cached --others --exclude-standard -- 'scripts/*.sh'"
    c = make_context(run={command: Result(stdout="scripts/a.sh\0", command=command)})
    assert project_files(c, Path("scripts"), ".sh") == [Path("scripts/a.sh")]


@pytest.mark.usefixtures("repo")
def test_project_files_skips_the_output_directories_in_the_walk(repo: Path) -> None:
    _touch(repo, "build/a.sh", "site/b.sh", "c.sh")
    assert project_files(_git_context("", exited=1), Path(), ".sh") == [Path("c.sh")]


@pytest.mark.parametrize("name", sorted(CACHE_DIRS | ENVIRONMENT_DIRS))
def test_project_files_leaves_out_an_environment_directory_that_git_lists(
    repo: Path, name: str
) -> None:
    _touch(repo, "a.sh", f"{name}/b.sh")
    assert project_files(_git_context(f"a.sh\0{name}/b.sh\0"), Path(), ".sh") == [Path("a.sh")]


@pytest.mark.parametrize("name", sorted(OUTPUT_DIRS))
def test_project_files_keeps_an_output_directory_that_git_lists(repo: Path, name: str) -> None:
    _touch(repo, f"{name}/a.sh")
    assert project_files(_git_context(f"{name}/a.sh\0"), Path(), ".sh") == [Path(f"{name}/a.sh")]


#####################################
#     Tests for EXCLUDED_DIRS       #
#####################################


def test_excluded_dirs_is_the_union_of_the_three_groups() -> None:
    assert EXCLUDED_DIRS == CACHE_DIRS | OUTPUT_DIRS | ENVIRONMENT_DIRS


@pytest.mark.parametrize(
    ("first", "second"),
    [
        (CACHE_DIRS, OUTPUT_DIRS),
        (CACHE_DIRS, ENVIRONMENT_DIRS),
        (OUTPUT_DIRS, ENVIRONMENT_DIRS),
    ],
)
def test_the_groups_of_excluded_dirs_do_not_overlap(
    first: frozenset[str], second: frozenset[str]
) -> None:
    assert set() == first & second


###################################
#     Tests for require_path      #
###################################


def test_require_path_accepts_an_existing_directory(tmp_path: Path) -> None:
    assert require_path(str(tmp_path), "tasklib.paths.src") is None


def test_require_path_accepts_an_existing_file(tmp_path: Path) -> None:
    (tmp_path / "a.yml").write_text("")
    assert require_path(str(tmp_path / "a.yml"), "tasklib.paths.docs_config", file=True) is None


def test_require_path_names_the_path_and_the_key() -> None:
    with pytest.raises(
        Exit,
        match=r"^'no/dir' \(tasklib\.paths\.src\) does not exist: set it in invoke\.yaml$",
    ):
        require_path("no/dir", "tasklib.paths.src")


def test_require_path_exits_with_code_2() -> None:
    with pytest.raises(Exit, match=r"does not exist") as info:
        require_path("no/dir", "tasklib.paths.src")
    assert info.value.code == 2


def test_require_path_rejects_a_directory_when_a_file_is_needed(tmp_path: Path) -> None:
    with pytest.raises(Exit, match=r"\(tasklib\.paths\.docs_config\) does not exist"):
        require_path(str(tmp_path), "tasklib.paths.docs_config", file=True)


####################################################
#     Tests for the rule of the missing paths      #
####################################################

_CONFIG = {"package": {"name": "mypkg"}}


@pytest.mark.parametrize(
    ("task", "key"),
    [
        pytest.param(testing.doctest_src, "tasklib.paths.src", id="doctest-src"),
        pytest.param(formatting.check_docstrings, "tasklib.paths.src", id="check-docstrings"),
        pytest.param(formatting.fix_docstrings, "tasklib.paths.src", id="fix-docstrings"),
        pytest.param(doc.build, "tasklib.paths.docs_config", id="doc-build"),
    ],
)
def test_a_missing_path_of_the_task_exits_with_2_and_names_the_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, task: Callable[..., None], key: str
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(Exit, match=rf"\({re.escape(key)}\) does not exist") as info:
        task(make_context(_CONFIG))
    assert info.value.code == 2


@pytest.mark.parametrize(
    "task", [testing.unit, testing.integration, testing.functional], ids=lambda t: t.__name__
)
def test_a_missing_optional_directory_is_skipped_with_a_message(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    task: Callable[..., None],
) -> None:
    monkeypatch.chdir(tmp_path)
    task(make_context(_CONFIG))
    assert "⏭️" in capsys.readouterr().out


def test_a_missing_benchmarks_directory_exits_with_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(Exit, match=r"No 'tests/benchmarks' directory") as info:
        testing.benchmark(make_context(_CONFIG))
    assert info.value.code == 1


@pytest.mark.parametrize(
    "task", [testing.doctest_src, formatting.check_docstrings, formatting.fix_docstrings]
)
def test_a_path_given_with_paths_is_not_checked_by_the_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, task: Callable[..., None]
) -> None:
    monkeypatch.chdir(tmp_path)
    c = make_context(_CONFIG)
    task(c, paths="no/such/dir")
    assert "no/such/dir" in commands(c)[0]
