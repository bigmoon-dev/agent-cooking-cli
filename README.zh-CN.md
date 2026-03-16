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

## 快速开始（嵌入式/系统）

选择一个工作区根目录（建议放在代码仓库外）：

```bash
export TRIAGEFLOW_ROOT=/path/to/workspace
python -m triageflow init --profile embedded_system_v1

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
