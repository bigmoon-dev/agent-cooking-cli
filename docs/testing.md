# Testing

## Unit tests

```bash
python -m pytest -q
```

## Acceptance suite

```bash
python -m triageflow acceptance run
```

## Coverage

Current coverage target is informational. Coverage requires `pytest-cov`.

```bash
python -m pytest -q --cov=triageflow --cov-report=term-missing
```
