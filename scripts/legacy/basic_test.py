#!/usr/bin/env python3
"""
综合基础测试脚本 (legacy v1)
============================
覆盖: 模型发现、基础对话、代码生成、多轮、推理、图像生成、流式、并发

使用方法:
  export LLM_API_BASE="https://api.example.com"
  export LLM_API_KEY="sk-xxxx"
  python scripts/legacy/basic_test.py

报告输出: ${LLM_REPORT_DIR:-reports}/legacy_basic/
"""

import base64
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from openai import OpenAI

BASE_URL = os.getenv("LLM_API_BASE", "").rstrip("/")
API_KEY = os.getenv("LLM_API_KEY", "")
if not BASE_URL or not API_KEY:
    raise SystemExit("请先设置 LLM_API_BASE 与 LLM_API_KEY 环境变量")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = Path(os.getenv("LLM_REPORT_DIR", str(PROJECT_ROOT / "reports"))) / "legacy_basic"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

OPENAI_BASE_URL = f"{BASE_URL}/v1" if not BASE_URL.endswith("/v1") else BASE_URL

# ------------------------------------------------------------------
# 待测模型列表 —— 根据实际平台修改
# ------------------------------------------------------------------
MODELS = [
    {
        "id": "gpt-4o-mini",
        "company": "OpenAI",
        "capabilities": "文本、推理、代码",
        "category": "text",
        "rpm": 500,
        "tpm": 2_000_000,
        "scenario": "通用文本、对话、内容创作",
    },
    # 按需追加更多模型
]

BASIC_PROMPT = "请用一句话介绍你自己，包含你的模型名称。"
CODE_PROMPT = "用 Python 写一个快速排序函数，包含注释。"
REASONING_PROMPT = """请一步步推理以下问题，展示你的完整思考过程：

一个农夫需要将一只狐狸、一只鸡和一袋谷物带过河。他的船每次只能载他和另外一样东西。
如果农夫不在场，狐狸会吃鸡，鸡会吃谷物。请问农夫应该如何安全地将所有东西带过河？
"""
MATH_REASONING_PROMPT = """请详细推理以下数学问题：

如果 f(x) = x^3 - 6x^2 + 11x - 6，求 f(x) = 0 的所有实数根，并验证你的答案。
展示完整的推理和计算过程。
"""
MULTI_TURN_MESSAGES = [
    {"role": "user", "content": "我想学习 Python，你能帮我制定一个学习计划吗？"},
    {
        "role": "assistant",
        "content": "当然可以！以下是一个 Python 学习计划的框架：\n1. 基础语法\n2. 数据结构\n3. 面向对象编程\n4. 常用库\n5. 项目实践",
    },
    {"role": "user", "content": "我有一些 JavaScript 的基础，想转学 Python。请重点讲讲主要区别。"},
]
IMAGE_GEN_PROMPT = "Generate a simple illustration of a cute cat sitting on a stack of books, digital art style."


@dataclass
class TestResult:
    model_id: str
    test_name: str
    success: bool
    latency_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    response_preview: str = ""
    error_message: str = ""
    timestamp: str = ""
    has_reasoning: bool = False
    reasoning_preview: str = ""
    image_saved: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class APITester:
    def __init__(self):
        self.client = OpenAI(base_url=OPENAI_BASE_URL, api_key=API_KEY)
        self.results: list[TestResult] = []

    def _call_chat(self, model_id, messages, temperature=0.7, max_tokens=1024, **kwargs):
        start = time.time()
        try:
            resp = self.client.chat.completions.create(
                model=model_id,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            latency = (time.time() - start) * 1000
            choice = resp.choices[0]
            content = choice.message.content or ""
            reasoning = ""
            has_reasoning = False
            if hasattr(choice.message, "reasoning_content") and choice.message.reasoning_content:
                reasoning = choice.message.reasoning_content
                has_reasoning = True
            usage = resp.usage
            return {
                "success": True,
                "latency_ms": round(latency, 2),
                "content": content,
                "prompt_tokens": usage.prompt_tokens if usage else 0,
                "completion_tokens": usage.completion_tokens if usage else 0,
                "total_tokens": usage.total_tokens if usage else 0,
                "has_reasoning": has_reasoning,
                "reasoning": reasoning,
                "finish_reason": choice.finish_reason,
            }
        except Exception as e:
            return {
                "success": False,
                "latency_ms": round((time.time() - start) * 1000, 2),
                "error": f"{type(e).__name__}: {str(e)[:500]}",
            }

    def _record(self, model_id, test_name, result, **extra):
        tr = TestResult(
            model_id=model_id,
            test_name=test_name,
            success=result["success"],
            latency_ms=result["latency_ms"],
            prompt_tokens=result.get("prompt_tokens", 0),
            completion_tokens=result.get("completion_tokens", 0),
            total_tokens=result.get("total_tokens", 0),
            response_preview=result.get("content", "")[:300],
            error_message=result.get("error", ""),
            has_reasoning=result.get("has_reasoning", False),
            reasoning_preview=result.get("reasoning", "")[:300],
            **extra,
        )
        self.results.append(tr)
        status = "PASS" if tr.success else "FAIL"
        print(f"  [{status}] {test_name} | {tr.latency_ms:.0f}ms | tokens: {tr.total_tokens}")
        if not tr.success:
            print(f"     Error: {tr.error_message[:200]}")
        return tr

    def test_list_models(self):
        print("\n" + "=" * 60)
        print("TEST: 获取可用模型列表")
        print("=" * 60)
        start = time.time()
        try:
            models = self.client.models.list()
            latency = (time.time() - start) * 1000
            model_ids = [m.id for m in models.data]
            print(f"  成功获取 {len(model_ids)} 个模型 | {latency:.0f}ms")
            target_ids = {m["id"] for m in MODELS}
            missing = target_ids - set(model_ids)
            if missing:
                print(f"  WARN 未在列表中找到: {', '.join(missing)}")
            return model_ids
        except Exception as e:
            print(f"  FAIL 获取模型列表失败: {e}")
            return []

    def test_basic_chat(self, model):
        self._record(
            model["id"],
            "基础对话",
            self._call_chat(model["id"], [{"role": "user", "content": BASIC_PROMPT}], max_tokens=256),
        )

    def test_code_generation(self, model):
        self._record(
            model["id"],
            "代码生成",
            self._call_chat(model["id"], [{"role": "user", "content": CODE_PROMPT}], max_tokens=1024),
        )

    def test_multi_turn(self, model):
        self._record(model["id"], "多轮对话", self._call_chat(model["id"], MULTI_TURN_MESSAGES, max_tokens=512))

    def test_reasoning(self, model):
        self._record(
            model["id"],
            "逻辑推理(过河问题)",
            self._call_chat(model["id"], [{"role": "user", "content": REASONING_PROMPT}], max_tokens=2048),
        )
        self._record(
            model["id"],
            "数学推理(求根)",
            self._call_chat(model["id"], [{"role": "user", "content": MATH_REASONING_PROMPT}], max_tokens=2048),
        )

    def test_image_generation(self, model):
        model_id = model["id"]
        print(f"\n  [图像生成测试] {model_id}")

        messages = [{"role": "user", "content": IMAGE_GEN_PROMPT}]
        result = self._call_chat(model_id, messages, max_tokens=4096)
        image_path = ""
        if result["success"]:
            content = result.get("content", "")
            if "base64" in content.lower() or content.startswith("data:image"):
                try:
                    b64_match = re.search(r"(?:data:image/\w+;base64,)?([A-Za-z0-9+/=]{100,})", content)
                    if b64_match:
                        img_data = base64.b64decode(b64_match.group(1))
                        image_path = str(REPORT_DIR / f"generated_{model_id.replace('/', '_')}.png")
                        with open(image_path, "wb") as f:
                            f.write(img_data)
                        print(f"  图片已保存: {image_path}")
                except Exception as img_err:
                    print(f"  WARN 图片解码失败: {img_err}")
        self._record(model_id, "图像生成", result, image_saved=image_path)

        print("  [尝试 images.generate API]")
        start = time.time()
        try:
            img_resp = self.client.images.generate(model=model_id, prompt=IMAGE_GEN_PROMPT, n=1, size="1024x1024")
            latency = (time.time() - start) * 1000
            if img_resp.data and len(img_resp.data) > 0:
                img_url = img_resp.data[0].url or ""
                img_b64 = img_resp.data[0].b64_json or ""
                image_info = img_url[:200] if img_url else f"base64({len(img_b64)} chars)"
                if img_b64:
                    path2 = str(REPORT_DIR / f"generated_api_{model_id.replace('/', '_')}.png")
                    with open(path2, "wb") as f:
                        f.write(base64.b64decode(img_b64))
                self._record(
                    model_id,
                    "Images API 生成",
                    {
                        "success": True,
                        "latency_ms": round(latency, 2),
                        "content": image_info,
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                    },
                )
            else:
                self._record(
                    model_id,
                    "Images API 生成",
                    {
                        "success": False,
                        "latency_ms": round(latency, 2),
                        "error": "No image data returned",
                    },
                )
        except Exception as e:
            self._record(
                model_id,
                "Images API 生成",
                {
                    "success": False,
                    "latency_ms": round((time.time() - start) * 1000, 2),
                    "error": f"{type(e).__name__}: {str(e)[:300]}",
                },
            )

    def test_streaming(self, model):
        model_id = model["id"]
        messages = [{"role": "user", "content": "简要列出三个学习编程的建议。"}]
        start = time.time()
        try:
            stream = self.client.chat.completions.create(model=model_id, messages=messages, max_tokens=512, stream=True)
            chunks = []
            first_token_time = None
            for chunk in stream:
                if not first_token_time:
                    first_token_time = time.time()
                if chunk.choices and chunk.choices[0].delta.content:
                    chunks.append(chunk.choices[0].delta.content)
            latency = (time.time() - start) * 1000
            ttft = ((first_token_time - start) * 1000) if first_token_time else latency
            self._record(
                model_id,
                f"流式输出(TTFT:{ttft:.0f}ms)",
                {
                    "success": True,
                    "latency_ms": round(latency, 2),
                    "content": "".join(chunks),
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                },
            )
        except Exception as e:
            self._record(
                model_id,
                "流式输出",
                {
                    "success": False,
                    "latency_ms": round((time.time() - start) * 1000, 2),
                    "error": f"{type(e).__name__}: {str(e)[:300]}",
                },
            )

    def test_concurrent(self, model, num_requests=5):
        model_id = model["id"]
        messages = [{"role": "user", "content": "用一句话回答：天空为什么是蓝色的？"}]
        print(f"  [并发测试] {model_id} x{num_requests}")
        start = time.time()

        def single_request(_i):
            s = time.time()
            try:
                resp = self.client.chat.completions.create(model=model_id, messages=messages, max_tokens=128)
                return {
                    "success": True,
                    "latency_ms": round((time.time() - s) * 1000, 2),
                    "tokens": resp.usage.total_tokens if resp.usage else 0,
                }
            except Exception as e:
                return {"success": False, "latency_ms": round((time.time() - s) * 1000, 2), "error": str(e)[:200]}

        with ThreadPoolExecutor(max_workers=num_requests) as ex:
            futures = [ex.submit(single_request, i) for i in range(num_requests)]
            results = [f.result() for f in as_completed(futures)]

        total_time = (time.time() - start) * 1000
        success_count = sum(1 for r in results if r["success"])
        latencies = [r["latency_ms"] for r in results if r["success"]]
        avg = sum(latencies) / len(latencies) if latencies else 0
        summary = f"并发{num_requests}: 成功{success_count}/{num_requests} | 总耗时{total_time:.0f}ms | avg={avg:.0f}ms"
        self._record(
            model_id,
            f"并发测试(x{num_requests})",
            {
                "success": success_count == num_requests,
                "latency_ms": round(total_time, 2),
                "content": summary,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": sum(r.get("tokens", 0) for r in results),
                "error": ""
                if success_count == num_requests
                else f"{num_requests - success_count} 个失败: "
                + "; ".join(r.get("error", "")[:100] for r in results if not r["success"]),
            },
        )

    def run_all(self):
        print("=" * 60)
        print("  综合基础测试")
        print(f"  Base URL: {BASE_URL}")
        print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  待测模型: {len(MODELS)} 个")
        print("=" * 60)

        self.test_list_models()
        for i, model in enumerate(MODELS, 1):
            print(f"\n[{i}/{len(MODELS)}] {model['id']} | {model['company']}")
            category = model["category"]
            self.test_basic_chat(model)
            if category == "image_gen":
                self.test_image_generation(model)
            elif category == "reasoning":
                self.test_reasoning(model)
                self.test_code_generation(model)
                self.test_streaming(model)
                self.test_concurrent(model, num_requests=3)
            else:
                self.test_code_generation(model)
                self.test_multi_turn(model)
                self.test_reasoning(model)
                self.test_streaming(model)
                self.test_concurrent(model, num_requests=5)

        self.generate_report()

    def generate_report(self):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = REPORT_DIR / f"test_results_{ts}.json"
        md_path = REPORT_DIR / f"test_report_{ts}.md"

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump([asdict(r) for r in self.results], f, ensure_ascii=False, indent=2)

        total_pass = sum(1 for r in self.results if r.success)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# 综合基础测试报告\n\n")
            f.write(f"- 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- API Host: `{BASE_URL}`\n")
            f.write(f"- 测试模型数: {len(MODELS)}\n")
            f.write(f"- 总测试项数: {len(self.results)}\n")
            f.write(f"- 通过/失败: {total_pass} / {len(self.results) - total_pass}\n")
            f.write(f"- 通过率: {(total_pass / len(self.results) * 100) if self.results else 0:.1f}%\n\n")

            f.write("## 测试汇总\n\n")
            f.write("| 模型 | 测试项 | 结果 | 延迟(ms) | Tokens | 备注 |\n")
            f.write("|------|--------|------|----------|--------|------|\n")
            for r in self.results:
                status = "PASS" if r.success else "FAIL"
                note = "含推理链" if r.has_reasoning else ""
                if r.error_message:
                    note = r.error_message[:60].replace("|", "/").replace("\n", " ")
                if r.image_saved:
                    note = "图片已保存"
                f.write(
                    f"| {r.model_id} | {r.test_name} | {status} | {r.latency_ms:.0f} | {r.total_tokens} | {note} |\n"
                )

            failures = [r for r in self.results if not r.success]
            if failures:
                f.write("\n## 失败项\n\n")
                for r in failures:
                    f.write(f"- `{r.model_id}` / {r.test_name}: `{r.error_message[:200]}`\n")

        print("\n" + "=" * 60)
        print(f"  JSON: {json_path}")
        print(f"  Markdown: {md_path}")
        print(f"  通过: {total_pass} | 失败: {len(self.results) - total_pass} | 总计: {len(self.results)}")
        print("=" * 60)


if __name__ == "__main__":
    APITester().run_all()
