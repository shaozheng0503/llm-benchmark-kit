#!/usr/bin/env python3
"""
预算驱动的高并发压测脚本 (legacy)
==================================
按每个模型预设的美元预算持续发起并发请求，自动计费停机；
适合评估在给定金额下各模型的吞吐、稳定性与性价比。

使用方法:
  export LLM_API_BASE="https://api.example.com"
  export LLM_API_KEY="sk-xxxx"
  python scripts/legacy/budget_stress_test.py

按需修改 STRESS_PLAN 与 PRICING 中的模型 / 价格。
"""

import json
import os
import random
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import httpx
from openai import OpenAI

BASE_URL = os.getenv("LLM_API_BASE", "").rstrip("/")
API_KEY = os.getenv("LLM_API_KEY", "")
if not BASE_URL or not API_KEY:
    raise SystemExit("请先设置 LLM_API_BASE 与 LLM_API_KEY 环境变量")

OPENAI_BASE_URL = f"{BASE_URL}/v1" if not BASE_URL.endswith("/v1") else BASE_URL

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = Path(os.getenv("LLM_REPORT_DIR", str(PROJECT_ROOT / "reports"))) / "legacy_budget_stress"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


PRICING = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}

STRESS_PLAN = [
    {"id": "gpt-4o-mini", "budget": 1.0, "concurrency": 10, "api": "chat", "prompts": "mixed", "max_tokens": 512},
]


SHORT_PROMPTS = [
    "用一句话解释什么是微服务架构。",
    "Python 中 list 和 tuple 的区别是什么？",
    "什么是 CAP 定理？简要说明。",
    "解释 HTTP 状态码 429 的含义。",
    "什么是幂等性？举一个 API 的例子。",
    "简要解释数据库索引的 B+ 树原理。",
    "Redis 和 Memcached 的主要区别？",
    "什么是 JWT？它由哪三部分组成？",
    "解释 CORS 是什么以及为什么需要它。",
    "简要说明 TCP 三次握手的过程。",
]

MEDIUM_PROMPTS = [
    "请设计一个简单的限流算法（令牌桶），用 Python 实现核心逻辑，包含注释。",
    "请用 Python 实现一个线程安全的单例模式，要求支持带参数的初始化，并写出测试代码。",
    "请解释 MVCC（多版本并发控制）的原理，以 MySQL InnoDB 为例说明。",
    "用 Python 实现一个简单的事件驱动架构，包含事件总线、事件发布和订阅功能。",
]

LONG_PROMPTS = [
    "请详细设计一个分布式任务调度系统：1）系统架构 2）核心组件 3）任务分配 4）故障恢复 5）监控告警。",
    "请对比 PostgreSQL、MySQL、MongoDB、Redis 在以下场景中的适用性：1）电商订单 2）社交动态 3）实时排行榜 4）日志分析。",
]

IMAGE_PROMPTS = [
    "Generate a futuristic city skyline at sunset with flying cars and neon lights, digital art style",
    "Create an illustration of a cozy coffee shop interior with warm lighting and a cat on the counter",
]


def get_prompt(prompt_type: str, index: int) -> str:
    if prompt_type == "short":
        return SHORT_PROMPTS[index % len(SHORT_PROMPTS)]
    if prompt_type == "image":
        return IMAGE_PROMPTS[index % len(IMAGE_PROMPTS)]
    r = random.random()
    if r < 0.4:
        return SHORT_PROMPTS[index % len(SHORT_PROMPTS)]
    if r < 0.8:
        return MEDIUM_PROMPTS[index % len(MEDIUM_PROMPTS)]
    return LONG_PROMPTS[index % len(LONG_PROMPTS)]


class StatsCollector:
    def __init__(self):
        self.lock = threading.Lock()
        self.model_stats = defaultdict(
            lambda: {
                "requests": 0,
                "success": 0,
                "fail": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "latencies": [],
                "errors": [],
                "cost": 0.0,
                "start_time": None,
                "end_time": None,
            }
        )
        self.global_start = time.time()
        self.total_cost = 0.0

    def record(self, model_id, success, latency_ms, prompt_tokens=0, completion_tokens=0, total_tokens=0, error=""):
        pricing = PRICING.get(model_id, {"input": 5.0, "output": 15.0})
        cost = (prompt_tokens / 1e6) * pricing["input"] + (completion_tokens / 1e6) * pricing["output"]
        with self.lock:
            s = self.model_stats[model_id]
            s["requests"] += 1
            if success:
                s["success"] += 1
            else:
                s["fail"] += 1
                if error:
                    s["errors"].append(error[:200])
            s["prompt_tokens"] += prompt_tokens
            s["completion_tokens"] += completion_tokens
            s["total_tokens"] += total_tokens
            s["latencies"].append(latency_ms)
            s["cost"] += cost
            self.total_cost += cost
            now = time.time()
            if s["start_time"] is None:
                s["start_time"] = now
            s["end_time"] = now

    def get_snapshot(self):
        with self.lock:
            return {
                "elapsed": time.time() - self.global_start,
                "total_cost": self.total_cost,
                "models": {k: dict(v) for k, v in self.model_stats.items()},
            }


def run_model_stress(plan, stats: StatsCollector, stop_event: threading.Event):
    model_id = plan["id"]
    budget = plan["budget"]
    concurrency = plan["concurrency"]
    api_type = plan["api"]
    prompt_type = plan["prompts"]
    max_tokens = plan["max_tokens"]

    client = OpenAI(base_url=OPENAI_BASE_URL, api_key=API_KEY, timeout=120)
    http_client = httpx.Client(timeout=180)

    print(f"  [START] {model_id} | budget=${budget} | concurrency={concurrency}")

    def execute_one(idx):
        if stop_event.is_set():
            return
        prompt = get_prompt(prompt_type, idx)
        start = time.time()
        try:
            if api_type == "responses":
                resp = http_client.post(
                    f"{OPENAI_BASE_URL}/responses",
                    headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                    json={"model": model_id, "input": prompt, "max_output_tokens": max_tokens},
                )
                latency = (time.time() - start) * 1000
                if resp.status_code != 200:
                    stats.record(model_id, False, latency, error=f"HTTP {resp.status_code}")
                    return
                data = resp.json()
                usage = data.get("usage", {})
                stats.record(
                    model_id,
                    True,
                    latency,
                    prompt_tokens=usage.get("input_tokens", 0),
                    completion_tokens=usage.get("output_tokens", 0),
                    total_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
                )
            else:
                messages = [{"role": "user", "content": prompt}]
                resp = client.chat.completions.create(
                    model=model_id,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=0.7,
                )
                latency = (time.time() - start) * 1000
                usage = resp.usage
                stats.record(
                    model_id,
                    True,
                    latency,
                    prompt_tokens=usage.prompt_tokens if usage else 0,
                    completion_tokens=usage.completion_tokens if usage else 0,
                    total_tokens=usage.total_tokens if usage else 0,
                )
        except Exception as e:
            latency = (time.time() - start) * 1000
            stats.record(model_id, False, latency, error=f"{type(e).__name__}: {str(e)[:150]}")

    request_idx = 0
    while not stop_event.is_set():
        with stats.lock:
            if stats.model_stats[model_id]["cost"] >= budget:
                break
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = [pool.submit(execute_one, request_idx + i) for i in range(concurrency)]
            for f in as_completed(futures):
                try:
                    f.result()
                except Exception:
                    pass
        request_idx += concurrency

    with stats.lock:
        s = stats.model_stats[model_id]
    elapsed = (s["end_time"] - s["start_time"]) if s["start_time"] and s["end_time"] else 0
    rps = s["success"] / elapsed if elapsed > 0 else 0
    print(f"  [DONE] {model_id} | req={s['requests']} success={s['success']} cost=${s['cost']:.2f} rps={rps:.2f}")


def progress_monitor(stats: StatsCollector, stop_event: threading.Event):
    while not stop_event.wait(30):
        snap = stats.get_snapshot()
        total_req = sum(m["requests"] for m in snap["models"].values())
        total_ok = sum(m["success"] for m in snap["models"].values())
        total_fail = sum(m["fail"] for m in snap["models"].values())
        total_tok = sum(m["total_tokens"] for m in snap["models"].values())
        print(
            f"\n  ==== 进度 [{snap['elapsed'] / 60:.1f}min] 费用 ${snap['total_cost']:.2f} | "
            f"req={total_req} ok={total_ok} fail={total_fail} tokens={total_tok:,}"
        )


def pct(data, p):
    if not data:
        return 0
    s = sorted(data)
    k = (len(s) - 1) * p / 100
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (k - f) * (s[c] - s[f])


def generate_report(stats: StatsCollector):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    snap = stats.get_snapshot()

    json_data = {}
    for mid, m in snap["models"].items():
        dur = (m["end_time"] - m["start_time"]) if m["start_time"] and m["end_time"] else 0
        lats = m["latencies"]
        json_data[mid] = {
            "requests": m["requests"],
            "success": m["success"],
            "fail": m["fail"],
            "prompt_tokens": m["prompt_tokens"],
            "completion_tokens": m["completion_tokens"],
            "total_tokens": m["total_tokens"],
            "cost": round(m["cost"], 4),
            "duration_s": round(dur, 2),
            "rps": round(m["success"] / dur, 2) if dur > 0 else 0,
            "latency_avg": round(sum(lats) / len(lats), 1) if lats else 0,
            "latency_p50": round(pct(lats, 50), 1),
            "latency_p95": round(pct(lats, 95), 1),
            "latency_p99": round(pct(lats, 99), 1),
            "latency_max": round(max(lats), 1) if lats else 0,
            "error_samples": m["errors"][:10],
        }

    json_path = REPORT_DIR / f"stress_{ts}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {"metadata": {"total_cost": snap["total_cost"], "elapsed_s": snap["elapsed"]}, "models": json_data},
            f,
            ensure_ascii=False,
            indent=2,
        )

    md_path = REPORT_DIR / f"stress_report_{ts}.md"
    total_req = sum(m["requests"] for m in snap["models"].values())
    total_ok = sum(m["success"] for m in snap["models"].values())
    total_fail = sum(m["fail"] for m in snap["models"].values())
    total_tok = sum(m["total_tokens"] for m in snap["models"].values())

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# 预算驱动压测报告\n\n")
        f.write(f"- 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- API Host: `{BASE_URL}`\n")
        f.write(f"- 总运行: {snap['elapsed'] / 60:.1f} 分钟\n")
        f.write(f"- 总请求: {total_req:,} (成功 {total_ok:,}，失败 {total_fail:,})\n")
        f.write(f"- 总 Tokens: {total_tok:,}\n")
        f.write(f"- 总费用 (估算): ${snap['total_cost']:.2f}\n\n")

        f.write("## 各模型压测结果\n\n")
        f.write("| 模型 | 请求 | 成功率 | RPS | Tokens | 费用 | Avg | P95 | P99 | Max |\n")
        f.write("|------|------|--------|-----|--------|------|-----|-----|-----|-----|\n")
        for mid, d in sorted(json_data.items()):
            rate = f"{d['success'] / d['requests'] * 100:.0f}%" if d["requests"] > 0 else "-"
            f.write(
                f"| {mid} | {d['requests']:,} | {rate} | {d['rps']:.1f} | "
                f"{d['total_tokens']:,} | ${d['cost']:.2f} | "
                f"{d['latency_avg']:.0f} | {d['latency_p95']:.0f} | {d['latency_p99']:.0f} | {d['latency_max']:.0f} |\n"
            )

    print(f"\n报告: {json_path}\n       {md_path}")


def main():
    print("=" * 70)
    print("  预算驱动压测")
    print(f"  模型数: {len(STRESS_PLAN)} | 总预算 ${sum(p['budget'] for p in STRESS_PLAN):.0f}")
    print("=" * 70)

    stats = StatsCollector()
    stop_event = threading.Event()
    monitor = threading.Thread(target=progress_monitor, args=(stats, stop_event), daemon=True)
    monitor.start()

    threads = []
    for plan in STRESS_PLAN:
        t = threading.Thread(target=run_model_stress, args=(plan, stats, stop_event), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()
    stop_event.set()

    generate_report(stats)


if __name__ == "__main__":
    main()
