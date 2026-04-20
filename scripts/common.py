from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from openai import OpenAI


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"
RAW_DIR = PROJECT_ROOT / "data" / "raw"
REPORTS_DIR = Path(os.getenv("LLM_REPORT_DIR", str(PROJECT_ROOT / "reports")))


def now_ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"缺少环境变量: {name}")
    return value


def get_base_host() -> str:
    return require_env("LLM_API_BASE").rstrip("/")


def get_openai_base_url() -> str:
    return f"{get_base_host()}/v1"


def get_timeout() -> float:
    raw = os.getenv("LLM_HTTP_TIMEOUT", "180").strip()
    return float(raw or "180")


def get_max_workers(default: int = 8) -> int:
    raw = os.getenv("LLM_MAX_WORKERS", str(default)).strip()
    return int(raw or str(default))


def get_target_models(default: str = "gpt-4o-mini") -> list[str]:
    raw = os.getenv("TARGET_MODELS", default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def ensure_project_dirs() -> None:
    for path in [
        CONFIG_DIR,
        RAW_DIR,
        REPORTS_DIR / "smoke",
        REPORTS_DIR / "cases",
        REPORTS_DIR / "stress",
        REPORTS_DIR / "authenticity",
        REPORTS_DIR / "summary",
    ]:
        path.mkdir(parents=True, exist_ok=True)


def get_openai_client() -> OpenAI:
    return OpenAI(
        base_url=get_openai_base_url(),
        api_key=require_env("LLM_API_KEY"),
        timeout=get_timeout(),
    )


def get_http_client() -> httpx.Client:
    return httpx.Client(
        base_url=get_base_host(),
        timeout=httpx.Timeout(get_timeout()),
        headers={
            "Authorization": f"Bearer {require_env('LLM_API_KEY')}",
            "Content-Type": "application/json",
        },
    )


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def dump_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def percentile(values: list[float], target: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    k = (len(ordered) - 1) * target / 100
    floor_idx = int(k)
    ceil_idx = min(floor_idx + 1, len(ordered) - 1)
    return ordered[floor_idx] + (k - floor_idx) * (ordered[ceil_idx] - ordered[floor_idx])


def cli_models(value: str | None) -> list[str]:
    if value:
        return [item.strip() for item in value.split(",") if item.strip()]
    return get_target_models()


def load_discovered_models() -> list[dict[str, Any]]:
    return load_json(RAW_DIR / "models_latest.json", default=[]) or []


def list_available_model_ids() -> list[str]:
    discovered = load_discovered_models()
    if discovered:
        return [item["id"] for item in discovered]
    with get_http_client() as client:
        response = client.get("/v1/models")
        response.raise_for_status()
        payload = response.json()
    data = payload.get("data", [])
    return [item["id"] for item in data]


def call_chat_completion(
    *,
    model: str,
    messages: list[dict[str, Any]],
    max_tokens: int = 512,
    temperature: float = 0.2,
    stream: bool = False,
) -> dict[str, Any]:
    client = get_openai_client()
    started_at = time.time()
    if not stream:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        latency_ms = (time.time() - started_at) * 1000
        choice = response.choices[0]
        message = choice.message
        usage = response.usage
        content = (
            message.content
            or getattr(message, "reasoning_content", None)
            or getattr(message, "reasoning", None)
            or ""
        )
        return {
            "success": True,
            "content": content,
            "latency_ms": round(latency_ms, 2),
            "ttft_ms": 0.0,
            "finish_reason": choice.finish_reason,
            "prompt_tokens": usage.prompt_tokens if usage else 0,
            "completion_tokens": usage.completion_tokens if usage else 0,
            "total_tokens": usage.total_tokens if usage else 0,
        }

    stream_response = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        stream=True,
    )
    chunks: list[str] = []
    first_token_at = None
    for chunk in stream_response:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        piece = (
            delta.content
            or getattr(delta, "reasoning_content", None)
            or getattr(delta, "reasoning", None)
            or ""
        )
        if piece and first_token_at is None:
            first_token_at = time.time()
        if piece:
            chunks.append(piece)
    ended_at = time.time()
    ttft_ms = ((first_token_at - started_at) * 1000) if first_token_at else 0.0
    return {
        "success": True,
        "content": "".join(chunks),
        "latency_ms": round((ended_at - started_at) * 1000, 2),
        "ttft_ms": round(ttft_ms, 2),
        "finish_reason": "stream_completed",
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }


@dataclass
class ReportArtifact:
    name: str
    json_path: str
    markdown_path: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
