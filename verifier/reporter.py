import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def count_statuses(checks: list[dict[str, Any]]) -> dict[str, int]:
    stats = {
        "total": len(checks),
        "PASS": 0,
        "FAIL": 0,
        "NOT_SUPPORTED": 0,
    }

    for check in checks:
        status = check.get("status")
        if status in stats:
            stats[status] += 1

    return stats

def build_report(
    checks: list[dict[str, Any]],
    emulator_url: str,
    specification_version: str = "unknown",
    resources_filter: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "emulator_url": emulator_url,
            "specification_version": specification_version,
            "resources_filter": resources_filter or [],
        },
        "summary": count_statuses(checks),
        "checks": checks,
    }

def save_report(
    report: dict[str, Any],
    output_path: str,
    filename: str = "report.json",
) -> Path:
    output_dir = Path(output_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    report_path = output_dir / filename

    with open(report_path, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=2, ensure_ascii=False)

    return report_path
