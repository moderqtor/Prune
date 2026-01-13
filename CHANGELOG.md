# Changelog

## 0.1.1
- Gate symbol-level dead-code scanning behind `--experimental-dead-code` with a CLI notice.
- Restore default thresholds (0.4 default, 0.65 in `--one-run`) and record them in plan summaries.
- Write `undo.sh` at the apply root (and copy into the trash directory) for reliable restores.
- Improve packaging excludes, add release zip script, and extend CI/testing coverage.
