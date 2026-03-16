# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog.

## Unreleased

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
