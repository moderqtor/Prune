from __future__ import annotations

import textwrap
from pathlib import Path

from prune.analyzer import _module_name_for_path, analyze


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_duplicate_files(tmp_path: Path) -> None:
    _write(tmp_path / "a.txt", "same")
    _write(tmp_path / "b.txt", "same")

    plan = analyze(tmp_path, include=[], exclude=[], confidence_threshold=0.0)

    duplicates = [c for c in plan.candidates if c.reason == "duplicate_file"]
    assert len(duplicates) == 1
    assert duplicates[0].details["duplicate_of"] in {"a.txt", "b.txt"}


def test_unreferenced_python_detects_imports(tmp_path: Path) -> None:
    _write(tmp_path / "main.py", "import util\n")
    _write(tmp_path / "util.py", "def helper():\n    return 1\n")

    plan = analyze(tmp_path, include=[], exclude=[], confidence_threshold=0.0)

    unreferenced = [c for c in plan.candidates if c.reason == "unreferenced_python"]
    assert all(c.path != "util.py" for c in unreferenced)


def test_dead_code_detection(tmp_path: Path) -> None:
    _write(
        tmp_path / "module.py",
        textwrap.dedent(
            """
            def used():
                return 1

            def unused():
                return 2

            used()
            """
        ).lstrip(),
    )

    plan = analyze(
        tmp_path,
        include=[],
        exclude=[],
        confidence_threshold=0.0,
        dead_code=True,
    )

    dead = [c for c in plan.candidates if c.reason == "dead_code"]
    assert any(c.details.get("symbol") == "unused" for c in dead)


def test_hard_excludes_skip_critical_files(tmp_path: Path) -> None:
    _write(tmp_path / "README.md", "readme")
    _write(tmp_path / "pyproject.toml", '[project]\nname = "x"\n')

    plan = analyze(
        tmp_path,
        include=["README.md", "pyproject.toml"],
        exclude=[],
        confidence_threshold=0.0,
    )

    assert all(c.path not in {"README.md", "pyproject.toml"} for c in plan.candidates)


def test_experiment_python_increases_confidence(tmp_path: Path) -> None:
    _write(tmp_path / "experiments" / "scratch.py", "value = 1\n")

    plan = analyze(tmp_path, include=[], exclude=[], confidence_threshold=0.0)

    candidates = [c for c in plan.candidates if c.reason == "unreferenced_python"]
    assert any(c.path == "experiments/scratch.py" and c.confidence == 0.75 for c in candidates)


def test_src_layout_module_resolution() -> None:
    root = Path("/repo")
    module = _module_name_for_path(root, root / "src" / "prune" / "analyzer.py")
    assert module == "prune.analyzer"


def test_src_layout_imports_prevent_false_unreferenced(tmp_path: Path) -> None:
    _write(tmp_path / "src" / "prune" / "__init__.py", "")
    _write(tmp_path / "src" / "prune" / "a.py", "def helper():\n    return 1\n")
    _write(
        tmp_path / "src" / "prune" / "b.py",
        "from prune import a\n\nvalue = a.helper()\n",
    )

    plan = analyze(tmp_path, include=[], exclude=[], confidence_threshold=0.0)

    unreferenced = [c for c in plan.candidates if c.reason == "unreferenced_python"]
    assert all(c.path != "src/prune/a.py" for c in unreferenced)
