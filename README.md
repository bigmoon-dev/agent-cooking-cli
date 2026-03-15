# agent-cooking-cli

"Workflow recipes" for agents: generate a workspace, then execute steps with evidence.

This package provides a `kitchen` CLI (entry point) and a `python -m triageflow ...`
module entry that create and maintain a `triage/` workspace:

- `triage/case.yaml` (inputs only; facts, not guesses)
- `triage/evidence/` (raw snippets; logs/code/cmd)
- `triage/evidence/index.md` (EID registry)
- `triage/facts.md` (facts only; each cites EIDs)
- `triage/hypotheses.md` (each hypothesis must cite EIDs)
- `triage/directions.md` (top directions; must cite EIDs)
- `triage/experiments.md`, `triage/excluded.md`

Install (dev):

```bash
python -m pip install -e /home/maxin/project/triageflow/triageflow
python -m triageflow --help
```

Typical flow:

```bash
export TRIAGEFLOW_ROOT=/home/maxin/project
python -m triageflow init --profile embedded_system_v1

# Then keep running this; it tells you the next command.
python -m triageflow next
```

Developer:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m triageflow acceptance run
```
