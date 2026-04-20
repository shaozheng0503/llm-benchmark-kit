# 模型真伪鉴别样例报告

> 本样例演示 `scripts/run_authenticity.py` / `scripts/legacy/cross_vendor_authenticity.py` 的输出结构。
> 下述厂商/模型名均为占位符，判定结果仅用于说明报告格式，不代表任何真实平台现状。

---

| 项目 | 值 |
|------|----|
| 生成时间 | 2026-04-03 21:22:34 |
| API Host | `<LLM_API_BASE>` |
| 测试维度 | 身份自报 / 反向诱导 / 提示词泄露 / 双调用一致性 / 并发身份稳定性 |

## 汇总

| 模型 | 通过测试 | 可疑点 | 初步结论 |
|------|----------|--------|----------|
| vendor-a/flagship        | 5/5 | 0 | LIKELY_GENUINE |
| vendor-a/mini            | 5/5 | 0 | LIKELY_GENUINE |
| vendor-b/claude-sonnet   | 4/5 | 1 | NEEDS_REVIEW   |
| vendor-c/gemini-flash    | 5/5 | 0 | LIKELY_GENUINE |
| vendor-d/unknown-model   | 2/5 | 3 | HIGH_RISK      |

## 详细记录

### vendor-a/flagship

| 测试项 | 结果 | 说明 |
|--------|------|------|
| 身份自报         | PASS | 回复中明确出现自家品牌关键词 |
| 反向诱导         | PASS | 正确否认自己是其他厂商模型 |
| 提示词泄露       | PASS | 未发现身份伪装相关字段 |
| 双调用一致性     | PASS | 两次询问厂商归属一致 |
| 并发身份稳定性   | PASS | 并发 3 次回答完全一致 |

### vendor-b/claude-sonnet

| 测试项 | 结果 | 说明 |
|--------|------|------|
| 身份自报         | PASS | 回复中含 `claude` 关键词 |
| 反向诱导         | FAIL | 被诱导为 OpenAI GPT（可疑） |
| 提示词泄露       | PASS | 无泄露迹象 |
| 双调用一致性     | PASS | 两次回答一致 |
| 并发身份稳定性   | PASS | 并发稳定 |

- 可疑点:
  - 反向诱导测试中模型承认自己是 GPT，需人工复核是否为真厂商被诱导或冒充

### vendor-d/unknown-model

| 测试项 | 结果 | 说明 |
|--------|------|------|
| 身份自报         | FAIL | 自称为其他厂商品牌 |
| 反向诱导         | FAIL | 被诱导为 OpenAI GPT |
| 提示词泄露       | PASS | - |
| 双调用一致性     | FAIL | 两次回答厂商归属漂移 |
| 并发身份稳定性   | PASS | - |

- 可疑点:
  - 身份自报未命中期望品牌
  - 反向诱导失败
  - 双调用一致性不稳定

## 判定等级说明

| 判定 | 含义 |
|------|------|
| LIKELY_GENUINE | 全部或几乎全部维度通过，与期望模型家族一致 |
| NEEDS_REVIEW   | 有 1-2 个维度异常，需要人工抽样复核实际答题风格与能力 |
| HIGH_RISK      | 3+ 维度异常，高度怀疑为冒充或代理到其他模型的场景 |
| UNAVAILABLE    | 调用全部失败，可能为额度耗尽 / 网络 / 授权问题 |

---

*样例数据，用于演示报告结构。复现请执行 `python scripts/run_authenticity.py --models <id>`。*
