import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class Reporter:
    """Формирует и сохраняет отчёт по результатам проверки."""

    def generate(self, all_results: list[dict[str, Any]], config) -> dict[str, Any]:
        report = {
            "metadata": self._build_metadata(config),
            "summary": self._build_summary(all_results),
            "by_resource": self._group_by_resource(all_results),
            "all_checks": all_results,
        }

        self._save_json(report, config.output_path)
        return report

    def _build_metadata(self, config) -> dict[str, Any]:
        return {
            "version": "1.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "emulator_url": config.emulator_url,
            "spec_version": "Swordfish v1.2.9",
        }

    def _build_summary(self, all_results: list[dict[str, Any]]) -> dict[str, Any]:
        total = len(all_results)
        passed = sum(1 for r in all_results if r.get("status") == "PASS")
        failed = sum(1 for r in all_results if r.get("status") == "FAIL")
        not_supported = sum(
            1 for r in all_results if r.get("status") == "NOT_SUPPORTED"
        )

        return {
            "total": total,
            "pass": passed,
            "fail": failed,
            "not_supported": not_supported,
            "pass_rate": f"{round(passed / total * 100)}%" if total else "0%",
        }

    def _group_by_resource(
        self,
        all_results: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        by_resource = {}

        for result in all_results:
            resource = result.get("resource", "unknown")

            if resource not in by_resource:
                by_resource[resource] = {
                    "pass": 0,
                    "fail": 0,
                    "not_supported": 0,
                    "checks": [],
                }

            status = result.get("status")

            if status == "PASS":
                by_resource[resource]["pass"] += 1
            elif status == "FAIL":
                by_resource[resource]["fail"] += 1
            elif status == "NOT_SUPPORTED":
                by_resource[resource]["not_supported"] += 1

            by_resource[resource]["checks"].append(result)

        return by_resource

    def _save_json(
        self,
        report: dict[str, Any],
        output_path: str,
        filename: str = "report.json",
    ) -> Path:
        output_dir = Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)

        report_path = output_dir / filename

        with report_path.open("w", encoding="utf-8") as file:
            json.dump(report, file, indent=2, ensure_ascii=False)

        return report_path