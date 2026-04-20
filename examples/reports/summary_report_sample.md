# 综合测试总结样例报告

> 本样例演示 `scripts/build_summary.py` 的输出结构，用于把最近一次的能力测试、压测、真伪测试合并为单页汇总。

---

| 项目 | 值 |
|------|----|
| 生成时间 | 2026-04-03 21:35:00 |
| API Host | `<LLM_API_BASE>` |

## 结论摘要

- 能力测试共 `30` 项，整体通过 `26` 项，失败 `4` 项。
- `example-flagship`：`10/10`，全部通过。
- `example-mini`：`9/10`，主要失分：复杂-数学积分。
- `example-reasoning`：`7/10`，主要失分：边界-流式响应、安全-提示注入、冒烟-中英双语。
- 压测当前共有 `9` 条记录，最高吞吐为 `example-mini / medium / 6.8 RPS`。
- 真伪判定 `example-flagship`：`LIKELY_GENUINE`，可疑点 `0` 个。
- 真伪判定 `example-mini`：`LIKELY_GENUINE`，可疑点 `0` 个。
- 真伪判定 `example-reasoning`：`NEEDS_REVIEW`，可疑点 `1` 个。

## 详细结果

### 产物索引

| 模块         | 最新 JSON |
|--------------|-----------|
| cases        | `reports/cases/cases_20260403_143724.json` |
| stress       | `reports/stress/stress_20260403_155010.json` |
| authenticity | `reports/authenticity/authenticity_20260403_212234.json` |

### 能力测试细节

- 总数: `30`
- 通过: `26`
- 失败: `4`

| 模型 | 通过/总数 | 备注 |
|------|-----------|------|
| example-flagship  | 10/10 | 全部通过 |
| example-mini      | 9/10  | 复杂-数学积分 |
| example-reasoning | 7/10  | 冒烟-中英双语, 安全-提示注入, 边界-流式响应 |

### 压测细节

- 记录数: `9`
- 最高吞吐: `example-mini / medium / 6.8 RPS`

| 模型 | 档位 | 成功率 | RPS | P95(ms) |
|------|------|--------|-----|---------|
| example-mini      | low    | 10/10  | 2.1 |  980 |
| example-mini      | medium | 40/40  | 6.8 | 1580 |
| example-flagship  | low    | 10/10  | 1.2 | 1820 |
| example-reasoning | low    |  9/10  | 0.4 | 8400 |

### 真伪测试细节

| 模型 | 通过/总数 | 判定 | 可疑点 |
|------|-----------|------|--------|
| example-flagship  | 5/5 | LIKELY_GENUINE | 0 |
| example-mini      | 5/5 | LIKELY_GENUINE | 0 |
| example-reasoning | 4/5 | NEEDS_REVIEW   | 1 |

---

*样例数据。真实输出将基于 `reports/cases/`、`reports/stress/`、`reports/authenticity/` 下的最新 JSON 自动生成。*
