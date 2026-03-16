# Install

## pipx (recommended)

```bash
pipx install git+https://github.com/bigmoon-dev/agent-cooking-cli.git
```

Run:

```bash
python -m triageflow --help
```

## Development (editable)

```bash
git clone https://github.com/bigmoon-dev/agent-cooking-cli.git
cd agent-cooking-cli
python -m pip install -e ".[dev]"
python -m triageflow acceptance run
```
