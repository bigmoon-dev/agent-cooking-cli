# agent-cooking-cli

Evidence-first workflow CLI for agents.

This skill drives work via a persistent on-disk workspace so the agent does not rely on chat memory.

## When To Trigger

Use this skill when the user asks you to:

- Triage/debug issues and narrow down directions
- Do software design/architecture decision work
- Do product definition / requirements work

Profile mapping:

- Embedded/system (stability/power/bt/charging): `embedded_system_v1`
- Software design decisions: `design_system_v1`
- Product definition decisions: `product_definition_v1`

## How To Run (Golden Path)

1) Pick a workspace root outside the code repo:

```bash
export TRIAGEFLOW_ROOT=/path/to/workspace
```

2) Initialize a workflow:

```bash
python -m triageflow start --profile <profile_id>
```

3) Always drive the session by `next`:

```bash
python -m triageflow next
```

Repeat `next` until you reach `validate`.

## Hard Rules

- No guessing: hypotheses/directions MUST cite evidence IDs (E###).
- Persist everything under `TRIAGEFLOW_ROOT/triage/`.
- Prefer CLI writers over manual edits:
  - `facts add`, `hypotheses add`, `direction-build`, `validate`.
- Keep chat output small: reference EIDs and use `python -m triageflow status`.

## Useful Commands

- List profiles: `python -m triageflow profile list`
- Show a profile: `python -m triageflow profile show <profile_id>`
- Validate profile: `python -m triageflow profile validate`
- Attach UART log (embedded): `python -m triageflow evidence attach --uart-log /path/to/uart.log`
- Add evidence (embedded): `python -m triageflow evidence add-log ...`
- Add evidence (design/product): `python -m triageflow evidence add-text ...`
- Status digest: `python -m triageflow status`
