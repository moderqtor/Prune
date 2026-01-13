from __future__ import annotations

import textwrap
from pathlib import Path

from prune.analyzer import analyze


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

    plan = analyze(tmp_path, include=[], exclude=[], confidence_threshold=0.0)

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
