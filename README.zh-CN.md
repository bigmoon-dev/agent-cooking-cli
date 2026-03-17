# agent-cooking-cli

这是一个给 AI agent 使用的命令行工具：用“菜谱（workflow profile）”把复杂工作变成可执行的步骤，并把所有状态落盘到工作区，避免依赖聊天上下文。

English version: see `README.md`.

## 它解决什么问题

你先选择一个领域“菜谱”（profile），工具会在工作区里生成结构化产物，然后 agent 按步骤执行。

工作区默认位于 `TRIAGEFLOW_ROOT/triage/`，核心文件包括：

- `triage/case.yaml`：输入与上下文（只写事实，不写猜测）
- `triage/evidence/` + `triage/evidence/index.md`：证据片段与编号（E001, E002, ...）
- `triage/facts.md`：事实清单（每条必须引用 EID）
- `triage/hypotheses.md`：假设清单（每条必须引用 EID）
- `triage/directions.md`：问题方向 Top 1-3（每条必须引用 EID）

硬规则：没有证据（EID）就不能写假设/方向。

## 安装

开发安装（可编辑安装）：

```bash
python -m pip install -e .
python -m triageflow --help
```

也提供命令入口 `kitchen`，但最稳定的方式是使用 `python -m triageflow ...`。

## 5-Minute MVP

这是最快的、可验证的上手路径：从安装到得到一个可以通过 `validate` 的完整结果。

你将完成：

1. 创建一个 triage workspace
2. 绑定一个小的 UART log
3. 捕获一条证据（E001）
4. 添加一条由证据支持的事实
5. 添加一条由证据支持的假设
6. 生成一条 direction
7. 验证 workspace

成功后，你将得到一个完整的 `triage/` 目录，所有证据与决策产物都落盘。

### 运行

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

如果你想看更“讲解式”的版本，请看 `docs/quickstart.zh-CN.md`。

## 快速开始（嵌入式/系统）

选择一个工作区根目录（建议放在代码仓库外）：

```bash
export TRIAGEFLOW_ROOT=/path/to/workspace
python -m triageflow start --profile embedded_system_v1

# 反复运行 next，它会告诉你下一步该执行什么命令
python -m triageflow next
```

## Profiles（菜谱）

查看内置 profiles：

```bash
python -m triageflow profile list
```

当前内置：

- `embedded_system_v1`：稳定性/功耗/蓝牙/充电（UART 优先）
- `design_system_v1`：软件设计/架构决策
- `product_definition_v1`：产品定义/需求决策

## 开发与测试

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m triageflow acceptance run
```
