from __future__ import annotations

import argparse
from datetime import datetime

from common import (
    RAW_DIR,
    REPORTS_DIR,
    ReportArtifact,
    dump_json,
    dump_text,
    ensure_project_dirs,
    get_base_host,
    get_http_client,
    now_ts,
)


def build_markdown(models: list[dict], elapsed_ms: float) -> str:
    lines = [
        "# 模型发现报告",
        "",
        "| 项目 | 值 |",
        "|------|----|",
        f"| 生成时间 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |",
        f"| API Host | `{get_base_host()}` |",
        f"| 模型数 | {len(models)} |",
        f"| 耗时 | {elapsed_ms:.0f} ms |",
        "",
        "## 模型列表",
        "",
        "| 模型ID | owned_by | 支持端点 |",
        "|--------|----------|----------|",
    ]
    for model in models:
        endpoints = ", ".join(model.get("supported_endpoint_types", [])) or "-"
        lines.append(f"| `{model.get('id', '-')}` | {model.get('owned_by', '-')} | {endpoints} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover models exposed by the target API via /v1/models.")
    parser.parse_args()

    ensure_project_dirs()
    started = datetime.now()
    with get_http_client() as client:
        response = client.get("/v1/models")
        response.raise_for_status()
        payload = response.json()
    ended = datetime.now()
    elapsed_ms = (ended - started).total_seconds() * 1000

    models = payload.get("data", [])
    timestamp = now_ts()
    json_path = RAW_DIR / f"models_{timestamp}.json"
    latest_path = RAW_DIR / "models_latest.json"
    markdown_path = REPORTS_DIR / "summary" / f"models_report_{timestamp}.md"

    dump_json(json_path, payload)
    dump_json(latest_path, models)
    dump_text(markdown_path, build_markdown(models, elapsed_ms))

    artifact = ReportArtifact(
        name="discover_models",
        json_path=str(json_path),
        markdown_path=str(markdown_path),
    )
    print(f"模型发现完成: {artifact.as_dict()}")


if __name__ == "__main__":
    main()
