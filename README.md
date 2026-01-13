# prune

![PRUNE demo](assets/demo.gif)
**Prebuilt download (supports development):** https://moderqtor.gumroad.com/l/prune

Local-first CLI that analyzes a project directory and produces a safe, reviewable deletion plan
for likely-unused files, dead code, and redundant artifacts.

## What it does
- Walks a project directory and builds a file map
- Applies static heuristics (imports, text references, duplicate hashes, orphan configs, experiments)
- Scores each candidate with a confidence (0-1)
- Writes `deletion_plan.json`, `deletion_plan.md`, and `deletion_plan.diff`
- Optionally moves files to a timestamped `._trash_YYYYMMDD_HHMMSS/` and writes `undo.sh`

## Safety model
- Default is dry-run
- Apply mode moves files (no deletes) and generates a reversible undo script
- No network access, no external services

## Install (editable)
```
pip install -e .
```

## Usage
```
prune --path /path/to/project
prune --path . --confidence-threshold 0.7
prune --path . --apply --yes
prune --path . --one-run
```

Flags:
- `--path`: target directory (default: current directory)
- `--dry-run`: default, generates plans without moving files
- `--apply`: move eligible files to `._trash_TIMESTAMP/` and create `undo.sh`
- `--yes`: required confirmation for `--apply`
- `--confidence-threshold`: only include candidates >= threshold (default: 0.4)
- `--include`: repeatable glob to include (relative to `--path`)
- `--exclude`: repeatable glob to exclude (relative to `--path`)
- `--one-run`: safer defaults for a single run (threshold 0.65) and banner
- `--version`: print the version and exit

## Outputs
- `deletion_plan.json`: structured results for tooling
- `deletion_plan.md`: human-readable plan with warnings
- `deletion_plan.diff`: unified diff preview of file removals
- `undo.sh`: only in apply mode; stored inside the trash directory
- `CLOSURE.md`: written after apply with a full move manifest

## Undo
After `--apply`, run the generated script:
```
./._trash_YYYYMMDD_HHMMSS/undo.sh
```

## Testing
```
pytest
```

## Notes
This tool is conservative. Anything flagged still requires review.
