# agent-cooking-cli

[![CI](https://github.com/bigmoon-dev/agent-cooking-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/bigmoon-dev/agent-cooking-cli/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-66%25-yellow)](docs/testing.md)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Lint: ruff](https://img.shields.io/badge/lint-ruff-black.svg)](https://github.com/astral-sh/ruff)

Evidence-first workflows for agents. Generate a workspace, then execute steps with auditable artifacts.

[中文版 README](README.zh-CN.md)

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

### pipx (recommended)

```bash
pipx install git+https://github.com/bigmoon-dev/agent-cooking-cli.git
kitchen --help
```

### Editable install (dev)

```bash
python -m pip install -e .
python -m triageflow --help
```

The console entry point is `kitchen`, but `python -m triageflow ...` is the most reliable way to run.

## 5-Minute MVP

This is the fastest verified path to experience the full workflow from install to a validated result.

What you will do:

1. Create a triage workspace
2. Attach a small UART log
3. Capture one evidence item (`E001`)
4. Add one fact backed by evidence
5. Add one hypothesis backed by evidence
6. Build one direction
7. Validate the workspace

When it succeeds, you will have a complete `triage/` folder with evidence and decision artifacts on disk.

### Run It

```bash
python3 -m pip install -e .
export TRIAGEFLOW_ROOT=/tmp/triageflow-mvp
rm -rf "$TRIAGEFLOW_ROOT"
mkdir -p "$TRIAGEFLOW_ROOT"

cat > "$TRIAGEFLOW_ROOT/uart.log" <<'EOF'
boot
panic: watchdog
stack: ...
reboot
EOF

python3 -m triageflow start --profile embedded_system_v1

printf "mvp reboot\naffects all\nfw-mvp\nhw-mvp\nopen lid, pair, wait\nnow\n" | \
  python3 -m triageflow round run 0 --no-editor

printf "mixed\nn\nunknown\nunknown\nunknown\nunknown\npanic\n" | \
  python3 -m triageflow round run 1 --no-editor

python3 -m triageflow evidence attach --uart-log "$TRIAGEFLOW_ROOT/uart.log"
python3 -m triageflow evidence hunt

python3 -m triageflow facts add \
  --text "panic observed during flow" \
  --evidence E001

python3 -m triageflow hypotheses add \
  --hypothesis "watchdog reset triggers reboot" \
  --evidence E001 \
  --test "print reset cause / wdt reason"

python3 -m triageflow direction-build --overwrite --top-n 1
python3 -m triageflow validate
python3 -m triageflow status
python3 -m triageflow next
```

Expected Result

You should see output like:

- Initialized .../triage
- Next: round run 0
- Added E001: .../triage/evidence/log/E001_log.txt
- Added F... to .../triage/facts.md
- Added H... to .../triage/hypotheses.md
- Wrote .../triage/directions.md (1 directions)
- OK: validation passed
- Next: validate

Files You Should See

After the MVP completes, these files should exist:

- $TRIAGEFLOW_ROOT/triage/profile.yaml
- $TRIAGEFLOW_ROOT/triage/case.yaml
- $TRIAGEFLOW_ROOT/triage/evidence/index.md
- $TRIAGEFLOW_ROOT/triage/evidence/log/E001_log.txt
- $TRIAGEFLOW_ROOT/triage/facts.md
- $TRIAGEFLOW_ROOT/triage/hypotheses.md
- $TRIAGEFLOW_ROOT/triage/directions.md

What You Just Proved

This MVP shows that triageflow can:

- persist a workspace on disk
- capture evidence with stable EIDs
- enforce evidence-backed facts and hypotheses
- generate directions from evidence-backed hypotheses
- validate the resulting workspace

If you want a more guided version of this flow, see `docs/quickstart.md`.

## Concepts

The triage workspace lives under `TRIAGEFLOW_ROOT/triage/` and is designed to be stable and reviewable.

Key idea: evidence first. Facts, hypotheses, and directions should cite evidence IDs.

## Quickstart (Embedded)

Pick a workspace root (outside your code repo) and run:

```bash
export TRIAGEFLOW_ROOT=/path/to/workspace
python -m triageflow start --profile embedded_system_v1

# Keep running this; it tells you the next command.
python -m triageflow next
```

If you want a minimal reproducible demo, create a small UART log:

```bash
cat > "$TRIAGEFLOW_ROOT/uart.log" <<'EOF'
boot
panic: watchdog
stack: ...
reboot
EOF
```

Then follow `next`.

### Legacy MVP Script (Deprecated)

This older script remains for reference. Prefer the 5-Minute MVP section above, or `docs/quickstart.md`.

```bash
export TRIAGEFLOW_ROOT=/path/to/workspace
rm -rf "$TRIAGEFLOW_ROOT/triage"
mkdir -p "$TRIAGEFLOW_ROOT"

cat > "$TRIAGEFLOW_ROOT/uart.log" <<'EOF'
boot
panic: watchdog
stack: ...
reboot
EOF

python -m triageflow init --profile embedded_system_v1

printf "mvp reboot\naffects all\nfw-mvp\nhw-mvp\nopen lid, pair, wait\nnow\n" | \
  python -m triageflow round run 0 --no-editor

printf "mixed\nn\nunknown\nunknown\nunknown\nunknown\npanic\n" | \
  python -m triageflow round run 1 --no-editor

python -m triageflow evidence attach --uart-log "$TRIAGEFLOW_ROOT/uart.log"
python -m triageflow evidence hunt

python -m triageflow facts add --text "panic observed during flow" --evidence E001
python -m triageflow hypotheses add \
  --hypothesis "watchdog reset triggers reboot" \
  --evidence E001 \
  --test "print reset cause / wdt reason"

python -m triageflow direction-build --overwrite --top-n 1
python -m triageflow validate
python -m triageflow status
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

## Expert Constraints (dianoia integration)

Use a [dianoia](https://github.com/bigmoon-dev/dianoia-ai) distilled expert profile to inject domain expertise into the workflow.
The expert profile acts as a continuous supervisor — its constraints apply to every decision throughout the workflow, not just during review.

```bash
kitchen init --profile design_system_v1 --expert ~/dianoia-experts/ai-product-architect
```

This generates a `CLAUDE.md` in the workspace root with all expert constraints grouped by domain layer (identity, goals, methods, values).
The AI agent reads these as authoritative guardrails: every hypothesis, direction, and decision must respect the expert's knowledge.

## For Agents

See `AGENTS.md`.

## Developer

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m triageflow acceptance run
```
