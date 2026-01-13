"""Experimental symbol-level dead-code analysis (opt-in and conservative)."""

from __future__ import annotations

from prune.models import Candidate


def _find_dead_code(python_index: dict[str, dict[str, object]]) -> list[Candidate]:
    candidates: list[Candidate] = []
    metadata = python_index.get("metadata", {})
    for module, meta in metadata.items():
        defs = meta.get("defs", {})
        used = meta.get("used", set())
        exports = meta.get("exports", set())
        rel_path = meta.get("rel_path")
        if not isinstance(rel_path, str):
            continue
        for name, lineno in defs.items():
            if name in used or name in exports:
                continue
            confidence = 0.5
            if name.startswith("_"):
                confidence = 0.4
            candidates.append(
                Candidate(
                    kind="code",
                    action="manual_review",
                    path=rel_path,
                    reason="dead_code",
                    confidence=confidence,
                    details={"symbol": name, "line": lineno, "module": module},
                )
            )
    return candidates
