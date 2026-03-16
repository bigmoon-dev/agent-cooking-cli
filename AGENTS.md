# Agent Entry

This repository is designed to be operated by CLI agents (OpenCode / Claude Code / OpenClaw).

The workflow is evidence-first: decisions must be backed by artifacts saved to disk.

## Trigger

When asked to do triage/design/product work, start a workflow by selecting a profile:

- Embedded/system (stability/power/bt/charging): `embedded_system_v1`
- Software design decisions: `design_system_v1`
- Product definition decisions: `product_definition_v1`

## Golden Path

Use a workspace root outside the code repo:

```bash
export TRIAGEFLOW_ROOT=/path/to/workspace
python -m triageflow start --profile <profile_id>

# Repeat: it prints the recommended next command.
python -m triageflow next
```

## Hard Rules

- Do not rely on chat memory: state must be persisted under `TRIAGEFLOW_ROOT/triage/`.
- No guessing: any hypothesis or direction MUST cite evidence IDs (E###).
- Store evidence snippets under `triage/evidence/` via CLI commands.
- Prefer CLI writers over manual file edits:
  - `facts add`, `hypotheses add`, `direction-build`, `validate`.

Embedded hint:

- Capture UART evidence with `python -m triageflow evidence add-log ...`.

Design/product hint:

- Add document/notes evidence with `python -m triageflow evidence add-text ...`.

## Minimal Commands

- Status digest: `python -m triageflow status`
- Validate gates: `python -m triageflow validate`
- Acceptance (dev only): `python -m triageflow acceptance run`
