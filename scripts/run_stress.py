from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime

from common import (
    REPORTS_DIR,
    ReportArtifact,
    call_chat_completion,
    cli_models,
    dump_json,
    dump_text,
    ensure_project_dirs,
    get_base_host,
    list_available_model_ids,
    now_ts,
    percentile,
)

TIER_CONFIG = {
    "low": {"concurrency": 5, "requests": 10, "max_tokens": 128},
    "medium": {"concurrency": 20, "requests": 40, "max_tokens": 160},
    "high": {"concurrency": 30, "requests": 90, "max_tokens": 192},
}

PROMPTS = [
    "用一句话解释什么是 API 网关。",
    "列出三种常见限流算法，并各用一句话说明。",
    "说明 429 状态码的含义以及服务端通常如何处理。",
    "给出一个高并发订单创建接口的幂等设计思路。",
]


@dataclass
class StressRecord:
    model: str
    tier: str
    concurrency: int
    requests: int
    success: int
    fail: int
    rps: float
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    avg_ttft_ms: float
    error_samples: list[str]


def run_one(model: str, prompt: str, max_tokens: int) -> dict:
    try:
        response = call_chat_completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        )
        return {
            "ok": True,
            "latency_ms": response["latency_ms"],
            "ttft_ms": 0.0,
            "error": "",
        }
    except Exception as exc:
        return {"ok": False, "latency_ms": 0.0, "ttft_ms": 0.0, "error": f"{type(exc).__name__}: {exc}"}


def probe_ttft(model: str) -> float:
    try:
        response = call_chat_completion(
            model=model,
            messages=[{"role": "user", "content": "请简要说明首 token 延迟 TTFT 的含义。"}],
            max_tokens=80,
            stream=True,
        )
        return response.get("ttft_ms", 0.0)
    except Exception:
        return 0.0


def run_tier(model: str, tier_name: str) -> StressRecord:
    config = TIER_CONFIG[tier_name]
    prompt_cycle = [PROMPTS[i % len(PROMPTS)] for i in range(config["requests"])]
    results = []
    started = datetime.now()
    with ThreadPoolExecutor(max_workers=config["concurrency"]) as pool:
        futures = [pool.submit(run_one, model, prompt, config["max_tokens"]) for prompt in prompt_cycle]
        for future in as_completed(futures):
            results.append(future.result())
    elapsed = max((datetime.now() - started).total_seconds(), 0.001)

    latencies = [item["latency_ms"] for item in results if item["ok"]]
    errors = [item["error"] for item in results if not item["ok"]]
    ttft_probe = probe_ttft(model)
    success = len(latencies)
    fail = len(errors)
    return StressRecord(
        model=model,
        tier=tier_name,
        concurrency=config["concurrency"],
        requests=config["requests"],
        success=success,
        fail=fail,
        rps=round(success / elapsed, 2),
        avg_latency_ms=round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
        p50_latency_ms=round(percentile(latencies, 50), 2),
        p95_latency_ms=round(percentile(latencies, 95), 2),
        p99_latency_ms=round(percentile(latencies, 99), 2),
        avg_ttft_ms=round(ttft_probe, 2),
        error_samples=errors[:5],
    )


def build_markdown(records: list[StressRecord], models: list[str], tiers: list[str]) -> str:
    lines = [
        "# 并发压力测试报告",
        "",
        "| 项目 | 值 |",
        "|------|----|",
        f"| 生成时间 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |",
        f"| API Host | `{get_base_host()}` |",
        f"| 模型 | {', '.join(models)} |",
        f"| 档位 | {', '.join(tiers)} |",
        "",
        "## 结果总览",
        "",
        "| 模型 | 档位 | 并发 | 请求数 | 成功率 | RPS | Avg(ms) | P95(ms) | P99(ms) | TTFT(ms) |",
        "|------|------|------|--------|--------|-----|---------|---------|---------|----------|",
    ]
    for item in records:
        success_rate = (
            f"{item.success}/{item.requests} ({(item.success / item.requests * 100) if item.requests else 0:.1f}%)"
        )
        lines.append(
            f"| {item.model} | {item.tier} | {item.concurrency} | {item.requests} | {success_rate} | "
            f"{item.rps} | {item.avg_latency_ms:.0f} | {item.p95_latency_ms:.0f} | {item.p99_latency_ms:.0f} | {item.avg_ttft_ms:.0f} |"
        )
    lines.append("")
    for item in records:
        lines.append(f"### {item.model} / {item.tier}")
        lines.append("")
        if item.error_samples:
            lines.append("- 错误样例:")
            for error in item.error_samples:
                lines.append(f"  - `{error}`")
            lines.append("")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run tiered concurrency tests against the target API.")
    parser.add_argument("--models", help="Comma separated model ids. Defaults to TARGET_MODELS.")
    parser.add_argument(
        "--tiers",
        nargs="+",
        choices=sorted(TIER_CONFIG.keys()),
        default=["low"],
        help="Stress tiers to execute. Default: low",
    )
    args = parser.parse_args()

    ensure_project_dirs()
    selected_models = cli_models(args.models)
    available = set(list_available_model_ids())
    missing = [model for model in selected_models if model not in available]
    if missing:
        raise RuntimeError(f"目标模型不存在于 /v1/models: {missing}")

    records: list[StressRecord] = []
    for model in selected_models:
        for tier in args.tiers:
            print(f"Running stress tier {tier} for {model}")
            records.append(run_tier(model, tier))

    timestamp = now_ts()
    json_path = REPORTS_DIR / "stress" / f"stress_{timestamp}.json"
    markdown_path = REPORTS_DIR / "stress" / f"stress_{timestamp}.md"
    payload = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "api_host": get_base_host(),
            "models": selected_models,
            "tiers": args.tiers,
            "tier_config": TIER_CONFIG,
        },
        "records": [asdict(item) for item in records],
    }
    dump_json(json_path, payload)
    dump_text(markdown_path, build_markdown(records, selected_models, args.tiers))

    artifact = ReportArtifact("run_stress", str(json_path), str(markdown_path))
    print(f"压测完成: {artifact.as_dict()}")


if __name__ == "__main__":
    main()
