# feb	01ff009cb

fd9efdfeb	01ff009cb30735762feceb898c5230f972303ef	a8cbc1684 triage ed379c6847007ed3ef	760defdefdefb65	aa4002

b8362fe3a	996b21f7f528f0c0f3148f53	a8ce00ed3168d41a0b6845282371c6907684f0ce0d	700981f6014870bb8c16847dee4e0e982ff5002

## 6ee807

1e02086	49f185f0cf60c06f1af1a

- 21befae00e2ade5f5c33a
- ed1b9ae00e2ac0f684 UART log
- 355b7e00761bc136e
- dfb2a0e00761e8bb9e
- dfb2a0e00761047bbe
- 51f210e00761 direction
- 	a8cbc1700ec8ed379c

70040ef0cf60c062e5709e00e2a71fb9e684 `triage/` 587ef693943d6d182308c16d8002

## 24df6e761ef6

f60	7009801f1a

- Python 3.8+
- e00e2a shell 3af883
- df2ecf72872c730 check out 72ced3e93

## Step 1: b898c5

728ed3e938396eef5526784cf1a

```bash
python3 -m pip install -e .
```

86eba4 CLI 3ef528f1a

```bash
python3 -m triageflow --help
```

## Step 2: 1c6907de5f5c33a

	0092e9e00e2ae0d728ed3e93185684de5f5c33a6eef55f1a

```bash
export TRIAGEFLOW_ROOT=/tmp/triageflow-mvp
rm -rf "$TRIAGEFLOW_ROOT"
mkdir -p "$TRIAGEFLOW_ROOT"
```

fd9e2a6eef55f1ab5853e51f210684 `triage/` de5f5c33a48c93af8b log 587ef6002

## Step 3: 21befae00e2ac0f68493af8b log

21befae00e2a70960e86e931d25279f81684 UART logf1a

```bash
cat > "$TRIAGEFLOW_ROOT/uart.log" <<'EOF'
boot
panic: watchdog
stack: ...
reboot
EOF
```

## Step 4: f009cbd41a0b

f7f528d4c165f0f profile 21d9cb316de5f5c33af1a

```bash
python3 -m triageflow start --profile embedded_system_v1
```

	88471ff931fae2d30542bf1a

- Initialized .../triage
- Next: round run 0

## Step 5: b8c210 Round 0

3d0ea4700c11684848ef6f93165f08	75eea4e0df7f528 editorf09f1a

```bash
printf "mvp reboot\naffects all\nfw-mvp\nhw-mvp\nopen lid, pair, wait\nnow\n" | \
  python3 -m triageflow round run 0 --no-editor
```

fd9f1a28af93165199165 `triage/case.yaml`002

## Step 6: b8c210 Round 1

3d0f9b700c11684bc136e3d13b0bbef6ef1a

```bash
printf "mixed\nn\nunknown\nunknown\nunknown\nunknown\npanic\n" | \
  python3 -m triageflow round run 1 --no-editor
```

fd9f1abb0f55 UART 6f8173bbef6e48c anchor keywords002

## Step 7: ed1b9a UART log

28ade5f5c33a48c93af8b log 587ef6173054d77765f1a

```bash
python3 -m triageflow evidence attach --uart-log "$TRIAGEFLOW_ROOT/uart.log"
```

	88471ff931faf1a

- Wrote .../triage/case.yaml

## Step 8: 355b7bc136e

f7f528 anchor keyword 1ea2a8355b7	ad8fe13f7684 log windowf1a

```bash
python3 -m triageflow evidence hunt
```

	88471ff931fa30542bc7bf3cf1a

- Added E001: .../triage/evidence/log/E001_log.txt
- Created evidence:
  - panic: E001

230fd9e00b65f0cde5177df2ecf7288c16d8e0a21befae86f60684b2ce00efdbc136eea7269002

## Step 9: dfb2a0e00761e8bb9e

21befae00761531 E001 52f301684e8bb9ef1a

```bash
python3 -m triageflow facts add \
  --text "panic observed during flow" \
  --evidence E001
```

	88471ff931faf1a

- Added F... to .../triage/facts.md

## Step 10: dfb2a0e00761047bbe

21befae0076153140ce00efdbc136e52f301684047bbef1a

```bash
python3 -m triageflow hypotheses add \
  --hypothesis "watchdog reset triggers reboot" \
  --evidence E001 \
  --test "print reset cause / wdt reason"
```

	88471ff931faf1a

- Added H... to .../triage/hypotheses.md

## Step 11: 51f210 Direction

ecebc136e52f301684047bbee2d51f210e00761700	ad8f18148ea7684 directionf1a

```bash
python3 -m triageflow direction-build --overwrite --top-n 1
```

	88471ff931faf1a

- Wrote .../triage/directions.md (1 directions)

## Step 12: 	a8cbc1de5f5c33a

	a8cbc1700ec8ed379cf1a

```bash
python3 -m triageflow validate
```

	88471ff931faf1a

- OK: validation passed

fd962f MVP 21029f684173	52efe13f7002

## Step 13: 7e570bed379c

c5593ae00efdcbeb80458981f1a

```bash
python3 -m triageflow status
```

be2	5eede51773a8350684e0be00b65f1a

```bash
python3 -m triageflow next
```

	88471f700ec8f931faf1a

- Next: validate

## f60e94be570b230684587ef6

b8c210 MVP 40ef0ce94be570b230f1a

- $TRIAGEFLOW_ROOT/triage/profile.yaml
- $TRIAGEFLOW_ROOT/triage/case.yaml
- $TRIAGEFLOW_ROOT/triage/evidence/index.md
- $TRIAGEFLOW_ROOT/triage/evidence/log/E001_log.txt
- $TRIAGEFLOW_ROOT/triage/facts.md
- $TRIAGEFLOW_ROOT/triage/hypotheses.md
- $TRIAGEFLOW_ROOT/triage/directions.md

## fd9e2a MVP bc160ee86ec0e48

f603b0728df2ecf	a8cbc1 triageflow 3efee5f1a

- 21befa3ef301e45684de5f5c33a
- ed1b9a916	0e8f93165230de5f5c33a
- 355b7bc136ee76528 EID f163f7
- f3a236e8bb9e48c047bbefc5	87b709bc136e52f301
- ecebc136e52f301684047bbee2d51f210 directions
- 	a8cbc1700ec8684 triage 2b6001

## Notes

- fd9efd quickstart f7f528 `embedded_system_v1` profile f0c6e0e3ab8368401cbc136ef1814801db63411d41a0b700e05670002
- 51f210684587ef63ef0fdfd830542be00e9ba2177f360f4db260023ea981 `validate` 	01afc7f0ce14f6021befa684bc136e52f301185bb9b58728f0cfd9c31e0df1af714cd	524 MVP002
- 98279c0f3	1cd90d	a8cbc1f0c220389de5f5c33a	1cd765f1a

```bash
rm -rf "$TRIAGEFLOW_ROOT/triage"
```

## e0be00b65

b8c210 quickstart 40ef0cf603efee5f1a

- 7e570b185f6e profiles:

```bash
python3 -m triageflow profile list
```

- 7e570bf5324dde5f5c33a458981:

```bash
python3 -m triageflow status
```

- fd084cf003d1005	a8c536528f8b:

```bash
python3 -m triageflow acceptance run
```
