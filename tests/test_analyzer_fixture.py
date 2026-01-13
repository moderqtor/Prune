from __future__ import annotations

from pathlib import Path

from prune.analyzer import analyze


def test_fixture_produces_candidates() -> None:
    fixture_root = Path(__file__).parent / "fixtures" / "sample_repo"
    plan = analyze(
        fixture_root,
        include=[],
        exclude=[],
        confidence_threshold=0.0,
        dead_code=False,
    )
    assert plan.summary["candidates"] >= 1
