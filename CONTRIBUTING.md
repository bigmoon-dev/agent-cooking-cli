# Contributing

Thanks for your interest in contributing.

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m triageflow acceptance run
```

## Sign-off (DCO)

By contributing, you agree that your contributions are licensed under the
Apache-2.0 license of this repository.

Please sign your commits with `Signed-off-by` (Developer Certificate of Origin):

```bash
git commit -s -m "your message"
```

## Notes

- Keep changes evidence-first: add or update acceptance cases for behavior.
- Avoid adding new commands unless a workflow case requires it.
