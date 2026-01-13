from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path
from typing import Iterable

from prune.analyzer import analyze, write_plan
from prune.models import Plan


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="prune",
        description="Generate a safe, reviewable deletion plan for a project directory.",
    )
    parser.add_argument("--path", default=".", help="Target project directory")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Dry-run (default)")
    mode.add_argument("--apply", action="store_true", help="Move files to trash")
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.4,
        help="Only include candidates >= threshold (0-1)",
    )
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        help="Glob to include (repeatable, relative to --path)",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Glob to exclude (repeatable, relative to --path)",
    )

    args = parser.parse_args(list(argv) if argv is not None else None)
    root = Path(args.path).resolve()
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Path does not exist or is not a directory: {root}")

    plan = analyze(
        root=root,
        include=args.include,
        exclude=args.exclude,
        confidence_threshold=args.confidence_threshold,
    )
    write_plan(root, plan)

    if args.apply:
        apply_plan(root, plan)
        print(f"Moved files to trash under {root}")
    else:
        print(f"Dry-run complete. Plans written to {root}")
    return 0


def apply_plan(root: Path, plan: Plan) -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    trash_root = root / f"._trash_{timestamp}"
    trash_root.mkdir(parents=True, exist_ok=True)

    undo_lines = ["#!/bin/sh", "set -e"]
    moved: set[str] = set()

    for candidate in plan.candidates:
        if candidate.kind != "file" or candidate.action != "delete":
            continue
        if candidate.path in moved:
            continue
        src = root / candidate.path
        if not src.exists():
            continue
        dst = trash_root / candidate.path
        dst.parent.mkdir(parents=True, exist_ok=True)
        os.replace(src, dst)
        undo_lines.append(f'mkdir -p "{src.parent}"')
        undo_lines.append(f'mv "{dst}" "{src}"')
        moved.add(candidate.path)

    undo_path = trash_root / "undo.sh"
    undo_path.write_text("\n".join(undo_lines) + "\n")
    undo_path.chmod(0o700)


if __name__ == "__main__":
    raise SystemExit(main())
