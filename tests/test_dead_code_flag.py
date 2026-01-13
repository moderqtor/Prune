from __future__ import annotations

import textwrap
from pathlib import Path

from prune.analyzer import analyze


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_dead_code_flag_increases_candidates(tmp_path: Path) -> None:
    _write(
        tmp_path / "main.py",
        textwrap.dedent(
            """
            def used():
                return 1

            def unused():
                return 2

            if __name__ == "__main__":
                used()
            """
        ).lstrip(),
    )

    base = analyze(
        tmp_path,
        include=[],
        exclude=[],
        confidence_threshold=0.0,
        dead_code=False,
    )
    with_dead_code = analyze(
        tmp_path,
        include=[],
        exclude=[],
        confidence_threshold=0.0,
        dead_code=True,
    )

    assert with_dead_code.summary["candidates"] > base.summary["candidates"]
