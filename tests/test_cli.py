from __future__ import annotations

import json
from pathlib import Path

import pytest

from prune import cli


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_apply_requires_yes(tmp_path: Path) -> None:
    _write(tmp_path / "unused.txt", "unused")
    with pytest.raises(SystemExit, match="--yes"):
        cli.main(["--path", str(tmp_path), "--apply"])


def test_apply_writes_closure(tmp_path: Path) -> None:
    _write(tmp_path / "unused.txt", "unused")

    result = cli.main(
        [
            "--path",
            str(tmp_path),
            "--apply",
            "--yes",
            "--confidence-threshold",
            "0.0",
        ]
    )
    assert result == 0

    closure = tmp_path / "CLOSURE.md"
    assert closure.exists()
    content = closure.read_text()
    assert "Trash directory:" in content
    assert "Undo script:" in content
    assert "unused.txt" in content


def test_one_run_sets_threshold(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(tmp_path / "unused.txt", "unused")

    cli.main(["--path", str(tmp_path), "--one-run"])
    captured = capsys.readouterr().out
    assert "One-run mode" in captured

    plan = json.loads((tmp_path / "deletion_plan.json").read_text())
    assert plan["summary"]["confidence_threshold"] == 0.65
