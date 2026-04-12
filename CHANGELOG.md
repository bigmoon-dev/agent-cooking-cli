# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog.

## Unreleased

## 0.1.6 - 2026-04-12

### Fixed
- `dump_yaml` now uses atomic writes (`atomic_write_text`) to prevent `case.yaml` corruption when the process is interrupted mid-write.
- `dump_yaml` now uses `allow_unicode=True` so CJK characters are written correctly instead of being escaped to `\uXXXX`.
- `validate`: banned-word detection now uses word-boundary regex (`\b`) for ASCII words, eliminating false positives (e.g. "shoulder" no longer triggers "should").
- `validate`: removed early `break` in banned-word and fact-citation loops — all errors are now reported in a single pass instead of stopping after the first.
- `validate`: template block exemption is now based on empty content fields (`Hypothesis: `, `Direction: `) instead of matching by ID (`H001`, `DIR-1`), so user-created H001/DIR-1 entries are correctly validated.
- `split_blocks` now preserves the file preamble (header and rules text) as `blocks[0]`, fixing a bug where `prune_directions` and `close_hypothesis` permanently deleted the `# Directions` / `# Hypotheses` header and rules.
- `load_yaml` now raises a clear `typer.BadParameter` on corrupt YAML instead of silently returning an empty dict.
- `workspace_lock`: when the lock file PID is unparseable (empty/corrupt), stale detection now checks mtime age instead of unconditionally deleting the lock.
- `workspace_lock`: lock file cleanup now catches `OSError` (not just `FileNotFoundError`), preventing orphaned lock files on permission errors.
- Removed dead code: impossible `if path is None` branch in `profile.py` after a `Path / str` operation.

### Added
- `set_profile_loader()` / `get_profile_loader()` API in `profile.py` for downstream code to register custom profile loaders without monkey-patching.
- `navigator.print_next()` now respects `workflow_state.yaml` active phase — recommends `validate` when workspace is in implement/review/deliver/validate phase.
- 27 new tests: `test_navigator.py` (12), `test_directions_build.py` (8), `test_workspace_lock.py` (7). Test count 31 → 58.
- CI: `bandit` (SAST) and `pip-audit` (dependency audit) security scanning.

### Changed
- CI: all GitHub Actions pinned to immutable commit SHAs instead of mutable tags.
- CI: release workflow now requires CI to pass before publishing (`needs: ci` gate).
- CI: release build uses isolated environment (removed `--no-isolation` flag).

## 0.1.5 - 2026-03-26

### Added
- Event hook system: `register_hook()`, `emit()`, `set_hook_error_handler()` for enterprise extensions.
- Events emitted: `evidence.added`, `validate.passed`, `validate.failed`, `fact.added`, `hypothesis.added`, `hypothesis.closed`.
- Unit tests for the hook system in `tests/test_hooks.py`.

### Fixed
- `set_fact()` now uses atomic writes to prevent partial file corruption.
- `close_hypothesis()` now uses atomic writes for consistency.

### Changed
- `evidence.added` now fires outside the workspace lock to avoid blocking concurrent writes.

## 0.1.4 - 2026-03-17

### Changed
- Docs: improve first-run MVP experience (English + Chinese) with 5-minute walkthroughs and quickstart guides.

### Changed
- Packaging: unify build/release metadata under `pyproject.toml` and remove stale build artifacts.

### Fixed
- Evidence writes: add atomic file writes and a lightweight lock to reduce EID allocation races and partial evidence/index updates.

### Changed
- Refactor: move markdown block helpers and facts/hypotheses/directions operations out of `cli.py`.

### Changed
- Docs: improve first-run MVP experience with a 5-minute walkthrough and quickstart guide.

## 0.1.3 - 2026-03-17

### Changed
- Refactor: split the large CLI implementation into focused modules (evidence, rounds, navigation, validation, acceptance runner) while preserving behavior.

## 0.1.2 - 2026-03-16

### Added
- Agent entry docs: `AGENTS.md`, `CLAUDE.md`, `skill.md`.
- Documentation entrypoint under `docs/`.

### Changed
- Testing docs and dev dependencies aligned (coverage requires `pytest-cov`).
- README badges and MVP documentation improved.

## 0.1.1 - 2026-03-16

### Fixed
- Prevent template placeholders from affecting the MVP flow ("next" guidance and direction selection).

### Added
- README MVP copy/paste script for an end-to-end embedded demo.
- README language link polish.

## 0.1.0 - 2026-03-16

### Added
- Profiles (workflow recipes):
  - `embedded_system_v1` for embedded/system triage (stability/power/bt/charging), UART-first.
  - `design_system_v1` for software design decisions.
  - `product_definition_v1` for product definition decisions.
- Profile-driven execution:
  - `round run <id>` executes profile-defined rounds.
  - `--no-editor` supports fully non-interactive runs.
- Evidence-first workspace under `triage/`:
  - Evidence registry with EIDs (`evidence/index.md` and `evidence/*/E###_*.txt`).
  - `evidence add-log` supports context capture, multi-pattern OR, line range, and max-matches.
  - `evidence add-text` for generic text evidence (design/product workflows).
- Hard gates:
  - `validate` enforces evidence citations (facts/hypotheses/directions) and blocks missing evidence files.
- Direction filtering:
  - `direction-build` generates top directions from evidence-backed hypotheses with deterministic ordering.
- State machine navigation:
  - `next` prints the recommended next command based on workspace state.
- Developer workflow:
  - YAML-driven acceptance suite (`python -m triageflow acceptance run`).
  - Unit tests (`pytest`).
  - CI workflow to run tests on GitHub.
