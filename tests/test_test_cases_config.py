"""校验 config/test_cases.json 的结构完整性。

CI 里即使没有真实 API Key 也能跑，用来防止 PR 误改用例破坏 run_cases.py 的假设。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "test_cases.json"
VALID_CATEGORIES = {"smoke", "core", "complex", "safety", "boundary"}
VALID_ROLES = {"system", "user", "assistant", "tool"}
VALID_CHECK_KEYS = {
    "min_length",
    "should_include_any",
    "should_include_all",
    "should_not_include_any",
    "json_required",
    "json_keys",
}


@pytest.fixture(scope="module")
def cases() -> list[dict]:
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    assert isinstance(data, list), "test_cases.json 顶层必须是数组"
    return data


def test_non_empty(cases: list[dict]) -> None:
    assert len(cases) > 0, "至少需要一个测试用例"


def test_ids_unique(cases: list[dict]) -> None:
    ids = [case["id"] for case in cases]
    assert len(ids) == len(set(ids)), f"用例 id 必须唯一，重复项: {[i for i in ids if ids.count(i) > 1]}"


@pytest.mark.parametrize("case", [pytest.param(c, id=c["id"]) for c in json.loads(CONFIG_PATH.read_text("utf-8"))])
def test_case_shape(case: dict) -> None:
    assert {"id", "category", "name", "messages"} <= case.keys(), f"用例 {case.get('id')} 缺字段"
    assert case["category"] in VALID_CATEGORIES, f"{case['id']}: 非法 category {case['category']}"
    assert isinstance(case["messages"], list) and case["messages"], f"{case['id']}: messages 不能为空"

    for msg in case["messages"]:
        assert {"role", "content"} <= msg.keys(), f"{case['id']}: message 缺字段"
        assert msg["role"] in VALID_ROLES, f"{case['id']}: 非法 role {msg['role']}"
        assert isinstance(msg["content"], str) and msg["content"].strip(), f"{case['id']}: content 不能为空"

    checks = case.get("checks", {})
    assert isinstance(checks, dict), f"{case['id']}: checks 必须是 dict"
    unknown = set(checks.keys()) - VALID_CHECK_KEYS
    assert not unknown, f"{case['id']}: 未知的 check key {unknown}"

    if "json_required" in checks:
        assert isinstance(checks["json_required"], bool)
        if checks["json_required"]:
            assert isinstance(checks.get("json_keys", []), list)

    max_tokens = case.get("max_tokens", 512)
    assert isinstance(max_tokens, int) and max_tokens > 0, f"{case['id']}: max_tokens 必须为正整数"
