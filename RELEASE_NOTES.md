# Release Notes

## Unreleased

### Summary
This release makes dead-code scanning explicitly opt-in, lowers default thresholds back to the
conservative baseline, cleans packaging, and adds CI/tests for the new behavior.

### Behavior changes
- `--experimental-dead-code` now gates symbol-level dead-code candidates and prints a notice when
  enabled.
- Default confidence threshold is 0.4; `--one-run` uses 0.65.
- Plan summaries now record `dead_code` and the chosen `confidence_threshold` in outputs.

### Structural changes
- Experimental dead-code logic lives in `src/prune/experimental/dead_code.py` with a clear module
  boundary.
- Analyzer and CLI parameter naming now uses `dead_code` for clarity.

### Packaging and release
- Hatch build excludes venvs, caches, and local artifacts to avoid symlink errors.
- Added a release zip script under `gumroad_upload/`.

### Documentation and housekeeping
- Updated README installation and flag documentation for the new default thresholds.
- Cleaned `.gitignore` entries for builds, envs, plans, and release zips.

### Testing and CI
- Added fixture-based analyzer coverage and a dead-code flag comparison test.
- CI now runs ruff and pytest on Python 3.11 and 3.12.
