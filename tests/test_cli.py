from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from prune import cli
from prune.models import Candidate, Plan


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
    assert (tmp_path / "undo.sh").exists()


def test_one_run_sets_threshold(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(tmp_path / "unused.txt", "unused")

    cli.main(["--path", str(tmp_path), "--one-run"])
    captured = capsys.readouterr().out
    assert "One-run mode" in captured

    plan = json.loads((tmp_path / "deletion_plan.json").read_text())
    assert plan["summary"]["confidence_threshold"] == 0.65


def test_help_exits_zero() -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--help"])
    assert excinfo.value.code == 0


def test_apply_and_undo_round_trip(tmp_path: Path) -> None:
    _write(tmp_path / "a.txt", "payload")
    plan = Plan(
        root=str(tmp_path),
        generated_at="2024-01-01T00:00:00Z",
        candidates=[
            Candidate(
                kind="file",
                action="delete",
                path="a.txt",
                reason="unreferenced_file",
                confidence=0.9,
            )
        ],
        summary={},
    )

    cli.apply_plan(tmp_path, plan, confidence_threshold=0.9)

    trash_dirs = sorted(tmp_path.glob("._trash_*"))
    assert len(trash_dirs) == 1
    trash_root = trash_dirs[0]
    assert not (tmp_path / "a.txt").exists()
    assert (trash_root / "a.txt").exists()

    undo_path = tmp_path / "undo.sh"
    assert undo_path.exists()
    subprocess.run(["sh", str(undo_path)], check=True)

    assert (tmp_path / "a.txt").exists()


def test_cli_apply_writes_root_undo(tmp_path: Path) -> None:
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

    undo_path = tmp_path / "undo.sh"
    assert undo_path.exists()

    subprocess.run(["sh", str(undo_path)], check=True)
    assert (tmp_path / "unused.txt").exists()
