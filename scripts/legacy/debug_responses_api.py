#!/usr/bin/env python3
"""
Responses API 调试脚本 (legacy)
=================================
当某个模型在 /v1/responses 上返回非预期错误（如 400 / 404 / 参数不兼容）时，
依次尝试多种调用策略并打印完整响应细节，帮助定位兼容性问题。

使用方法:
  export LLM_API_BASE="https://api.example.com"
  export LLM_API_KEY="sk-xxxx"
  export DEBUG_MODEL="gpt-4o"   # 可选，默认 gpt-4o
  python scripts/legacy/debug_responses_api.py
"""

import json
import os
import traceback

import httpx
from openai import OpenAI

BASE_URL = os.getenv("LLM_API_BASE", "").rstrip("/")
API_KEY = os.getenv("LLM_API_KEY", "")
MODEL = os.getenv("DEBUG_MODEL", "gpt-4o")
if not BASE_URL or not API_KEY:
    raise SystemExit("请先设置 LLM_API_BASE 与 LLM_API_KEY 环境变量")

OPENAI_BASE_URL = f"{BASE_URL}/v1" if not BASE_URL.endswith("/v1") else BASE_URL

client = OpenAI(api_key=API_KEY, base_url=OPENAI_BASE_URL)

DIVIDER = "=" * 72


def attempt(label: str, fn):
    """Run fn(), print success or full error details."""
    print(f"\n{DIVIDER}")
    print(f"  TEST: {label}")
    print(DIVIDER)
    try:
        result = fn()
        print("[SUCCESS]")
        # Handle different result types
        if hasattr(result, "model_dump"):
            print(json.dumps(result.model_dump(), indent=2, default=str))
        elif hasattr(result, "__iter__") and not isinstance(result, (str, dict)):
            # Streaming response
            full = ""
            for chunk in result:
                if hasattr(chunk, "model_dump"):
                    data = chunk.model_dump()
                    delta = (data.get("choices") or [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        full += content
                        print(content, end="", flush=True)
            print()  # newline after stream
            print(f"\n[STREAM COMPLETE] Total length: {len(full)}")
        else:
            print(result)
    except Exception as exc:
        print(f"[FAILED] {type(exc).__name__}: {exc}")
        # If it's an openai APIError, dig into the response
        if hasattr(exc, "response"):
            resp = exc.response
            print(f"  HTTP status : {resp.status_code}")
            print(f"  Headers     : {dict(resp.headers)}")
            try:
                print(f"  Body        : {resp.text}")
            except Exception:
                pass
        if hasattr(exc, "body"):
            print(f"  Error body  : {exc.body}")
        if hasattr(exc, "code"):
            print(f"  Error code  : {exc.code}")
        traceback.print_exc()


# ------------------------------------------------------------------ #
# 1. Standard chat completions (minimal params)
# ------------------------------------------------------------------ #
def test_1():
    return client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": "Say hello."}],
    )


attempt("1 - Standard chat completions (minimal params)", test_1)


# ------------------------------------------------------------------ #
# 2. Chat completions with stream=True
# ------------------------------------------------------------------ #
def test_2():
    return client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": "Say hello."}],
        stream=True,
    )


attempt("2 - Chat completions with stream=True", test_2)


# ------------------------------------------------------------------ #
# 3. Chat completions WITHOUT temperature
# ------------------------------------------------------------------ #
def test_3():
    return client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": "Say hello."}],
        # explicitly no temperature, no top_p, no anything extra
    )


attempt("3 - Chat completions without temperature (same as #1, confirming)", test_3)


# ------------------------------------------------------------------ #
# 4. Chat completions with response_format=text
# ------------------------------------------------------------------ #
def test_4():
    return client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": "Say hello."}],
        response_format={"type": "text"},
    )


attempt("4 - Chat completions with response_format={'type':'text'}", test_4)


# ------------------------------------------------------------------ #
# 5. Try the OpenAI Responses API (/v1/responses) via raw HTTP
# ------------------------------------------------------------------ #
def test_5():
    http = httpx.Client(timeout=60)
    resp = http.post(
        f"{OPENAI_BASE_URL}/responses",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "input": "Say hello.",
        },
    )
    print(f"  HTTP {resp.status_code}")
    print(f"  Body: {resp.text}")
    resp.raise_for_status()
    return resp.json()


attempt("5 - Responses API (/v1/responses) via raw HTTP", test_5)


# ------------------------------------------------------------------ #
# 6a. reasoning_effort = low
# ------------------------------------------------------------------ #
def test_6a():
    http = httpx.Client(timeout=120)
    resp = http.post(
        f"{OPENAI_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": "Say hello."}],
            "reasoning_effort": "low",
        },
    )
    print(f"  HTTP {resp.status_code}")
    print(f"  Body: {resp.text}")
    resp.raise_for_status()
    return resp.json()


attempt("6a - reasoning_effort=low (raw HTTP)", test_6a)


# ------------------------------------------------------------------ #
# 6b. reasoning_effort = medium
# ------------------------------------------------------------------ #
def test_6b():
    http = httpx.Client(timeout=120)
    resp = http.post(
        f"{OPENAI_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": "Say hello."}],
            "reasoning_effort": "medium",
        },
    )
    print(f"  HTTP {resp.status_code}")
    print(f"  Body: {resp.text}")
    resp.raise_for_status()
    return resp.json()


attempt("6b - reasoning_effort=medium (raw HTTP)", test_6b)


# ------------------------------------------------------------------ #
# 6c. reasoning_effort = high
# ------------------------------------------------------------------ #
def test_6c():
    http = httpx.Client(timeout=120)
    resp = http.post(
        f"{OPENAI_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": "Say hello."}],
            "reasoning_effort": "high",
        },
    )
    print(f"  HTTP {resp.status_code}")
    print(f"  Body: {resp.text}")
    resp.raise_for_status()
    return resp.json()


attempt("6c - reasoning_effort=high (raw HTTP)", test_6c)


# ------------------------------------------------------------------ #
# 7. System message only (no user message)
# ------------------------------------------------------------------ #
def test_7():
    return client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": "You are a helpful assistant. Say hello."}],
    )


attempt("7 - System message only, no user message", test_7)


# ------------------------------------------------------------------ #
# 8a. max_tokens=50 (very small)
# ------------------------------------------------------------------ #
def test_8a():
    return client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": "Say hello."}],
        max_tokens=50,
    )


attempt("8a - max_tokens=50", test_8a)


# ------------------------------------------------------------------ #
# 8b. max_completion_tokens=50 (newer param name for reasoning models)
# ------------------------------------------------------------------ #
def test_8b():
    http = httpx.Client(timeout=60)
    resp = http.post(
        f"{OPENAI_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": "Say hello."}],
            "max_completion_tokens": 50,
        },
    )
    print(f"  HTTP {resp.status_code}")
    print(f"  Body: {resp.text}")
    resp.raise_for_status()
    return resp.json()


attempt("8b - max_completion_tokens=50 (raw HTTP)", test_8b)


# ------------------------------------------------------------------ #
# BONUS 9: List models to confirm gpt-5.4-pro exists
# ------------------------------------------------------------------ #
def test_9():
    http = httpx.Client(timeout=30)
    resp = http.get(
        f"{OPENAI_BASE_URL}/models",
        headers={"Authorization": f"Bearer {API_KEY}"},
    )
    print(f"  HTTP {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        models = data.get("data", [])
        # Show all models, highlight any with "5.4" in name
        matches = [m.get("id", "") for m in models if "5.4" in m.get("id", "")]
        print(f"  Total models: {len(models)}")
        print(f"  Models containing '5.4': {matches}")
        # Also show all models for reference
        all_ids = sorted(m.get("id", "") for m in models)
        print(f"  All model IDs ({len(all_ids)}):")
        for mid in all_ids:
            print(f"    - {mid}")
    else:
        print(f"  Body: {resp.text}")
    resp.raise_for_status()
    return "done"


attempt("BONUS 9 - List models (check gpt-5.4-pro exists)", test_9)


# ------------------------------------------------------------------ #
# BONUS 10: Try stream + reasoning_effort together
# ------------------------------------------------------------------ #
def test_10():
    http = httpx.Client(timeout=120)
    resp = http.post(
        f"{OPENAI_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": "Say hello."}],
            "stream": True,
            "reasoning_effort": "low",
            "max_completion_tokens": 200,
        },
    )
    print(f"  HTTP {resp.status_code}")
    if resp.status_code == 200:
        for line in resp.iter_lines():
            if line.strip():
                print(f"  >> {line}")
    else:
        print(f"  Body: {resp.text}")
    resp.raise_for_status()
    return "done"


attempt("BONUS 10 - stream + reasoning_effort=low + max_completion_tokens", test_10)


# ------------------------------------------------------------------ #
# BONUS 11: Try with developer role (new OpenAI role for o-series)
# ------------------------------------------------------------------ #
def test_11():
    http = httpx.Client(timeout=120)
    resp = http.post(
        f"{OPENAI_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "messages": [
                {"role": "developer", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say hello."},
            ],
            "max_completion_tokens": 200,
        },
    )
    print(f"  HTTP {resp.status_code}")
    print(f"  Body: {resp.text}")
    resp.raise_for_status()
    return resp.json()


attempt("BONUS 11 - developer role + max_completion_tokens (o-series style)", test_11)


print(f"\n{DIVIDER}")
print("  ALL TESTS COMPLETE")
print(DIVIDER)
