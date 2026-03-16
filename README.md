# agent-cooking-cli

Evidence-first workflows for agents. Generate a workspace, then execute steps with auditable artifacts.

Language: English | (Chinese) see `README.zh-CN.md`.

## What It Does

`agent-cooking-cli` gives your agent a "recipe" (profile) and a persistent workspace so it can work without relying on chat memory.

The workspace lives under `TRIAGEFLOW_ROOT/triage/` and includes:

- `triage/case.yaml`: input and context (facts, not guesses)
- `triage/evidence/` + `triage/evidence/index.md`: evidence snippets with EIDs (E001, E002, ...)
- `triage/facts.md`: facts only (each cites EIDs)
- `triage/hypotheses.md`: hypotheses (must cite EIDs)
- `triage/directions.md`: top directions (must cite EIDs)

Hard rule: no evidence -> no hypothesis/direction.

## Install

For local development:

```bash
python -m pip install -e .
python -m triageflow --help
```

The console entry point is `kitchen`, but `python -m triageflow ...` is the most reliable way to run.

## Quickstart (Embedded)

Pick a workspace root (outside your code repo) and run:

```bash
export TRIAGEFLOW_ROOT=/path/to/workspace
python -m triageflow init --profile embedded_system_v1

# Keep running this; it tells you the next command.
python -m triageflow next
```

## Profiles

List built-in profiles:

```bash
python -m triageflow profile list
```

Current profiles:

- `embedded_system_v1`: stability/power/bt/charging (UART-first)
- `design_system_v1`: software design decisions
- `product_definition_v1`: product definition decisions

## Developer

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m triageflow acceptance run
```
