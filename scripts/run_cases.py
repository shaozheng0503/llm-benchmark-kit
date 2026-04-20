from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from common import (
    CONFIG_DIR,
    REPORTS_DIR,
    ReportArtifact,
    call_chat_completion,
    cli_models,
    dump_json,
    dump_text,
    ensure_project_dirs,
    get_base_host,
    list_available_model_ids,
    load_json,
    now_ts,
)


@dataclass
class CaseResult:
    model: str
    case_id: str
    case_name: str
    category: str
    passed: bool
    latency_ms: float
    ttft_ms: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    finish_reason: str
    error: str
    checks: list[str]
    response_preview: str


def load_cases() -> list[dict[str, Any]]:
    return load_json(CONFIG_DIR / "test_cases.json", default=[])


def extract_json_block(text: str) -> dict[str, Any] | None:
    text = text.strip()
    candidates = [text]
    if "```json" in text:
        part = text.split("```json", 1)[1].split("```", 1)[0]
        candidates.append(part.strip())
    if "```" in text:
        part = text.split("```", 1)[1].split("```", 1)[0]
        candidates.append(part.strip())
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except Exception:
            continue
    return None


def evaluate_case(response_text: str, checks: dict[str, Any]) -> tuple[bool, list[str]]:
    notes: list[str] = []
    lowered = response_text.lower()
    passed = True

    min_length = checks.get("min_length")
    if min_length:
        ok = len(response_text.strip()) >= min_length
        notes.append(f"min_length>={min_length}:{'ok' if ok else 'fail'}")
        passed = passed and ok

    should_include_any = checks.get("should_include_any", [])
    if should_include_any:
        ok = any(token.lower() in lowered for token in should_include_any)
        notes.append(f"include_any:{'ok' if ok else 'fail'}")
        passed = passed and ok

    should_include_all = checks.get("should_include_all", [])
    if should_include_all:
        ok = all(token.lower() in lowered for token in should_include_all)
        notes.append(f"include_all:{'ok' if ok else 'fail'}")
        passed = passed and ok

    should_not_include_any = checks.get("should_not_include_any", [])
    if should_not_include_any:
        ok = all(token.lower() not in lowered for token in should_not_include_any)
        notes.append(f"exclude_any:{'ok' if ok else 'fail'}")
        passed = passed and ok

    if checks.get("json_required"):
        payload = extract_json_block(response_text)
        ok = isinstance(payload, dict)
        notes.append(f"json_required:{'ok' if ok else 'fail'}")
        passed = passed and ok
        if ok:
            keys = checks.get("json_keys", [])
            key_ok = all(key in payload for key in keys)
            notes.append(f"json_keys:{'ok' if key_ok else 'fail'}")
            passed = passed and key_ok

    return passed, notes


def run_case(model: str, case: dict[str, Any]) -> CaseResult:
    try:
        response = call_chat_completion(
            model=model,
            messages=case["messages"],
            max_tokens=case.get("max_tokens", 512),
            stream=case.get("stream", False),
        )
        passed, notes = evaluate_case(response["content"], case.get("checks", {}))
        return CaseResult(
            model=model,
            case_id=case["id"],
            case_name=case["name"],
            category=case["category"],
            passed=passed,
            latency_ms=response["latency_ms"],
            ttft_ms=response.get("ttft_ms", 0.0),
            prompt_tokens=response.get("prompt_tokens", 0),
            completion_tokens=response.get("completion_tokens", 0),
            total_tokens=response.get("total_tokens", 0),
            finish_reason=response.get("finish_reason", ""),
            error="",
            checks=notes,
            response_preview=response["content"][:800],
        )
    except Exception as exc:
        return CaseResult(
            model=model,
            case_id=case["id"],
            case_name=case["name"],
            category=case["category"],
            passed=False,
            latency_ms=0.0,
            ttft_ms=0.0,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            finish_reason="error",
            error=f"{type(exc).__name__}: {exc}",
            checks=[],
            response_preview="",
        )


def build_markdown(results: list[CaseResult], selected_models: list[str]) -> str:
    total = len(results)
    passed = sum(1 for item in results if item.passed)
    lines = [
        "# 模型能力测试报告",
        "",
        "| 项目 | 值 |",
        "|------|----|",
        f"| 生成时间 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |",
        f"| API Host | `{get_base_host()}` |",
        f"| 测试模型 | {', '.join(selected_models)} |",
        f"| 测试项数 | {total} |",
        f"| 通过率 | {passed}/{total} ({(passed / total * 100) if total else 0:.1f}%) |",
        "",
        "## 总览",
        "",
        "| 模型 | 分类 | 测试项 | 结果 | 延迟(ms) | TTFT(ms) | Tokens | 检查摘要 |",
        "|------|------|--------|------|----------|----------|--------|----------|",
    ]
    for item in results:
        status = "PASS" if item.passed else "FAIL"
        summary = "; ".join(item.checks) if item.checks else (item.error[:60] or "-")
        lines.append(
            f"| {item.model} | {item.category} | {item.case_name} | {status} | "
            f"{item.latency_ms:.0f} | {item.ttft_ms:.0f} | {item.total_tokens} | {summary} |"
        )

    lines.append("")
    lines.append("## 详细记录")
    lines.append("")
    for item in results:
        status = "PASS" if item.passed else "FAIL"
        lines.append(f"### [{status}] {item.model} / {item.case_name}")
        lines.append("")
        lines.append(f"- 分类: `{item.category}`")
        lines.append(f"- 延迟: `{item.latency_ms:.2f} ms`")
        if item.ttft_ms:
            lines.append(f"- TTFT: `{item.ttft_ms:.2f} ms`")
        lines.append(f"- Tokens: `{item.total_tokens}`")
        if item.checks:
            lines.append(f"- 检查: `{'; '.join(item.checks)}`")
        if item.error:
            lines.append(f"- 错误: `{item.error}`")
        lines.append("")
        if item.response_preview:
            lines.append("```text")
            lines.append(item.response_preview)
            lines.append("```")
            lines.append("")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run capability test cases against the target API.")
    parser.add_argument("--models", help="Comma separated model ids. Defaults to TARGET_MODELS.")
    args = parser.parse_args()

    ensure_project_dirs()
    selected_models = cli_models(args.models)
    available = set(list_available_model_ids())
    missing = [model for model in selected_models if model not in available]
    if missing:
        raise RuntimeError(f"目标模型不存在于 /v1/models: {missing}")

    cases = load_cases()
    results: list[CaseResult] = []
    for model in selected_models:
        for case in cases:
            print(f"Running {model} -> {case['name']}")
            results.append(run_case(model, case))

    timestamp = now_ts()
    json_path = REPORTS_DIR / "cases" / f"cases_{timestamp}.json"
    markdown_path = REPORTS_DIR / "cases" / f"cases_{timestamp}.md"
    payload = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "api_host": get_base_host(),
            "models": selected_models,
            "case_count": len(cases),
        },
        "results": [asdict(item) for item in results],
    }
    dump_json(json_path, payload)
    dump_text(markdown_path, build_markdown(results, selected_models))

    artifact = ReportArtifact("run_cases", str(json_path), str(markdown_path))
    print(f"能力测试完成: {artifact.as_dict()}")


if __name__ == "__main__":
    main()
