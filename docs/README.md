# Documentation

Start here:

- `install.md`: installation options
- `testing.md`: tests and coverage

## Developer Notes

Most CLI behavior lives in small modules under `src/triageflow/`.

- `cli.py`: Typer app wiring + thin command shells
- `evidence.py`: evidence capture/index helpers
- `rounds.py`: profile-driven rounds and deprecated round commands
- `navigator.py`: `next` decision logic
- `validate.py` + `validate_rules.py`: evidence gating and validation rules
- `acceptance/runner.py`: YAML-driven acceptance test runner
