#!/usr/bin/env bash
set -euo pipefail

root_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
version=$(python - <<'PY'
from __future__ import annotations

import pathlib
import sys

root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
from prune import __version__

print(__version__)
PY
)

output_dir="$root_dir/gumroad_upload"
mkdir -p "$output_dir"
zip_path="$output_dir/prune-$version.zip"

cd "$root_dir"
zip -r "$zip_path" \
  README.md \
  LICENSE \
  pyproject.toml \
  src \
  tests \
  .github \
  RELEASE_NOTES.md \
  CHANGELOG.md \
  -x "*/__pycache__/*" \
  "*/.pytest_cache/*" \
  "*/.mypy_cache/*" \
  "*/.ruff_cache/*" \
  "*/dist/*" \
  "*/build/*" \
  "*/.venv/*" \
  "*/venv/*" \
  "*/.git/*" \
  "*/gumroad_upload/*" \
  "*/._trash_*/*" \
  "*/deletion_plan.*" \
  "*/CLOSURE.md"

echo "Wrote $zip_path"
