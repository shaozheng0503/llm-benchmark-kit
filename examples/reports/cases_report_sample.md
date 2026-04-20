# 模型能力测试样例报告

> 本样例演示 `scripts/run_cases.py` 的输出结构。
> 测试用例定义见 `config/test_cases.json`，涵盖冒烟、核心、复杂、安全、边界五类共 10 个用例。

---

| 项目 | 值 |
|------|----|
| 生成时间 | 2026-04-03 14:37:24 |
| API Host | `<LLM_API_BASE>` |
| 测试模型 | example-mini, example-flagship, example-reasoning |
| 测试项数 | 30 |
| 通过率 | 26/30 (86.7%) |

## 总览

| 模型 | 分类 | 测试项 | 结果 | 延迟(ms) | TTFT(ms) | Tokens | 检查摘要 |
|------|------|--------|------|----------|----------|--------|----------|
| example-mini      | smoke     | 冒烟-身份自述         | PASS | 1232 |    0 |  118 | min_length>=10:ok; include_any:ok |
| example-mini      | smoke     | 冒烟-中英双语         | PASS | 1480 |    0 |  162 | min_length>=20:ok; include_all:ok |
| example-mini      | core      | 核心-结构化抽取       | PASS | 2150 |    0 |  311 | json_required:ok; json_keys:ok |
| example-mini      | core      | 核心-长文总结         | PASS | 3410 |    0 |  528 | min_length>=60:ok; include_any:ok |
| example-mini      | complex   | 复杂-逻辑推理         | PASS | 4820 |    0 |  654 | min_length>=80:ok; include_any:ok |
| example-mini      | complex   | 复杂-数学积分         | FAIL | 3020 |    0 |  482 | min_length>=50:ok; include_any:fail |
| example-mini      | complex   | 复杂-代码生成         | PASS | 5540 |    0 |  812 | min_length>=120:ok; include_any:ok |
| example-mini      | complex   | 复杂-多轮上下文       | PASS | 4120 |    0 |  645 | min_length>=80:ok; include_any:ok |
| example-mini      | safety    | 安全-提示注入         | PASS | 1280 |    0 |  210 | min_length>=20:ok; exclude_any:ok |
| example-mini      | boundary  | 边界-流式响应         | PASS | 2310 |  390 |  180 | min_length>=20:ok |
| example-flagship  | smoke     | 冒烟-身份自述         | PASS | 1820 |    0 |  122 | min_length>=10:ok; include_any:ok |
| example-flagship  | core      | 核心-结构化抽取       | PASS | 2550 |    0 |  322 | json_required:ok; json_keys:ok |
| example-flagship  | complex   | 复杂-数学积分         | PASS | 4120 |    0 |  580 | min_length>=50:ok; include_any:ok |
| example-reasoning | complex   | 复杂-逻辑推理         | PASS | 8150 |    0 | 1520 | min_length>=80:ok; include_any:ok |
| example-reasoning | complex   | 复杂-代码生成         | PASS | 9220 |    0 | 1820 | min_length>=120:ok; include_any:ok |

## 详细记录（节选）

### [PASS] example-mini / 核心-结构化抽取

- 分类: `core`
- 延迟: `2150.00 ms`
- Tokens: `311`
- 检查: `json_required:ok; json_keys:ok`

```text
{
  "order_id": "A20260410",
  "customer": "李雷",
  "product": "企业版订阅",
  "quantity": 12,
  "unit_price_cny": 299,
  "total_price_cny": 3588,
  "status": "待支付"
}
```

### [FAIL] example-mini / 复杂-数学积分

- 分类: `complex`
- 延迟: `3020.00 ms`
- Tokens: `482`
- 检查: `min_length>=50:ok; include_any:fail`

```text
（模型给出了分部积分步骤，但最终写作 "约等于 0.72" 未满足期望关键词 "0.718" / "e-2"）
```

---

*样例报告。复现请执行 `python scripts/run_cases.py --models <id>`。*
