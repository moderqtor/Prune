from __future__ import annotations

import argparse
import os
import shlex
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from prune import __version__
from prune.models import Plan


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="prune",
        description=(
            "Generate a safe, reviewable deletion plan for a project directory. "
            "Apply mode requires --yes confirmation."
        ),
    )
    parser.add_argument("--path", default=".", help="Target project directory")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Dry-run (default)")
    mode.add_argument("--apply", action="store_true", help="Move files to trash")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm apply mode (required with --apply)",
    )
    parser.add_argument(
        "--one-run",
        action="store_true",
        help="Use safer defaults and print a one-run banner",
    )
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=None,
        help="Only include candidates >= threshold (0-1)",
    )
    parser.add_argument(
        "--experimental-dead-code",
        action="store_true",
        help="Include experimental symbol-level dead-code candidates",
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
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    args = parser.parse_args(list(argv) if argv is not None else None)
    root = Path(args.path).resolve()
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Path does not exist or is not a directory: {root}")

    if args.one_run:
        print("One-run mode: using safe defaults and dry-run unless --apply is set.")
    if args.experimental_dead_code:
        print("Including experimental symbol-level dead-code analysis...")
    if args.apply and not args.yes:
        raise SystemExit("Refusing to apply without --yes confirmation.")
    threshold = args.confidence_threshold
    if threshold is None:
        threshold = 0.65 if args.one_run else 0.4

    excludes = list(args.exclude)
    if args.one_run:
        excludes.extend(
            [
                "tests/**",
                "docs/**",
                "examples/**",
                ".github/**",
                ".devcontainer/**",
                "**/*.md",
                "**/*.rst",
            ]
        )

    from prune.analyzer import analyze, write_plan

    plan = analyze(
        root=root,
        include=args.include,
        exclude=excludes,
        confidence_threshold=threshold,
        dead_code=args.experimental_dead_code,
    )
    write_plan(root, plan)

    if args.apply:
        apply_plan(root, plan, threshold)
        print(f"Moved files to trash under {root}")
    else:
        print(f"Dry-run complete. Plans written to {root}")
    return 0


def apply_plan(root: Path, plan: Plan, confidence_threshold: float) -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    trash_dir_name = f"._trash_{timestamp}"
    trash_root = root / trash_dir_name
    trash_root.mkdir(parents=True, exist_ok=True)

    undo_lines = [
        "#!/bin/sh",
        "set -eu",
        'ROOT="$(cd "$(dirname "$0")" && pwd)"',
        f'TRASH_DIR="$ROOT/{trash_dir_name}"',
        'if [ ! -d "$TRASH_DIR" ]; then',
        '  echo "Trash directory missing: $TRASH_DIR" >&2',
        "  exit 1",
        "fi",
    ]
    moved: set[str] = set()
    moved_rows: list[dict[str, str]] = []

    for candidate in plan.candidates:
        if candidate.kind != "file" or candidate.action != "delete":
            continue
        if candidate.path in moved:
            continue
        rel_path = candidate.path
        src = root / rel_path
        if not src.exists():
            continue
        dst = trash_root / rel_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        os.replace(src, dst)
        parent = Path(rel_path).parent
        if parent != Path("."):
            undo_lines.append(f'mkdir -p "$ROOT"/{shlex.quote(parent.as_posix())}')
        undo_lines.append(
            f'mv "$TRASH_DIR"/{shlex.quote(rel_path)} "$ROOT"/{shlex.quote(rel_path)}'
        )
        moved.add(rel_path)
        moved_rows.append(
            {
                "old": src.as_posix(),
                "new": dst.as_posix(),
                "reason": candidate.reason,
                "confidence": f"{candidate.confidence:.2f}",
            }
        )

    undo_path = root / "undo.sh"
    undo_contents = "\n".join(undo_lines) + "\n"
    undo_path.write_text(undo_contents)
    undo_path.chmod(0o700)
    trash_undo_path = trash_root / "undo.sh"
    trash_undo_path.write_text(undo_contents)
    trash_undo_path.chmod(0o700)

    closure_path = root / "CLOSURE.md"
    closure_path.write_text(
        _render_closure(
            timestamp=timestamp,
            root=root,
            confidence_threshold=confidence_threshold,
            trash_root=trash_root,
            undo_path=undo_path,
            moved_rows=moved_rows,
        )
    )


def _render_closure(
    timestamp: str,
    root: Path,
    confidence_threshold: float,
    trash_root: Path,
    undo_path: Path,
    moved_rows: list[dict[str, str]],
) -> str:
    lines = [
        "# CLOSURE",
        "",
        "Apply mode completed. Review this file before deleting the trash directory.",
        "",
        f"Timestamp: {timestamp}",
        f"Root: {root}",
        f"Confidence threshold: {confidence_threshold:.2f}",
        f"Trash directory: {trash_root}",
        f"Undo script: {undo_path}",
        "",
        "## Moved files",
    ]
    if not moved_rows:
        lines.append("- (none)")
    else:
        for row in moved_rows:
            lines.append(
                f"- {row['old']} -> {row['new']} "
                f"(reason={row['reason']}, confidence={row['confidence']})"
            )
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
