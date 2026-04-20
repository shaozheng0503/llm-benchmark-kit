# 架构说明

## 分层

```
┌─────────────────────────────────────────────────────────────┐
│           入口脚本 (scripts/*.py, scripts/legacy/*.py)       │
│  discover · run_cases · run_stress · run_authenticity · ... │
└──────────────────┬──────────────────────────────────────────┘
                   │ 调用
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  scripts/common.py                                           │
│  • 环境变量读取 (LLM_API_BASE / LLM_API_KEY / ...)            │
│  • OpenAI / httpx client 构建                                │
│  • 报告目录与 I/O (dump_json / dump_text)                    │
│  • call_chat_completion (兼容 chat & stream，含 TTFT)        │
│  • percentile / list_available_model_ids / load_discovered   │
└──────────────────┬──────────────────────────────────────────┘
                   │ 调用
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  OpenAI 兼容网关                                              │
│  /v1/models · /v1/chat/completions · /v1/responses           │
└─────────────────────────────────────────────────────────────┘
```

## 模块职责

### scripts/common.py

统一封装**鉴权 / 客户端 / 超时 / 报告 I/O**。所有其他脚本都应通过它来拿到 client，避免：

- 任何脚本自己读取 `os.environ` —— 新增环境变量在此处集中维护
- 重复实现 TTFT / 延迟统计 —— 以 `call_chat_completion` 为单一入口
- 报告路径硬编码 —— 以 `REPORTS_DIR` 为根，默认 `<repo>/reports`，可被 `LLM_REPORT_DIR` 覆盖

### 入口脚本约定

所有 `scripts/*.py` 遵循如下结构：

```python
def main() -> None:
    parser = argparse.ArgumentParser(...)
    # argparse 参数
    args = parser.parse_args()

    ensure_project_dirs()                 # 建所需目录
    selected_models = cli_models(args.models)
    available = set(list_available_model_ids())
    missing = [m for m in selected_models if m not in available]
    if missing:
        raise RuntimeError(...)

    results = ...  # 调用 call_chat_completion

    dump_json(json_path, payload)         # 原始数据
    dump_text(markdown_path, build_md())  # 可读报告
```

### legacy/

`scripts/legacy/` 是早期快速迭代时的脚本集合，保留原始功能以作**回归对照 / 覆盖率参考**：

- `basic_test.py` — 含多模型基础对话 / 代码 / 推理 / 流式 / 并发的一次性全量脚本
- `pro_test.py` — 进阶版，补充 Responses API 支持与专业报告
- `budget_stress_test.py` — 预算驱动压测（与档位驱动的 `run_stress.py` 正交）
- `cross_vendor_authenticity.py` — 10+ 维度真伪鉴别（与精简版 `run_authenticity.py` 正交）
- `debug_responses_api.py` — 对单个模型在 `/v1/responses` 上的兼容性逐策略调试

Legacy 脚本不再共用 `common.py`（有自己的 env var 读取 / 客户端），但都已改为环境变量驱动，可作为新建脚本的参考。

## 数据流

```
env vars ──► scripts/*.py ──► common.py ──► httpx / openai ──► API Gateway
                  │
                  ├──► data/raw/models_latest.json     (discover_models)
                  ├──► reports/cases/*.{json,md}       (run_cases)
                  ├──► reports/stress/*.{json,md}      (run_stress)
                  ├──► reports/authenticity/*.{json,md}(run_authenticity)
                  └──► reports/summary/*.{json,md}     (build_summary)
```

- `data/raw/models_latest.json` 是后续脚本避免重复调用 `/v1/models` 的缓存；删掉后会自动回源。
- `reports/summary/*` 的生成只依赖最新的 `cases/`、`stress/`、`authenticity/` JSON，不会触发实际 API 调用。

## 扩展

### 新增测试用例

编辑 `config/test_cases.json`，追加一项：

```json
{
  "id": "smoke_reject_long_input",
  "category": "boundary",
  "name": "边界-超长输入拒绝",
  "max_tokens": 256,
  "messages": [{"role": "user", "content": "..."}],
  "checks": {
    "should_include_any": ["context length", "输入过长"],
    "min_length": 10
  }
}
```

新 key 若需新增断言类型，在 `scripts/run_cases.py::evaluate_case` 扩展。

### 新增压测档位

在 `scripts/run_stress.py::TIER_CONFIG` 中追加：

```python
TIER_CONFIG = {
    ...
    "burst": {"concurrency": 50, "requests": 150, "max_tokens": 96},
}
```

`argparse` 的 `choices` 会自动包含新 key。

### 新增真伪判据

在 `scripts/run_authenticity.py::run_model_checks` 中追加一个 `AuthenticityCheck`：

```python
codewords = ask_once(model, "请逐字复述一句：'HELLO-WORLD-42'")
codewords_ok = "HELLO-WORLD-42" in codewords
checks.append(AuthenticityCheck(model, "复述稳定性", codewords_ok, codewords[:120], codewords))
if not codewords_ok:
    flags.append("复述指令无法严格执行")
```

阈值与判定等级在 `main()` 中按 `len(flags)` 分段，可按业务严格度调整。

### 新增厂商识别

`EXPECTED_MODEL_SIGNALS` 按 `model_id` → `关键词列表` 维护。`normalize_vendor_signal` 则将文本统一归一到厂商 slug（`openai` / `anthropic` / `google` / `xai` / `zhipu` / ...）。

## 报告命名约定

- `cases/cases_<YYYYMMDD_HHMMSS>.{json,md}`
- `stress/stress_<YYYYMMDD_HHMMSS>.{json,md}`
- `authenticity/authenticity_<YYYYMMDD_HHMMSS>.{json,md}`
- `summary/summary_<YYYYMMDD_HHMMSS>.{json,md}`
- `summary/models_report_<YYYYMMDD_HHMMSS>.md`（模型发现）

`build_summary.py` 总是聚合**每个子模块的最新 JSON**，不会跨时间窗合并。

## CI 建议

```yaml
# .github/workflows/benchmark.yml (示意)
name: benchmark
on:
  workflow_dispatch:
  schedule:
    - cron: "0 2 * * *"

jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.11"}
      - run: pip install -r requirements.txt
      - run: python scripts/discover_models.py
        env:
          LLM_API_BASE: ${{ secrets.LLM_API_BASE }}
          LLM_API_KEY:  ${{ secrets.LLM_API_KEY }}
      - run: python scripts/run_cases.py --models ${{ vars.TARGET_MODELS }}
        env:
          LLM_API_BASE: ${{ secrets.LLM_API_BASE }}
          LLM_API_KEY:  ${{ secrets.LLM_API_KEY }}
      - uses: actions/upload-artifact@v4
        with:
          name: reports
          path: reports/
```

使用 Secrets 注入 Key，并把 reports 作为 artifact 留档；必要时可再加一步解析 JSON，把核心指标推到 Prometheus / Grafana。
