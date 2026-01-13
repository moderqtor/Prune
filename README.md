# prune

![PRUNE demo](assets/demo.gif)

**Prebuilt download (recommended):** https://moderqtor.gumroad.com/l/prune

Local-first CLI that analyzes a project directory and produces a safe, reviewable deletion plan
for likely-unused files, dead code, and redundant artifacts.

## What it does
- Walks a project directory and builds a file map
- Applies static heuristics (imports, text references, duplicate hashes, orphan configs, experiments)
- Scores each candidate with a confidence (0–1)
- Writes `deletion_plan.json`, `deletion_plan.md`, and `deletion_plan.diff`
- Optionally moves files to a timestamped `._trash_YYYYMMDD_HHMMSS/` and writes `undo.sh`

## Safety model
- Default is dry-run
- Apply mode moves files (no deletes) and generates a reversible undo script
- No network access, no external services

## Install (recommended)

PRUNE is a CLI application. To avoid breaking system Python (PEP 668),
the recommended installation method is **pipx**.

### macOS / Linux

Install pipx once:

```bash
brew install pipx
pipx ensurepath
````

Install PRUNE:

```bash
pipx install prune-0.1.0-py3-none-any.whl
```

> The wheel is provided via Gumroad until PyPI release.

## Developer install (editable)

```bash
git clone https://github.com/moderqtor/Prune.git
cd Prune
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Usage

```bash
prune --path /path/to/project
prune --path . --confidence-threshold 0.7
prune --path . --apply --yes
prune --path . --one-run
```

### Flags

* `--path`: target directory (default: current directory)
* `--dry-run`: default, generates plans without moving files
* `--apply`: move eligible files to `._trash_TIMESTAMP/` and create `undo.sh`
* `--yes`: required confirmation for `--apply`
* `--confidence-threshold`: only include candidates >= threshold (default: 0.4)
* `--include`: repeatable glob to include (relative to `--path`)
* `--exclude`: repeatable glob to exclude (relative to `--path`)
* `--one-run`: safer defaults for a single run (threshold 0.65) and banner
* `--version`: print the version and exit

## Outputs

* `deletion_plan.json`: structured results for tooling
* `deletion_plan.md`: human-readable plan with warnings
* `deletion_plan.diff`: unified diff preview of file removals
* `undo.sh`: only in apply mode; stored inside the trash directory
* `CLOSURE.md`: written after apply with a full move manifest

## Undo

After `--apply`, run the generated script:

```bash
./._trash_YYYYMMDD_HHMMSS/undo.sh
```

## Testing

```bash
pytest
```

## Notes

This tool is conservative. Anything flagged still requires review.
