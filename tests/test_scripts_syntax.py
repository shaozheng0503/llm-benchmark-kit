"""对所有 Python 脚本做 AST 解析，防止 PR 合入语法错误。

直接 import 会因为环境变量缺失而 SystemExit，所以用 ast.parse 做静态检查。
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIRS = [REPO_ROOT / "scripts", REPO_ROOT / "scripts" / "legacy", REPO_ROOT / "tests"]

ALL_PY = sorted({path for directory in SCRIPT_DIRS if directory.exists() for path in directory.glob("*.py")})


@pytest.mark.parametrize("path", ALL_PY, ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_parses(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    ast.parse(source, filename=str(path))


def test_common_surface_exports() -> None:
    """锁定 scripts/common.py 的公共 API，避免后续重构无意中破坏 legacy 外的调用方。"""
    source = (REPO_ROOT / "scripts" / "common.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {
        node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    } | {
        target.id
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    required = {
        "PROJECT_ROOT",
        "CONFIG_DIR",
        "RAW_DIR",
        "REPORTS_DIR",
        "now_ts",
        "require_env",
        "get_base_host",
        "get_openai_base_url",
        "get_timeout",
        "get_target_models",
        "ensure_project_dirs",
        "get_openai_client",
        "get_http_client",
        "load_json",
        "dump_json",
        "dump_text",
        "percentile",
        "cli_models",
        "load_discovered_models",
        "list_available_model_ids",
        "call_chat_completion",
        "ReportArtifact",
    }
    missing = required - names
    assert not missing, f"scripts/common.py 缺少公共导出: {missing}"
