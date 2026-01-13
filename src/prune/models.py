from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FileInfo:
    path: Path
    rel_path: str
    size: int
    mtime: float
    extension: str


@dataclass(frozen=True)
class Candidate:
    kind: str  # "file" or "code"
    action: str  # "delete" or "manual_review"
    path: str
    reason: str
    confidence: float
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Plan:
    root: str
    generated_at: str
    candidates: list[Candidate]
    summary: dict[str, Any]
