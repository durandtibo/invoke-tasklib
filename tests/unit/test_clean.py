from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
from invoke.config import Config
from invoke.context import MockContext
from invoke.runners import Result

from invoke_tasklib import clean
from tests.helpers import commands, make_context, run_kwargs

if TYPE_CHECKING:
    from collections.abc import Callable


def _context() -> MockContext:
    return MockContext(config=Config(), run=True)


def _git_context(stdout: str = "", exited: int = 0) -> MockContext:
    r"""A context where every command (the ``git ls-files`` calls)
    returns the given result."""
    c = _context()
    c.run = Mock(return_value=Result(stdout=stdout, exited=exited))
    return c


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _mkdir(*parts: str) -> Callable[[Path], Path]:
    def make(root: Path) -> Path:
        path = root.joinpath(*parts)
        path.mkdir(parents=True)
        return path

    return make


#########################
#     Tests for all     #
#########################

_CFG = {"package": {"name": "mypkg"}}


def test_all_removes_the_dist_dir(project: Path) -> None:
    _mkdir("dist")(project)
    clean.all_(_context())
    assert not (project / "dist").exists()


def test_all_removes_the_htmlcov_dir(project: Path) -> None:
    _mkdir("htmlcov")(project)
    clean.all_(_context())
    assert not (project / "htmlcov").exists()


def test_all_removes_mypy_cache(project: Path) -> None:
    _mkdir(".mypy_cache")(project)
    clean.all_(_context())
    assert not (project / ".mypy_cache").exists()


def test_all_removes_artifact_files(project: Path) -> None:
    (project / ".coverage").write_text("")
    (project / "coverage.xml").write_text("")
    clean.all_(_context())
    assert [p.name for p in project.iterdir()] == []


def test_all_removes_egg_info(project: Path) -> None:
    _mkdir("pkg.egg-info")(project)
    clean.all_(_context())
    assert not (project / "pkg.egg-info").exists()


def test_all_removes_src_egg_info(project: Path) -> None:
    _mkdir("src", "demo.egg-info")(project)
    clean.all_(_context())
    assert not (project / "src" / "demo.egg-info").exists()


def test_all_keeps_the_src_directory_with_its_egg_info(project: Path) -> None:
    _mkdir("src", "demo.egg-info")(project)
    clean.all_(_context())
    assert (project / "src").is_dir()


@pytest.mark.parametrize("name", [".tox", ".nox", ".hypothesis"])
def test_all_removes_tool_caches(project: Path, name: str) -> None:
    _mkdir(name)(project)
    clean.all_(_context())
    assert not (project / name).exists()


def test_all_removes_parallel_coverage_files(project: Path) -> None:
    (project / ".coverage.host.123.456").write_text("")
    clean.all_(_context())
    assert not (project / ".coverage.host.123.456").exists()


def test_all_keeps_site_without_mkdocs_config(project: Path) -> None:
    site = _mkdir("site")(project)
    clean.all_(_context())
    assert site.exists()


@pytest.mark.parametrize(
    ("config", "site"), [("mkdocs.yml", "site"), ("docs/mkdocs.yml", "docs/site")]
)
def test_all_removes_site_with_mkdocs_config(project: Path, config: str, site: str) -> None:
    _mkdir(*site.split("/"))(project)
    (project / config).parent.mkdir(exist_ok=True)
    (project / config).write_text("")
    clean.all_(_context())
    assert not (project / site).exists()


def test_all_removes_the_site_of_the_docs_config(project: Path) -> None:
    _mkdir("docs", "site")(project)
    (project / "docs" / "mkdocs.yml").write_text("")
    clean.all_(make_context(_CFG))
    assert not (project / "docs" / "site").exists()


def test_all_removes_the_configured_site_dir(project: Path) -> None:
    _mkdir("docs", "public")(project)
    (project / "docs" / "mkdocs.yml").write_text("site_dir: public\n")
    clean.all_(make_context(_CFG))
    assert not (project / "docs" / "public").exists()


def test_all_keeps_the_root_site_with_a_docs_config(project: Path) -> None:
    site = _mkdir("site")(project)
    _mkdir("docs")(project)
    (project / "docs" / "mkdocs.yml").write_text("")
    clean.all_(make_context(_CFG))
    assert site.exists()


def test_all_removes_nested_pycache(project: Path) -> None:
    _mkdir("src", "pkg", "__pycache__")(project)
    clean.all_(_context())
    assert not (project / "src" / "pkg" / "__pycache__").exists()


def test_all_keeps_other_files(project: Path) -> None:
    (project / "README.md").write_text("")
    clean.all_(_context())
    assert (project / "README.md").exists()


def test_all_does_not_touch_pycache_in_venv(project: Path) -> None:
    venv_cache = _mkdir(".venv", "lib", "__pycache__")(project)
    clean.all_(_context())
    assert venv_cache.exists()


def test_all_does_not_touch_pycache_in_node_modules(project: Path) -> None:
    cache = _mkdir("node_modules", "pkg", "__pycache__")(project)
    clean.all_(_context())
    assert cache.exists()


def test_all_no_artifacts_keeps_empty_project_unchanged(project: Path) -> None:
    clean.all_(_context())
    assert list(project.iterdir()) == []


def test_all_reports_progress(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _mkdir("dist")(project)
    clean.all_(_context())
    assert capsys.readouterr().out == (
        "🧹 Cleaning build artifacts and caches...\n🗑️  Removing dist\n✅ Cleanup complete\n"
    )


def test_all_dry_run_keeps_a_directory(project: Path) -> None:
    dist = _mkdir("dist")(project)
    clean.all_(_context(), dry_run=True)
    assert dist.is_dir()


def test_all_dry_run_keeps_a_file(project: Path) -> None:
    (project / ".coverage").write_text("")
    clean.all_(_context(), dry_run=True)
    assert (project / ".coverage").is_file()


def test_all_dry_run_keeps_a_nested_pycache(project: Path) -> None:
    cache = _mkdir("src", "pkg", "__pycache__")(project)
    clean.all_(_context(), dry_run=True)
    assert cache.is_dir()


def test_all_dry_run_reports_what_it_would_remove(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _mkdir("dist")(project)
    (project / ".coverage").write_text("")
    clean.all_(_context(), dry_run=True)
    assert capsys.readouterr().out == (
        "🧹 Cleaning build artifacts and caches (dry run)...\n"
        "🗑️  Would remove dist\n"
        "🗑️  Would remove .coverage\n"
        "✅ Dry run complete: nothing was removed\n"
    )


@pytest.mark.usefixtures("project")
def test_all_dry_run_on_a_clean_project_reports_nothing_to_remove(
    capsys: pytest.CaptureFixture[str],
) -> None:
    clean.all_(_context(), dry_run=True)
    assert capsys.readouterr().out == (
        "🧹 Cleaning build artifacts and caches (dry run)...\n"
        "✅ Dry run complete: nothing was removed\n"
    )


def test_all_keeps_a_directory_with_tracked_files(project: Path) -> None:
    build = _mkdir("build")(project)
    clean.all_(_git_context("build/script.sh\n"))
    assert build.is_dir()


def test_all_says_why_it_keeps_a_directory(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _mkdir("build")(project)
    clean.all_(_git_context("build/script.sh\n"))
    assert capsys.readouterr().out == (
        "🧹 Cleaning build artifacts and caches...\n"
        "⏭️  Keeping build: it contains files tracked by git\n"
        "✅ Cleanup complete\n"
    )


def test_all_removes_a_directory_without_tracked_files(project: Path) -> None:
    build = _mkdir("build")(project)
    clean.all_(_git_context(""))
    assert not build.exists()


def test_all_removes_a_directory_when_git_fails(project: Path) -> None:
    build = _mkdir("build")(project)
    clean.all_(_git_context("build/script.sh\n", exited=128))
    assert not build.exists()


def test_all_asks_git_only_about_the_directories_that_exist(project: Path) -> None:
    _mkdir("dist")(project)
    c = _git_context("")
    clean.all_(c)
    assert commands(c) == ["git ls-files -- dist"]


def test_all_does_not_ask_git_about_pycache_directories(project: Path) -> None:
    _mkdir("src", "__pycache__")(project)
    c = _git_context("")
    clean.all_(c)
    assert commands(c) == []


def test_all_keeps_the_tracked_site_directory(project: Path) -> None:
    (project / "mkdocs.yml").write_text("")
    site = _mkdir("site")(project)
    clean.all_(_git_context("site/index.html\n"))
    assert site.is_dir()


def test_all_dry_run_says_that_it_keeps_a_tracked_directory(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _mkdir("build")(project)
    clean.all_(_git_context("build/script.sh\n"), dry_run=True)
    assert "⏭️  Keeping build: it contains files tracked by git\n" in capsys.readouterr().out


#############################
#     Tests for pycache     #
#############################


def test_pycache_removes_nested_pycache_dirs(project: Path) -> None:
    _mkdir("a", "b", "__pycache__")(project)
    _mkdir("__pycache__")(project)
    clean.pycache(_context())
    assert [p.name for p in project.rglob("__pycache__")] == []


def test_pycache_keeps_other_dirs(project: Path) -> None:
    _mkdir("dist")(project)
    clean.pycache(_context())
    assert (project / "dist").exists()


def test_pycache_does_not_touch_venv(project: Path) -> None:
    venv_cache = _mkdir(".venv", "lib", "__pycache__")(project)
    clean.pycache(_context())
    assert venv_cache.exists()


def test_pycache_dry_run_keeps_the_directories(project: Path) -> None:
    cache = _mkdir("pkg", "__pycache__")(project)
    clean.pycache(_context(), dry_run=True)
    assert cache.is_dir()


def test_pycache_dry_run_reports_what_it_would_remove(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _mkdir("pkg", "__pycache__")(project)
    clean.pycache(_context(), dry_run=True)
    assert capsys.readouterr().out == (
        "🧹 Cleaning __pycache__ directories (dry run)...\n"
        "🗑️  Would remove pkg/__pycache__\n"
        "✅ Dry run complete: nothing was removed\n"
    )


########################################
#     Tests for _find_pycache_dirs     #
########################################


def test_find_pycache_dirs_returns_sorted_paths(tmp_path: Path) -> None:
    _mkdir("b", "__pycache__")(tmp_path)
    _mkdir("a", "__pycache__")(tmp_path)
    assert clean._find_pycache_dirs(tmp_path) == [
        tmp_path / "a" / "__pycache__",
        tmp_path / "b" / "__pycache__",
    ]


def test_find_pycache_dirs_empty(tmp_path: Path) -> None:
    assert clean._find_pycache_dirs(tmp_path) == []


@pytest.mark.parametrize("excluded", [".venv", ".git", "node_modules", ".pytest_cache"])
def test_find_pycache_dirs_skips_excluded_dirs(tmp_path: Path, excluded: str) -> None:
    _mkdir(excluded, "pkg", "__pycache__")(tmp_path)
    assert clean._find_pycache_dirs(tmp_path) == []


def test_find_pycache_dirs_skips_excluded_dir_but_finds_sibling(tmp_path: Path) -> None:
    _mkdir(".venv", "__pycache__")(tmp_path)
    _mkdir("src", "__pycache__")(tmp_path)
    assert clean._find_pycache_dirs(tmp_path) == [tmp_path / "src" / "__pycache__"]


def test_find_pycache_dirs_does_not_descend_into_pycache(tmp_path: Path) -> None:
    _mkdir("__pycache__", "__pycache__")(tmp_path)
    assert clean._find_pycache_dirs(tmp_path) == [tmp_path / "__pycache__"]


################################
#     Tests for _site_dirs     #
################################


@pytest.mark.usefixtures("project")
def test_site_dirs_is_empty_without_a_config() -> None:
    assert clean._site_dirs(_context()) == []


def test_site_dirs_finds_the_root_config(project: Path) -> None:
    (project / "mkdocs.yml").write_text("")
    assert clean._site_dirs(_context()) == [Path("site")]


def test_site_dirs_finds_the_docs_config(project: Path) -> None:
    _mkdir("docs")(project)
    (project / "docs" / "mkdocs.yml").write_text("")
    assert clean._site_dirs(_context()) == [Path("docs/site")]


def test_site_dirs_uses_the_configured_docs_config(project: Path) -> None:
    _mkdir("d")(project)
    (project / "d" / "mkdocs.yml").write_text("")
    c = make_context({**_CFG, "paths": {"docs_config": "d/mkdocs.yml"}})
    assert clean._site_dirs(c) == [Path("d/site")]


def test_site_dirs_ignores_the_fallback_files_with_a_valid_config(project: Path) -> None:
    (project / "mkdocs.yml").write_text("")
    assert clean._site_dirs(make_context(_CFG)) == []


def test_site_dirs_reads_the_site_dir_option(project: Path) -> None:
    _mkdir("docs")(project)
    (project / "docs" / "mkdocs.yml").write_text("site_dir: out\n")
    assert clean._site_dirs(make_context(_CFG)) == [Path("docs/out")]


def test_site_dirs_ignores_a_directory_named_like_the_config(project: Path) -> None:
    _mkdir("mkdocs.yml")(project)
    assert clean._site_dirs(_context()) == []


####################################
#     Tests for _read_site_dir     #
####################################


@pytest.fixture
def mkdocs(project: Path) -> Path:
    return project / "mkdocs.yml"


def test_read_site_dir_defaults_to_site(mkdocs: Path) -> None:
    mkdocs.write_text("site_name: demo\n")
    assert clean._read_site_dir(mkdocs) == "site"


@pytest.mark.parametrize(
    "line",
    ["site_dir: public", "site_dir: 'public'", 'site_dir: "public"', "site_dir: public  # out"],
)
def test_read_site_dir_reads_the_value(mkdocs: Path, line: str) -> None:
    mkdocs.write_text(f"site_name: demo\n{line}\n")
    assert clean._read_site_dir(mkdocs) == "public"


def test_read_site_dir_with_an_empty_value_defaults_to_site(mkdocs: Path) -> None:
    mkdocs.write_text("site_dir:\n")
    assert clean._read_site_dir(mkdocs) == "site"


def test_read_site_dir_ignores_an_indented_option(mkdocs: Path) -> None:
    mkdocs.write_text("extra:\n  site_dir: other\n")
    assert clean._read_site_dir(mkdocs) == "site"


#################################
#     Tests for _remove_dir     #
#################################


@pytest.mark.usefixtures("project")
def test_remove_dir_removes_existing_dir(tmp_path: Path) -> None:
    target = _mkdir("cache")(tmp_path)
    clean._remove_dir(_context(), target)
    assert not target.exists()


def test_remove_dir_ignores_missing_dir(tmp_path: Path) -> None:
    clean._remove_dir(_context(), tmp_path / "missing")
    assert tmp_path.exists()


@pytest.mark.usefixtures("project")
def test_remove_dir_removes_a_symlink_to_a_directory(tmp_path: Path) -> None:
    target = _mkdir("real")(tmp_path)
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    clean._remove_dir(_context(), link)
    assert not link.is_symlink()


def test_remove_dir_keeps_the_target_of_a_symlink(tmp_path: Path) -> None:
    target = _mkdir("real")(tmp_path)
    (tmp_path / "link").symlink_to(target, target_is_directory=True)
    clean._remove_dir(_context(), tmp_path / "link")
    assert target.is_dir()


@pytest.mark.usefixtures("project")
def test_remove_dir_reports_removal(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = _mkdir("cache")(tmp_path)
    clean._remove_dir(_context(), target)
    assert capsys.readouterr().out == f"🗑️  Removing {target}\n"


def test_remove_dir_dry_run_keeps_the_directory(tmp_path: Path) -> None:
    target = _mkdir("cache")(tmp_path)
    clean._remove_dir(_context(), target, dry_run=True)
    assert target.is_dir()


@pytest.mark.usefixtures("project")
def test_remove_dir_dry_run_reports_the_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = _mkdir("cache")(tmp_path)
    clean._remove_dir(_context(), target, dry_run=True)
    assert capsys.readouterr().out == f"🗑️  Would remove {target}\n"


def test_remove_dir_dry_run_ignores_a_missing_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    clean._remove_dir(_context(), tmp_path / "missing", dry_run=True)
    assert capsys.readouterr().out == ""


def test_remove_dir_dry_run_keeps_a_symlink(tmp_path: Path) -> None:
    target = _mkdir("real")(tmp_path)
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    clean._remove_dir(_context(), link, dry_run=True)
    assert link.is_symlink()


def test_remove_dir_keeps_a_tracked_directory(tmp_path: Path) -> None:
    target = _mkdir("build")(tmp_path)
    clean._remove_dir(_git_context("build/a.py\n"), target, keep_tracked=True)
    assert target.is_dir()


@pytest.mark.usefixtures("project")
def test_remove_dir_reports_a_tracked_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = _mkdir("build")(tmp_path)
    clean._remove_dir(_git_context("build/a.py\n"), target, keep_tracked=True)
    assert capsys.readouterr().out == f"⏭️  Keeping {target}: it contains files tracked by git\n"


@pytest.mark.usefixtures("project")
def test_remove_dir_removes_a_tracked_directory_unless_asked_to_keep_it(tmp_path: Path) -> None:
    target = _mkdir("build")(tmp_path)
    clean._remove_dir(_git_context("build/a.py\n"), target)
    assert not target.exists()


def test_remove_dir_does_not_ask_git_about_a_missing_directory(tmp_path: Path) -> None:
    c = _git_context("a.py\n")
    clean._remove_dir(c, tmp_path / "missing", keep_tracked=True)
    assert commands(c) == []


##################################
#     Tests for _remove_file     #
##################################


def test_remove_file_removes_existing_file(tmp_path: Path) -> None:
    target = tmp_path / ".coverage"
    target.write_text("data")
    clean._remove_file(_context(), target)
    assert not target.exists()


def test_remove_file_ignores_missing_file(tmp_path: Path) -> None:
    clean._remove_file(_context(), tmp_path / "missing")
    assert tmp_path.exists()


###################################
#     Tests for _done_message     #
###################################


def test_done_message() -> None:
    assert clean._done_message(dry_run=False) == "✅ Cleanup complete"


def test_done_message_of_a_dry_run() -> None:
    assert clean._done_message(dry_run=True) == "✅ Dry run complete: nothing was removed"


########################################
#     Tests for _has_tracked_files     #
########################################


def test_has_tracked_files_when_git_lists_a_file() -> None:
    assert clean._has_tracked_files(_git_context("build/a.py\n"), Path("build")) is True


def test_has_tracked_files_is_false_when_git_lists_nothing() -> None:
    assert clean._has_tracked_files(_git_context(""), Path("build")) is False


def test_has_tracked_files_is_false_when_git_lists_only_whitespace() -> None:
    assert clean._has_tracked_files(_git_context("\n"), Path("build")) is False


def test_has_tracked_files_is_false_when_git_fails() -> None:
    assert clean._has_tracked_files(_git_context("a.py\n", exited=128), Path("build")) is False


def test_has_tracked_files_runs_git_ls_files_on_the_path() -> None:
    c = _git_context()
    clean._has_tracked_files(c, Path("build"))
    assert commands(c) == ["git ls-files -- build"]


def test_has_tracked_files_quotes_the_path() -> None:
    c = _git_context()
    clean._has_tracked_files(c, Path("my build"))
    assert commands(c) == ["git ls-files -- 'my build'"]


def test_has_tracked_files_does_not_echo_nor_fail() -> None:
    c = _git_context()
    clean._has_tracked_files(c, Path("build"))
    kwargs = run_kwargs(c)[0]
    assert (kwargs["hide"], kwargs["warn"], kwargs["echo"], kwargs["pty"]) == (
        True,
        True,
        False,
        False,
    )


def test_remove_file_dry_run_keeps_the_file(tmp_path: Path) -> None:
    target = tmp_path / ".coverage"
    target.write_text("data")
    clean._remove_file(_context(), target, dry_run=True)
    assert target.is_file()


def test_remove_file_dry_run_reports_the_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / ".coverage"
    target.write_text("data")
    clean._remove_file(_context(), target, dry_run=True)
    assert capsys.readouterr().out == f"🗑️  Would remove {target}\n"


###################################
#     Tests for outside paths     #
###################################


def _outside_site(project: Path) -> Path:
    outside = project.parent / f"{project.name}-outside"
    outside.mkdir()
    (project / "mkdocs.yml").write_text(f"site_dir: {outside}\n")
    return outside


def test_all_keeps_an_absolute_site_dir_outside_the_project(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    outside = _outside_site(project)
    with pytest.MonkeyPatch.context() as m:
        m.chdir(project)
        clean.all_(_git_context(""))
    assert outside.is_dir()


def test_all_says_that_it_keeps_a_site_dir_outside_the_project(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    outside = _outside_site(project)
    with pytest.MonkeyPatch.context() as m:
        m.chdir(project)
        clean.all_(_git_context(""))
    assert f"⏭️  Not removing {outside}: it is outside the project\n" in capsys.readouterr().out


def test_all_dry_run_does_not_announce_a_site_dir_outside_the_project(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    outside = _outside_site(project)
    with pytest.MonkeyPatch.context() as m:
        m.chdir(project)
        clean.all_(_git_context(""), dry_run=True)
    assert f"Would remove {outside}" not in capsys.readouterr().out


def test_all_keeps_a_relative_site_dir_with_dotdot(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (tmp_path / "public").mkdir()
    (project / "mkdocs.yml").write_text("site_dir: ../public\n")
    with pytest.MonkeyPatch.context() as m:
        m.chdir(project)
        clean.all_(_git_context(""))
    assert (tmp_path / "public").is_dir()


def test_all_keeps_the_project_root_as_site_dir(project: Path) -> None:
    (project / "mkdocs.yml").write_text("site_dir: .\n")
    clean.all_(_git_context(""))
    assert (project / "mkdocs.yml").is_file()


def test_all_removes_a_site_dir_inside_the_project(project: Path) -> None:
    public = _mkdir("public")(project)
    (project / "mkdocs.yml").write_text("site_dir: public\n")
    clean.all_(_git_context(""))
    assert not public.exists()


def test_all_removes_a_link_inside_the_project_and_keeps_its_target(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    target = tmp_path / "target"
    target.mkdir()
    (project / "build").symlink_to(target, target_is_directory=True)
    with pytest.MonkeyPatch.context() as m:
        m.chdir(project)
        clean.all_(_git_context(""))
    assert (target.is_dir(), (project / "build").exists()) == (True, False)


def test_all_keeps_a_site_dir_below_a_link_to_the_outside(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (tmp_path / "target" / "site").mkdir(parents=True)
    (project / "out").symlink_to(tmp_path / "target", target_is_directory=True)
    (project / "mkdocs.yml").write_text("site_dir: out/site\n")
    with pytest.MonkeyPatch.context() as m:
        m.chdir(project)
        clean.all_(_git_context(""))
    assert (tmp_path / "target" / "site").is_dir()


######################################
#     Tests for _is_inside_project   #
######################################


@pytest.mark.usefixtures("project")
@pytest.mark.parametrize("path", ["build", "docs/site", "a/b/c", "./build"])
def test_is_inside_project_accepts_a_path_below_the_cwd(path: str) -> None:
    assert clean._is_inside_project(Path(path)) is True


@pytest.mark.usefixtures("project")
@pytest.mark.parametrize("path", [".", "", "..", "../build", "build/../..", "a/../../b"])
def test_is_inside_project_rejects_the_cwd_and_the_paths_above(path: str) -> None:
    assert clean._is_inside_project(Path(path)) is False


def test_is_inside_project_rejects_an_absolute_path_outside(project: Path) -> None:
    assert clean._is_inside_project(project.parent / "other") is False


def test_is_inside_project_accepts_an_absolute_path_inside(project: Path) -> None:
    assert clean._is_inside_project(project / "build") is True


def test_is_inside_project_accepts_a_link_to_the_outside(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "link").symlink_to(tmp_path, target_is_directory=True)
    with pytest.MonkeyPatch.context() as m:
        m.chdir(project)
        assert clean._is_inside_project(Path("link")) is True


def test_is_inside_project_rejects_a_path_below_a_link_to_the_outside(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "link").symlink_to(tmp_path, target_is_directory=True)
    with pytest.MonkeyPatch.context() as m:
        m.chdir(project)
        assert clean._is_inside_project(Path("link/site")) is False


#########################################
#     Tests for the coverage HTML dir   #
#########################################


def _html_dir_project(project: Path, directory: str) -> Path:
    (project / "pyproject.toml").write_text(f'[tool.coverage.html]\ndirectory = "{directory}"\n')
    return _mkdir(directory)(project)


def test_all_removes_the_configured_coverage_html_dir(project: Path) -> None:
    html = _html_dir_project(project, "reports/html")
    clean.all_(_git_context(""))
    assert not html.exists()


def test_all_keeps_the_parent_of_the_configured_coverage_html_dir(project: Path) -> None:
    _html_dir_project(project, "reports/html")
    clean.all_(_git_context(""))
    assert (project / "reports").is_dir()


def test_all_removes_the_default_coverage_html_dir_without_config(project: Path) -> None:
    html = _mkdir("htmlcov")(project)
    clean.all_(_git_context(""))
    assert not html.exists()


def test_all_asks_git_once_for_the_default_coverage_html_dir(project: Path) -> None:
    _mkdir("htmlcov")(project)
    c = _git_context("")
    clean.all_(c)
    assert commands(c) == ["git ls-files -- htmlcov"]


def test_all_keeps_a_configured_coverage_html_dir_tracked_by_git(project: Path) -> None:
    html = _html_dir_project(project, "reports/html")
    clean.all_(_git_context("reports/html/index.html\n"))
    assert html.is_dir()


def test_all_dry_run_reports_the_configured_coverage_html_dir(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _html_dir_project(project, "reports/html")
    clean.all_(_git_context(""), dry_run=True)
    assert "🗑️  Would remove reports/html\n" in capsys.readouterr().out


def test_all_keeps_a_coverage_html_dir_outside_the_project(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "outside-html"
    outside.mkdir()
    (project / "pyproject.toml").write_text(f'[tool.coverage.html]\ndirectory = "{outside}"\n')
    with pytest.MonkeyPatch.context() as m:
        m.chdir(project)
        clean.all_(_git_context(""))
    assert outside.is_dir()
