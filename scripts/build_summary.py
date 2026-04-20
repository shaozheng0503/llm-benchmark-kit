from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from common import REPORTS_DIR, dump_json, dump_text, ensure_project_dirs, get_base_host, now_ts


def latest_json_files() -> dict[str, Path | None]:
    sections = ["cases", "stress", "authenticity"]
    result: dict[str, Path | None] = {}
    for section in sections:
        candidates = sorted((REPORTS_DIR / section).glob("*.json"))
        result[section] = candidates[-1] if candidates else None
    return result


def load_payload(path: Path | None) -> dict:
    if path is None:
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def collect_latest_case_results() -> dict[str, list[dict]]:
    model_map: dict[str, list[dict]] = {}
    for path in sorted((REPORTS_DIR / "cases").glob("*.json"), reverse=True):
        payload = load_payload(path)
        grouped: dict[str, list[dict]] = {}
        for item in payload.get("results", []):
            grouped.setdefault(item["model"], []).append(item)
        for model, rows in grouped.items():
            if model not in model_map:
                model_map[model] = rows
    return model_map


def collect_latest_auth_results() -> dict[str, dict]:
    model_map: dict[str, dict] = {}
    for path in sorted((REPORTS_DIR / "authenticity").glob("*.json"), reverse=True):
        payload = load_payload(path)
        for item in payload.get("summary", []):
            if item["model"] not in model_map:
                model_map[item["model"]] = item
    return model_map


def collect_latest_stress_results() -> dict[str, list[dict]]:
    model_map: dict[str, list[dict]] = {}
    for path in sorted((REPORTS_DIR / "stress").glob("*.json"), reverse=True):
        payload = load_payload(path)
        grouped: dict[str, list[dict]] = {}
        for item in payload.get("records", []):
            grouped.setdefault(item["model"], []).append(item)
        for model, rows in grouped.items():
            if model not in model_map:
                model_map[model] = rows
    return model_map


def build_markdown(summary: dict) -> str:
    case_results = [item for rows in summary["aggregated"]["cases"].values() for item in rows]
    stress_records = [item for rows in summary["aggregated"]["stress"].values() for item in rows]
    auth_summary = list(summary["aggregated"]["authenticity"].values())

    lines = [
        "# 综合测试总结报告",
        "",
        "| 项目 | 值 |",
        "|------|----|",
        f"| 生成时间 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |",
        f"| API Host | `{get_base_host()}` |",
        "",
        "## 结论摘要",
        "",
    ]

    if case_results:
        passed = sum(1 for item in case_results if item.get("passed"))
        lines.append(
            f"- 能力测试共 `{len(case_results)}` 项，整体通过 `{passed}` 项，失败 `{len(case_results) - passed}` 项。"
        )
        for model, rows in sorted(summary["aggregated"]["cases"].items()):
            model_passed = sum(1 for item in rows if item.get("passed"))
            notes = [item["case_name"] for item in rows if not item.get("passed")]
            note_text = "，主要失分：" + "、".join(notes) if notes else "，全部通过"
            lines.append(f"- `{model}`：`{model_passed}/{len(rows)}`{note_text}。")

    if stress_records:
        best = max(stress_records, key=lambda item: item.get("rps", 0))
        lines.append(
            f"- 压测当前共有 `{len(stress_records)}` 条记录，最高吞吐为 `{best.get('model')} / {best.get('tier')} / {best.get('rps')} RPS`。"
        )

    if auth_summary:
        for item in sorted(auth_summary, key=lambda entry: entry.get("model", "")):
            lines.append(
                f"- 真伪判定 `{item.get('model')}`：`{item.get('verdict')}`，可疑点 `{len(item.get('flags', []))}` 个。"
            )

    lines.extend(
        [
            "",
            "## 详细结果",
            "",
            "### 产物索引",
            "",
            "| 模块 | 最新 JSON |",
            "|------|-----------|",
        ]
    )
    for section, info in summary["artifacts"].items():
        lines.append(f"| {section} | `{info or '-'}` |")

    if case_results:
        passed = sum(1 for item in case_results if item.get("passed"))
        lines.extend(
            [
                "",
                "### 能力测试细节",
                "",
                f"- 总数: `{len(case_results)}`",
                f"- 通过: `{passed}`",
                f"- 失败: `{len(case_results) - passed}`",
                "",
                "| 模型 | 通过/总数 | 备注 |",
                "|------|-----------|------|",
            ]
        )
        for model, rows in sorted(summary["aggregated"]["cases"].items()):
            model_passed = sum(1 for item in rows if item.get("passed"))
            notes = [item["case_name"] for item in rows if not item.get("passed")]
            lines.append(f"| {model} | {model_passed}/{len(rows)} | {', '.join(notes) if notes else '全部通过'} |")

    if stress_records:
        best = max(stress_records, key=lambda item: item.get("rps", 0))
        lines.extend(
            [
                "",
                "### 压测细节",
                "",
                f"- 记录数: `{len(stress_records)}`",
                f"- 最高吞吐: `{best.get('model')} / {best.get('tier')} / {best.get('rps')} RPS`",
                "",
                "| 模型 | 档位 | 成功率 | RPS | P95(ms) |",
                "|------|------|--------|-----|---------|",
            ]
        )
        for model, rows in sorted(summary["aggregated"]["stress"].items()):
            for row in rows:
                lines.append(
                    f"| {model} | {row.get('tier')} | {row.get('success')}/{row.get('requests')} | "
                    f"{row.get('rps')} | {row.get('p95_latency_ms')} |"
                )

    if auth_summary:
        lines.extend(
            [
                "",
                "### 真伪测试细节",
                "",
                "| 模型 | 通过/总数 | 判定 | 可疑点 |",
                "|------|-----------|------|--------|",
            ]
        )
        for item in sorted(auth_summary, key=lambda entry: entry.get("model", "")):
            lines.append(
                f"| {item.get('model')} | {item.get('passed')}/{item.get('total')} | "
                f"{item.get('verdict')} | {len(item.get('flags', []))} |"
            )

    return "\n".join(lines) + "\n"


def main() -> None:
    ensure_project_dirs()
    artifacts = latest_json_files()
    payloads = {section: load_payload(path) for section, path in artifacts.items()}
    summary = {
        "generated_at": datetime.now().isoformat(),
        "artifacts": {section: (str(path) if path else "") for section, path in artifacts.items()},
        "payloads": payloads,
        "aggregated": {
            "cases": collect_latest_case_results(),
            "stress": collect_latest_stress_results(),
            "authenticity": collect_latest_auth_results(),
        },
    }

    timestamp = now_ts()
    json_path = REPORTS_DIR / "summary" / f"summary_{timestamp}.json"
    markdown_path = REPORTS_DIR / "summary" / f"summary_{timestamp}.md"
    dump_json(json_path, summary)
    dump_text(markdown_path, build_markdown(summary))
    print({"json": str(json_path), "markdown": str(markdown_path)})


if __name__ == "__main__":
    main()
