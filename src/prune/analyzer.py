from __future__ import annotations

import ast
import difflib
import fnmatch
import hashlib
import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from prune.models import Candidate, FileInfo, Plan

TEXT_EXTENSIONS = {
    ".py",
    ".md",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".ini",
    ".cfg",
    ".txt",
    ".rst",
    ".sh",
}
CONFIG_EXTENSIONS = {".toml", ".yaml", ".yml", ".json", ".ini", ".cfg"}
SCRIPT_EXTENSIONS = {".sh", ".bash", ".zsh"}
EXPERIMENT_DIRS = {"experiments", "scratch", "tmp", "old", "archive", "backup"}
DEFAULT_EXCLUDES = [
    ".git/**",
    ".venv/**",
    "__pycache__/**",
    ".pytest_cache/**",
    ".mypy_cache/**",
    ".ruff_cache/**",
    "._trash_*/**",
    "deletion_plan.json",
    "deletion_plan.md",
    "deletion_plan.diff",
]
MAX_TEXT_BYTES = 1_000_000


def analyze(
    root: Path,
    include: list[str],
    exclude: list[str],
    confidence_threshold: float,
) -> Plan:
    root = root.resolve()
    files = _collect_files(root, include, exclude)
    file_infos = [_file_info(root, path) for path in files]
    text_refs = _build_text_reference_index(file_infos)
    python_index = _build_python_index(file_infos)
    candidates: list[Candidate] = []

    candidates.extend(_find_duplicate_files(file_infos))
    candidates.extend(_find_unreferenced_files(file_infos, text_refs, python_index))
    candidates.extend(_find_orphan_configs(file_infos, text_refs))
    candidates.extend(_find_unused_scripts(file_infos, text_refs))
    candidates.extend(_find_experiment_artifacts(file_infos))
    candidates.extend(_find_dead_code(python_index))

    filtered = [c for c in candidates if c.confidence >= confidence_threshold]
    filtered.sort(key=lambda c: (c.kind, c.path, c.reason))

    summary = {
        "total_files": len(file_infos),
        "candidates": len(filtered),
        "by_reason": _summarize_by_reason(filtered),
        "confidence_threshold": confidence_threshold,
    }
    plan = Plan(
        root=str(root),
        generated_at=datetime.now(timezone.utc).isoformat() + "Z",
        candidates=filtered,
        summary=summary,
    )
    return plan


def write_plan(root: Path, plan: Plan) -> None:
    json_path = root / "deletion_plan.json"
    md_path = root / "deletion_plan.md"
    diff_path = root / "deletion_plan.diff"

    json_path.write_text(json.dumps(asdict(plan), indent=2, sort_keys=True))
    md_path.write_text(_render_markdown(plan))
    diff_path.write_text(_render_diff_preview(root, plan))


def _collect_files(root: Path, include: list[str], exclude: list[str]) -> list[Path]:
    exclude_patterns = DEFAULT_EXCLUDES + exclude
    results: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = Path(dirpath).relative_to(root).as_posix()
        if rel_dir != "." and _matches(rel_dir + "/", exclude_patterns):
            dirnames[:] = []
            continue
        for name in filenames:
            full_path = Path(dirpath) / name
            rel_path = full_path.relative_to(root).as_posix()
            if _matches(rel_path, exclude_patterns):
                continue
            if include and not _matches(rel_path, include):
                continue
            results.append(full_path)
    results.sort(key=lambda p: p.as_posix())
    return results


def _matches(path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def _file_info(root: Path, path: Path) -> FileInfo:
    stat = path.stat()
    return FileInfo(
        path=path,
        rel_path=path.relative_to(root).as_posix(),
        size=stat.st_size,
        mtime=stat.st_mtime,
        extension=path.suffix.lower(),
    )


def _build_text_reference_index(file_infos: list[FileInfo]) -> set[str]:
    text_files = [f for f in file_infos if f.extension in TEXT_EXTENSIONS]
    terms = set()
    for info in file_infos:
        terms.add(info.rel_path)
        terms.add(Path(info.rel_path).name)
    referenced: set[str] = set()
    for info in text_files:
        if info.size > MAX_TEXT_BYTES:
            continue
        try:
            content = info.path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for term in terms:
            if term in content:
                referenced.add(term)
    return referenced


def _build_python_index(file_infos: list[FileInfo]) -> dict[str, dict[str, object]]:
    modules: dict[str, Path] = {}
    module_relpaths: dict[str, str] = {}
    for info in file_infos:
        if info.extension != ".py":
            continue
        module_name = _module_name(info.rel_path)
        modules[module_name] = info.path
        module_relpaths[module_name] = info.rel_path
    imports: dict[str, set[str]] = {}
    module_metadata: dict[str, dict[str, object]] = {}

    for module, path in modules.items():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        collector = _ImportCollector(module)
        collector.visit(tree)
        imports[module] = collector.imports
        module_metadata[module] = {
            "path": path,
            "rel_path": module_relpaths.get(module, path.as_posix()),
            "is_script": collector.is_script,
            "exports": collector.exports,
            "defs": collector.defs,
            "used": collector.used,
        }
    referenced_modules: set[str] = set()
    for module, imported in imports.items():
        for name in imported:
            if name in modules:
                referenced_modules.add(name)
    return {
        "modules": modules,
        "referenced_modules": referenced_modules,
        "metadata": module_metadata,
    }


def _module_name(rel_path: str) -> str:
    path = Path(rel_path)
    parts = list(path.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


class _ImportCollector(ast.NodeVisitor):
    def __init__(self, module_name: str) -> None:
        self.module_name = module_name
        self.imports: set[str] = set()
        self.is_script = False
        self.exports: set[str] = set()
        self.defs: dict[str, int] = {}
        self.used: set[str] = set()

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        for alias in node.names:
            self.imports.add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        module = node.module or ""
        if node.level:
            module = self._resolve_relative(module, node.level)
        if module:
            self.imports.add(module)
        for alias in node.names:
            if module:
                self.imports.add(f"{module}.{alias.name}")
            else:
                self.imports.add(alias.name)
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:  # noqa: N802
        if isinstance(node.test, ast.Compare):
            left = node.test.left
            if (
                isinstance(left, ast.Name)
                and left.id == "__name__"
                and any(
                    isinstance(op, ast.Eq) for op in node.test.ops
                )
            ):
                for comparator in node.test.comparators:
                    if isinstance(comparator, ast.Constant) and comparator.value == "__main__":
                        self.is_script = True
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "__all__":
                self.exports.update(_extract_string_list(node.value))
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        self.defs[node.name] = node.lineno
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        self.defs[node.name] = node.lineno
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:  # noqa: N802
        if isinstance(node.ctx, ast.Load):
            self.used.add(node.id)
        self.generic_visit(node)

    def _resolve_relative(self, module: str, level: int) -> str:
        parts = self.module_name.split(".")
        if parts[-1] == "__init__":
            parts = parts[:-1]
        base = parts[:-level]
        suffix = module.split(".") if module else []
        return ".".join(base + suffix)


def _extract_string_list(node: ast.AST) -> set[str]:
    if isinstance(node, (ast.List, ast.Tuple)):
        values = []
        for elt in node.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                values.append(elt.value)
        return set(values)
    return set()


def _find_duplicate_files(file_infos: list[FileInfo]) -> list[Candidate]:
    hashes: dict[str, list[FileInfo]] = {}
    for info in file_infos:
        if info.size == 0:
            continue
        digest = _hash_file(info.path)
        hashes.setdefault(digest, []).append(info)
    candidates: list[Candidate] = []
    for digest, infos in hashes.items():
        if len(infos) < 2:
            continue
        infos_sorted = sorted(infos, key=lambda i: (len(i.rel_path), i.rel_path))
        keep = infos_sorted[0]
        for info in infos_sorted[1:]:
            candidates.append(
                Candidate(
                    kind="file",
                    action="delete",
                    path=info.rel_path,
                    reason="duplicate_file",
                    confidence=0.9,
                    details={"duplicate_of": keep.rel_path, "hash": digest},
                )
            )
    return candidates


def _hash_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _find_unreferenced_files(
    file_infos: list[FileInfo],
    text_refs: set[str],
    python_index: dict[str, dict[str, object]],
) -> list[Candidate]:
    referenced_modules = python_index.get("referenced_modules", set())
    metadata = python_index.get("metadata", {})
    candidates: list[Candidate] = []

    for info in file_infos:
        rel_path = info.rel_path
        if info.extension == ".py":
            module = _module_name(rel_path)
            module_meta = metadata.get(module, {})
            is_script = bool(module_meta.get("is_script"))
            if module not in referenced_modules and not is_script and not rel_path.endswith("__init__.py"):
                confidence = 0.65
                if any(part in EXPERIMENT_DIRS for part in Path(rel_path).parts):
                    confidence = 0.75
                candidates.append(
                    Candidate(
                        kind="file",
                        action="delete",
                        path=rel_path,
                        reason="unreferenced_python",
                        confidence=confidence,
                        details={"module": module},
                    )
                )
            continue

        if rel_path not in text_refs and Path(rel_path).name not in text_refs:
            confidence = 0.45
            if any(part in EXPERIMENT_DIRS for part in Path(rel_path).parts):
                confidence = 0.6
            candidates.append(
                Candidate(
                    kind="file",
                    action="delete",
                    path=rel_path,
                    reason="unreferenced_file",
                    confidence=confidence,
                    details={"extension": info.extension},
                )
            )
    return candidates


def _find_orphan_configs(
    file_infos: list[FileInfo],
    text_refs: set[str],
) -> list[Candidate]:
    candidates: list[Candidate] = []
    for info in file_infos:
        if info.extension not in CONFIG_EXTENSIONS:
            continue
        rel_path = info.rel_path
        if rel_path in text_refs or Path(rel_path).name in text_refs:
            continue
        candidates.append(
            Candidate(
                kind="file",
                action="delete",
                path=rel_path,
                reason="orphan_config",
                confidence=0.6,
                details={},
            )
        )
    return candidates


def _find_unused_scripts(
    file_infos: list[FileInfo],
    text_refs: set[str],
) -> list[Candidate]:
    candidates: list[Candidate] = []
    for info in file_infos:
        if info.extension not in SCRIPT_EXTENSIONS:
            continue
        rel_path = info.rel_path
        if rel_path in text_refs or Path(rel_path).name in text_refs:
            continue
        is_exec = os.access(info.path, os.X_OK)
        confidence = 0.5 if not is_exec else 0.4
        candidates.append(
            Candidate(
                kind="file",
                action="delete",
                path=rel_path,
                reason="unused_script",
                confidence=confidence,
                details={"executable": is_exec},
            )
        )
    return candidates


def _find_experiment_artifacts(file_infos: list[FileInfo]) -> list[Candidate]:
    candidates: list[Candidate] = []
    for info in file_infos:
        parts = set(Path(info.rel_path).parts)
        if not parts.intersection(EXPERIMENT_DIRS):
            continue
        candidates.append(
            Candidate(
                kind="file",
                action="delete",
                path=info.rel_path,
                reason="experiment_artifact",
                confidence=0.7,
                details={},
            )
        )
    return candidates


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


def _summarize_by_reason(candidates: list[Candidate]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for candidate in candidates:
        summary[candidate.reason] = summary.get(candidate.reason, 0) + 1
    return dict(sorted(summary.items()))


def _render_markdown(plan: Plan) -> str:
    lines = [
        "# Deletion Plan",
        "",
        "WARNING: This plan is conservative and requires review.",
        "Apply mode moves files into a trash directory and writes undo.sh.",
        "",
        f"Root: `{plan.root}`",
        f"Generated: `{plan.generated_at}`",
        f"Candidates: `{len(plan.candidates)}`",
        "",
        "## Summary",
    ]
    for reason, count in plan.summary.get("by_reason", {}).items():
        lines.append(f"- {reason}: {count}")
    lines.append("")
    lines.append("## Candidates")
    for candidate in plan.candidates:
        lines.append(
            f"- [{candidate.kind}] {candidate.path} ({candidate.reason}, "
            f"confidence={candidate.confidence:.2f})"
        )
        if candidate.details:
            details = ", ".join(f"{k}={v}" for k, v in candidate.details.items())
            lines.append(f"  - {details}")
    lines.append("")
    return "\n".join(lines)


def _render_diff_preview(root: Path, plan: Plan) -> str:
    lines: list[str] = []
    for candidate in plan.candidates:
        if candidate.kind != "file" or candidate.action != "delete":
            continue
        file_path = root / candidate.path
        if not file_path.exists():
            continue
        rel_path = candidate.path
        try:
            data = file_path.read_bytes()
        except OSError:
            continue
        if b"\x00" in data[:2048]:
            lines.extend([
                f"--- {rel_path}",
                "+++ /dev/null",
                "@@ -1 +0,0 @@",
                "-Binary file omitted",
                "",
            ])
            continue
        try:
            text = data.decode("utf-8", errors="ignore").splitlines()
        except UnicodeDecodeError:
            text = []
        diff = list(
            _unified_diff(text, fromfile=rel_path, tofile="/dev/null")
        )
        lines.extend(diff)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _unified_diff(lines: list[str], fromfile: str, tofile: str) -> Iterable[str]:
    return difflib.unified_diff(
        lines,
        [],
        fromfile=fromfile,
        tofile=tofile,
        lineterm="",
    )
