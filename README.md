# agent-cooking-cli

[![CI](https://github.com/bigmoon-dev/agent-cooking-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/bigmoon-dev/agent-cooking-cli/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-31%25-yellow)](docs/testing.md)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

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
python -m triageflow --help
```

### Editable install (dev)

```bash
python -m pip install -e .
python -m triageflow --help
```

The console entry point is `kitchen`, but `python -m triageflow ...` is the most reliable way to run.

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

### MVP Script (Copy/Paste)

This script runs the smallest end-to-end flow non-interactively:

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

printf "mixed\nn\nunknown\nunknown\nunknown\nunknown\n\n" | \
  python -m triageflow round run 1 --no-editor

python -m triageflow evidence add-log \
  --log-path "$TRIAGEFLOW_ROOT/uart.log" \
  --pattern "panic" --before 1 --after 2 --max-matches 1 \
  --note "panic window"

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

## For Agents

See `AGENTS.md`.

## Developer

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m triageflow acceptance run
```
