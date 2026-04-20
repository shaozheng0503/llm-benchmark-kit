# Contributing

欢迎贡献！下面是本仓库的工作方式，请先读一遍再提 PR。

## 本地开发

```bash
git clone https://github.com/shaozheng0503/llm-benchmark-kit.git
cd llm-benchmark-kit
python3 -m pip install -e ".[dev]"
cp .env.example .env    # 填入真实的 LLM_API_BASE / LLM_API_KEY
```

常用命令（都在 `Makefile` 里）：

```bash
make lint          # ruff check
make format        # ruff format + --fix
make test          # pytest
make cases         # 对 $TARGET_MODELS 跑能力测试
make full          # discover → cases → stress → authenticity → summary
```

## 代码风格

- Python 3.10+，一律用 `from __future__ import annotations`
- 走 `ruff check` + `ruff format`，配置在 [`pyproject.toml`](pyproject.toml)
- 导入排序由 ruff (isort 规则) 自动处理
- `scripts/legacy/` 是历史快照，被额外放宽了若干 ruff 规则；新功能请放到 `scripts/` 根下

## 提交 PR 前的自检

| 检查 | 命令 |
|------|------|
| lint | `make lint` |
| format | `ruff format --check .` |
| tests | `make test` |

启用 GitHub Actions CI：把 [`docs/ci-sample/github-actions.yml`](docs/ci-sample/github-actions.yml) 复制到 `.github/workflows/ci.yml`，CI 会在 Python 3.10 / 3.11 / 3.12 下并行跑上述三项。推送 workflow 文件需要 OAuth token 带 `workflow` scope，先跑一次 `gh auth refresh -s workflow` 即可。

## 常见改动指引

| 目标 | 改哪里 |
|------|--------|
| 新增测试用例 | [`config/test_cases.json`](config/test_cases.json) |
| 新增压测档位 | [`scripts/run_stress.py`](scripts/run_stress.py) 里的 `TIER_CONFIG` |
| 新增真伪判据 | [`scripts/run_authenticity.py`](scripts/run_authenticity.py) 的 `run_model_checks` |
| 新增厂商识别 | `EXPECTED_MODEL_SIGNALS` + `normalize_vendor_signal` |
| 改报告样式 | 对应脚本里的 `build_markdown` |
| 架构整体 | [`docs/architecture.md`](docs/architecture.md) |

## 敏感信息

**严禁**在代码或测试用例中提交：

- 真实 API Key / token
- 带有真实用户隐私数据的 prompt
- 绝对路径（形如 `/Users/<name>/...` 或 `/home/<name>/...`）

`.gitignore` 已屏蔽 `.env`、`reports/*`、`data/raw/*`；提交前请再手工 `git diff` 一遍。

## 报告 bug

请在 [Issues](https://github.com/shaozheng0503/llm-benchmark-kit/issues) 里附上：

1. 使用的脚本名
2. 命令行参数
3. Python 版本 (`python3 --version`) 与依赖版本 (`pip show openai httpx`)
4. 复现步骤（注意抹掉真实 Key）
5. 报错信息或异常 traceback

## 许可证

提交即同意以 [MIT](LICENSE) 协议授权你的贡献。
