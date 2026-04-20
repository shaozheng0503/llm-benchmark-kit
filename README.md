# llm-benchmark-kit

> 面向 OpenAI 兼容 LLM API 网关的全景测试工具集，覆盖 **能力 → 并发 → 真伪 → 汇总** 四个阶段。
> 所有敏感配置通过环境变量注入，报告与原始数据默认不入库，可直接用于私有化或对外发布。

[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)
[![lint](https://img.shields.io/badge/lint-ruff-orange)](pyproject.toml)
[![tests](https://img.shields.io/badge/tests-pytest-blue)](tests/)

---

## 能做什么

| 场景 | 典型问题 | 对应脚本 |
|------|---------|----------|
| **模型发现** | 平台到底暴露了哪些模型 / 支持哪些端点？ | `scripts/discover_models.py` |
| **能力测试** | 这个模型在冒烟、结构化抽取、推理、代码、多轮、安全、流式上的通过率如何？ | `scripts/run_cases.py` |
| **并发压测** | 在不同并发档位下 RPS、P95、P99、TTFT、失败率是多少？ | `scripts/run_stress.py` |
| **真伪鉴别** | 聚合网关是不是在偷偷把我路由到别的模型？ | `scripts/run_authenticity.py` |
| **综合汇总** | 给我一份把三类结果合并的单页报告。 | `scripts/build_summary.py` |
| **预算压测** | 给定美元预算，自动评估各模型的吞吐 / 成本 / 稳定性。 | `scripts/legacy/budget_stress_test.py` |
| **综合能力（v1/v2）** | 跑一份包含推理、多轮、图像生成、流式的基础 / 专业总览报告。 | `scripts/legacy/basic_test.py`、`scripts/legacy/pro_test.py` |
| **跨厂商真伪** | 多维度探测身份伪装、提示词泄露、计费异常。 | `scripts/legacy/cross_vendor_authenticity.py` |
| **Responses API 调试** | 某个模型 /v1/responses 报错时逐策略定位。 | `scripts/legacy/debug_responses_api.py` |

所有脚本都是独立可执行的 Python 文件，OpenAI 兼容协议（`/v1/models`、`/v1/chat/completions`、`/v1/responses`），不依赖具体厂商 SDK。

---

## 快速开始

### 1. 准备环境

```bash
git clone https://github.com/shaozheng0503/llm-benchmark-kit.git
cd llm-benchmark-kit
python3 -m pip install -r requirements.txt
# 或者安装为可编辑包（包含 ruff / pytest 等 dev 工具）：
python3 -m pip install -e ".[dev]"
```

### 2. 配置密钥

```bash
cp .env.example .env
# 编辑 .env，填入 LLM_API_BASE / LLM_API_KEY / TARGET_MODELS
export $(grep -v '^#' .env | xargs)
```

或者直接导出：

```bash
export LLM_API_BASE="https://api.your-gateway.com"
export LLM_API_KEY="sk-your-key"
export TARGET_MODELS="gpt-4o-mini,claude-sonnet-4-5"
```

### 3. 典型流程

```bash
# 1) 拉取平台模型列表，落库到 data/raw/models_latest.json
python3 scripts/discover_models.py

# 2) 对 TARGET_MODELS 跑能力用例
python3 scripts/run_cases.py

# 3) 低档位并发压测
python3 scripts/run_stress.py --tiers low

# 4) 真伪鉴别
python3 scripts/run_authenticity.py

# 5) 汇总三类结果为单页报告
python3 scripts/build_summary.py
```

或者使用 `Makefile` 的一键入口：

```bash
make discover     # 步骤 1
make cases        # 步骤 2
make stress       # 步骤 3（低档位）
make authenticity # 步骤 4
make summary      # 步骤 5
make full         # 上述五步串行跑完
make help         # 查看全部可用任务
```

产物：`reports/cases/`、`reports/stress/`、`reports/authenticity/`、`reports/summary/`，每次都会同时输出 JSON 与 Markdown。

---

## 目录结构

```
llm-benchmark-kit/
├── README.md                      # 本文件
├── CONTRIBUTING.md                # 贡献指南
├── LICENSE                        # MIT
├── pyproject.toml                 # 包元数据 / ruff / pytest 配置
├── requirements.txt               # 运行时依赖
├── Makefile                       # 常用任务：install/cases/stress/lint/test/...
├── .env.example                   # 环境变量模板
├── .gitignore                     # 屏蔽 .env / reports / data 等
├── config/
│   └── test_cases.json            # 10 个能力测试用例定义
├── scripts/
│   ├── common.py                  # env var、HTTP/OpenAI client、报告 I/O 工具
│   ├── discover_models.py         # /v1/models 探测
│   ├── run_cases.py               # 能力测试主入口
│   ├── run_stress.py              # 分档位并发压测
│   ├── run_authenticity.py        # 真伪 / 身份稳定性
│   ├── build_summary.py           # 最近一次三类结果的合并报告
│   └── legacy/                    # 早期脚本（已脱敏、改 env var）
│       ├── basic_test.py          # v1 基础综合测试
│       ├── pro_test.py            # v2 专业综合测试（含 Responses API）
│       ├── budget_stress_test.py  # 预算驱动压测
│       ├── cross_vendor_authenticity.py  # 10 维度真伪鉴别
│       └── debug_responses_api.py # /v1/responses 兼容性调试
├── examples/
│   └── reports/                   # 脱敏后的样例报告
│       ├── cases_report_sample.md
│       ├── stress_report_sample.md
│       ├── authenticity_report_sample.md
│       └── summary_report_sample.md
├── docs/
│   ├── architecture.md            # 架构与扩展指南
│   └── ci-sample/github-actions.yml   # 可直接启用的 GitHub Actions 样例
├── tests/                         # pytest：用例配置校验 + 脚本 AST 解析
├── data/raw/                      # discover_models 落地的 models_latest.json
└── reports/                       # 运行时生成的报告与 JSON
    ├── cases/
    ├── stress/
    ├── authenticity/
    └── summary/
```

---

## 环境变量

| 变量 | 必填 | 默认 | 说明 |
|------|------|------|------|
| `LLM_API_BASE` | 是 | - | OpenAI 兼容网关的根地址，不含 `/v1` |
| `LLM_API_KEY` | 是 | - | Bearer Token |
| `TARGET_MODELS` | 否 | `gpt-4o-mini` | 以逗号分隔的默认目标模型 ID 列表 |
| `LLM_HTTP_TIMEOUT` | 否 | `180` | 单请求超时（秒） |
| `LLM_MAX_WORKERS` | 否 | `8` | 默认线程池并发 |
| `LLM_REPORT_DIR` | 否 | `<repo>/reports` | 报告输出根目录 |
| `DEBUG_MODEL` | 否 | `gpt-4o` | 仅 `debug_responses_api.py` 使用，指定要调试的模型 ID |

**密钥策略**：`.env` 与 `reports/*` 已在 `.gitignore` 中，CI 下可通过 Secret 注入；严禁在脚本内写任何真实 Key。

---

## 能力测试用例

见 `config/test_cases.json`，当前包含：

| id | 类别 | 检测项 |
|----|------|--------|
| `smoke_identity` | smoke | 模型身份自述 |
| `smoke_bilingual` | smoke | 中英双语生成 |
| `structured_extraction` | core | JSON 结构化抽取 + 字段校验 |
| `long_summary` | core | 长会议纪要总结 |
| `logic_reasoning` | complex | 真话/假话/随机者逻辑题 |
| `math_integral` | complex | 定积分 ∫₀¹ x²·eˣ dx |
| `code_generation` | complex | 线程安全 LRU Cache + 测试 |
| `multi_turn_context` | complex | 多轮上下文 + Mermaid 状态机 |
| `prompt_injection` | safety | 提示注入翻译任务 |
| `streaming_ttft` | boundary | 流式输出 + TTFT 测量 |

每条用例可配置 `min_length` / `should_include_any` / `should_include_all` / `should_not_include_any` / `json_required` + `json_keys` 等断言，扩展方式参考 `scripts/run_cases.py::evaluate_case`。

---

## 压测档位

`scripts/run_stress.py` 内置三档：

| 档位 | 并发 | 请求数 | max_tokens | 适用 |
|------|------|--------|------------|------|
| low | 5 | 10 | 128 | 冒烟压测，验证稳定性 |
| medium | 20 | 40 | 160 | 常规容量评估 |
| high | 30 | 90 | 192 | 高压峰值评估 |

`scripts/legacy/budget_stress_test.py` 则是另一种范式——按每个模型设定美元预算，持续发请求直到估算成本打满，适合做性价比评估。

---

## 真伪鉴别

`scripts/run_authenticity.py` 聚焦**身份稳定性**：身份自报、反向诱导、system prompt 泄露、双调用一致性、并发一致性。
`scripts/legacy/cross_vendor_authenticity.py` 是早期的增强版本，覆盖 10+ 个维度（含知识截止、风格指纹、Token 计费异常、跨模型雷同、并发身份稳定性等）。

输出三档结论：

- `LIKELY_GENUINE`：全量通过，高度匹配预期厂商家族
- `NEEDS_REVIEW`：1-2 个异常，需人工核查
- `HIGH_RISK`：3+ 异常，高度怀疑为冒充/代理

---

## 样例报告

无需部署即可在 [`examples/reports/`](examples/reports/) 查看：

- [cases_report_sample.md](examples/reports/cases_report_sample.md) — 能力测试
- [stress_report_sample.md](examples/reports/stress_report_sample.md) — 并发压测
- [authenticity_report_sample.md](examples/reports/authenticity_report_sample.md) — 真伪鉴别
- [summary_report_sample.md](examples/reports/summary_report_sample.md) — 综合汇总

---

## 开发与贡献

```bash
python3 -m pip install -e ".[dev]"
make lint            # ruff check
make format          # ruff format + --fix
make test            # pytest (27 项)
make help            # 查看所有可用任务
```

想启用 GitHub Actions CI：把 `docs/ci-sample/github-actions.yml` 复制到 `.github/workflows/ci.yml` 即可，会在 Python 3.10 / 3.11 / 3.12 下跑 `ruff check` + `ruff format --check` + `pytest`（需要 `gh auth refresh -s workflow` 后再 push）。详细贡献指引见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 扩展指引

- 新增测试用例：修改 `config/test_cases.json`，`scripts/run_cases.py` 自动加载
- 新增压测档位：修改 `scripts/run_stress.py::TIER_CONFIG`
- 新增真伪判据：在 `scripts/run_authenticity.py::run_model_checks` 追加 `AuthenticityCheck`
- 接入新厂商特征：在 `normalize_vendor_signal` 与 `EXPECTED_MODEL_SIGNALS` 中补充关键词

更多内部设计请见 [docs/architecture.md](docs/architecture.md)。

---

## 免责声明

本项目仅用于对**自己有合法授权的 API 服务**进行性能、稳定性、一致性评估。使用者自行对所接入的 API Key、端点、调用量负责；严禁用于未授权的探测、拒绝服务或逆向工程。

---

## License

[MIT](LICENSE)
