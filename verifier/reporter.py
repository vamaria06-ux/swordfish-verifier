import json
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
