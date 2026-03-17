# Quickstart

This quickstart is the shortest reliable path from installation to a validated triage result.
It is designed for first-time users who want to experience the workflow before learning all commands and concepts.

## Goal

In a few minutes, you will:

- create a workspace
- attach a small UART log
- capture one evidence item
- add one fact
- add one hypothesis
- build one direction
- validate the final result

At the end, you will have a real `triage/` folder on disk.

## Prerequisites

You need:

- Python 3.8+
- a shell environment
- the repository checked out locally

## Step 1: Install

From the repository root:

```bash
python3 -m pip install -e .
```

Verify the CLI is available:

```bash
python3 -m triageflow --help
```

## Step 2: Prepare a Workspace

Choose a workspace directory outside the repo:

```bash
export TRIAGEFLOW_ROOT=/tmp/triageflow-mvp
rm -rf "$TRIAGEFLOW_ROOT"
mkdir -p "$TRIAGEFLOW_ROOT"
```

This directory will hold your generated triage/ workspace and sample log file.

## Step 3: Create a Small Demo Log

Create a tiny UART log with a clear failure signature:

```bash
cat > "$TRIAGEFLOW_ROOT/uart.log" <<'EOF'
boot
panic: watchdog
stack: ...
reboot
EOF
```

## Step 4: Start the Workflow

Initialize the workspace with the embedded triage profile:

```bash
python3 -m triageflow start --profile embedded_system_v1
```

Expected output includes:

- Initialized .../triage
- Next: round run 0

## Step 5: Complete Round 0

Provide the minimal case inputs non-interactively:

```bash
printf "mvp reboot\naffects all\nfw-mvp\nhw-mvp\nopen lid, pair, wait\nnow\n" | \
  python3 -m triageflow round run 0 --no-editor
```

This writes your case inputs into triage/case.yaml.

## Step 6: Complete Round 1

Provide the minimal evidence-discovery inputs:

```bash
printf "mixed\nn\nunknown\nunknown\nunknown\nunknown\npanic\n" | \
  python3 -m triageflow round run 1 --no-editor
```

This records UART-related setup and anchor keywords.

## Step 7: Attach the UART Log

Bind the workspace to the sample UART log:

```bash
python3 -m triageflow evidence attach --uart-log "$TRIAGEFLOW_ROOT/uart.log"
```

Expected output:

- Wrote .../triage/case.yaml

## Step 8: Capture Evidence

Use the anchor keyword to automatically capture a high-signal log window:

```bash
python3 -m triageflow evidence hunt
```

Expected output includes something like:

- Added E001: .../triage/evidence/log/E001_log.txt
- Created evidence:
  - panic: E001

At this point, the tool has created your first evidence artifact.

## Step 9: Add One Fact

Create one fact backed by the captured evidence:

```bash
python3 -m triageflow facts add \
  --text "panic observed during flow" \
  --evidence E001
```

Expected output:

- Added F... to .../triage/facts.md

## Step 10: Add One Hypothesis

Create one hypothesis backed by the same evidence:

```bash
python3 -m triageflow hypotheses add \
  --hypothesis "watchdog reset triggers reboot" \
  --evidence E001 \
  --test "print reset cause / wdt reason"
```

Expected output:

- Added H... to .../triage/hypotheses.md

## Step 11: Build a Direction

Generate one top direction from the evidence-backed hypothesis:

```bash
python3 -m triageflow direction-build --overwrite --top-n 1
```

Expected output:

- Wrote .../triage/directions.md (1 directions)

## Step 12: Validate the Workspace

Validate the workflow result:

```bash
python3 -m triageflow validate
```

Expected output:

- OK: validation passed

This is the key success signal for the MVP.

## Step 13: Inspect the Result

Show a compact digest:

```bash
python3 -m triageflow status
```

Ask the workflow for the recommended next step:

```bash
python3 -m triageflow next
```

Expected final output:

- Next: validate

## What You Should Have on Disk

After the MVP completes, you should see:

- $TRIAGEFLOW_ROOT/triage/profile.yaml
- $TRIAGEFLOW_ROOT/triage/case.yaml
- $TRIAGEFLOW_ROOT/triage/evidence/index.md
- $TRIAGEFLOW_ROOT/triage/evidence/log/E001_log.txt
- $TRIAGEFLOW_ROOT/triage/facts.md
- $TRIAGEFLOW_ROOT/triage/hypotheses.md
- $TRIAGEFLOW_ROOT/triage/directions.md

## What This MVP Demonstrates

You have now verified that triageflow can:

- create a persistent workspace
- attach external inputs to that workspace
- capture evidence as EIDs
- require evidence-backed facts and hypotheses
- generate directions from evidence-backed hypotheses
- validate the resulting triage state

## Notes

- This quickstart uses the embedded triage profile because it has the clearest evidence-first happy path.
- The generated files may still include template placeholders in addition to the new entries you created. That does not invalidate the MVP as long as validate passes and the evidence-backed entries are present.
- For repeated experiments, delete the workspace and start again:

```bash
rm -rf "$TRIAGEFLOW_ROOT/triage"
```

## Next Steps

After this quickstart, you can:

- explore built-in profiles:

```bash
python3 -m triageflow profile list
```

- inspect the active workspace:

```bash
python3 -m triageflow status
```

- run developer acceptance checks:

```bash
python3 -m triageflow acceptance run
```

- read the full README for additional usage patterns
